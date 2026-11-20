"""Plain-text extraction for files attached to a single conversation.

Attachments are read immediately and kept with the conversation, so this
path deliberately avoids the heavy OCR pipeline used by the library.
"""

from __future__ import annotations

import io
from pathlib import PurePath

from termpilot.errors import InvalidInput

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
    ".ipynb",
}
DOCUMENT_SUFFIXES = {".pdf", ".docx", ".pptx"}
SUPPORTED_SUFFIXES = TEXT_SUFFIXES | DOCUMENT_SUFFIXES
MAX_PDF_PAGES = 40


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", errors="replace")


def _pdf(data: bytes) -> str:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(data)) as pdf:
        pages = pdf.pages[:MAX_PDF_PAGES]
        return "\n\n".join(page.extract_text() or "" for page in pages)


def _docx(data: bytes) -> str:
    from docx import Document

    document = Document(io.BytesIO(data))
    parts = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
    for table in document.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text.strip() for cell in row.cells))
    return "\n".join(parts)


def _pptx(data: bytes) -> str:
    from pptx import Presentation

    slides = []
    for number, slide in enumerate(Presentation(io.BytesIO(data)).slides, start=1):
        texts = [shape.text_frame.text for shape in slide.shapes if getattr(shape, "has_text_frame", False)]
        body = "\n".join(text for text in texts if text.strip())
        if body:
            slides.append(f"Slide {number}\n{body}")
    return "\n\n".join(slides)


def extract_text(filename: str, data: bytes, max_chars: int) -> tuple[str, bool]:
    """Return ``(text, truncated)``; unreadable or unsupported files raise ``InvalidInput``."""
    suffix = PurePath(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise InvalidInput("Attach a PDF, Word, PowerPoint or plain-text file.")
    if not data:
        raise InvalidInput("The file is empty.")
    try:
        if suffix == ".pdf":
            text = _pdf(data)
        elif suffix == ".docx":
            text = _docx(data)
        elif suffix == ".pptx":
            text = _pptx(data)
        else:
            text = _decode(data)
    except InvalidInput:
        raise
    except Exception as exc:  # parsers raise many unrelated exception types on corrupt input
        raise InvalidInput(f"{filename} could not be read. Is the file damaged?") from exc
    text = "\n".join(line.rstrip() for line in text.splitlines()).strip()
    if not text:
        raise InvalidInput(f"No text was found in {filename}. Scanned PDFs need the document library.")
    if len(text) > max_chars:
        return text[:max_chars], True
    return text, False
