from datetime import date, time

import pytest

from termpilot.campus.periods import describe_weeks, parse_period_range, parse_weeks, period_times
from termpilot.campus.terms import default_start, resolve_term, season_of


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (date(2026, 9, 10), ("autumn", 2026)),
        (date(2027, 1, 15), ("autumn", 2026)),
        (date(2027, 3, 1), ("spring", 2027)),
        (date(2027, 7, 20), ("summer", 2027)),
    ],
)
def test_season_of(day, expected):
    assert season_of(day) == expected


def test_default_starts_are_mondays():
    assert default_start("spring", 2026) == date(2026, 2, 23)
    assert default_start("autumn", 2026) == date(2026, 9, 7)
    assert all(default_start(s, 2027).weekday() == 0 for s in ("autumn", "spring", "summer"))


def test_term_labels_and_weeks():
    term = resolve_term(date(2026, 10, 14))
    assert term.label == "Fall 2026"
    assert term.academic_year == "2026-2027"
    assert term.records_code == "1"
    assert "2026秋" in term.lms_labels
    assert term.week_of(date(2026, 10, 14)) == 6
    assert term.date_of(6, 3) == date(2026, 10, 14)
    assert term.contains(date(2026, 12, 27)) and not term.contains(date(2026, 12, 28))


def test_personal_start_wins_but_stale_overrides_are_ignored():
    personal = resolve_term(date(2026, 10, 14), personal_start=date(2026, 9, 16))
    assert personal.start == date(2026, 9, 14)  # snapped to that week's Monday
    stale = resolve_term(date(2026, 10, 14), personal_start=date(2026, 2, 23), deployment_start=date(2026, 9, 1))
    assert stale.start == date(2026, 8, 31)


@pytest.mark.parametrize(
    ("text", "weeks"),
    [
        ("1-16周", list(range(1, 17))),
        ("1-8,10-12周", [1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12]),
        ("1-15单周", [1, 3, 5, 7, 9, 11, 13, 15]),
        ("2-16双周", [2, 4, 6, 8, 10, 12, 14, 16]),
        ("odd weeks 1-5", [1, 3, 5]),
        ("3周", [3]),
        ("", []),
        (None, []),
    ],
)
def test_parse_weeks(text, weeks):
    assert parse_weeks(text) == weeks


def test_period_ranges_and_times():
    assert parse_period_range("3-4节") == (3, 4)
    assert parse_period_range("第5节") == (5, 5)
    assert parse_period_range("periods 11-12") == (11, 11)  # clamped to the last period
    assert parse_period_range("no period") is None
    assert period_times(3, 4) == (time(10, 20), time(12, 10))


def test_describe_weeks():
    assert describe_weeks([1, 2, 3, 5, 7, 8]) == "1-3, 5, 7-8"
    assert describe_weeks([]) == "every week"
