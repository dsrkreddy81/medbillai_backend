import uuid

from sqlalchemy import String, Text, Float, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ExtractedCode(Base):
    __tablename__ = "extracted_codes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    billing_note_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("billing_notes.id", ondelete="CASCADE"))
    cpt_code_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cpt_codes.id"), nullable=True)
    cpt_code_raw: Mapped[str] = mapped_column(String(10))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    supporting_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)

    billing_note: Mapped["BillingNote"] = relationship(back_populates="extracted_codes")
    cpt_code: Mapped["CPTCode | None"] = relationship(back_populates="extracted_codes")
