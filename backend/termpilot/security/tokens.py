"""Signed access tokens.

Two scopes exist: ``api`` tokens authenticate the web client and expire after
``TP_TOKEN_TTL_MINUTES``; ``feed`` tokens are embedded in calendar
subscription URLs, which calendar apps fetch without custom headers. Both carry
the student's session epoch, so signing out revokes every token at once.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Literal

import jwt

from termpilot.clock import utcnow
from termpilot.errors import NotAuthenticated
from termpilot.settings import Settings

ALGORITHM = "HS256"
FEED_TTL = timedelta(days=180)

Scope = Literal["api", "feed"]


@dataclass(frozen=True)
class TokenClaims:
    student_id: int
    epoch: int
    scope: Scope


def issue_token(settings: Settings, student_id: int, epoch: int, scope: Scope = "api") -> str:
    issued = utcnow()
    lifetime = timedelta(minutes=settings.token_ttl_minutes) if scope == "api" else FEED_TTL
    claims = {
        "sub": str(student_id),
        "ep": epoch,
        "scope": scope,
        "iat": int(issued.timestamp()),
        "exp": int((issued + lifetime).timestamp()),
    }
    return jwt.encode(claims, settings.signing_key(), algorithm=ALGORITHM)


def read_token(settings: Settings, token: str, scope: Scope = "api") -> TokenClaims:
    try:
        # Expiry is checked against termpilot.clock below so that tests can control time.
        claims = jwt.decode(
            token,
            settings.signing_key(),
            algorithms=[ALGORITHM],
            options={"require": ["exp", "sub"], "verify_exp": False, "verify_iat": False},
        )
    except jwt.InvalidTokenError as exc:
        raise NotAuthenticated("The access token is not valid.") from exc
    if not isinstance(claims.get("exp"), int) or claims["exp"] <= utcnow().timestamp():
        raise NotAuthenticated("Your session has expired. Please sign in again.")
    if claims.get("scope") != scope:
        raise NotAuthenticated("The access token cannot be used here.")
    try:
        return TokenClaims(student_id=int(claims["sub"]), epoch=int(claims["ep"]), scope=scope)
    except (KeyError, TypeError, ValueError) as exc:
        raise NotAuthenticated("The access token is not valid.") from exc
