"""Proposed side effects and the student's decisions on them.

Tools never send mail, edit the timetable or touch files directly. They store
a :class:`PendingAction` with everything needed to carry out the change. The
payload stays on the server, so a decision can only approve exactly what was
shown. Claiming the action with a conditional update guarantees it runs at
most once even if the approve button is pressed twice.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from termpilot.clock import utcnow
from termpilot.db.models import PendingAction, Student
from termpilot.errors import AppError, Conflict, InvalidInput, NotFound
from termpilot.services import mailbox, study_planner, tasks, timetable
from termpilot.services.workspace import Workspace
from termpilot.settings import Settings

Executor = Callable[[Session, Settings, Student, dict[str, Any]], str]


def _time(value: Any) -> time:
    try:
        return time.fromisoformat(str(value))
    except ValueError as exc:
        raise InvalidInput(f"{value} is not a valid time.") from exc


def _entry_fields(raw: dict[str, Any]) -> dict[str, Any]:
    fields = dict(raw)
    for key in ("starts_at", "ends_at"):
        if key in fields and fields[key] is not None:
            fields[key] = _time(fields[key])
    return fields


def _task_fields(raw: dict[str, Any]) -> dict[str, Any]:
    fields = dict(raw)
    if fields.get("due_at"):
        fields["due_at"] = datetime.fromisoformat(str(fields["due_at"]))
    return fields


def _send_mail(db: Session, settings: Settings, student: Student, payload: dict[str, Any]) -> str:
    message = mailbox.compose(
        payload.get("to", []),
        payload.get("cc", []),
        payload.get("bcc", []),
        payload.get("subject", ""),
        payload.get("body", ""),
    )
    mailbox.send(db, settings, student, message)
    return f"Sent “{message.subject}” to {', '.join(message.to)}."


def _timetable_create(db: Session, settings: Settings, student: Student, payload: dict[str, Any]) -> str:
    entry = timetable.create_entry(db, student, _entry_fields(payload["fields"]), origin="assistant")
    return f"Added {entry.title} to your timetable."


def _timetable_update(db: Session, settings: Settings, student: Student, payload: dict[str, Any]) -> str:
    entry = timetable.update_entry(db, student, int(payload["entry_id"]), _entry_fields(payload["changes"]))
    return f"Updated {entry.title}."


def _timetable_delete(db: Session, settings: Settings, student: Student, payload: dict[str, Any]) -> str:
    entry = timetable.get_entry(db, student, int(payload["entry_id"]))
    title = entry.title
    timetable.delete_entry(db, student, entry.id)
    return f"Removed {title} from your timetable."


def _task_create(db: Session, settings: Settings, student: Student, payload: dict[str, Any]) -> str:
    task = tasks.create_task(db, student, _task_fields(payload["fields"]), origin=payload.get("origin", "assistant"))
    return f"Added the task {task.title}."


def _task_update(db: Session, settings: Settings, student: Student, payload: dict[str, Any]) -> str:
    task = tasks.update_task(db, student, int(payload["task_id"]), _task_fields(payload["changes"]))
    return f"Updated the task {task.title}."


def _study_schedule(db: Session, settings: Settings, student: Student, payload: dict[str, Any]) -> str:
    picks = [
        (int(block["task_id"]), date.fromisoformat(block["day"]), _time(block["starts_at"]), _time(block["ends_at"]))
        for block in payload.get("blocks", [])
    ]
    created = study_planner.accept(db, settings, student, picks)
    return f"Booked {len(created)} study block(s) on your timetable."


def _files(db: Session, settings: Settings, student: Student, payload: dict[str, Any]) -> str:
    return Workspace(settings, student.id).apply(payload)


EXECUTORS: dict[str, Executor] = {
    "email.send": _send_mail,
    "timetable.create": _timetable_create,
    "timetable.update": _timetable_update,
    "timetable.delete": _timetable_delete,
    "task.create": _task_create,
    "task.update": _task_update,
    "study.schedule": _study_schedule,
    "files.change": _files,
}


def propose(
    db: Session,
    settings: Settings,
    student: Student,
    *,
    kind: str,
    title: str,
    summary: str,
    payload: dict[str, Any],
    preview: str | None = None,
    conversation_id: str | None = None,
) -> PendingAction:
    if kind not in EXECUTORS:
        raise ValueError(f"No executor for {kind}")
    action = PendingAction(
        student_id=student.id,
        conversation_id=conversation_id,
        kind=kind,
        title=title,
        summary=summary,
        preview=preview,
        payload=payload,
        expires_at=utcnow() + timedelta(minutes=settings.approval_ttl_minutes),
    )
    db.add(action)
    db.commit()
    return action


def list_actions(
    db: Session, student: Student, *, status: str | None = "pending", limit: int = 50
) -> list[PendingAction]:
    expire_stale(db, student)
    query = select(PendingAction).where(PendingAction.student_id == student.id)
    if status:
        query = query.where(PendingAction.status == status)
    return list(db.scalars(query.order_by(PendingAction.created_at.desc()).limit(limit)))


def expire_stale(db: Session, student: Student) -> None:
    db.execute(
        update(PendingAction)
        .where(
            PendingAction.student_id == student.id,
            PendingAction.status == "pending",
            PendingAction.expires_at <= utcnow(),
        )
        .values(status="expired", outcome="The proposal expired before a decision was made.")
    )
    db.commit()


def decide(db: Session, settings: Settings, student: Student, action_id: str, approve: bool) -> PendingAction:
    action = db.get(PendingAction, action_id)
    if action is None or action.student_id != student.id:
        raise NotFound("That proposal does not exist.")
    expire_stale(db, student)
    db.refresh(action)
    if action.status != "pending":
        raise Conflict(f"This proposal is already {action.status}.")

    claimed = db.execute(
        update(PendingAction)
        .where(PendingAction.id == action.id, PendingAction.status == "pending")
        .values(status="running" if approve else "rejected", decided_at=utcnow())
    )
    db.commit()
    if claimed.rowcount != 1:
        raise Conflict("This proposal was decided in another window.")
    db.refresh(action)
    if not approve:
        action.outcome = "Declined. Nothing was changed."
        db.commit()
        return action
    try:
        action.outcome = EXECUTORS[action.kind](db, settings, student, dict(action.payload))
        action.status = "done"
    except AppError as exc:
        db.rollback()
        action = db.get(PendingAction, action_id)  # type: ignore[assignment]
        action.status = "failed"
        action.outcome = exc.message
    db.commit()
    return action
