"""Mailbox connection, synchronisation, reading and sending."""

from __future__ import annotations

from fastapi import APIRouter, Query, Response, status

from termpilot.api import schemas
from termpilot.api.deps import AppSettings, CurrentStudent, DbSession, Model
from termpilot.assistant.helpers import extract_tasks
from termpilot.db.models import MailItem
from termpilot.services import mailbox

router = APIRouter(prefix="/mail", tags=["mail"])


def _account(settings: AppSettings, link) -> schemas.MailAccountView:  # type: ignore[no-untyped-def]
    providers = ["demo"] if settings.demo_mode else sorted(settings.mail_providers)
    if link is None:
        return schemas.MailAccountView(connected=False, providers=providers)
    return schemas.MailAccountView(
        connected=True,
        provider=link.provider,
        address=link.address,
        linked_at=link.linked_at,
        last_synced_at=link.last_synced_at,
        providers=providers,
    )


@router.get("/account", response_model=schemas.MailAccountView)
def account(student: CurrentStudent, db: DbSession, settings: AppSettings) -> schemas.MailAccountView:
    return _account(settings, mailbox.get_link(db, student))


@router.put("/account", response_model=schemas.MailAccountView)
def connect(
    body: schemas.MailAccountRequest, student: CurrentStudent, db: DbSession, settings: AppSettings
) -> schemas.MailAccountView:
    link = mailbox.connect(db, settings, student, body.provider, body.address, body.secret)
    return _account(settings, link)


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
def disconnect(student: CurrentStudent, db: DbSession) -> Response:
    mailbox.disconnect(db, student)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/sync", response_model=schemas.MailSyncView)
def synchronise(
    body: schemas.MailSyncRequest, student: CurrentStudent, db: DbSession, settings: AppSettings
) -> schemas.MailSyncView:
    summary = mailbox.synchronise(
        db, settings, student, folder=body.folder, limit=body.limit, unread_only=body.unread_only
    )
    return schemas.MailSyncView(
        folder=summary.folder, fetched=summary.fetched, added=summary.added, updated=summary.updated
    )


@router.get("/messages", response_model=list[schemas.MailSummaryView])
def messages(
    student: CurrentStudent,
    db: DbSession,
    folder: str | None = None,
    unread_only: bool = False,
    q: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[MailItem]:
    return mailbox.list_messages(db, student, folder=folder, unread_only=unread_only, query=q, limit=limit)


@router.get("/messages/{message_id}", response_model=schemas.MailDetailView)
def message(message_id: int, student: CurrentStudent, db: DbSession) -> MailItem:
    return mailbox.get_message(db, student, message_id)


@router.post("/messages/{message_id}/tasks", response_model=list[schemas.TaskCandidateView])
def suggested_tasks(
    message_id: int, student: CurrentStudent, db: DbSession, settings: AppSettings, model: Model
) -> list[schemas.TaskCandidateView]:
    """Ask the model for deadlines mentioned in a message. Nothing is saved."""
    item = mailbox.get_message(db, student, message_id)
    return [
        schemas.TaskCandidateView(title=c.title, due_at=c.due_at, category=c.category, notes=c.notes)
        for c in extract_tasks(settings, model, item)
    ]


@router.post("/send", response_model=schemas.MailSentView)
def send(
    body: schemas.MailSendRequest, student: CurrentStudent, db: DbSession, settings: AppSettings
) -> schemas.MailSentView:
    message = mailbox.compose(body.to, body.cc, body.bcc, body.subject, body.body)
    return schemas.MailSentView(message_id=mailbox.send(db, settings, student, message))
