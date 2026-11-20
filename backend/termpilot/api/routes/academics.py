"""Grades, credits, course materials and campus synchronisation."""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, status
from sqlalchemy import select

from termpilot.api import schemas
from termpilot.api.deps import AppSettings, CurrentStudent, DbSession, Gateway
from termpilot.api.views import sync_view
from termpilot.db.models import CourseGrade, CourseMaterial, CreditSummary
from termpilot.services import campus_sync

router = APIRouter(tags=["academics"])


@router.get("/academics", response_model=schemas.AcademicsView)
def academics(student: CurrentStudent, db: DbSession) -> schemas.AcademicsView:
    credits = db.get(CreditSummary, student.id)
    grouped: dict[str, list[schemas.GradeItemView]] = defaultdict(list)
    for row in db.scalars(
        select(CourseGrade)
        .where(CourseGrade.student_id == student.id)
        .order_by(CourseGrade.course_title, CourseGrade.id)
    ):
        grouped[row.course_title].append(schemas.GradeItemView(item=row.item, score=row.score))
    return schemas.AcademicsView(
        gpa=student.gpa,
        rank=student.gpa_rank,
        credits_total=credits.total if credits else None,
        credits_by_category={key: float(value) for key, value in (credits.by_category if credits else {}).items()},
        credits_refreshed_at=credits.refreshed_at if credits else None,
        courses=[schemas.CourseGradesView(course=course, items=items) for course, items in grouped.items()],
    )


@router.get("/academics/materials", response_model=list[schemas.MaterialView])
def materials(student: CurrentStudent, db: DbSession) -> list[CourseMaterial]:
    return list(
        db.scalars(
            select(CourseMaterial)
            .where(CourseMaterial.student_id == student.id)
            .order_by(CourseMaterial.course_title, CourseMaterial.section, CourseMaterial.title)
        )
    )


@router.post("/sync", response_model=schemas.SyncRunView, status_code=status.HTTP_201_CREATED)
def sync(
    body: schemas.SyncRequest, student: CurrentStudent, db: DbSession, settings: AppSettings, gateway: Gateway
) -> schemas.SyncRunView:
    sources = tuple(body.sources) if body.sources else campus_sync.ALL_SOURCES
    run = campus_sync.run_sync(db, settings, gateway, student, sources=sources, trigger="manual")
    return sync_view(run)


@router.get("/sync/runs", response_model=list[schemas.SyncRunView])
def sync_runs(student: CurrentStudent, db: DbSession) -> list[schemas.SyncRunView]:
    return [sync_view(run) for run in campus_sync.recent_runs(db, student)]
