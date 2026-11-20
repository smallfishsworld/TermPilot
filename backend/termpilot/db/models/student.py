from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, deferred, mapped_column

from termpilot.db.base import Base, Timestamped


class Student(Timestamped, Base):
    """A signed-in student. The primary key is the campus student number."""

    __tablename__ = "students"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    display_name: Mapped[str] = mapped_column(String(120))
    pinyin_name: Mapped[str | None] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(40))
    gender: Mapped[str | None] = mapped_column(String(16))
    birth_date: Mapped[date | None]
    college: Mapped[str | None] = mapped_column(String(160))
    department: Mapped[str | None] = mapped_column(String(160))
    class_name: Mapped[str | None] = mapped_column(String(160))
    dormitory: Mapped[str | None] = mapped_column(String(120))
    photo: Mapped[bytes | None] = deferred(mapped_column(LargeBinary))
    photo_type: Mapped[str | None] = mapped_column(String(32))
    gpa: Mapped[float | None]
    gpa_rank: Mapped[str | None] = mapped_column(String(40))
    interests: Mapped[str | None] = mapped_column(Text)
    term_start: Mapped[date | None]
    is_demo: Mapped[bool] = mapped_column(default=False)
    # Incremented on sign-out so that previously issued tokens stop working.
    session_epoch: Mapped[int] = mapped_column(default=0)


class CampusLink(Base):
    """Encrypted cookies for the campus services a student signed in to."""

    __tablename__ = "campus_links"

    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), primary_key=True)
    sealed_cookies: Mapped[str] = mapped_column(Text)
    services: Mapped[list[str]] = mapped_column(default=list)
    linked_at: Mapped[datetime]
    checked_at: Mapped[datetime | None]


class SyncRun(Base):
    """One execution of the campus import, with a result per source."""

    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    trigger: Mapped[str] = mapped_column(String(20))
    outcome: Mapped[str] = mapped_column(String(16), default="running")
    steps: Mapped[list[dict[str, Any]]] = mapped_column(default=list)
    started_at: Mapped[datetime]
    finished_at: Mapped[datetime | None]
