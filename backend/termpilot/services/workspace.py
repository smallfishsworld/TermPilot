"""A private file area per student, used for uploads and assistant file tasks.

Every path is resolved inside ``var/workspaces/<student id>``; absolute paths,
``..`` segments and symbolic links that point outside are rejected. Changes
the assistant proposes are described as payloads, stored with the pending
approval and re-validated against the file's current hash when applied, so a
file edited in the meantime is never overwritten blindly.
"""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from termpilot.clock import utcnow
from termpilot.errors import Conflict, InvalidInput, NotFound
from termpilot.settings import Settings

TRASH = ".trash"
TEXT_SUFFIXES = {
    ".txt",
    ".md",
    ".markdown",
    ".csv",
    ".json",
    ".yaml",
    ".yml",
    ".py",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".js",
    ".ts",
    ".vue",
    ".html",
    ".css",
    ".sql",
    ".tex",
    ".bib",
    ".ipynb",
    ".sh",
    ".toml",
    ".ini",
}
MAX_READ_BYTES = 200_000
MAX_WRITE_BYTES = 200_000
_FORBIDDEN_NAME_CHARS = set('<>:"\\|?*\x00')


@dataclass(frozen=True)
class FileInfo:
    path: str
    is_dir: bool
    size: int
    modified: datetime


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path: Path) -> str:
    # Bytes in, bytes out: line endings are kept exactly as the student wrote them.
    return path.read_bytes().decode("utf-8", errors="replace")


def _write(path: Path, text: str) -> None:
    path.write_bytes(text.encode("utf-8"))


def _rename_pair(item: Any) -> tuple[Any, Any]:
    """Accept ``{"from": a, "to": b}`` or ``[a, b]``."""
    if isinstance(item, dict):
        return item.get("from"), item.get("to")
    if isinstance(item, list | tuple) and len(item) == 2:
        return item[0], item[1]
    return None, None


def checked_file_name(name: str) -> str:
    name = PurePosixPath(name.replace("\\", "/")).name.strip()
    if not name or name in {".", ".."} or any(char in _FORBIDDEN_NAME_CHARS for char in name):
        raise InvalidInput(f"{name or 'This'} is not a valid file name.")
    return name[:200]


class Workspace:
    def __init__(self, settings: Settings, student_id: int) -> None:
        self.root = (settings.workspaces_dir / str(student_id)).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.quota_bytes = settings.workspace_quota_mb * 1024 * 1024

    # --- paths -------------------------------------------------------------
    def resolve(self, relative: str | None) -> Path:
        text = (relative or ".").replace("\\", "/").strip()
        if "\x00" in text:
            raise InvalidInput("The path contains an invalid character.")
        pure = PurePosixPath(text)
        # "C:/..." is a relative path on Linux, so drive letters are checked explicitly.
        has_drive = len(text) >= 2 and text[1] == ":" and text[0].isascii() and text[0].isalpha()
        if has_drive or pure.is_absolute() or ".." in pure.parts or (pure.parts and pure.parts[0] == TRASH):
            raise InvalidInput("Use a path inside your workspace, such as notes/week05.md.")
        target = (self.root / pure).resolve()
        if target != self.root and self.root not in target.parents:
            raise InvalidInput("The path leaves your workspace.")
        return target

    def relative(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix() or "."

    def _info(self, path: Path) -> FileInfo:
        stat = path.stat()
        return FileInfo(
            path=self.relative(path),
            is_dir=path.is_dir(),
            size=0 if path.is_dir() else stat.st_size,
            modified=datetime.fromtimestamp(stat.st_mtime, UTC),
        )

    def _existing_file(self, relative: str) -> Path:
        path = self.resolve(relative)
        if not path.is_file():
            raise NotFound(f"{relative} does not exist in your workspace.")
        return path

    # --- direct operations by the student ------------------------------------
    def listing(self, relative: str = ".", limit: int = 500) -> list[FileInfo]:
        base = self.resolve(relative)
        if not base.is_dir():
            raise NotFound(f"{relative} is not a folder in your workspace.")
        items: list[FileInfo] = []
        for path in sorted(base.rglob("*")):
            if TRASH in path.relative_to(self.root).parts:
                continue
            items.append(self._info(path))
            if len(items) >= limit:
                break
        return items

    def usage(self) -> int:
        return sum(path.stat().st_size for path in self.root.rglob("*") if path.is_file())

    def save_upload(self, folder: str, filename: str, data: bytes, *, replace: bool = False) -> FileInfo:
        directory = self.resolve(folder)
        target = directory / checked_file_name(filename)
        if target.exists() and not replace:
            raise Conflict(f"{self.relative(target)} already exists.")
        existing = target.stat().st_size if target.exists() else 0
        if self.usage() - existing + len(data) > self.quota_bytes:
            raise InvalidInput("Your workspace is full. Delete some files first.")
        directory.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return self._info(target)

    def read_text(self, relative: str) -> tuple[str, str]:
        path = self._existing_file(relative)
        if path.suffix.lower() not in TEXT_SUFFIXES:
            raise InvalidInput(f"{relative} is not a text file the assistant can read.")
        if path.stat().st_size > MAX_READ_BYTES:
            raise InvalidInput(f"{relative} is larger than {MAX_READ_BYTES // 1000} kB.")
        data = path.read_bytes()
        return data.decode("utf-8", errors="replace"), hashlib.sha256(data).hexdigest()

    def download_path(self, relative: str) -> Path:
        return self._existing_file(relative)

    def remove(self, relative: str) -> str:
        """Move a file or folder into the hidden trash; returns where it went."""
        path = self.resolve(relative)
        if path == self.root or not path.exists():
            raise NotFound(f"{relative} does not exist in your workspace.")
        stamp = utcnow().strftime("%Y%m%d-%H%M%S")
        destination = self.root / TRASH / stamp / self.relative(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), destination)
        return self.relative(destination)

    # --- proposals made by the assistant ---------------------------------------
    def propose(self, operation: str, arguments: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
        """Validate a change and return ``(summary, preview, payload)`` without touching files."""
        if operation == "rename":
            return self._propose_rename(arguments.get("renames") or [])
        relative = str(arguments.get("path") or "")
        path = self.resolve(relative)
        if path.suffix.lower() not in TEXT_SUFFIXES:
            raise InvalidInput("The assistant can only change text files.")
        exists = path.is_file()
        base_hash = _sha(path) if exists else None
        name = self.relative(path)
        if operation == "write":
            content = str(arguments.get("content") or "")
            self._check_size(content)
            verb = "Overwrite" if exists else "Create"
            return (
                f"{verb} {name}",
                content[:1500],
                {"op": "write", "path": name, "content": content, "base_hash": base_hash},
            )
        if not exists:
            raise NotFound(f"{name} does not exist in your workspace.")
        if operation == "append":
            content = str(arguments.get("content") or "")
            self._check_size(content)
            return (
                f"Append to {name}",
                content[:1500],
                {"op": "append", "path": name, "content": content, "base_hash": base_hash},
            )
        if operation == "replace":
            old, new = str(arguments.get("old_text") or ""), str(arguments.get("new_text") or "")
            current, _ = self.read_text(name)
            if not old or old not in current:
                raise InvalidInput("The text to replace was not found in the file.")
            self._check_size(new)
            preview = f"- {old[:600]}\n+ {new[:600]}"
            return (
                f"Edit {name}",
                preview,
                {"op": "replace", "path": name, "old": old, "new": new, "base_hash": base_hash},
            )
        if operation == "delete":
            return f"Move {name} to the trash", name, {"op": "delete", "path": name, "base_hash": base_hash}
        raise InvalidInput(f"Unknown file operation: {operation}.")

    def _check_size(self, content: str) -> None:
        if len(content.encode("utf-8")) > MAX_WRITE_BYTES:
            raise InvalidInput("The proposed content is too large.")

    def _propose_rename(self, renames: list[Any]) -> tuple[str, str, dict[str, Any]]:
        pairs: list[tuple[str, str]] = []
        targets: set[str] = set()
        for item in renames:
            source, target = _rename_pair(item)
            if not source or not target:
                raise InvalidInput("Each rename needs a 'from' and a 'to' path.")
            source_path = self._existing_file(str(source))
            target_path = self.resolve(str(target))
            checked_file_name(target_path.name)
            target_name = self.relative(target_path)
            if target_path.exists() or target_name in targets:
                raise Conflict(f"{target_name} already exists.")
            targets.add(target_name)
            pairs.append((self.relative(source_path), target_name))
        if not pairs:
            raise InvalidInput("Nothing to rename.")
        if len(pairs) > 200:
            raise InvalidInput("Rename at most 200 files at once.")
        preview = "\n".join(f"{source} -> {target}" for source, target in pairs)
        return f"Rename {len(pairs)} file(s)", preview, {"op": "rename", "renames": [list(pair) for pair in pairs]}

    def apply(self, payload: dict[str, Any]) -> str:
        operation = payload.get("op")
        if operation == "rename":
            return self._apply_rename(payload["renames"])
        name = str(payload["path"])
        path = self.resolve(name)
        current_hash = _sha(path) if path.is_file() else None
        if current_hash != payload.get("base_hash"):
            raise Conflict(f"{name} changed after the proposal was made. Ask the assistant again.")
        if operation == "write":
            path.parent.mkdir(parents=True, exist_ok=True)
            _write(path, payload["content"])
            return f"Saved {name}."
        if operation == "append":
            current = _read(path)
            separator = "" if not current or current.endswith("\n") else "\n"
            _write(path, current + separator + payload["content"])
            return f"Appended to {name}."
        if operation == "replace":
            _write(path, _read(path).replace(payload["old"], payload["new"], 1))
            return f"Updated {name}."
        if operation == "delete":
            return f"Moved {name} to the trash ({self.remove(name)})."
        raise InvalidInput(f"Unknown file operation: {operation}.")

    def _apply_rename(self, renames: list[list[str]]) -> str:
        done: list[tuple[Path, Path]] = []
        try:
            for source, target in renames:
                source_path, target_path = self.resolve(source), self.resolve(target)
                if not source_path.is_file():
                    raise Conflict(f"{source} no longer exists.")
                if target_path.exists():
                    raise Conflict(f"{target} already exists.")
                target_path.parent.mkdir(parents=True, exist_ok=True)
                source_path.rename(target_path)
                done.append((source_path, target_path))
        except Exception:
            for source_path, target_path in reversed(done):
                target_path.rename(source_path)
            raise
        return f"Renamed {len(done)} file(s)."
