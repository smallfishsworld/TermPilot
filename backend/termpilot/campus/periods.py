"""Teaching periods and week specifications used by the records system.

Course meetings are published as period ranges ("3-4节") and week ranges
("1-16周", "2-16双周"). This module turns both into concrete values.
"""

from __future__ import annotations

import re
from datetime import time

# Period number -> (start, end), as printed on the campus timetable.
PERIODS: dict[int, tuple[time, time]] = {
    1: (time(8, 0), time(8, 50)),
    2: (time(9, 0), time(9, 50)),
    3: (time(10, 20), time(11, 10)),
    4: (time(11, 20), time(12, 10)),
    5: (time(14, 0), time(14, 50)),
    6: (time(15, 0), time(15, 50)),
    7: (time(16, 20), time(17, 10)),
    8: (time(17, 20), time(18, 10)),
    9: (time(19, 0), time(19, 50)),
    10: (time(20, 0), time(20, 50)),
    11: (time(21, 0), time(21, 50)),
}

_RANGE = re.compile(r"(\d{1,2})\s*(?:[-~—–至到]\s*(\d{1,2}))?")


def period_times(first: int, last: int) -> tuple[time, time]:
    """Start of ``first`` and end of ``last``; unknown periods raise ``KeyError``."""
    low, high = sorted((first, last))
    return PERIODS[low][0], PERIODS[high][1]


def parse_period_range(text: str | None) -> tuple[int, int] | None:
    """Read "3-4节", "第5节" or "periods 7-8" as an inclusive period range."""
    if not text:
        return None
    match = _RANGE.search(text)
    if not match:
        return None
    first = int(match.group(1))
    last = int(match.group(2) or first)
    first, last = sorted((first, last))
    if first < 1 or first > max(PERIODS):
        return None
    return first, min(last, max(PERIODS))


def parse_weeks(text: str | None, *, limit: int = 30) -> list[int]:
    """Expand a week specification into sorted week numbers.

    Supports lists and ranges ("1-8,10-16周"), single weeks ("3周") and odd or
    even filters ("1-15单周", "2-16双周", "odd weeks 1-15"). Unknown input gives
    an empty list, which callers treat as "every week".
    """
    if not text:
        return []
    weeks: set[int] = set()
    for match in _RANGE.finditer(text):
        first = int(match.group(1))
        last = int(match.group(2) or first)
        low, high = sorted((first, last))
        weeks.update(week for week in range(low, high + 1) if 1 <= week <= limit)
    odd = bool(re.search(r"单|\bodd\b", text, re.IGNORECASE))
    even = bool(re.search(r"双|\beven\b", text, re.IGNORECASE))
    if odd != even:
        parity = 1 if odd else 0
        filtered = {week for week in weeks if week % 2 == parity}
        weeks = filtered or weeks
    return sorted(weeks)


def describe_weeks(weeks: list[int]) -> str:
    """Compact form of a week list, e.g. ``[1, 2, 3, 5]`` -> ``"1-3, 5"``."""
    if not weeks:
        return "every week"
    ordered = sorted(set(weeks))
    parts: list[str] = []
    start = previous = ordered[0]
    for week in ordered[1:] + [None]:  # type: ignore[list-item]
        if week is not None and week == previous + 1:
            previous = week
            continue
        parts.append(str(start) if start == previous else f"{start}-{previous}")
        if week is not None:
            start = previous = week
    return ", ".join(parts)
