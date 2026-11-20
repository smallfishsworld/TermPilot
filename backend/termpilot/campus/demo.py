"""Offline campus gateway with sample data for demonstrations and tests.

Enable it with ``TP_DEMO_MODE=true`` and sign in as ``demo`` / ``demo``. Due
dates are generated relative to the current time so the sample semester always
looks current.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

from termpilot.campus.periods import parse_weeks, period_times
from termpilot.campus.records import (
    CampusCookies,
    ClassMeeting,
    CreditRecord,
    GpaRecord,
    LmsCourse,
    LmsEvent,
    LmsGradeItem,
    LmsMaterial,
    Photo,
    ProfileRecord,
)
from termpilot.campus.sso import InvalidCampusCredentials
from termpilot.campus.terms import Term
from termpilot.settings import Settings

DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo"
DEMO_STUDENT_ID = 20_260_001

# title, weekday, first period, last period, weeks, location, instructor
_COURSES = [
    ("Data Structures and Algorithms", 1, 3, 4, "1-16周", "Teaching Building 1, Room 203", "Dr. Lin Wei"),
    ("Data Structures and Algorithms (Lab)", 3, 7, 8, "2-16双周", "Computer Lab 402", "Dr. Lin Wei"),
    ("Probability and Statistics", 2, 1, 2, "1-16周", "Lecture Hall 3", "Prof. Helen Zhou"),
    ("Database Systems", 2, 5, 6, "1-16周", "Teaching Building 2, Room 108", "Dr. Marco Rossi"),
    ("Linear Algebra", 4, 3, 4, "1-15单周", "Lecture Hall 1", "Prof. Chen Yu"),
    ("Computer Networks", 4, 5, 6, "1-16周", "Teaching Building 1, Room 305", "Dr. Aisha Khan"),
    ("Academic English Writing", 5, 1, 2, "1-12周", "Liberal Arts Building 210", "Ms. Sarah Lee"),
    ("Physical Education: Badminton", 5, 7, 8, "3-16周", "Sports Hall B", "Coach Wang"),
]

_COURSE_REFS = {
    "Data Structures and Algorithms": "_9101_1",
    "Probability and Statistics": "_9102_1",
    "Database Systems": "_9103_1",
    "Linear Algebra": "_9104_1",
    "Computer Networks": "_9105_1",
    "Academic English Writing": "_9106_1",
}

# title, course, category, days from now, hour (local)
_DEADLINES = [
    ("Problem Set 6: Graph Traversal", "Data Structures and Algorithms", "assignment", 1, 23),
    ("Query optimisation report", "Database Systems", "assignment", 3, 18),
    ("Quiz 3: Conditional Probability", "Probability and Statistics", "exam", 5, 10),
    ("Socket programming lab report", "Computer Networks", "assignment", 6, 23),
    ("Argumentative essay draft", "Academic English Writing", "assignment", 9, 12),
    ("Midterm exam", "Linear Algebra", "exam", 13, 14),
    ("Reading response 4", "Academic English Writing", "assignment", -2, 23),
]

_GRADES = [
    ("Data Structures and Algorithms", "Problem Set 4", "92/100"),
    ("Data Structures and Algorithms", "Problem Set 5", "88/100"),
    ("Probability and Statistics", "Quiz 2", "17/20"),
    ("Database Systems", "ER diagram design", "A-"),
    ("Computer Networks", "Lab 2: Packet capture", "48/50"),
    ("Academic English Writing", "Summary assignment", "B+"),
]

_MATERIALS = [
    ("Data Structures and Algorithms", "Lecture notes", "Week 8 - Shortest paths.pdf"),
    ("Data Structures and Algorithms", "Assignments", "Problem Set 6.pdf"),
    ("Probability and Statistics", "Slides", "Chapter 4 - Random variables.pptx"),
    ("Database Systems", "Lecture slides", "Normalisation worked examples.pptx"),
    ("Computer Networks", "Labs", "Socket programming handout.pdf"),
    ("Linear Algebra", "Lecture notes", "Eigenvalues and eigenvectors.pdf"),
]


def _placeholder_avatar() -> bytes:
    """Draw a neutral silhouette so the demo never shows a real person's picture."""
    import io

    from PIL import Image, ImageDraw

    image = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    pen = ImageDraw.Draw(image)
    pen.ellipse((0, 0, 95, 95), fill=(15, 118, 110, 255))
    pen.ellipse((30, 16, 66, 52), fill=(204, 251, 241, 255))
    pen.pieslice((14, 56, 82, 124), 180, 360, fill=(204, 251, 241, 255))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


class DemoCampusGateway:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def sign_in(self, username: str, password: str) -> CampusCookies:
        if username.strip().lower() != DEMO_USERNAME or password != DEMO_PASSWORD:
            raise InvalidCampusCredentials("Demo mode accepts only the account demo / demo.")
        return CampusCookies(services={"lms": {"demo": "1"}, "records": {"demo": "1"}})

    def profile(self, cookies: CampusCookies) -> ProfileRecord:
        return ProfileRecord(
            name="Alex Morgan",
            english_name="Alex Morgan",
            pinyin_name="Alex Morgan",
            gender=None,
            email="alex.morgan@example.edu",
            college="Harmony College",
            department="Department of Computer Science and Engineering",
            class_name="Computer Science 2024",
            dormitory="Residence 7, Room 512",
            internal_id="demo-profile",
        )

    def timetable(self, cookies: CampusCookies, term: Term) -> tuple[list[ClassMeeting], int]:
        meetings = []
        for title, weekday, first, last, weeks, location, instructor in _COURSES:
            starts_at, ends_at = period_times(first, last)
            meetings.append(
                ClassMeeting(
                    title=title,
                    weekday=weekday,
                    starts_at=starts_at,
                    ends_at=ends_at,
                    first_period=first,
                    last_period=last,
                    weeks=parse_weeks(weeks),
                    week_label=weeks,
                    location=location,
                    instructor=instructor,
                )
            )
        return meetings, 0

    def gpa(self, cookies: CampusCookies) -> GpaRecord:
        return GpaRecord(gpa=3.72, rank="18/164")

    def credits(self, cookies: CampusCookies) -> CreditRecord:
        by_category = {
            "General education": 32.0,
            "Major core": 41.5,
            "Major elective": 12.0,
            "Physical education": 4.0,
        }
        return CreditRecord(total=sum(by_category.values()), by_category=by_category)

    def photo(self, cookies: CampusCookies, profile: ProfileRecord) -> Photo | None:
        return Photo(content=_placeholder_avatar(), media_type="image/png")

    def courses(self, cookies: CampusCookies, term: Term) -> list[LmsCourse]:
        return [
            LmsCourse(ref=ref, title=f"{title} ({term.label})", url=f"https://lms.example.edu/course/{ref}")
            for title, ref in _COURSE_REFS.items()
        ]

    def calendar(self, cookies: CampusCookies, around: datetime) -> list[LmsEvent]:
        local_now = around.astimezone(self.settings.tz)
        events = []
        for index, (title, course, category, days, hour) in enumerate(_DEADLINES):
            local_due = datetime.combine(
                local_now.date() + timedelta(days=days), time(hour, 59 if hour == 23 else 0), self.settings.tz
            )
            events.append(
                LmsEvent(
                    ref=f"demo-event-{index}",
                    title=title,
                    due_at=local_due,
                    course=course,
                    category=category,
                    color=None,
                )
            )
        return events

    def grades(self, cookies: CampusCookies, courses: list[LmsCourse]) -> list[LmsGradeItem]:
        return [
            LmsGradeItem(course_ref=_COURSE_REFS[course], course_title=course, item=item, score=score)
            for course, item, score in _GRADES
        ]

    def materials(self, cookies: CampusCookies, courses: list[LmsCourse]) -> list[LmsMaterial]:
        return [
            LmsMaterial(
                course_title=course,
                section=section,
                title=title,
                url=f"https://lms.example.edu/files/{_COURSE_REFS[course]}/{index}",
            )
            for index, (course, section, title) in enumerate(_MATERIALS)
        ]
