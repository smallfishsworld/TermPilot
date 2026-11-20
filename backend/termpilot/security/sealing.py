"""Symmetric encryption for credentials kept on behalf of a student.

Campus cookies and mailbox authorization codes are sealed with a Fernet key
derived from ``TP_SECRET_KEY``. Rotating the secret makes stored values
unreadable, which simply forces students to reconnect.
"""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from termpilot.settings import Settings


class SealError(Exception):
    pass


def _fernet(settings: Settings) -> Fernet:
    digest = hashlib.sha256(f"termpilot-seal:{settings.signing_key()}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def seal(settings: Settings, value: str) -> str:
    return _fernet(settings).encrypt(value.encode("utf-8")).decode("ascii")


def unseal(settings: Settings, token: str) -> str:
    try:
        return _fernet(settings).decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise SealError("Stored credentials could not be decrypted.") from exc


def seal_json(settings: Settings, value: Any) -> str:
    return seal(settings, json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def unseal_json(settings: Settings, token: str) -> Any:
    return json.loads(unseal(settings, token))
