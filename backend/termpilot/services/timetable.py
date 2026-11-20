"""Weekly timetable: course meetings, study blocks and personal activities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from termpilot.campus.periods import describe_weeks
from termpilot.campus.terms import Term
from termpilot.db.models import Student, TimetableEntry
from termpilot.errors import InvalidInput, NotFound
from termpilot.services.term_calendar import occurs_on

KINDS = ("course", "study", "activity", "meeting", "other")
EDITABLE_FIELDS = (
    "title",
    "kind",
    "weekday",
    "starts_at",
    "ends_at",
    "weeks",
    "location",
    "instructor",
    "notes",
    "color",
)


def list_entries(db: Session, student: Student) -> list[TimetableEntry]:
    return list(
        db.scalars(
            select(TimetableEntry)
            .where(TimetableEntry.student_id == student.id)
            .order_by(TimetableEntry.weekday, TimetableEntry.starts_at, TimetableEntry.id)
        )
    )


def get_entry(db: Session, student: Student, entry_id: int) -> TimetableEntry:
    entry = db.get(TimetableEntry, entry_id)
    if entry is None or entry.student_id != student.id:
        raise NotFound("That timetable entry does not exist.")
    return entry


def _validate(values: dict[str, Any]) -> None:
    title = values.get("title")
    if title is not None and not str(title).strip():
        raise InvalidInput("Give the entry a title.")
    if values.get("kind") is not None and values["kind"] not in KINDS:
        raise InvalidInput(f"Kind must be one of: {', '.join(KINDS)}.")
    weekday = values.get("weekday")
    if weekday is not None and not 1 <= int(weekday) <= 7:
        raise InvalidInput("Weekday must be between 1 (Monday) and 7 (Sunday).")
    starts_at, ends_at = values.get("starts_at"), values.get("ends_at")
    if isinstance(starts_at, time) and isinstance(ends_at, time) and starts_at >= ends_at:
        raise InvalidInput("The entry must end after it starts.")
    weeks = values.get("weeks")
    if weeks is not None and any(not 1 <= int(week) <= 30 for week in weeks):
        raise InvalidInput("Weeks must be between 1 and 30.")


def create_entry(db: Session, student: Student, values: dict[str, Any], *, origin: str = "manual") -> TimetableEntry:
    for required in ("title", "weekday", "starts_at", "ends_at"):
        if values.get(required) in (None, ""):
            raise InvalidInput(f"Missing field: {required}.")
    _validate(values)
    entry = TimetableEntry(
        student_id=student.id,
        origin=origin,
        kind=values.get("kind") or "activity",
        **{key: values[key] for key in EDITABLE_FIELDS if key in values and key != "kind"},
    )
    entry.title = entry.title.strip()
    entry.weeks = sorted(set(entry.weeks or []))
    db.add(entry)
    db.commit()
    return entry


def update_entry(db: Session, student: Student, entry_id: int, changes: dict[str, Any]) -> TimetableEntry:
    entry = get_entry(db, student, entry_id)
    merged = {key: getattr(entry, key) for key in EDITABLE_FIELDS} | {
        key: value for key, value in changes.items() if key in EDITABLE_FIELDS
    }
    _validate(merged)
    for key, value in changes.items():
        if key in EDITABLE_FIELDS:
            setattr(entry, key, sorted(set(value)) if key == "weeks" and value is not None else value)
    if entry.origin == "records" and changes:
        # An edited import is now the student's own; the next sync must not overwrite it.
        entry.origin = "manual"
    db.commit()
    return entry


def delete_entry(db: Session, student: Student, entry_id: int) -> None:
    db.delete(get_entry(db, student, entry_id))
    db.commit()


def entries_on(entries: list[TimetableEntry], day: date, term: Term) -> list[TimetableEntry]:
    return sorted(
        (entry for entry in entries if occurs_on(entry.weeks, entry.weekday, day, term)),
        key=lambda entry: entry.starts_at,
    )


@dataclass(frozen=True)
class Clash:
    first_id: int
    second_id: int
    weekday: int
    weeks: list[int]
    starts_at: time
    ends_at: time

    def describe(self, titles: dict[int, str]) -> str:
        return (
            f"{titles.get(self.first_id, '?')} overlaps {titles.get(self.second_id, '?')} "
            f"on weekday {self.weekday} ({self.starts_at:%H:%M}-{self.ends_at:%H:%M}, "
            f"weeks {describe_weeks(self.weeks)})"
        )


def find_clashes(entries: list[TimetableEntry], term_weeks: int) -> list[Clash]:
    """Pairs of entries that occupy the same time in at least one week."""
    clashes: list[Clash] = []
    by_day: dict[int, list[TimetableEntry]] = {}
    for entry in entries:
        by_day.setdefault(entry.weekday, []).append(entry)
    every_week = set(range(1, term_weeks + 1))
    for weekday, day_entries in by_day.items():
        day_entries.sort(key=lambda entry: entry.starts_at)
        for index, first in enumerate(day_entries):
            for second in day_entries[index + 1 :]:
                if second.starts_at >= first.ends_at:
                    break
                shared = (set(first.weeks) or every_week) & (set(second.weeks) or every_week)
                if shared:
                    clashes.append(
                        Clash(
                            first_id=first.id,
                            second_id=second.id,
                            weekday=weekday,
                            weeks=sorted(shared),
                            starts_at=max(first.starts_at, second.starts_at),
                            ends_at=min(first.ends_at, second.ends_at),
                        )
                    )
    return clashes
