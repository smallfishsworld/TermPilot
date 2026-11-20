"""Time helpers.

All timestamps are stored in UTC. Campus-facing logic (today's classes, the
current teaching week) works in the configured campus time zone. Tests replace
``now`` through :func:`freeze`.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

_now: Callable[[], datetime] = lambda: datetime.now(UTC)  # noqa: E731


def utcnow() -> datetime:
    return _now()


def local_now(tz: ZoneInfo) -> datetime:
    return utcnow().astimezone(tz)


def local_today(tz: ZoneInfo) -> date:
    return local_now(tz).date()


def as_utc(value: datetime, assume: ZoneInfo | None = None) -> datetime:
    """Return an aware UTC datetime; naive values are read in ``assume`` (or UTC)."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=assume or UTC)
    return value.astimezone(UTC)


def freeze(moment: datetime | None) -> None:
    """Pin the clock to ``moment`` (aware) or restore the real clock with ``None``."""
    global _now
    if moment is None:
        _now = lambda: datetime.now(UTC)  # noqa: E731
    else:
        pinned = as_utc(moment)
        _now = lambda: pinned  # noqa: E731
