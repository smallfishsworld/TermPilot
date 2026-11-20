"""Timetable, tasks, the study planner, the Today briefing and calendar export."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query, Request, Response, status

from termpilot.api import schemas
from termpilot.api.deps import AppSettings, CurrentStudent, DbSession
from termpilot.api.views import briefing_view, clash_view, term_view
from termpilot.clock import local_today, utcnow
from termpilot.db.models import Task, TimetableEntry
from termpilot.security.deps import resolve_student
from termpilot.security.tokens import FEED_TTL, issue_token
from termpilot.services import briefing, calendar_feed, study_planner, tasks, timetable
from termpilot.services.term_calendar import current_term

router = APIRouter(tags=["planning"])


# --- timetable ---------------------------------------------------------------------
@router.get("/timetable", response_model=schemas.TimetableView)
def get_timetable(student: CurrentStudent, db: DbSession, settings: AppSettings) -> schemas.TimetableView:
    today = local_today(settings.tz)
    term = current_term(settings, student, today)
    entries = timetable.list_entries(db, student)
    return schemas.TimetableView(
        term=term_view(term, today),
        entries=[schemas.EntryView.model_validate(entry) for entry in entries],
        clashes=[clash_view(clash, entries) for clash in timetable.find_clashes(entries, term.weeks)],
    )


@router.post("/timetable", response_model=schemas.EntryView, status_code=status.HTTP_201_CREATED)
def add_entry(body: schemas.EntryInput, student: CurrentStudent, db: DbSession) -> TimetableEntry:
    return timetable.create_entry(db, student, body.model_dump())


@router.patch("/timetable/{entry_id}", response_model=schemas.EntryView)
def edit_entry(entry_id: int, body: schemas.EntryPatch, student: CurrentStudent, db: DbSession) -> TimetableEntry:
    return timetable.update_entry(db, student, entry_id, body.model_dump(exclude_unset=True))


@router.delete("/timetable/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_entry(entry_id: int, student: CurrentStudent, db: DbSession) -> Response:
    timetable.delete_entry(db, student, entry_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- tasks --------------------------------------------------------------------------------
@router.get("/tasks", response_model=list[schemas.TaskView])
def get_tasks(
    student: CurrentStudent, db: DbSession, status_filter: Literal["open", "done", "all"] = Query("all", alias="status")
) -> list[Task]:
    return tasks.list_tasks(db, student, status=status_filter)


@router.post("/tasks", response_model=schemas.TaskView, status_code=status.HTTP_201_CREATED)
def add_task(body: schemas.TaskInput, student: CurrentStudent, db: DbSession) -> Task:
    return tasks.create_task(db, student, body.model_dump())


@router.patch("/tasks/{task_id}", response_model=schemas.TaskView)
def edit_task(task_id: int, body: schemas.TaskPatch, student: CurrentStudent, db: DbSession) -> Task:
    return tasks.update_task(db, student, task_id, body.model_dump(exclude_unset=True))


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_task(task_id: int, student: CurrentStudent, db: DbSession) -> Response:
    tasks.delete_task(db, student, task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- study planner ----------------------------------------------------------------------------
@router.post("/planner/suggestions", response_model=list[schemas.StudyBlockView])
def suggest_blocks(
    body: schemas.PlannerRequest, student: CurrentStudent, db: DbSession, settings: AppSettings
) -> list[schemas.StudyBlockView]:
    options = study_planner.PlannerOptions(
        days=body.days, block_minutes=body.block_minutes, day_start=body.day_start, day_end=body.day_end
    )
    return [
        schemas.StudyBlockView(
            task_id=block.task_id,
            task_title=block.task_title,
            day=block.day,
            week=block.week,
            starts_at=block.starts_at,
            ends_at=block.ends_at,
        )
        for block in study_planner.suggest(db, settings, student, options)
    ]


@router.post("/planner/accept", response_model=list[schemas.EntryView], status_code=status.HTTP_201_CREATED)
def accept_blocks(
    body: schemas.AcceptBlocksRequest, student: CurrentStudent, db: DbSession, settings: AppSettings
) -> list[TimetableEntry]:
    picks = [(block.task_id, block.day, block.starts_at, block.ends_at) for block in body.blocks]
    return study_planner.accept(db, settings, student, picks)


# --- today -------------------------------------------------------------------------------------
@router.get("/briefing", response_model=schemas.BriefingView)
def get_briefing(student: CurrentStudent, db: DbSession, settings: AppSettings) -> schemas.BriefingView:
    return briefing_view(briefing.build(db, settings, student))


# --- calendar export -----------------------------------------------------------------------------
@router.get("/calendar/link", response_model=schemas.FeedLinkView)
def calendar_link(request: Request, student: CurrentStudent, settings: AppSettings) -> schemas.FeedLinkView:
    """A private subscription URL for calendar apps; signing out revokes it."""
    token = issue_token(settings, student.id, student.session_epoch, scope="feed")
    url = str(request.url_for("calendar_feed").include_query_params(token=token))
    return schemas.FeedLinkView(url=url, expires_in_days=FEED_TTL.days)


@router.get("/calendar/feed.ics", name="calendar_feed", response_class=Response)
def calendar_export(token: str, db: DbSession, settings: AppSettings) -> Response:
    student = resolve_student(db, settings, token, "feed")
    term = current_term(settings, student)
    body = calendar_feed.build_calendar(
        entries=timetable.list_entries(db, student),
        tasks=tasks.list_tasks(db, student, status="open"),
        term=term,
        tz=settings.tz,
        generated=utcnow(),
        name=f"TermPilot · {term.label}",
    )
    return Response(
        content=body,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'inline; filename="termpilot.ics"', "Cache-Control": "no-store"},
    )
