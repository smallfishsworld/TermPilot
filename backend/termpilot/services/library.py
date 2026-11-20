"""The student's searchable document library."""

from __future__ import annotations

import logging
import shutil
from pathlib import PurePath
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from termpilot.db.models import LibraryDocument, Student
from termpilot.errors import AppError, Conflict, FeatureUnavailable, InvalidInput, NotFound
from termpilot.knowledge.index import LibraryIndex
from termpilot.services.workspace import checked_file_name
from termpilot.settings import Settings

logger = logging.getLogger(__name__)

SUPPORTED = {
    ".pdf",
    ".docx",
    ".pptx",
    ".xlsx",
    ".xls",
    ".txt",
    ".md",
    ".markdown",
    ".html",
    ".htm",
    ".json",
    ".py",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".js",
    ".ts",
    ".go",
    ".sql",
}


def _magic_ok(suffix: str, data: bytes) -> bool:
    if suffix in {".docx", ".pptx", ".xlsx"}:
        return data.startswith(b"PK")
    if suffix == ".xls":
        return data.startswith(b"\xd0\xcf\x11\xe0")
    if suffix == ".pdf":
        return data.lstrip()[:5] == b"%PDF-"
    return True


def list_documents(db: Session, student: Student) -> list[LibraryDocument]:
    return list(
        db.scalars(
            select(LibraryDocument)
            .where(LibraryDocument.student_id == student.id)
            .order_by(LibraryDocument.created_at.desc())
        )
    )


def get_document(db: Session, student: Student, document_id: int) -> LibraryDocument:
    document = db.get(LibraryDocument, document_id)
    if document is None or document.student_id != student.id:
        raise NotFound("That document is not in your library.")
    return document


def upload(db: Session, settings: Settings, student: Student, filename: str, data: bytes) -> LibraryDocument:
    if not settings.embeddings_enabled:
        raise FeatureUnavailable("The document library needs TP_EMBEDDING_API_KEY and a search cluster.")
    name = checked_file_name(filename)
    suffix = PurePath(name).suffix.lower()
    if suffix not in SUPPORTED:
        raise InvalidInput("Upload PDF, Word, PowerPoint, Excel, Markdown, HTML, JSON or plain-text files.")
    if not data:
        raise InvalidInput(f"{name} is empty.")
    if len(data) > settings.upload_max_mb * 1024 * 1024:
        raise InvalidInput(f"Files are limited to {settings.upload_max_mb} MB.")
    if not _magic_ok(suffix, data):
        raise InvalidInput(f"{name} does not look like a real {suffix[1:].upper()} file.")
    if db.scalar(
        select(LibraryDocument.id).where(LibraryDocument.student_id == student.id, LibraryDocument.filename == name)
    ):
        raise Conflict(f"{name} is already in your library. Delete it first to replace it.")

    document = LibraryDocument(
        student_id=student.id, filename=name, media_type=suffix[1:], size_bytes=len(data), doc_key=uuid4().hex
    )
    db.add(document)
    db.commit()

    folder = settings.uploads_dir / str(student.id) / document.doc_key
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(data)
    try:
        document.chunks = LibraryIndex(student.id).ingest(name, data, document.doc_key)
        document.status = "ready" if document.chunks else "empty"
        document.error = None if document.chunks else "No text could be extracted."
    except AppError as exc:
        document.status = "failed"
        document.error = exc.message
    except Exception:
        logger.exception("Ingesting %s failed", name)
        document.status = "failed"
        document.error = "The document could not be processed."
    db.commit()
    return document


def delete(db: Session, settings: Settings, student: Student, document_id: int) -> None:
    document = get_document(db, student, document_id)
    if document.chunks:
        LibraryIndex(student.id).delete_document(document.doc_key)
    shutil.rmtree(settings.uploads_dir / str(student.id) / document.doc_key, ignore_errors=True)
    db.delete(document)
    db.commit()


def document_text(student: Student, document: LibraryDocument, max_chars: int = 24_000) -> str:
    if document.status != "ready":
        raise InvalidInput("This document has no searchable text yet.")
    return LibraryIndex(student.id).document_text(document.doc_key, max_chars)
