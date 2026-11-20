from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from termpilot.campus.academic_records import (
    parse_gpa,
    parse_profile,
    parse_timetable,
    parse_timetable_cell,
    summarise_credits,
)
from termpilot.campus.learning_platform import (
    course_ref_from_url,
    in_term,
    normalise_score,
    parse_calendar,
    parse_course_module,
    parse_grade_page,
)
from termpilot.campus.records import LmsCourse
from termpilot.campus.terms import resolve_term


def test_timetable_cell_with_instructor_weeks_and_periods():
    cell = "Operating Systems\n[Dr. Ada Park]\n[1-15单周][Teaching Building 3, Room 101][5-6节]"
    meeting = parse_timetable_cell(cell, "xq2_jc5")
    assert meeting is not None
    assert (meeting.title, meeting.weekday, meeting.instructor) == ("Operating Systems", 2, "Dr. Ada Park")
    assert (meeting.starts_at, meeting.ends_at) == (time(14, 0), time(15, 50))
    assert meeting.weeks == [1, 3, 5, 7, 9, 11, 13, 15]
    assert meeting.location == "Teaching Building 3, Room 101"


def test_two_line_cell_does_not_mistake_weeks_for_instructor():
    meeting = parse_timetable_cell("Seminar\n[1-4周][Room 9][9-10节]", "xq5")
    assert meeting is not None and meeting.instructor is None and meeting.weekday == 5


def test_unplaceable_cells_are_counted():
    meetings, skipped = parse_timetable(
        {"content": [{"kbxx": "Lecture\n[1-16周][Hall][3-4节]", "key": "xq1"}, {"kbxx": "TBA\n[1-16周]", "key": "xq3"}]}
    )
    assert len(meetings) == 1 and skipped == 1


def test_profile_codes_become_names():
    profile = parse_profile(
        {
            "xm": "Test Student",
            "xbm": "2",
            "csrq": "2005-03-04 00:00:00",
            "sssym": "150010",
            "dzyx": "t@example.edu",
            "id": "77",
        }
    )
    assert profile.gender == "female"
    assert profile.birth_date.isoformat() == "2005-03-04"
    assert profile.college == "Zhiren College"
    assert profile.internal_id == "77"


def test_gpa_and_credit_summary():
    assert parse_gpa({"xfjandpm": {"PJXFJ": "3.81", "PM": 12}}).gpa == 3.81
    assert parse_gpa({}).gpa is None
    summary = summarise_credits([{"xf": "3", "kclb": "Core"}, {"xf": 2.5, "kclb": "Core"}, {"xf": "x"}, {"xf": 1}])
    assert summary.total == 6.5 and summary.by_category == {"Core": 5.5, "Other": 1.0}


def test_course_module_parsing_and_term_filter():
    body = (
        '<contents><![CDATA[<ul><li><a href="/webapps/blackboard/execute/launcher?type=Course&id=_123_1">'
        'Algorithms (Fall 2026)</a></li><li><a href="/x?course_id=_77_1">Old course (Spring 2025)</a></li>'
        "</ul>]]></contents>"
    )
    courses = parse_course_module(body, "https://lms.example.edu/")
    assert [course.ref for course in courses] == ["_123_1", "_77_1"]
    term = resolve_term(date(2026, 10, 14))
    assert [course.ref for course in courses if in_term(course, term.lms_labels)] == ["_123_1"]
    assert course_ref_from_url("https://lms/ultra/courses/_9_1/outline") == "_9_1"


def test_calendar_events_are_converted_to_utc():
    events = parse_calendar(
        [
            {
                "id": "e1",
                "title": "Lab 3",
                "end": "2026-10-20T23:59:00",
                "calendarName": "Networks",
                "eventType": "Assignment",
            },
            {"title": ""},
        ],
        ZoneInfo("Asia/Shanghai"),
    )
    assert len(events) == 1
    assert events[0].due_at == datetime(2026, 10, 20, 15, 59, tzinfo=UTC)
    assert events[0].ref == "e1" and events[0].course == "Networks"


def test_scores_and_grade_tables():
    assert normalise_score("45 / 50") == "45/50"
    assert normalise_score("b+") == "B+"
    assert normalise_score("Oct 3, 2026") is None
    assert normalise_score("—") is None
    html = (
        "<table><tr><td>Homework 1 Graded</td><td>Oct 1, 2026</td><td>9/10</td></tr>"
        "<tr><td>Quiz</td><td>A-</td></tr><tr><td>Upcoming project</td><td>-</td></tr></table>"
    )
    items = parse_grade_page(html, LmsCourse(ref="_1_1", title="Algorithms", url=""))
    assert [(item.item, item.score) for item in items] == [("Homework 1", "9/10"), ("Quiz", "A-")]
