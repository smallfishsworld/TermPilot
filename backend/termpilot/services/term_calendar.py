"""The student's current term and teaching week."""

from __future__ import annotations

from datetime import date

from termpilot.campus.terms import Term, resolve_term
from termpilot.clock import local_today
from termpilot.db.models import Student
from termpilot.settings import Settings


def current_term(settings: Settings, student: Student | None, today: date | None = None) -> Term:
    return resolve_term(
        today or local_today(settings.tz),
        weeks=settings.term_weeks,
        personal_start=student.term_start if student is not None else None,
        deployment_start=settings.term_start_override,
    )


def occurs_on(weeks: list[int], weekday: int, day: date, term: Term) -> bool:
    """Whether a weekly block with ``weeks``/``weekday`` takes place on ``day``."""
    if day.isoweekday() != weekday or not term.contains(day):
        return False
    return not weeks or term.week_of(day) in weeks
