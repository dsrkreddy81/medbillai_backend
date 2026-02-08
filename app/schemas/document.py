from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: UUID
    filename: str
    page_count: int | None
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class DocumentDetailResponse(DocumentResponse):
    file_path: str
    extracted_text: str | None

    model_config = {"from_attributes": True}
