"""Suggest study sessions for upcoming tasks in the student's free time.

The planner works day by day across the planning horizon. For each free
interval between classes it repeatedly gives the next block to the open task
with the earliest due date (earliest-deadline-first), until the task's
estimated effort is covered. Blocks never end after the task is due, and a
short gap separates consecutive blocks.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from termpilot.clock import local_now, utcnow
from termpilot.db.models import Student, Task, TimetableEntry
from termpilot.errors import InvalidInput
from termpilot.services.tasks import effort_of, get_task, list_tasks
from termpilot.services.term_calendar import current_term
from termpilot.services.timetable import entries_on, list_entries
from termpilot.settings import Settings

_PRIORITY_RANK = {"high": 0, "normal": 1, "low": 2}


@dataclass(frozen=True)
class PlannerOptions:
    days: int = 7
    day_start: time = time(8, 0)
    day_end: time = time(22, 0)
    block_minutes: int = 90
    min_block_minutes: int = 30
    gap_minutes: int = 15
    max_blocks_per_day: int = 3


@dataclass(frozen=True)
class StudyBlock:
    task_id: int
    task_title: str
    day: date
    week: int
    starts_at: time
    ends_at: time

    @property
    def minutes(self) -> int:
        return _minutes(self.ends_at) - _minutes(self.starts_at)


def _minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def _clock(minutes: int) -> time:
    return time(minutes // 60, minutes % 60)


def _free_intervals(busy: list[tuple[int, int]], start: int, end: int, gap: int) -> list[tuple[int, int]]:
    free: list[tuple[int, int]] = []
    cursor = start
    for busy_start, busy_end in sorted(busy):
        if busy_start - gap > cursor:
            free.append((cursor, min(busy_start - gap, end)))
        cursor = max(cursor, busy_end + gap)
        if cursor >= end:
            break
    if cursor < end:
        free.append((cursor, end))
    return [(low, high) for low, high in free if high > low]


def _already_planned(db: Session, student: Student, today: date, term_week: int) -> dict[int, int]:
    """Minutes of future study blocks per task, so suggestions do not double up."""
    planned: dict[int, int] = {}
    for entry in db.scalars(
        select(TimetableEntry).where(TimetableEntry.student_id == student.id, TimetableEntry.task_id.is_not(None))
    ):
        if entry.weeks and max(entry.weeks) < term_week:
            continue
        length = _minutes(entry.ends_at) - _minutes(entry.starts_at)
        planned[entry.task_id] = planned.get(entry.task_id, 0) + length  # type: ignore[index]
    return planned


def suggest(
    db: Session, settings: Settings, student: Student, options: PlannerOptions | None = None
) -> list[StudyBlock]:
    options = options or PlannerOptions()
    tz = settings.tz
    now = local_now(tz)
    today = now.date()
    term = current_term(settings, student, today)
    if not term.contains(today):
        return []

    horizon_end = datetime.combine(today + timedelta(days=options.days), time.max, tz)
    tasks = [task for task in list_tasks(db, student, status="open", due_after=utcnow(), due_before=horizon_end)]
    planned = _already_planned(db, student, today, term.week_of(today))
    remaining = {task.id: max(0, effort_of(task) - planned.get(task.id, 0)) for task in tasks}
    entries = list_entries(db, student)
    blocks: list[StudyBlock] = []

    for offset in range(options.days):
        day = today + timedelta(days=offset)
        if not term.contains(day):
            break
        busy = [(_minutes(e.starts_at), _minutes(e.ends_at)) for e in entries_on(entries, day, term)]
        busy += [(_minutes(b.starts_at), _minutes(b.ends_at)) for b in blocks if b.day == day]
        start = _minutes(options.day_start)
        if day == today:
            rounded = -(-(now.hour * 60 + now.minute) // 15) * 15
            start = max(start, rounded)
        end = _minutes(options.day_end)
        placed_today = 0
        for low, high in _free_intervals(busy, start, end, options.gap_minutes):
            cursor = low
            while placed_today < options.max_blocks_per_day and high - cursor >= options.min_block_minutes:
                block_start = datetime.combine(day, _clock(cursor), tz)
                candidates = [
                    task
                    for task in tasks
                    if remaining[task.id] >= options.min_block_minutes
                    and task.due_at > block_start + timedelta(minutes=options.min_block_minutes)
                ]
                if not candidates:
                    break
                task = min(candidates, key=lambda t: (t.due_at, _PRIORITY_RANK.get(t.priority, 1)))
                minutes_to_due = int((task.due_at - block_start).total_seconds() // 60)
                length = min(options.block_minutes, remaining[task.id], high - cursor, minutes_to_due)
                if length < options.min_block_minutes:
                    break
                blocks.append(
                    StudyBlock(
                        task_id=task.id,
                        task_title=task.title,
                        day=day,
                        week=term.week_of(day),
                        starts_at=_clock(cursor),
                        ends_at=_clock(cursor + length),
                    )
                )
                remaining[task.id] -= length
                cursor += length + options.gap_minutes
                placed_today += 1
    return blocks


def accept(
    db: Session, settings: Settings, student: Student, picks: list[tuple[int, date, time, time]]
) -> list[TimetableEntry]:
    """Turn chosen suggestions into one-week study entries on the timetable."""
    term = current_term(settings, student)
    created: list[TimetableEntry] = []
    for task_id, day, starts_at, ends_at in picks:
        task: Task = get_task(db, student, task_id)
        if not term.contains(day):
            raise InvalidInput(f"{day.isoformat()} is outside the current term.")
        if starts_at >= ends_at:
            raise InvalidInput("A study block must end after it starts.")
        entry = TimetableEntry(
            student_id=student.id,
            title=f"Study: {task.title}"[:200],
            kind="study",
            origin="planner",
            weekday=day.isoweekday(),
            starts_at=starts_at,
            ends_at=ends_at,
            weeks=[term.week_of(day)],
            notes=f"Planned for {task.title}" + (f" ({task.course})" if task.course else ""),
            task_id=task.id,
        )
        db.add(entry)
        created.append(entry)
    db.commit()
    return created
