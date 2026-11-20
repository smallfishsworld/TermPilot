"""Single-purpose model calls: study aids and task extraction from email."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from termpilot.assistant import prompts
from termpilot.assistant.events import sse
from termpilot.db.models import MailItem
from termpilot.errors import AppError
from termpilot.llm.client import ChatModel, Completion, complete_json
from termpilot.settings import Settings

logger = logging.getLogger(__name__)

StudyAidKind = Literal["summary", "quiz", "flashcards"]


def stream_study_aid(model: ChatModel, title: str, text: str, kind: StudyAidKind) -> Iterator[str]:
    """Stream a revision aid generated from one document's text as SSE ``answer`` events."""
    if not text.strip():
        yield sse("error", {"message": "This document has no indexed text to work from."})
        yield sse("done", {})
        return
    messages = [
        {"role": "system", "content": f"{prompts.PERSONA}\n\n{prompts.STUDY_AID[kind]}"},
        {"role": "user", "content": f"Document: {title}\n\n{text}"},
    ]
    try:
        for item in model.stream(messages):
            if isinstance(item, Completion):
                continue
            if item.kind == "text":
                yield sse("answer", {"text": item.text})
    except AppError as exc:
        yield sse("error", {"message": exc.message})
    yield sse("done", {})


@dataclass(frozen=True)
class TaskCandidate:
    title: str
    due_at: datetime
    category: str | None
    notes: str | None


def extract_tasks(settings: Settings, model: ChatModel, item: MailItem) -> list[TaskCandidate]:
    """Candidate tasks for the student to review; nothing is saved here."""
    received = item.received_at.astimezone(settings.tz).strftime("%A %Y-%m-%d %H:%M") if item.received_at else "unknown"
    prompt = (
        f"{prompts.MAIL_TASKS}\n\nReceived: {received}\nFrom: {item.sender}\nSubject: {item.subject}\n\n"
        f"{(item.body_text or item.preview or '')[:8000]}"
    )
    data = complete_json(model, prompt)
    candidates: list[TaskCandidate] = []
    for raw in data.get("tasks", []) if isinstance(data.get("tasks"), list) else []:
        if not isinstance(raw, dict) or not raw.get("title") or not raw.get("due_at"):
            continue
        try:
            due_at = datetime.fromisoformat(str(raw["due_at"]).replace(" ", "T"))
        except ValueError:
            logger.info("Skipping extracted task with unreadable date %r", raw.get("due_at"))
            continue
        if due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=settings.tz)
        candidates.append(
            TaskCandidate(
                title=str(raw["title"]).strip()[:300],
                due_at=due_at,
                category=(str(raw.get("category")).strip() or None) if raw.get("category") else None,
                notes=(str(raw.get("notes")).strip() or None) if raw.get("notes") else None,
            )
        )
    return candidates
