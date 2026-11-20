"""The single interface between TermPilot and campus systems."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from termpilot.campus.academic_records import AcademicRecordsClient
from termpilot.campus.learning_platform import LearningPlatformClient, in_term
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
from termpilot.campus.sso import CampusSignIn
from termpilot.campus.terms import Term
from termpilot.errors import CampusSessionExpired
from termpilot.settings import Settings


class CampusGateway(Protocol):
    def sign_in(self, username: str, password: str) -> CampusCookies: ...

    def profile(self, cookies: CampusCookies) -> ProfileRecord: ...

    def timetable(self, cookies: CampusCookies, term: Term) -> tuple[list[ClassMeeting], int]: ...

    def gpa(self, cookies: CampusCookies) -> GpaRecord: ...

    def credits(self, cookies: CampusCookies) -> CreditRecord: ...

    def photo(self, cookies: CampusCookies, profile: ProfileRecord) -> Photo | None: ...

    def courses(self, cookies: CampusCookies, term: Term) -> list[LmsCourse]: ...

    def calendar(self, cookies: CampusCookies, around: datetime) -> list[LmsEvent]: ...

    def grades(self, cookies: CampusCookies, courses: list[LmsCourse]) -> list[LmsGradeItem]: ...

    def materials(self, cookies: CampusCookies, courses: list[LmsCourse]) -> list[LmsMaterial]: ...


class LiveCampusGateway:
    """Talks to the real campus services over HTTPS."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _records(self, cookies: CampusCookies) -> AcademicRecordsClient:
        jar = cookies.for_service("records")
        if not jar:
            raise CampusSessionExpired("No academic records session is stored. Sign in again.")
        return AcademicRecordsClient(self.settings, jar)

    def _lms(self, cookies: CampusCookies) -> LearningPlatformClient:
        jar = cookies.for_service("lms")
        if not jar:
            raise CampusSessionExpired("No learning platform session is stored. Sign in again.")
        return LearningPlatformClient(self.settings, jar)

    def sign_in(self, username: str, password: str) -> CampusCookies:
        return CampusSignIn(self.settings).sign_in(username, password)

    def profile(self, cookies: CampusCookies) -> ProfileRecord:
        return self._records(cookies).profile()

    def timetable(self, cookies: CampusCookies, term: Term) -> tuple[list[ClassMeeting], int]:
        return self._records(cookies).timetable(term)

    def gpa(self, cookies: CampusCookies) -> GpaRecord:
        return self._records(cookies).gpa()

    def credits(self, cookies: CampusCookies) -> CreditRecord:
        return self._records(cookies).credits()

    def photo(self, cookies: CampusCookies, profile: ProfileRecord) -> Photo | None:
        if not profile.internal_id:
            return None
        return self._records(cookies).photo(profile.internal_id)

    def courses(self, cookies: CampusCookies, term: Term) -> list[LmsCourse]:
        return [course for course in self._lms(cookies).courses() if in_term(course, term.lms_labels)]

    def calendar(self, cookies: CampusCookies, around: datetime) -> list[LmsEvent]:
        return self._lms(cookies).calendar(around)

    def grades(self, cookies: CampusCookies, courses: list[LmsCourse]) -> list[LmsGradeItem]:
        return self._lms(cookies).grades(courses)

    def materials(self, cookies: CampusCookies, courses: list[LmsCourse]) -> list[LmsMaterial]:
        return self._lms(cookies).materials(courses)


def build_gateway(settings: Settings) -> CampusGateway:
    if settings.demo_mode:
        from termpilot.campus.demo import DemoCampusGateway

        return DemoCampusGateway(settings)
    return LiveCampusGateway(settings)
