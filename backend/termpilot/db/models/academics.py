from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from termpilot.db.base import Base


class CreditSummary(Base):
    """Earned credits, in total and per course category."""

    __tablename__ = "credit_summaries"

    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), primary_key=True)
    total: Mapped[float] = mapped_column(default=0.0)
    by_category: Mapped[dict[str, Any]] = mapped_column(default=dict)
    refreshed_at: Mapped[datetime]


class CourseGrade(Base):
    """A graded item from a course gradebook in the learning platform."""

    __tablename__ = "course_grades"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    course_ref: Mapped[str] = mapped_column(String(120))
    course_title: Mapped[str] = mapped_column(String(300))
    item: Mapped[str] = mapped_column(String(400))
    score: Mapped[str] = mapped_column(String(60))
    synced_at: Mapped[datetime]


class CourseMaterial(Base):
    """A downloadable file linked from a course page."""

    __tablename__ = "course_materials"
    __table_args__ = (UniqueConstraint("student_id", "url"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    course_title: Mapped[str] = mapped_column(String(300))
    section: Mapped[str | None] = mapped_column(String(300))
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(Text)
    synced_at: Mapped[datetime]
