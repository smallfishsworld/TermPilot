"""Academic terms and teaching weeks.

The calendar has three terms: autumn (August to January), spring (February to
June) and summer (July). Their exact first teaching day changes every year, so
the start can be overridden per student or for the whole deployment; without an
override a heuristic picks the usual Monday.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

Season = Literal["autumn", "spring", "summer"]

_SEASON_CODE: dict[Season, str] = {"autumn": "1", "spring": "2", "summer": "3"}
_SEASON_EN: dict[Season, str] = {"autumn": "Fall", "spring": "Spring", "summer": "Summer"}
_SEASON_ZH: dict[Season, str] = {"autumn": "秋", "spring": "春", "summer": "夏"}


@dataclass(frozen=True)
class Term:
    season: Season
    calendar_year: int  # the year in which the term starts
    start: date  # Monday of teaching week 1
    weeks: int

    @property
    def academic_year(self) -> str:
        """Records-system label such as ``2026-2027``."""
        first = self.calendar_year if self.season == "autumn" else self.calendar_year - 1
        return f"{first}-{first + 1}"

    @property
    def records_code(self) -> str:
        return _SEASON_CODE[self.season]

    @property
    def label(self) -> str:
        return f"{_SEASON_EN[self.season]} {self.calendar_year}"

    @property
    def lms_labels(self) -> tuple[str, ...]:
        """Spellings the learning platform uses in course titles."""
        return (self.label, f"{self.calendar_year}{_SEASON_ZH[self.season]}")

    @property
    def end(self) -> date:
        return self.start + timedelta(weeks=self.weeks, days=-1)

    def week_of(self, day: date) -> int:
        """1-based teaching week of ``day``; values outside 1..weeks are possible."""
        return (day - self.start).days // 7 + 1

    def date_of(self, week: int, weekday: int) -> date:
        """Calendar date of ``weekday`` (1 = Monday) in teaching ``week``."""
        return self.start + timedelta(weeks=week - 1, days=weekday - 1)

    def contains(self, day: date) -> bool:
        return self.start <= day <= self.end


def season_of(day: date) -> tuple[Season, int]:
    """Season and starting calendar year of the term that ``day`` belongs to."""
    if day.month >= 8:
        return "autumn", day.year
    if day.month == 1:
        return "autumn", day.year - 1
    if day.month <= 6:
        return "spring", day.year
    return "summer", day.year


def _first_monday_on_or_after(day: date) -> date:
    return day + timedelta(days=(7 - day.weekday()) % 7)


def default_start(season: Season, year: int) -> date:
    anchor = {"autumn": date(year, 9, 1), "spring": date(year, 2, 17), "summer": date(year, 7, 1)}
    return _first_monday_on_or_after(anchor[season])


def _monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def resolve_term(
    today: date,
    *,
    weeks: int = 16,
    personal_start: date | None = None,
    deployment_start: date | None = None,
) -> Term:
    """Pick the term containing ``today`` and the best known first teaching Monday.

    A configured start is used only when it falls into the same season as
    ``today``; stale overrides from an earlier term are ignored.
    """
    season, year = season_of(today)
    term_weeks = 8 if season == "summer" else weeks
    for candidate in (personal_start, deployment_start):
        if candidate is not None and season_of(candidate) == (season, year):
            return Term(season, year, _monday_of(candidate), term_weeks)
    return Term(season, year, default_start(season, year), term_weeks)
