"""Connecting a mailbox, synchronising messages and sending mail."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from termpilot.clock import utcnow
from termpilot.db.models import MailItem, MailLink, Student
from termpilot.errors import InvalidInput, NotFound
from termpilot.mail.parsing import normalise_recipients
from termpilot.mail.transport import MailTransport, Outgoing, build_transport
from termpilot.security.sealing import SealError, seal, unseal
from termpilot.settings import Settings

TransportFactory = Callable[[Settings, str], MailTransport]


@dataclass
class SyncSummary:
    folder: str
    fetched: int
    added: int
    updated: int


def _transport(settings: Settings, provider: str, factory: TransportFactory | None = None) -> MailTransport:
    return (factory or build_transport)(settings, provider)


def get_link(db: Session, student: Student) -> MailLink | None:
    return db.get(MailLink, student.id)


def require_link(db: Session, student: Student) -> MailLink:
    link = get_link(db, student)
    if link is None:
        raise NotFound("No mailbox is connected yet.", code="mailbox_not_connected")
    return link


def _secret(settings: Settings, link: MailLink) -> str:
    try:
        return unseal(settings, link.sealed_secret)
    except SealError as exc:
        raise InvalidInput("The stored mailbox credentials are unreadable. Connect the mailbox again.") from exc


def connect(
    db: Session,
    settings: Settings,
    student: Student,
    provider: str,
    address: str,
    secret: str,
    factory: TransportFactory | None = None,
) -> MailLink:
    address = address.strip()
    if "@" not in address:
        raise InvalidInput("Enter the full email address.")
    if not secret.strip():
        raise InvalidInput("Enter the mailbox authorization code.")
    _transport(settings, provider, factory).verify(address, secret.strip())
    link = get_link(db, student)
    if link is None:
        link = MailLink(student_id=student.id, provider=provider, address=address, sealed_secret="", linked_at=utcnow())
        db.add(link)
    elif link.address != address:
        # Messages of the previous mailbox are no longer reachable through this link.
        db.query(MailItem).filter(MailItem.student_id == student.id).delete()
    link.provider = provider
    link.address = address
    link.sealed_secret = seal(settings, secret.strip())
    link.linked_at = utcnow()
    db.commit()
    return link


def disconnect(db: Session, student: Student) -> bool:
    link = get_link(db, student)
    if link is None:
        return False
    db.query(MailItem).filter(MailItem.student_id == student.id).delete()
    db.delete(link)
    db.commit()
    return True


def synchronise(
    db: Session,
    settings: Settings,
    student: Student,
    *,
    folder: str = "INBOX",
    limit: int = 30,
    unread_only: bool = False,
    factory: TransportFactory | None = None,
) -> SyncSummary:
    link = require_link(db, student)
    folder = folder.strip() or "INBOX"
    messages = _transport(settings, link.provider, factory).fetch(
        link.address, _secret(settings, link), folder, limit, unread_only
    )
    existing = {
        item.uid: item
        for item in db.scalars(
            select(MailItem).where(
                MailItem.student_id == student.id,
                MailItem.address == link.address,
                MailItem.folder == folder,
                MailItem.uid.in_([message.uid for message in messages]),
            )
        )
    }
    now = utcnow()
    added = 0
    for message in messages:
        item = existing.get(message.uid)
        if item is None:
            item = MailItem(student_id=student.id, address=link.address, folder=folder, uid=message.uid, synced_at=now)
            db.add(item)
            added += 1
        for field in (
            "message_id",
            "subject",
            "sender",
            "recipients",
            "cc",
            "received_at",
            "preview",
            "body_text",
            "body_html",
            "seen",
            "has_attachments",
        ):
            setattr(item, field, getattr(message, field))
        item.synced_at = now
    link.last_synced_at = now
    db.commit()
    return SyncSummary(folder=folder, fetched=len(messages), added=added, updated=len(messages) - added)


def list_messages(
    db: Session,
    student: Student,
    *,
    folder: str | None = None,
    unread_only: bool = False,
    query: str | None = None,
    limit: int = 50,
) -> list[MailItem]:
    link = require_link(db, student)
    statement = select(MailItem).where(MailItem.student_id == student.id, MailItem.address == link.address)
    if folder:
        statement = statement.where(MailItem.folder == folder)
    if unread_only:
        statement = statement.where(MailItem.seen.is_(False))
    if query:
        pattern = f"%{query.strip()}%"
        statement = statement.where(MailItem.subject.ilike(pattern) | MailItem.sender.ilike(pattern))
    return list(
        db.scalars(statement.order_by(MailItem.received_at.desc().nulls_last(), MailItem.id.desc()).limit(limit))
    )


def get_message(db: Session, student: Student, message_id: int) -> MailItem:
    item = db.get(MailItem, message_id)
    if item is None or item.student_id != student.id:
        raise NotFound("That message does not exist.")
    return item


def unread_count(db: Session, student: Student) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(MailItem)
            .where(MailItem.student_id == student.id, MailItem.seen.is_(False))
        )
        or 0
    )


def compose(to: list[str], cc: list[str], bcc: list[str], subject: str, body: str, html: str | None = None) -> Outgoing:
    if not subject.strip():
        raise InvalidInput("Add a subject.")
    if not (body or "").strip() and not (html or "").strip():
        raise InvalidInput("The message is empty.")
    try:
        recipients = normalise_recipients(to)
        copies = normalise_recipients(cc)
        hidden = normalise_recipients(bcc)
    except ValueError as exc:
        raise InvalidInput(str(exc)) from exc
    if not recipients:
        raise InvalidInput("Add at least one recipient.")
    return Outgoing(to=recipients, cc=copies, bcc=hidden, subject=subject.strip(), body=(body or "").strip(), html=html)


def send(
    db: Session, settings: Settings, student: Student, message: Outgoing, factory: TransportFactory | None = None
) -> str:
    link = require_link(db, student)
    return _transport(settings, link.provider, factory).send(link.address, _secret(settings, link), message)
