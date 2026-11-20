"""Domain errors and their translation into HTTP responses.

Services raise these exceptions instead of ``HTTPException`` so they stay
independent from the web framework. Every error reaches the client in the
same envelope: ``{"error": {"code": ..., "message": ...}}``.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, code: str | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        self.details = details


class InvalidInput(AppError):
    status_code = 422
    code = "invalid_input"


class NotAuthenticated(AppError):
    status_code = 401
    code = "not_authenticated"


class PermissionDenied(AppError):
    status_code = 403
    code = "permission_denied"


class NotFound(AppError):
    status_code = 404
    code = "not_found"


class Conflict(AppError):
    status_code = 409
    code = "conflict"


class CampusSessionExpired(AppError):
    """The stored campus cookies no longer work; the student must sign in again."""

    status_code = 401
    code = "campus_session_expired"


class UpstreamFailure(AppError):
    """A campus system, mail server or model provider failed."""

    status_code = 502
    code = "upstream_failure"


class FeatureUnavailable(AppError):
    """An optional integration is not configured or its backing service is down."""

    status_code = 503
    code = "feature_unavailable"


def _envelope(code: str, message: str, details: Any = None) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        body["details"] = details
    return {"error": body}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            logger.warning("%s: %s", exc.code, exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, exc.details),
            headers={"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        problems = [
            {"field": ".".join(str(part) for part in err["loc"][1:]), "message": err["msg"]} for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=_envelope("invalid_input", "The request is not valid.", problems),
        )

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=_envelope("internal_error", "Something went wrong on the server."),
        )
