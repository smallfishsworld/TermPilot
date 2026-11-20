from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from termpilot.db.base import Base


class MailLink(Base):
    """A connected mailbox. The authorization code is encrypted at rest."""

    __tablename__ = "mail_links"

    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), primary_key=True)
    provider: Mapped[str] = mapped_column(String(20))
    address: Mapped[str] = mapped_column(String(255))
    sealed_secret: Mapped[str] = mapped_column(Text)
    linked_at: Mapped[datetime]
    last_synced_at: Mapped[datetime | None]


class MailItem(Base):
    """A message copied from the mailbox during synchronisation."""

    __tablename__ = "mail_items"
    __table_args__ = (UniqueConstraint("student_id", "address", "folder", "uid"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    address: Mapped[str] = mapped_column(String(255))
    folder: Mapped[str] = mapped_column(String(120), default="INBOX")
    uid: Mapped[str] = mapped_column(String(64))
    message_id: Mapped[str | None] = mapped_column(String(300))
    subject: Mapped[str | None] = mapped_column(String(500))
    sender: Mapped[str | None] = mapped_column(String(500))
    recipients: Mapped[str | None] = mapped_column(Text)
    cc: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime | None]
    preview: Mapped[str | None] = mapped_column(Text)
    body_text: Mapped[str | None] = mapped_column(Text)
    body_html: Mapped[str | None] = mapped_column(Text)
    seen: Mapped[bool] = mapped_column(default=False)
    has_attachments: Mapped[bool] = mapped_column(default=False)
    synced_at: Mapped[datetime]
