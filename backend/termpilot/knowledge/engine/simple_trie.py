"""Pure-Python stand-in for the parts of ``datrie`` the tokenizer uses.

``datrie`` is a C extension without wheels for every platform. This
replacement keeps a plain dictionary plus a lazily sorted key list, so prefix
checks are binary searches instead of a set of every prefix (which needs
gigabytes for the full dictionary). Its cache is a JSON file next to the
dictionary, written after the first build.
"""

from __future__ import annotations

import json
from bisect import bisect_left
from pathlib import Path


class Trie:
    def __init__(self, alphabet: str | None = None) -> None:
        self._values: dict[str, object] = {}
        self._sorted: list[str] | None = None

    @classmethod
    def load(cls, filename: str) -> Trie:
        cache = Path(f"{filename}.json")
        if not cache.exists():
            raise ValueError(f"No cache at {cache}")
        trie = cls()
        trie._values = json.loads(cache.read_text(encoding="utf-8"))
        return trie

    def save(self, filename: str) -> None:
        Path(f"{filename}.json").write_text(
            json.dumps(self._values, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )

    def __contains__(self, key: str) -> bool:
        return key in self._values

    def __getitem__(self, key: str) -> object:
        return self._values[key]

    def __setitem__(self, key: str, value: object) -> None:
        if key not in self._values:
            self._sorted = None
        self._values[key] = value

    def has_keys_with_prefix(self, prefix: str) -> bool:
        if self._sorted is None:
            self._sorted = sorted(self._values)
        index = bisect_left(self._sorted, prefix)
        return index < len(self._sorted) and self._sorted[index].startswith(prefix)
