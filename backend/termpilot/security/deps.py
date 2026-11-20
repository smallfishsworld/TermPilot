"""FastAPI dependencies that resolve the signed-in student."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from termpilot.db.models import Student
from termpilot.db.session import get_db
from termpilot.errors import NotAuthenticated
from termpilot.security.tokens import Scope, read_token
from termpilot.settings import Settings, get_settings

_bearer = HTTPBearer(auto_error=False, description="Token returned by POST /api/auth/session")

DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def resolve_student(db: Session, settings: Settings, token: str, scope: Scope) -> Student:
    claims = read_token(settings, token, scope)
    student = db.get(Student, claims.student_id)
    if student is None or student.session_epoch != claims.epoch:
        raise NotAuthenticated("You have been signed out. Please sign in again.")
    return student


def current_student(
    db: DbSession,
    settings: AppSettings,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Student:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise NotAuthenticated("Sign in to continue.")
    return resolve_student(db, settings, credentials.credentials, "api")


CurrentStudent = Annotated[Student, Depends(current_student)]
