"""Tasks with due dates: platform deadlines, exams and personal to-dos."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from termpilot.clock import utcnow
from termpilot.db.models import Student, Task
from termpilot.errors import InvalidInput, NotFound

PRIORITIES = ("low", "normal", "high")
EDITABLE_FIELDS = ("title", "due_at", "course", "category", "done", "priority", "effort_minutes", "notes", "color")

# Typical effort when the student has not estimated a task yet.
DEFAULT_EFFORT_MINUTES = {"exam": 240, "assignment": 150, "project": 240}
FALLBACK_EFFORT_MINUTES = 90

Status = Literal["open", "done", "all"]


def effort_of(task: Task) -> int:
    if task.effort_minutes:
        return task.effort_minutes
    return DEFAULT_EFFORT_MINUTES.get((task.category or "").lower(), FALLBACK_EFFORT_MINUTES)


def list_tasks(
    db: Session,
    student: Student,
    *,
    status: Status = "all",
    due_after: datetime | None = None,
    due_before: datetime | None = None,
    limit: int = 500,
) -> list[Task]:
    query = select(Task).where(Task.student_id == student.id)
    if status == "open":
        query = query.where(Task.done.is_(False))
    elif status == "done":
        query = query.where(Task.done.is_(True))
    if due_after is not None:
        query = query.where(Task.due_at >= due_after)
    if due_before is not None:
        query = query.where(Task.due_at <= due_before)
    return list(db.scalars(query.order_by(Task.done, Task.due_at, Task.id).limit(limit)))


def get_task(db: Session, student: Student, task_id: int) -> Task:
    task = db.get(Task, task_id)
    if task is None or task.student_id != student.id:
        raise NotFound("That task does not exist.")
    return task


def _validate(values: dict[str, Any]) -> None:
    if "title" in values and not str(values["title"] or "").strip():
        raise InvalidInput("Give the task a title.")
    if values.get("priority") is not None and values["priority"] not in PRIORITIES:
        raise InvalidInput("Priority must be low, normal or high.")
    effort = values.get("effort_minutes")
    if effort is not None and not 0 < int(effort) <= 60 * 100:
        raise InvalidInput("Effort must be between 1 minute and 100 hours.")
    due_at = values.get("due_at")
    if due_at is not None and (not isinstance(due_at, datetime) or due_at.tzinfo is None):
        raise InvalidInput("Due dates need a time zone.")


def create_task(db: Session, student: Student, values: dict[str, Any], *, origin: str = "manual") -> Task:
    if not values.get("title") or values.get("due_at") is None:
        raise InvalidInput("A task needs a title and a due date.")
    _validate(values)
    task = Task(
        student_id=student.id,
        origin=origin,
        **{key: values[key] for key in EDITABLE_FIELDS if values.get(key) is not None},
    )
    task.title = task.title.strip()
    db.add(task)
    db.commit()
    return task


def update_task(db: Session, student: Student, task_id: int, changes: dict[str, Any]) -> Task:
    task = get_task(db, student, task_id)
    accepted = {key: value for key, value in changes.items() if key in EDITABLE_FIELDS}
    _validate(accepted)
    for key, value in accepted.items():
        setattr(task, key, value.strip() if key == "title" else value)
    db.commit()
    return task


def delete_task(db: Session, student: Student, task_id: int) -> None:
    db.delete(get_task(db, student, task_id))
    db.commit()


def overdue(tasks: list[Task]) -> list[Task]:
    now = utcnow()
    return [task for task in tasks if not task.done and task.due_at < now]
