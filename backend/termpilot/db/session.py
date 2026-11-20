"""Engine and session lifecycle."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from termpilot.db.base import Base

_engine: Engine | None = None
_factory: sessionmaker[Session] | None = None


def _enable_sqlite_foreign_keys(dbapi_connection: Any, _: Any) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def configure_database(url: str) -> Engine:
    """(Re)create the engine. Called once at start-up and by the test suite."""
    global _engine, _factory
    options: dict[str, Any] = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
        if ":memory:" in url or url.endswith("sqlite://"):
            options["poolclass"] = StaticPool
        else:
            path = url.split("///", 1)[-1]
            from pathlib import Path

            Path(path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, **options)
    if url.startswith("sqlite"):
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    if _engine is not None:
        _engine.dispose()
    _engine = engine
    _factory = sessionmaker(bind=engine, expire_on_commit=False)
    return engine


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("The database is not configured yet.")
    return _engine


def create_schema() -> None:
    from termpilot.db import models  # noqa: F401  (register mappers)

    Base.metadata.create_all(get_engine())


def new_session() -> Session:
    if _factory is None:
        raise RuntimeError("The database is not configured yet.")
    return _factory()


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, rolled back on failure."""
    session = new_session()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Session for work outside a request, such as a streaming response."""
    session = new_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
