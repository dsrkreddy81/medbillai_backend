import uuid
from datetime import date, datetime

from sqlalchemy import String, Text, Date, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class BillingNote(Base):
    __tablename__ = "billing_notes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    patient_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    date_of_service: Mapped[date | None] = mapped_column(Date, nullable=True)
    provider_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    clinical_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    billing_narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    document: Mapped["Document"] = relationship(back_populates="billing_notes")
    extracted_codes: Mapped[list["ExtractedCode"]] = relationship(
        back_populates="billing_note", cascade="all, delete-orphan"
    )
    extracted_diagnoses: Mapped[list["ExtractedDiagnosis"]] = relationship(
        back_populates="billing_note", cascade="all, delete-orphan"
    )
