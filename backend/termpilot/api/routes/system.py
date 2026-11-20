"""Service health."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from termpilot import __version__
from termpilot.api import schemas
from termpilot.api.deps import AppSettings, DbSession

router = APIRouter(tags=["system"])


@router.get("/health", response_model=schemas.HealthView)
def health(db: DbSession, settings: AppSettings) -> schemas.HealthView:
    try:
        db.execute(text("SELECT 1"))
        database = True
    except Exception:
        database = False
    search: bool | None = None
    if settings.embeddings_enabled:
        from termpilot.knowledge.index import LibraryIndex

        search = LibraryIndex(0).ready()
    return schemas.HealthView(
        status="ok" if database else "degraded",
        version=__version__,
        database=database,
        search=search,
        assistant=settings.llm_enabled,
    )
