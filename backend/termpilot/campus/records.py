"""Plain data returned by campus adapters, independent of any HTTP details."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time


@dataclass
class CampusCookies:
    """Cookies per campus service, e.g. ``{"lms": {...}, "records": {...}}``."""

    services: dict[str, dict[str, str]] = field(default_factory=dict)

    def for_service(self, name: str) -> dict[str, str]:
        return self.services.get(name, {})


@dataclass
class ProfileRecord:
    name: str | None = None
    english_name: str | None = None
    pinyin_name: str | None = None
    gender: str | None = None
    birth_date: date | None = None
    email: str | None = None
    phone: str | None = None
    college: str | None = None
    department: str | None = None
    class_name: str | None = None
    dormitory: str | None = None
    internal_id: str | None = None


@dataclass
class ClassMeeting:
    title: str
    weekday: int
    starts_at: time
    ends_at: time
    first_period: int | None = None
    last_period: int | None = None
    weeks: list[int] = field(default_factory=list)
    week_label: str | None = None
    location: str | None = None
    instructor: str | None = None


@dataclass
class GpaRecord:
    gpa: float | None
    rank: str | None


@dataclass
class CreditRecord:
    total: float
    by_category: dict[str, float]


@dataclass
class Photo:
    content: bytes
    media_type: str


@dataclass
class LmsCourse:
    ref: str
    title: str
    url: str


@dataclass
class LmsEvent:
    ref: str
    title: str
    due_at: datetime
    course: str | None = None
    category: str | None = None
    color: str | None = None


@dataclass
class LmsGradeItem:
    course_ref: str
    course_title: str
    item: str
    score: str


@dataclass
class LmsMaterial:
    course_title: str
    section: str | None
    title: str
    url: str
