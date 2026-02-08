"""Billing notes CRUD routes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.billing_note import BillingNote
from app.models.document import Document
from app.models.extracted_code import ExtractedCode
from app.models.extracted_diagnosis import ExtractedDiagnosis
from app.schemas.billing_note import (
    BillingNoteResponse,
    BillingNoteDetailResponse,
    BillingNoteUpdateRequest,
    ConfirmCodeRequest,
    UpdateCodeRequest,
    AddCodeRequest,
    ExtractedCodeResponse,
    UpdateDiagnosisRequest,
    AddDiagnosisRequest,
    ExtractedDiagnosisResponse,
)

router = APIRouter()


@router.get("", response_model=list[BillingNoteResponse])
async def list_billing_notes(
    skip: int = 0,
    limit: int = 50,
    status: str | None = Query(None, description="Filter by status: draft, reviewed, finalized"),
    search: str | None = Query(None, description="Search by patient name"),
    db: AsyncSession = Depends(get_db),
):
    """List billing notes with optional filters."""
    query = select(BillingNote).order_by(BillingNote.created_at.desc())

    if status:
        query = query.where(BillingNote.status == status)
    if search:
        query = query.where(BillingNote.patient_name.ilike(f"%{search}%"))

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/stats")
async def get_billing_stats(db: AsyncSession = Depends(get_db)):
    """Get dashboard statistics."""
    total = await db.execute(select(func.count(BillingNote.id)))
    draft = await db.execute(
        select(func.count(BillingNote.id)).where(BillingNote.status == "draft")
    )
    reviewed = await db.execute(
        select(func.count(BillingNote.id)).where(BillingNote.status == "reviewed")
    )
    finalized = await db.execute(
        select(func.count(BillingNote.id)).where(BillingNote.status == "finalized")
    )
    documents = await db.execute(select(func.count(Document.id)))

    return {
        "total_notes": total.scalar() or 0,
        "draft": draft.scalar() or 0,
        "reviewed": reviewed.scalar() or 0,
        "finalized": finalized.scalar() or 0,
        "total_documents": documents.scalar() or 0,
    }


@router.get("/{note_id}", response_model=BillingNoteDetailResponse)
async def get_billing_note(
    note_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a billing note with all extracted CPT codes."""
    result = await db.execute(
        select(BillingNote)
        .where(BillingNote.id == note_id)
        .options(
            selectinload(BillingNote.extracted_codes),
            selectinload(BillingNote.extracted_diagnoses),
        )
    )
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Billing note not found")

    # Get document filename
    doc_result = await db.execute(select(Document).where(Document.id == note.document_id))
    doc = doc_result.scalar_one_or_none()

    response = BillingNoteDetailResponse.model_validate(note)
    response.document_filename = doc.filename if doc else None
    return response


@router.patch("/{note_id}", response_model=BillingNoteResponse)
async def update_billing_note(
    note_id: uuid.UUID,
    update: BillingNoteUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update a billing note (status, patient info, etc.)."""
    result = await db.execute(select(BillingNote).where(BillingNote.id == note_id))
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Billing note not found")

    update_data = update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(note, key, value)

    await db.commit()
    await db.refresh(note)
    return note


@router.delete("/{note_id}")
async def delete_billing_note(
    note_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a billing note and its extracted codes."""
    result = await db.execute(select(BillingNote).where(BillingNote.id == note_id))
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Billing note not found")

    await db.delete(note)
    await db.commit()
    return {"detail": "Billing note deleted"}


@router.patch("/{note_id}/codes/{code_id}/confirm")
async def confirm_extracted_code(
    note_id: uuid.UUID,
    code_id: uuid.UUID,
    body: ConfirmCodeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Confirm or unconfirm an extracted CPT code."""
    result = await db.execute(
        select(ExtractedCode).where(
            ExtractedCode.id == code_id,
            ExtractedCode.billing_note_id == note_id,
        )
    )
    code = result.scalar_one_or_none()
    if not code:
        raise HTTPException(status_code=404, detail="Extracted code not found")

    code.confirmed = body.confirmed
    await db.commit()
    return {"detail": "Code updated", "confirmed": code.confirmed}


# ── CPT Code CRUD ──────────────────────────────────────────────


@router.put("/{note_id}/codes/{code_id}", response_model=ExtractedCodeResponse)
async def update_extracted_code(
    note_id: uuid.UUID,
    code_id: uuid.UUID,
    body: UpdateCodeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Edit an extracted CPT code."""
    result = await db.execute(
        select(ExtractedCode).where(
            ExtractedCode.id == code_id,
            ExtractedCode.billing_note_id == note_id,
        )
    )
    code = result.scalar_one_or_none()
    if not code:
        raise HTTPException(status_code=404, detail="Extracted code not found")

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(code, key, value)

    await db.commit()
    await db.refresh(code)
    return code


@router.delete("/{note_id}/codes/{code_id}")
async def delete_extracted_code(
    note_id: uuid.UUID,
    code_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete an extracted CPT code."""
    result = await db.execute(
        select(ExtractedCode).where(
            ExtractedCode.id == code_id,
            ExtractedCode.billing_note_id == note_id,
        )
    )
    code = result.scalar_one_or_none()
    if not code:
        raise HTTPException(status_code=404, detail="Extracted code not found")

    await db.delete(code)
    await db.commit()
    return {"detail": "Code deleted"}


@router.post("/{note_id}/codes", response_model=ExtractedCodeResponse)
async def add_extracted_code(
    note_id: uuid.UUID,
    body: AddCodeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Manually add a CPT code to a billing note."""
    # Verify billing note exists
    result = await db.execute(select(BillingNote).where(BillingNote.id == note_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Billing note not found")

    code = ExtractedCode(
        id=uuid.uuid4(),
        billing_note_id=note_id,
        cpt_code_id=None,
        cpt_code_raw=body.cpt_code_raw,
        description=body.description,
        supporting_text=body.supporting_text,
        confidence=body.confidence,
        confirmed=False,
    )
    db.add(code)
    await db.commit()
    await db.refresh(code)
    return code


# ── ICD-10 Diagnosis CRUD ──────────────────────────────────────


@router.put("/{note_id}/diagnoses/{diag_id}", response_model=ExtractedDiagnosisResponse)
async def update_extracted_diagnosis(
    note_id: uuid.UUID,
    diag_id: uuid.UUID,
    body: UpdateDiagnosisRequest,
    db: AsyncSession = Depends(get_db),
):
    """Edit an extracted ICD-10 diagnosis."""
    result = await db.execute(
        select(ExtractedDiagnosis).where(
            ExtractedDiagnosis.id == diag_id,
            ExtractedDiagnosis.billing_note_id == note_id,
        )
    )
    diag = result.scalar_one_or_none()
    if not diag:
        raise HTTPException(status_code=404, detail="Extracted diagnosis not found")

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(diag, key, value)

    await db.commit()
    await db.refresh(diag)
    return diag


@router.delete("/{note_id}/diagnoses/{diag_id}")
async def delete_extracted_diagnosis(
    note_id: uuid.UUID,
    diag_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete an extracted ICD-10 diagnosis."""
    result = await db.execute(
        select(ExtractedDiagnosis).where(
            ExtractedDiagnosis.id == diag_id,
            ExtractedDiagnosis.billing_note_id == note_id,
        )
    )
    diag = result.scalar_one_or_none()
    if not diag:
        raise HTTPException(status_code=404, detail="Extracted diagnosis not found")

    await db.delete(diag)
    await db.commit()
    return {"detail": "Diagnosis deleted"}


@router.post("/{note_id}/diagnoses", response_model=ExtractedDiagnosisResponse)
async def add_extracted_diagnosis(
    note_id: uuid.UUID,
    body: AddDiagnosisRequest,
    db: AsyncSession = Depends(get_db),
):
    """Manually add an ICD-10 diagnosis to a billing note."""
    result = await db.execute(select(BillingNote).where(BillingNote.id == note_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Billing note not found")

    diag = ExtractedDiagnosis(
        id=uuid.uuid4(),
        billing_note_id=note_id,
        icd10_code_id=None,
        icd10_code_raw=body.icd10_code_raw,
        description=body.description,
        supporting_text=body.supporting_text,
        confidence=body.confidence,
        is_primary=body.is_primary,
    )
    db.add(diag)
    await db.commit()
    await db.refresh(diag)
    return diag
