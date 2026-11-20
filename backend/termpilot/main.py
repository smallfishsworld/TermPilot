"""Application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from termpilot import __version__, knowledge
from termpilot.api.router import api_router
from termpilot.db.session import configure_database, create_schema
from termpilot.errors import install_error_handlers
from termpilot.logging_setup import configure_logging
from termpilot.settings import Settings, get_settings

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        configure_database(settings.database_url)
        create_schema()
        knowledge.configure(settings)
        settings.signing_key()  # fail fast (or create the local key) before the first request
        logger.info(
            "TermPilot %s ready (demo mode: %s, assistant: %s, library: %s)",
            __version__,
            settings.demo_mode,
            settings.llm_enabled,
            settings.embeddings_enabled,
        )
        yield

    app = FastAPI(
        title="TermPilot API",
        version=__version__,
        summary="Timetable, deadlines, grades, mail and an assistant for one student's semester.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    install_error_handlers(app)
    app.include_router(api_router)
    # Routes read settings through this dependency; keep them identical to the factory's.
    app.dependency_overrides[get_settings] = lambda: settings
    return app


app = create_app()
