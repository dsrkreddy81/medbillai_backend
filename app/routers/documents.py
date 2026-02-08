"""Document upload and management routes."""

import hashlib
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from supabase import create_client

from app.config import settings
from app.database import get_db
from app.models.document import Document
from app.schemas.document import DocumentResponse, DocumentDetailResponse
from app.services.billing_service import process_document

router = APIRouter()


def _get_supabase():
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)


def _get_public_url(storage_path: str) -> str:
    """Build the public URL for a file in Supabase Storage."""
    return f"{settings.SUPABASE_URL}/storage/v1/object/public/{settings.SUPABASE_STORAGE_BUCKET}/{storage_path}"


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a PDF and trigger CPT code extraction."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    content = await file.read()

    # Check for duplicate by file hash
    file_hash = hashlib.sha256(content).hexdigest()
    existing = await db.execute(
        select(Document).where(Document.file_hash == file_hash)
    )
    existing_doc = existing.scalar_one_or_none()
    if existing_doc:
        return existing_doc

    file_id = uuid.uuid4()
    safe_filename = f"{file_id}_{file.filename}"
    storage_path = f"pdfs/{safe_filename}"

    # Upload to Supabase Storage
    supabase = _get_supabase()
    supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET).upload(
        path=storage_path,
        file=content,
        file_options={"content-type": "application/pdf"},
    )

    # Save locally as temp file for pdfplumber text extraction
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    local_path = os.path.join(settings.UPLOAD_DIR, safe_filename)
    with open(local_path, "wb") as f:
        f.write(content)

    # Create document record — file_path stores local path during processing
    document = Document(
        id=file_id,
        filename=file.filename,
        file_path=local_path,
        file_hash=file_hash,
    )
    db.add(document)
    await db.commit()

    # Process document (extract text + CPT codes)
    try:
        await process_document(document.id, db)
    except Exception as e:
        print(f"Processing error (document saved): {e}")

    # After extraction, update file_path to Supabase storage path and clean up local
    document.file_path = storage_path
    await db.commit()

    try:
        os.remove(local_path)
    except OSError:
        pass

    await db.refresh(document)
    return document


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List all uploaded documents."""
    result = await db.execute(
        select(Document).order_by(Document.uploaded_at.desc()).offset(skip).limit(limit)
    )
    return result.scalars().all()


@router.get("/{document_id}", response_model=DocumentDetailResponse)
async def get_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a single document with extracted text."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.post("/{document_id}/reprocess")
async def reprocess_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Re-run CPT/ICD-10 extraction on an existing document. Creates a new billing note."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        billing_note = await process_document(document.id, db)
        return {"detail": "Document reprocessed", "billing_note_id": str(billing_note.id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reprocessing failed: {e}")


@router.get("/{document_id}/download")
async def download_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Serve the PDF inline — from Supabase Storage (new) or local disk (old)."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # New uploads: file_path starts with "pdfs/" (Supabase storage path)
    if document.file_path.startswith("pdfs/"):
        supabase = _get_supabase()
        file_bytes = supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET).download(
            document.file_path
        )
        return Response(
            content=file_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{document.filename}"'},
        )

    # Old uploads: file_path is a local disk path
    if os.path.exists(document.file_path):
        return FileResponse(
            path=document.file_path,
            media_type="application/pdf",
            filename=document.filename,
            content_disposition_type="inline",
        )

    raise HTTPException(status_code=404, detail="PDF file not found")
