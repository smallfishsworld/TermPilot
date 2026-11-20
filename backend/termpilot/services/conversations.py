"""Conversations with the assistant and the files attached to them."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from termpilot.db.models import Attachment, Conversation, Student, Turn
from termpilot.errors import InvalidInput, NotFound
from termpilot.knowledge.extract import extract_text
from termpilot.settings import Settings

DEFAULT_TITLE = "New conversation"
MAX_ATTACHMENTS = 5


def list_conversations(
    db: Session, student: Student, query: str | None = None, limit: int = 100
) -> list[tuple[Conversation, int]]:
    turn_count = select(func.count(Turn.id)).where(Turn.conversation_id == Conversation.id).scalar_subquery()
    statement = select(Conversation, turn_count).where(Conversation.student_id == student.id)
    if query and query.strip():
        statement = statement.where(Conversation.title.ilike(f"%{query.strip()}%"))
    rows = db.execute(statement.order_by(Conversation.updated_at.desc()).limit(limit)).all()
    return [(conversation, int(count or 0)) for conversation, count in rows]


def create(db: Session, student: Student, title: str | None = None) -> Conversation:
    conversation = Conversation(
        student_id=student.id,
        title=(title or "").strip()[:200] or DEFAULT_TITLE,
        auto_title=not (title or "").strip(),
    )
    db.add(conversation)
    db.commit()
    return conversation


def get(db: Session, student: Student, conversation_id: str) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None or conversation.student_id != student.id:
        raise NotFound("That conversation does not exist.")
    return conversation


def rename(db: Session, student: Student, conversation_id: str, title: str) -> Conversation:
    title = title.strip()
    if not title:
        raise InvalidInput("The title cannot be empty.")
    conversation = get(db, student, conversation_id)
    conversation.title = title[:200]
    conversation.auto_title = False
    db.commit()
    return conversation


def delete(db: Session, student: Student, conversation_id: str) -> None:
    db.delete(get(db, student, conversation_id))
    db.commit()


def recent_turns(db: Session, conversation_id: str, limit: int) -> list[Turn]:
    rows = db.scalars(
        select(Turn)
        .where(Turn.conversation_id == conversation_id, Turn.failed.is_(False))
        .order_by(Turn.created_at.desc())
        .limit(limit)
    )
    return list(reversed(list(rows)))


def attach(
    db: Session, settings: Settings, student: Student, conversation_id: str, filename: str, data: bytes
) -> Attachment:
    conversation = get(db, student, conversation_id)
    if len(conversation.attachments) >= MAX_ATTACHMENTS:
        raise InvalidInput(f"A conversation can hold at most {MAX_ATTACHMENTS} attachments.")
    if len(data) > settings.upload_max_mb * 1024 * 1024:
        raise InvalidInput(f"Files are limited to {settings.upload_max_mb} MB.")
    text, truncated = extract_text(filename, data, settings.attachment_max_chars)
    attachment = Attachment(
        conversation_id=conversation.id,
        filename=filename[:255],
        media_type=filename.rsplit(".", 1)[-1].lower() if "." in filename else "text",
        size_bytes=len(data),
        text=text,
        truncated=truncated,
    )
    db.add(attachment)
    db.commit()
    return attachment


def detach(db: Session, student: Student, conversation_id: str, attachment_id: int) -> None:
    conversation = get(db, student, conversation_id)
    attachment = db.get(Attachment, attachment_id)
    if attachment is None or attachment.conversation_id != conversation.id:
        raise NotFound("That attachment does not exist.")
    db.delete(attachment)
    db.commit()
