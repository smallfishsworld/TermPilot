"""The "Today" overview: what is on now, what is due soon and what needs attention."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from termpilot.campus.terms import Term
from termpilot.clock import local_now, utcnow
from termpilot.db.models import LibraryDocument, MailItem, PendingAction, Student, SyncRun, Task, TimetableEntry
from termpilot.services.tasks import list_tasks
from termpilot.services.term_calendar import current_term
from termpilot.services.timetable import Clash, entries_on, find_clashes, list_entries
from termpilot.settings import Settings

DUE_SOON = timedelta(hours=72)


@dataclass
class Briefing:
    day: date
    term: Term
    week: int
    now_local: datetime
    classes_today: list[TimetableEntry]
    next_class: TimetableEntry | None
    classes_tomorrow: int
    due_soon: list[Task]
    overdue: list[Task]
    clashes: list[Clash]
    titles: dict[int, str]
    unread_mail: int
    pending_approvals: int
    library_documents: int
    last_sync: SyncRun | None
    tips: list[str] = field(default_factory=list)


def build(db: Session, settings: Settings, student: Student) -> Briefing:
    now_local = local_now(settings.tz)
    today = now_local.date()
    term = current_term(settings, student, today)
    week = term.week_of(today)
    entries = list_entries(db, student)
    todays = entries_on(entries, today, term)
    upcoming = [entry for entry in todays if entry.ends_at > now_local.time()]

    now = utcnow()
    open_tasks = list_tasks(db, student, status="open")
    due_soon = [task for task in open_tasks if now <= task.due_at <= now + DUE_SOON]
    overdue = [task for task in open_tasks if task.due_at < now]

    clashes = [clash for clash in find_clashes(entries, term.weeks) if any(w >= week for w in clash.weeks)]

    def count(statement) -> int:  # type: ignore[no-untyped-def]
        return int(db.scalar(statement) or 0)

    briefing = Briefing(
        day=today,
        term=term,
        week=week,
        now_local=now_local,
        classes_today=todays,
        next_class=upcoming[0] if upcoming else None,
        classes_tomorrow=len(entries_on(entries, today + timedelta(days=1), term)),
        due_soon=due_soon,
        overdue=overdue,
        clashes=clashes,
        titles={entry.id: entry.title for entry in entries},
        unread_mail=count(
            select(func.count())
            .select_from(MailItem)
            .where(MailItem.student_id == student.id, MailItem.seen.is_(False))
        ),
        pending_approvals=count(
            select(func.count())
            .select_from(PendingAction)
            .where(
                PendingAction.student_id == student.id,
                PendingAction.status == "pending",
                PendingAction.expires_at > now,
            )
        ),
        library_documents=count(
            select(func.count()).select_from(LibraryDocument).where(LibraryDocument.student_id == student.id)
        ),
        last_sync=db.scalar(
            select(SyncRun).where(SyncRun.student_id == student.id).order_by(SyncRun.started_at.desc()).limit(1)
        ),
    )
    briefing.tips = _tips(briefing)
    return briefing


def _tips(briefing: Briefing) -> list[str]:
    tips: list[str] = []
    if briefing.last_sync is None:
        tips.append("Run your first sync to import the timetable, grades and deadlines.")
    if briefing.overdue:
        tips.append(f"{len(briefing.overdue)} task(s) are past due. Mark them done or reschedule them.")
    heavy = [task for task in briefing.due_soon if (task.category or "") == "exam"]
    if heavy:
        tips.append(f"An exam is coming up: {heavy[0].title}. The planner can book study time for it.")
    if briefing.clashes:
        tips.append(f"{len(briefing.clashes)} timetable clash(es) ahead. Check the timetable.")
    if briefing.pending_approvals:
        tips.append("The assistant is waiting for your decision on a proposed action.")
    if not briefing.term.contains(briefing.day):
        tips.append(f"Classes are not in session. {briefing.term.label} teaching starts {briefing.term.start:%b %d}.")
    return tips
