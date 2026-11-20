from __future__ import annotations

from datetime import datetime, time

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from termpilot.db.base import Base, Timestamped


class TimetableEntry(Timestamped, Base):
    """A weekly recurring block: a course, a study session or a personal activity.

    ``weeks`` lists the teaching weeks the block occurs in; an empty list means
    every week of the term.
    """

    __tablename__ = "timetable_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20), default="course")
    origin: Mapped[str] = mapped_column(String(20), default="manual")
    weekday: Mapped[int]
    starts_at: Mapped[time]
    ends_at: Mapped[time]
    first_period: Mapped[int | None]
    last_period: Mapped[int | None]
    weeks: Mapped[list[int]] = mapped_column(default=list)
    week_label: Mapped[str | None] = mapped_column(String(80))
    location: Mapped[str | None] = mapped_column(String(160))
    instructor: Mapped[str | None] = mapped_column(String(160))
    notes: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str | None] = mapped_column(String(16))
    # Set for study blocks scheduled by the planner for a specific task.
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"))


class Task(Timestamped, Base):
    """Something with a due date: an LMS assignment, an exam or a personal to-do."""

    __tablename__ = "tasks"
    __table_args__ = (UniqueConstraint("student_id", "origin", "external_ref"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    due_at: Mapped[datetime]
    course: Mapped[str | None] = mapped_column(String(200))
    category: Mapped[str | None] = mapped_column(String(40))
    origin: Mapped[str] = mapped_column(String(20), default="manual")
    external_ref: Mapped[str | None] = mapped_column(String(200))
    done: Mapped[bool] = mapped_column(default=False)
    priority: Mapped[str] = mapped_column(String(10), default="normal")
    effort_minutes: Mapped[int | None]
    notes: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str | None] = mapped_column(String(16))
