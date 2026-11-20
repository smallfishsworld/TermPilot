"""Conversions from service results to response models."""

from __future__ import annotations

from datetime import date

from termpilot.api import schemas
from termpilot.campus.terms import Term
from termpilot.db.models import SyncRun, TimetableEntry
from termpilot.services.briefing import Briefing
from termpilot.services.timetable import Clash


def term_view(term: Term, today: date) -> schemas.TermView:
    return schemas.TermView(
        today=today,
        label=term.label,
        academic_year=term.academic_year,
        start=term.start,
        end=term.end,
        weeks=term.weeks,
        current_week=term.week_of(today),
        in_session=term.contains(today),
    )


def clash_view(clash: Clash, entries: list[TimetableEntry] | dict[int, str]) -> schemas.ClashView:
    titles = entries if isinstance(entries, dict) else {entry.id: entry.title for entry in entries}
    return schemas.ClashView(
        first_id=clash.first_id,
        second_id=clash.second_id,
        weekday=clash.weekday,
        weeks=clash.weeks,
        starts_at=clash.starts_at,
        ends_at=clash.ends_at,
        description=clash.describe(titles),
    )


def briefing_view(briefing: Briefing) -> schemas.BriefingView:
    entry = schemas.EntryView.model_validate
    task = schemas.TaskView.model_validate
    return schemas.BriefingView(
        day=briefing.day,
        term=term_view(briefing.term, briefing.day),
        now=briefing.now_local,
        classes_today=[entry(item) for item in briefing.classes_today],
        next_class=entry(briefing.next_class) if briefing.next_class else None,
        classes_tomorrow=briefing.classes_tomorrow,
        due_soon=[task(item) for item in briefing.due_soon],
        overdue=[task(item) for item in briefing.overdue],
        clashes=[clash_view(item, briefing.titles) for item in briefing.clashes],
        unread_mail=briefing.unread_mail,
        pending_approvals=briefing.pending_approvals,
        library_documents=briefing.library_documents,
        last_sync_at=briefing.last_sync.finished_at if briefing.last_sync else None,
        last_sync_outcome=briefing.last_sync.outcome if briefing.last_sync else None,
        tips=briefing.tips,
    )


def sync_view(run: SyncRun) -> schemas.SyncRunView:
    return schemas.SyncRunView.model_validate(run)
