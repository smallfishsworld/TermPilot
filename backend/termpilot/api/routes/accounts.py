"""Sign-in, sign-out and the student's own profile."""

from __future__ import annotations

import base64

from fastapi import APIRouter, Response, status

from termpilot.api import schemas
from termpilot.api.deps import AppSettings, CurrentStudent, DbSession, Gateway
from termpilot.api.views import term_view
from termpilot.clock import local_today
from termpilot.db.models import Student
from termpilot.services import accounts
from termpilot.services.term_calendar import current_term

router = APIRouter(tags=["accounts"])


@router.get("/config", response_model=schemas.FeaturesView)
def features(settings: AppSettings) -> schemas.FeaturesView:
    """Public: which optional features this deployment has enabled."""
    return schemas.FeaturesView(
        demo_mode=settings.demo_mode,
        assistant=settings.llm_enabled,
        library=settings.embeddings_enabled,
        web_search=settings.web_search_enabled,
    )


@router.post("/auth/session", response_model=schemas.SessionView, status_code=status.HTTP_201_CREATED)
def sign_in(body: schemas.SignInRequest, db: DbSession, settings: AppSettings, gateway: Gateway) -> schemas.SessionView:
    result = accounts.sign_in(db, settings, gateway, body.username, body.password)
    return schemas.SessionView(
        token=result.token,
        expires_in=settings.token_ttl_minutes * 60,
        first_visit=result.first_visit,
        student=schemas.StudentView.model_validate(result.student),
    )


@router.delete("/auth/session", status_code=status.HTTP_204_NO_CONTENT)
def sign_out(student: CurrentStudent, db: DbSession) -> Response:
    accounts.sign_out(db, student)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=schemas.StudentView)
def me(student: CurrentStudent) -> Student:
    return student


@router.patch("/me", response_model=schemas.StudentView)
def update_me(body: schemas.PreferencesUpdate, student: CurrentStudent, db: DbSession) -> Student:
    if body.interests is not None:
        student.interests = body.interests.strip() or None
    if body.clear_term_start:
        student.term_start = None
    elif body.term_start is not None:
        student.term_start = body.term_start
    db.commit()
    return student


@router.get("/me/term", response_model=schemas.TermView)
def my_term(student: CurrentStudent, settings: AppSettings) -> schemas.TermView:
    today = local_today(settings.tz)
    return term_view(current_term(settings, student, today), today)


@router.get("/me/photo", response_model=schemas.PhotoView)
def my_photo(student: CurrentStudent) -> schemas.PhotoView:
    if not student.photo:
        return schemas.PhotoView(data_url=None)
    encoded = base64.b64encode(student.photo).decode("ascii")
    return schemas.PhotoView(data_url=f"data:{student.photo_type or 'image/jpeg'};base64,{encoded}")
