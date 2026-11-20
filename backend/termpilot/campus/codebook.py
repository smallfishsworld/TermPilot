"""Lookup of the organisational codes that appear in academic records."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

_BOOK = Path(__file__).with_name("codebook.json")

Kind = Literal["departments", "colleges", "classes"]


@lru_cache(maxsize=1)
def _load() -> dict[str, dict[str, list[str]]]:
    data = json.loads(_BOOK.read_text(encoding="utf-8"))
    return {key: value for key, value in data.items() if not key.startswith("_")}


def lookup(kind: Kind, code: str | None, *, english: bool = True) -> str | None:
    """Readable name for ``code``; ``None`` when the code is unknown."""
    if not code:
        return None
    names = _load().get(kind, {}).get(code.strip())
    if not names:
        return None
    chinese, english_name = names
    return english_name if english else chinese
