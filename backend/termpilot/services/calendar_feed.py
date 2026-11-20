"""iCalendar (RFC 5545) export of the timetable and open tasks.

Weekly entries are expanded into one event per teaching week, because week
lists such as "1-15 odd weeks" cannot be expressed reliably with RRULE across
calendar apps. Times are written in UTC so no VTIMEZONE block is needed.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from termpilot.campus.terms import Term
from termpilot.db.models import Task, TimetableEntry

PRODUCT_ID = "-//TermPilot//Semester calendar//EN"


def _escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r\n", "\\n").replace("\n", "\\n")
    )


def _fold(line: str) -> list[str]:
    """Split a content line into chunks of at most 75 octets (continuations start with a space)."""
    chunks: list[str] = []
    current = ""
    limit = 75
    for char in line:
        if len((current + char).encode("utf-8")) > limit:
            chunks.append(current)
            current = " " + char
            limit = 75
        else:
            current += char
    chunks.append(current)
    return chunks


def _stamp(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _event(uid: str, start: datetime, end: datetime, summary: str, generated: datetime, **extra: str) -> list[str]:
    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{_stamp(generated)}",
        f"DTSTART:{_stamp(start)}",
        f"DTEND:{_stamp(end)}",
        f"SUMMARY:{_escape(summary)}",
    ]
    for key, value in extra.items():
        if value:
            lines.append(f"{key.upper()}:{_escape(value)}")
    return lines


def build_calendar(
    *,
    entries: Iterable[TimetableEntry],
    tasks: Iterable[Task],
    term: Term,
    tz: ZoneInfo,
    generated: datetime,
    name: str,
) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODUCT_ID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape(name)}",
        f"X-WR-TIMEZONE:{tz.key}",
    ]
    for entry in entries:
        details = " · ".join(part for part in (entry.instructor, entry.notes) if part)
        for week in entry.weeks or range(1, term.weeks + 1):
            day = term.date_of(week, entry.weekday)
            lines += _event(
                f"entry-{entry.id}-w{week}@termpilot",
                datetime.combine(day, entry.starts_at, tz),
                datetime.combine(day, entry.ends_at, tz),
                entry.title,
                generated,
                location=entry.location or "",
                description=details,
                categories=entry.kind,
            )
            lines.append("END:VEVENT")
    for task in tasks:
        if task.done:
            continue
        details = " · ".join(part for part in (task.course, task.category, task.notes) if part)
        lines += _event(
            f"task-{task.id}@termpilot",
            task.due_at - timedelta(minutes=30),
            task.due_at,
            f"Due: {task.title}",
            generated,
            description=details,
            categories="deadline",
        )
        lines += [
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            "TRIGGER:-PT24H",
            f"DESCRIPTION:{_escape(task.title)} is due tomorrow",
            "END:VALARM",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(chunk for line in lines for chunk in _fold(line)) + "\r\n"
