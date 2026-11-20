from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from termpilot.clock import utcnow
from termpilot.db.base import Base


class LibraryDocument(Base):
    """A file in the student's searchable library."""

    __tablename__ = "library_documents"
    __table_args__ = (UniqueConstraint("student_id", "filename"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int]
    doc_key: Mapped[str] = mapped_column(String(32))
    chunks: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(16), default="processing")
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
