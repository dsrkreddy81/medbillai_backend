from pydantic import BaseModel


class ExtractedCPTCode(BaseModel):
    cpt_code: str
    description: str
    supporting_text: str
    confidence: float


class ExtractedICD10Code(BaseModel):
    icd10_code: str
    description: str
    supporting_text: str
    confidence: float
    is_primary: bool = False


class ExtractionResult(BaseModel):
    patient_name: str | None = None
    date_of_service: str | None = None
    provider_name: str | None = None
    clinical_summary: str
    procedures: list[ExtractedCPTCode]
    diagnoses: list[ExtractedICD10Code] = []
    billing_narrative: str
