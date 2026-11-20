"""Import data from campus systems into the student's records.

A sync run executes independent steps. Each step commits on its own, so a
failing learning platform does not discard a freshly imported timetable. When
the campus session has expired, the remaining steps are skipped instead of
hammering the services with requests that cannot succeed.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from termpilot.campus.gateway import CampusGateway
from termpilot.campus.records import CampusCookies, LmsCourse
from termpilot.clock import utcnow
from termpilot.db.models import (
    CourseGrade,
    CourseMaterial,
    CreditSummary,
    Student,
    SyncRun,
    Task,
    TimetableEntry,
)
from termpilot.errors import AppError, CampusSessionExpired
from termpilot.services.accounts import apply_profile, load_cookies
from termpilot.services.term_calendar import current_term
from termpilot.settings import Settings

logger = logging.getLogger(__name__)

Source = Literal["profile", "grades", "timetable", "deadlines", "coursework", "materials"]
ALL_SOURCES: tuple[Source, ...] = ("profile", "grades", "timetable", "deadlines", "coursework", "materials")


@dataclass
class _Context:
    db: Session
    settings: Settings
    gateway: CampusGateway
    student: Student
    cookies: CampusCookies
    courses: list[LmsCourse] | None = None
    notes: list[str] = field(default_factory=list)

    def lms_courses(self) -> list[LmsCourse]:
        if self.courses is None:
            self.courses = self.gateway.courses(self.cookies, current_term(self.settings, self.student))
        return self.courses


def _sync_profile(ctx: _Context) -> str:
    profile = ctx.gateway.profile(ctx.cookies)
    changed = apply_profile(ctx.student, profile)
    photo = ctx.gateway.photo(ctx.cookies, profile)
    if photo is not None:
        ctx.student.photo = photo.content
        ctx.student.photo_type = photo.media_type
    return f"{len(changed)} profile fields updated" if changed else "Profile is up to date"


def _sync_grades(ctx: _Context) -> str:
    gpa = ctx.gateway.gpa(ctx.cookies)
    ctx.student.gpa = gpa.gpa
    ctx.student.gpa_rank = gpa.rank
    credits = ctx.gateway.credits(ctx.cookies)
    summary = ctx.db.get(CreditSummary, ctx.student.id)
    if summary is None:
        summary = CreditSummary(student_id=ctx.student.id, refreshed_at=utcnow())
        ctx.db.add(summary)
    summary.total = credits.total
    summary.by_category = credits.by_category
    summary.refreshed_at = utcnow()
    return f"GPA {gpa.gpa if gpa.gpa is not None else 'n/a'}, {credits.total:g} credits"


def _sync_timetable(ctx: _Context) -> str:
    term = current_term(ctx.settings, ctx.student)
    meetings, skipped = ctx.gateway.timetable(ctx.cookies, term)
    # Imported courses are replaced wholesale so dropped courses disappear;
    # blocks the student created or accepted from the planner stay untouched.
    ctx.db.execute(
        delete(TimetableEntry).where(TimetableEntry.student_id == ctx.student.id, TimetableEntry.origin == "records")
    )
    for meeting in meetings:
        ctx.db.add(
            TimetableEntry(
                student_id=ctx.student.id,
                title=meeting.title,
                kind="course",
                origin="records",
                weekday=meeting.weekday,
                starts_at=meeting.starts_at,
                ends_at=meeting.ends_at,
                first_period=meeting.first_period,
                last_period=meeting.last_period,
                weeks=meeting.weeks,
                week_label=meeting.week_label,
                location=meeting.location,
                instructor=meeting.instructor,
            )
        )
    message = f"{len(meetings)} class meetings for {term.label}"
    return f"{message}; {skipped} without a time slot skipped" if skipped else message


def _sync_deadlines(ctx: _Context) -> str:
    events = ctx.gateway.calendar(ctx.cookies, utcnow())
    existing = {
        task.external_ref: task
        for task in ctx.db.scalars(select(Task).where(Task.student_id == ctx.student.id, Task.origin == "lms"))
    }
    added = 0
    for event in events:
        task = existing.get(event.ref)
        if task is None:
            task = Task(
                student_id=ctx.student.id, origin="lms", external_ref=event.ref, title=event.title, due_at=event.due_at
            )
            ctx.db.add(task)
            existing[event.ref] = task
            added += 1
        # Platform-owned fields follow the platform; done/priority/effort stay the student's.
        task.title = event.title
        task.due_at = event.due_at
        task.course = event.course
        task.category = event.category
        task.color = event.color
    return f"{len(events)} calendar items, {added} new"


def _sync_coursework(ctx: _Context) -> str:
    items = ctx.gateway.grades(ctx.cookies, ctx.lms_courses())
    ctx.db.execute(delete(CourseGrade).where(CourseGrade.student_id == ctx.student.id))
    now = utcnow()
    for item in items:
        ctx.db.add(
            CourseGrade(
                student_id=ctx.student.id,
                course_ref=item.course_ref,
                course_title=item.course_title,
                item=item.item,
                score=item.score,
                synced_at=now,
            )
        )
    return f"{len(items)} graded items from {len(ctx.lms_courses())} courses"


def _sync_materials(ctx: _Context) -> str:
    materials = ctx.gateway.materials(ctx.cookies, ctx.lms_courses())
    ctx.db.execute(delete(CourseMaterial).where(CourseMaterial.student_id == ctx.student.id))
    now = utcnow()
    for material in materials:
        ctx.db.add(
            CourseMaterial(
                student_id=ctx.student.id,
                course_title=material.course_title,
                section=material.section,
                title=material.title,
                url=material.url,
                synced_at=now,
            )
        )
    return f"{len(materials)} course files listed"


_STEPS: dict[Source, Callable[[_Context], str]] = {
    "profile": _sync_profile,
    "grades": _sync_grades,
    "timetable": _sync_timetable,
    "deadlines": _sync_deadlines,
    "coursework": _sync_coursework,
    "materials": _sync_materials,
}


def run_sync(
    db: Session,
    settings: Settings,
    gateway: CampusGateway,
    student: Student,
    *,
    sources: tuple[Source, ...] | list[Source] = ALL_SOURCES,
    trigger: str = "manual",
) -> SyncRun:
    run = SyncRun(student_id=student.id, trigger=trigger, started_at=utcnow(), steps=[])
    db.add(run)
    db.commit()

    steps: list[dict[str, object]] = []
    try:
        ctx = _Context(db, settings, gateway, student, load_cookies(db, settings, student.id))
    except CampusSessionExpired as exc:
        ctx = None
        steps = [{"source": source, "ok": False, "message": exc.message} for source in sources]

    expired: str | None = None
    for source in sources if ctx is not None else ():
        if expired:
            steps.append({"source": source, "ok": False, "message": "Skipped: " + expired})
            continue
        try:
            message = _STEPS[source](ctx)
            db.commit()
            steps.append({"source": source, "ok": True, "message": message})
        except CampusSessionExpired as exc:
            db.rollback()
            expired = exc.message
            steps.append({"source": source, "ok": False, "message": exc.message})
        except AppError as exc:
            db.rollback()
            steps.append({"source": source, "ok": False, "message": exc.message})
        except Exception:  # a parser broke on unexpected markup
            db.rollback()
            logger.exception("Sync step %s failed", source)
            steps.append({"source": source, "ok": False, "message": "Unexpected data from the campus service."})

    succeeded = sum(1 for step in steps if step["ok"])
    run.steps = steps
    run.outcome = "ok" if succeeded == len(steps) else ("partial" if succeeded else "failed")
    run.finished_at = utcnow()
    db.commit()
    return run


def recent_runs(db: Session, student: Student, limit: int = 10) -> list[SyncRun]:
    return list(
        db.scalars(
            select(SyncRun).where(SyncRun.student_id == student.id).order_by(SyncRun.started_at.desc()).limit(limit)
        )
    )
