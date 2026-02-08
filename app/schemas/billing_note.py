from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class ExtractedCodeResponse(BaseModel):
    id: UUID
    cpt_code_raw: str
    description: str | None
    supporting_text: str | None
    confidence: float | None
    confirmed: bool
    cpt_code_id: UUID | None

    model_config = {"from_attributes": True}


class ExtractedDiagnosisResponse(BaseModel):
    id: UUID
    icd10_code_raw: str
    description: str | None
    supporting_text: str | None
    confidence: float | None
    is_primary: bool
    icd10_code_id: UUID | None

    model_config = {"from_attributes": True}


class BillingNoteResponse(BaseModel):
    id: UUID
    document_id: UUID
    patient_name: str | None
    date_of_service: date | None
    provider_name: str | None
    clinical_summary: str | None
    billing_narrative: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BillingNoteDetailResponse(BillingNoteResponse):
    extracted_codes: list[ExtractedCodeResponse]
    extracted_diagnoses: list[ExtractedDiagnosisResponse] = []
    document_filename: str | None = None

    model_config = {"from_attributes": True}


class BillingNoteUpdateRequest(BaseModel):
    status: str | None = None
    patient_name: str | None = None
    date_of_service: date | None = None
    provider_name: str | None = None
    clinical_summary: str | None = None
    billing_narrative: str | None = None


class ConfirmCodeRequest(BaseModel):
    confirmed: bool


class UpdateCodeRequest(BaseModel):
    cpt_code_raw: str | None = None
    description: str | None = None
    supporting_text: str | None = None
    confidence: float | None = None


class AddCodeRequest(BaseModel):
    cpt_code_raw: str
    description: str | None = None
    supporting_text: str | None = None
    confidence: float | None = None


class UpdateDiagnosisRequest(BaseModel):
    icd10_code_raw: str | None = None
    description: str | None = None
    supporting_text: str | None = None
    confidence: float | None = None
    is_primary: bool | None = None


class AddDiagnosisRequest(BaseModel):
    icd10_code_raw: str
    description: str | None = None
    supporting_text: str | None = None
    confidence: float | None = None
    is_primary: bool = False
