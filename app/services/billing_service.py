"""Billing orchestration service: PDF -> Claude -> Database."""

import uuid
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.document import Document
from app.models.billing_note import BillingNote
from app.models.cpt_code import CPTCode
from app.models.icd10_code import ICD10Code
from app.models.extracted_code import ExtractedCode
from app.models.extracted_diagnosis import ExtractedDiagnosis
from app.schemas.extraction import ExtractionResult
from app.services.pdf_service import extract_text_from_pdf
from app.services.claude_service import extract_cpt_codes


async def process_document(document_id: uuid.UUID, db: AsyncSession) -> BillingNote:
    """Full pipeline: take an uploaded document, extract CPT + ICD-10 codes, create billing note."""
    # 1. Get the document
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if not document:
        raise ValueError(f"Document {document_id} not found")

    # 2. Extract text from PDF if not already done
    if not document.extracted_text:
        text, page_count = extract_text_from_pdf(document.file_path)
        document.extracted_text = text
        document.page_count = page_count
        await db.flush()

    # 3. Send to Claude for CPT + ICD-10 extraction
    extraction = await extract_cpt_codes(document.extracted_text)

    # 4. Create billing note
    billing_note = BillingNote(
        id=uuid.uuid4(),
        document_id=document.id,
        patient_name=extraction.patient_name,
        date_of_service=_parse_date(extraction.date_of_service),
        provider_name=extraction.provider_name,
        clinical_summary=extraction.clinical_summary,
        billing_narrative=extraction.billing_narrative,
        status="draft",
    )
    db.add(billing_note)
    await db.flush()

    # 5. Create extracted CPT codes
    print(f"[DEBUG] CPT procedures count: {len(extraction.procedures)}")
    await _create_extracted_codes(db, billing_note.id, extraction)

    # 6. Create extracted ICD-10 diagnoses
    print(f"[DEBUG] ICD-10 diagnoses count: {len(extraction.diagnoses)}")
    for d in extraction.diagnoses:
        print(f"[DEBUG]   - {d.icd10_code}: {d.description}")
    await _create_extracted_diagnoses(db, billing_note.id, extraction)

    await db.commit()

    # 7. Reload with relationships
    result = await db.execute(
        select(BillingNote)
        .where(BillingNote.id == billing_note.id)
        .options(
            selectinload(BillingNote.extracted_codes),
            selectinload(BillingNote.extracted_diagnoses),
        )
    )
    return result.scalar_one()


async def _create_extracted_codes(
    db: AsyncSession,
    billing_note_id: uuid.UUID,
    extraction: ExtractionResult,
) -> None:
    """Create ExtractedCode records, cross-referencing with CPT code table."""
    result = await db.execute(select(CPTCode))
    cpt_lookup = {code.code: code for code in result.scalars().all()}

    for proc in extraction.procedures:
        cpt_ref = cpt_lookup.get(proc.cpt_code)
        extracted = ExtractedCode(
            id=uuid.uuid4(),
            billing_note_id=billing_note_id,
            cpt_code_id=cpt_ref.id if cpt_ref else None,
            cpt_code_raw=proc.cpt_code,
            description=proc.description,
            supporting_text=proc.supporting_text,
            confidence=proc.confidence,
            confirmed=False,
        )
        db.add(extracted)


async def _create_extracted_diagnoses(
    db: AsyncSession,
    billing_note_id: uuid.UUID,
    extraction: ExtractionResult,
) -> None:
    """Create ExtractedDiagnosis records, cross-referencing with ICD-10 code table."""
    result = await db.execute(select(ICD10Code))
    icd_lookup = {code.code: code for code in result.scalars().all()}

    for diag in extraction.diagnoses:
        icd_ref = icd_lookup.get(diag.icd10_code)
        extracted = ExtractedDiagnosis(
            id=uuid.uuid4(),
            billing_note_id=billing_note_id,
            icd10_code_id=icd_ref.id if icd_ref else None,
            icd10_code_raw=diag.icd10_code,
            description=diag.description,
            supporting_text=diag.supporting_text,
            confidence=diag.confidence,
            is_primary=diag.is_primary,
        )
        db.add(extracted)


def _parse_date(date_str: str | None) -> date | None:
    """Parse a date string in YYYY-MM-DD format."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None
