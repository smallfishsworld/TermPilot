from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from termpilot.clock import utcnow
from termpilot.db.base import Base, Timestamped


def new_id() -> str:
    return uuid4().hex


class Conversation(Timestamped, Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    auto_title: Mapped[bool] = mapped_column(default=True)

    turns: Mapped[list[Turn]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Turn.created_at",
        passive_deletes=True,
    )
    attachments: Mapped[list[Attachment]] = relationship(
        cascade="all, delete-orphan",
        order_by="Attachment.created_at",
        passive_deletes=True,
    )


class Turn(Base):
    """One question and the assistant's answer, with the evidence it used."""

    __tablename__ = "turns"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    mode: Mapped[str] = mapped_column(String(16))
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text, default="")
    reasoning: Mapped[str | None] = mapped_column(Text)
    sources: Mapped[list[dict[str, Any]]] = mapped_column(default=list)
    suggestions: Mapped[list[str]] = mapped_column(default=list)
    trace: Mapped[list[dict[str, Any]]] = mapped_column(default=list)
    failed: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    conversation: Mapped[Conversation] = relationship(back_populates="turns")


class Attachment(Base):
    """Text extracted from a file attached to one conversation."""

    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int]
    text: Mapped[str] = mapped_column(Text)
    truncated: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class PendingAction(Base):
    """A side effect proposed by the assistant that waits for the student's decision."""

    __tablename__ = "pending_actions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[str | None] = mapped_column(ForeignKey("conversations.id", ondelete="SET NULL"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text)
    preview: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(default=dict)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    outcome: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    expires_at: Mapped[datetime]
    decided_at: Mapped[datetime | None]
