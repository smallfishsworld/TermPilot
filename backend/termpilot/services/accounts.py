"""Signing in and out, and access to the stored campus session."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from termpilot.campus.demo import DEMO_STUDENT_ID, DEMO_USERNAME
from termpilot.campus.gateway import CampusGateway
from termpilot.campus.records import CampusCookies, ProfileRecord
from termpilot.clock import utcnow
from termpilot.db.models import CampusLink, Student
from termpilot.errors import AppError, CampusSessionExpired, InvalidInput
from termpilot.security.sealing import SealError, seal_json, unseal_json
from termpilot.security.tokens import issue_token
from termpilot.settings import Settings

logger = logging.getLogger(__name__)


@dataclass
class SignInResult:
    token: str
    student: Student
    first_visit: bool


def student_number(settings: Settings, username: str) -> int:
    name = username.strip()
    if settings.demo_mode and name.lower() == DEMO_USERNAME:
        return DEMO_STUDENT_ID
    if not name.isdigit() or len(name) > 12:
        raise InvalidInput("Sign in with your numeric student number.")
    return int(name)


def apply_profile(student: Student, profile: ProfileRecord) -> list[str]:
    """Copy known profile fields onto the student and report which changed."""
    changed = []
    mapping = {
        "display_name": profile.name,
        "pinyin_name": profile.pinyin_name,
        "gender": profile.gender,
        "birth_date": profile.birth_date,
        "email": profile.email,
        "phone": profile.phone,
        "college": profile.college,
        "department": profile.department,
        "class_name": profile.class_name,
        "dormitory": profile.dormitory,
    }
    for field, value in mapping.items():
        if value is not None and getattr(student, field) != value:
            setattr(student, field, value)
            changed.append(field)
    return changed


def sign_in(db: Session, settings: Settings, gateway: CampusGateway, username: str, password: str) -> SignInResult:
    if not username.strip() or not password:
        raise InvalidInput("Enter both your student number and password.")
    number = student_number(settings, username)
    # Credentials are checked by the campus before anything is stored or issued.
    cookies = gateway.sign_in(username.strip(), password)

    student = db.get(Student, number)
    first_visit = student is None
    if student is None:
        student = Student(id=number, display_name=username.strip(), is_demo=settings.demo_mode)
        db.add(student)
        try:
            apply_profile(student, gateway.profile(cookies))
        except AppError as exc:
            logger.info("Profile not imported at first sign-in: %s", exc.message)
    store_cookies(db, settings, student.id, cookies)
    db.commit()
    token = issue_token(settings, student.id, student.session_epoch)
    return SignInResult(token=token, student=student, first_visit=first_visit)


def sign_out(db: Session, student: Student) -> None:
    """Revoke all tokens of the student and forget the campus session."""
    student.session_epoch += 1
    link = db.get(CampusLink, student.id)
    if link is not None:
        db.delete(link)
    db.commit()


def store_cookies(db: Session, settings: Settings, student_id: int, cookies: CampusCookies) -> None:
    link = db.get(CampusLink, student_id)
    now = utcnow()
    if link is None:
        link = CampusLink(student_id=student_id, sealed_cookies="", linked_at=now)
        db.add(link)
    link.sealed_cookies = seal_json(settings, cookies.services)
    link.services = sorted(name for name, jar in cookies.services.items() if jar)
    link.linked_at = now
    link.checked_at = now


def load_cookies(db: Session, settings: Settings, student_id: int) -> CampusCookies:
    link = db.get(CampusLink, student_id)
    if link is None:
        raise CampusSessionExpired("No campus session is stored. Sign in again to sync.")
    try:
        services = unseal_json(settings, link.sealed_cookies)
    except SealError as exc:
        raise CampusSessionExpired("The stored campus session is unreadable. Sign in again.") from exc
    return CampusCookies(services={name: dict(jar) for name, jar in services.items()})
