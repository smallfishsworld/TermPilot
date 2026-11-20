"""Produce one assistant answer as a stream of server-sent events.

Three modes share the same bookkeeping:

``ask``       answer from the student's documents and attachments
``research``  like ``ask`` plus a web search
``agent``     the model calls tools in a loop (see :mod:`termpilot.assistant.toolkit`)

Every answer is stored as a :class:`Turn`, including the sources it cited and
the tool steps it took; a broken connection keeps whatever was produced.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy.orm import Session

from termpilot.assistant import prompts, web
from termpilot.assistant.events import sse
from termpilot.assistant.toolkit import REGISTRY, ToolContext, available_tools, run_tool
from termpilot.clock import local_now, utcnow
from termpilot.db.models import Conversation, PendingAction, Student, Turn
from termpilot.db.session import session_scope
from termpilot.errors import AppError, FeatureUnavailable
from termpilot.knowledge.index import LibraryIndex
from termpilot.llm.client import ChatModel, Completion, Delta, Message, complete_json
from termpilot.services import conversations
from termpilot.services.term_calendar import current_term
from termpilot.settings import Settings

logger = logging.getLogger(__name__)

Mode = Literal["ask", "research", "agent"]
TOOL_RESULT_LIMIT = 12_000
HISTORY_ANSWER_LIMIT = 1_500


@dataclass
class Question:
    text: str
    mode: Mode = "agent"
    deep_think: bool = False


@dataclass
class _Record:
    answer: list[str] = field(default_factory=list)
    reasoning: list[str] = field(default_factory=list)
    trace: list[dict[str, Any]] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


def approval_view(action: PendingAction) -> dict[str, Any]:
    return {
        "id": action.id,
        "kind": action.kind,
        "title": action.title,
        "summary": action.summary,
        "preview": action.preview,
        "status": action.status,
        "expires_at": action.expires_at.isoformat(),
    }


def _student_context(
    settings: Settings, student: Student, conversation: Conversation, *, include_attachments: bool = True
) -> str:
    now = local_now(settings.tz)
    term = current_term(settings, student, now.date())
    week = term.week_of(now.date())
    lines = [
        f"Now: {now:%A %Y-%m-%d %H:%M} ({settings.timezone}).",
        f"Term: {term.label}; teaching week {week} of {term.weeks} (week 1 began {term.start:%Y-%m-%d})."
        if term.contains(now.date())
        else f"Term: {term.label} teaching starts {term.start:%Y-%m-%d}; classes are not in session.",
        f"Student: {student.display_name}"
        + (f", {student.department}" if student.department else "")
        + (f", class {student.class_name}" if student.class_name else "")
        + (f", GPA {student.gpa:.2f}" if student.gpa is not None else "")
        + ".",
    ]
    if student.interests:
        lines.append(f"Interests and goals: {student.interests}")
    for attachment in conversation.attachments if include_attachments else []:
        note = " (truncated)" if attachment.truncated else ""
        lines.append(f"\nAttached file {attachment.filename}{note}:\n{attachment.text}")
    return "\n".join(lines)


def _history(db: Session, settings: Settings, conversation: Conversation, current_turn: str) -> list[Message]:
    messages: list[Message] = []
    for turn in conversations.recent_turns(db, conversation.id, settings.history_turns + 1):
        if turn.id == current_turn or not turn.answer:
            continue
        messages.append({"role": "user", "content": turn.question})
        messages.append({"role": "assistant", "content": turn.answer[:HISTORY_ANSWER_LIMIT]})
    return messages[-2 * settings.history_turns :]


class AnswerStream:
    def __init__(
        self, settings: Settings, model: ChatModel, student_id: int, conversation_id: str, question: Question
    ) -> None:
        self.settings = settings
        self.model = model
        self.student_id = student_id
        self.conversation_id = conversation_id
        self.question = question

    def __iter__(self) -> Iterator[str]:
        with session_scope() as db:
            student = db.get(Student, self.student_id)
            assert student is not None
            conversation = conversations.get(db, student, self.conversation_id)
            turn = Turn(conversation_id=conversation.id, mode=self.question.mode, question=self.question.text)
            db.add(turn)
            db.commit()
            record = _Record()
            yield sse("turn", {"turn_id": turn.id, "conversation_id": conversation.id, "mode": turn.mode})
            try:
                if self.question.mode == "agent":
                    yield from self._agent(db, student, conversation, turn, record)
                else:
                    yield from self._grounded(db, student, conversation, turn, record)
                yield from self._afterwards(db, conversation, turn, record)
            except AppError as exc:
                turn.failed = not record.answer
                yield sse("error", {"message": exc.message})
            except Exception:
                logger.exception("Answer stream failed")
                turn.failed = not record.answer
                yield sse("error", {"message": "The answer could not be completed. Please try again."})
            finally:
                turn.answer = "".join(record.answer)
                turn.reasoning = "".join(record.reasoning) or None
                turn.trace = record.trace
                turn.sources = record.sources
                turn.suggestions = record.suggestions
                conversation.updated_at = utcnow()
                db.commit()
            yield sse("done", {"turn_id": turn.id})

    # --- streaming helpers ---------------------------------------------------------
    def _relay(
        self, deltas: Iterator[Delta | Completion], record: _Record, *, show_text: bool = True
    ) -> Iterator[str | Completion]:
        for item in deltas:
            if isinstance(item, Completion):
                yield item
            elif item.kind == "reasoning":
                record.reasoning.append(item.text)
                yield sse("reasoning", {"text": item.text})
            elif show_text:
                record.answer.append(item.text)
                yield sse("answer", {"text": item.text})

    def _final(self, generator: Iterator[str | Completion]) -> Iterator[str]:
        for item in generator:
            if isinstance(item, str):
                yield item

    def _step(self, record: _Record, step_id: str, tool: str, label: str, status: str, detail: str = "") -> str:
        entry = {"id": step_id, "tool": tool, "label": label, "status": status, "detail": detail}
        record.trace = [step for step in record.trace if step["id"] != step_id] + [entry]
        return sse("step", entry)

    # --- ask / research ---------------------------------------------------------------
    def _grounded(
        self, db: Session, student: Student, conversation: Conversation, turn: Turn, record: _Record
    ) -> Iterator[str]:
        question = self.question.text
        sources: list[dict[str, Any]] = []
        blocks: list[str] = []

        def add(kind: str, title: str, text: str, url: str | None = None) -> None:
            index = len(sources) + 1
            sources.append({"index": index, "kind": kind, "title": title, "excerpt": text[:600], "url": url})
            blocks.append(f"[{index}] ({kind}: {title})\n{text}")

        for attachment in conversation.attachments:
            add("attachment", attachment.filename, attachment.text)

        if self.settings.embeddings_enabled:
            yield self._step(record, "library", "search_library", "Searching your documents", "running")
            try:
                passages = LibraryIndex(student.id).search(question, top_k=5)
                for passage in passages:
                    add("library", passage.document, passage.text)
                yield self._step(
                    record, "library", "search_library", "Searching your documents", "done", f"{len(passages)} passages"
                )
            except AppError as exc:
                yield self._step(record, "library", "search_library", "Searching your documents", "failed", exc.message)

        related: list[str] = []
        if self.question.mode == "research":
            yield self._step(record, "web", "web_search", "Searching the web", "running")
            try:
                found = web.search(self.settings, question, count=6)
                for result in found.results:
                    add("web", result.title, result.snippet, result.url)
                related = found.related_questions
                yield self._step(
                    record, "web", "web_search", "Searching the web", "done", f"{len(found.results)} results"
                )
            except AppError as exc:
                yield self._step(record, "web", "web_search", "Searching the web", "failed", exc.message)

        record.sources = sources
        if sources:
            yield sse("sources", {"items": sources})
        record.suggestions = related

        context = _student_context(self.settings, student, conversation, include_attachments=False)
        evidence = "\n\n".join(blocks) if blocks else "(no sources were found)"
        system = f"{prompts.PERSONA}\n\n{context}\n\n{prompts.GROUNDED}\n\nSources:\n{evidence}".strip()
        messages = [
            {"role": "system", "content": system},
            *_history(db, self.settings, conversation, turn.id),
            {"role": "user", "content": question},
        ]
        model_name = self.model.reasoning_model if self.question.deep_think else self.model.chat_model
        yield from self._final(self._relay(self.model.stream(messages, model=model_name), record))

    # --- agent ------------------------------------------------------------------------------
    def _agent(
        self, db: Session, student: Student, conversation: Conversation, turn: Turn, record: _Record
    ) -> Iterator[str]:
        ctx = ToolContext(db=db, settings=self.settings, student=student, conversation_id=conversation.id)
        schemas = [tool.schema() for tool in available_tools(ctx)]
        system = f"{prompts.PERSONA}\n\n{prompts.AGENT}\n\n{_student_context(self.settings, student, conversation)}"
        history = _history(db, self.settings, conversation, turn.id)
        messages: list[Message] = [
            {"role": "system", "content": system},
            *history,
            {"role": "user", "content": self.question.text},
        ]
        evidence: list[str] = []
        announced = 0
        step_number = 0

        for round_number in range(self.settings.agent_max_steps):
            last_round = round_number == self.settings.agent_max_steps - 1
            completion = Completion()
            stream = self.model.stream(messages, tools=None if last_round else schemas)
            for item in self._relay(stream, record, show_text=not self.question.deep_think):
                if isinstance(item, Completion):
                    completion = item
                else:
                    yield item
            if not completion.tool_calls:
                break
            messages.append(completion.as_message())
            for call in completion.tool_calls:
                step_number += 1
                step_id = f"s{step_number}"
                label = REGISTRY[call.name].label if call.name in REGISTRY else call.name
                yield self._step(record, step_id, call.name, label, "running")
                outcome, ok = run_tool(ctx, call.name, call.parsed_arguments())
                yield self._step(record, step_id, call.name, label, "done" if ok else "failed", outcome.summary)
                payload = json.dumps(outcome.content, ensure_ascii=False, default=str)[:TOOL_RESULT_LIMIT]
                messages.append({"role": "tool", "tool_call_id": call.id, "content": payload})
                evidence.append(f"{call.name}({call.arguments}) -> {payload}")
                for action in ctx.proposals[announced:]:
                    yield sse("approval", approval_view(action))
                announced = len(ctx.proposals)
                if len(ctx.sources) != len(record.sources):
                    record.sources = list(ctx.sources)
                    yield sse("sources", {"items": record.sources})

        if self.question.deep_think:
            # Reasoning models get the gathered evidence as plain text, which every provider accepts.
            notes = "\n\n".join(evidence) if evidence else "(no tools were used)"
            prompt = f"{self.question.text}\n\nEvidence gathered with tools:\n{notes[:24_000]}"
            final_messages = [{"role": "system", "content": system}, *history, {"role": "user", "content": prompt}]
            yield from self._final(
                self._relay(self.model.stream(final_messages, model=self.model.reasoning_model), record)
            )

    # --- titles and follow-ups -------------------------------------------------------------
    def _afterwards(self, db: Session, conversation: Conversation, turn: Turn, record: _Record) -> Iterator[str]:
        answer = "".join(record.answer)
        if not answer:
            return
        if not record.suggestions:
            try:
                data = complete_json(
                    self.model, f"{prompts.SUGGESTIONS}\n\nQuestion: {turn.question}\n\nAnswer: {answer[:2000]}"
                )
                record.suggestions = [q.strip() for q in data.get("questions", []) if isinstance(q, str) and q.strip()][
                    :3
                ]
            except (AppError, FeatureUnavailable):
                record.suggestions = []
        if record.suggestions:
            yield sse("suggestions", {"items": record.suggestions})
        if conversation.auto_title and len(conversation.turns) <= 1:
            title = ""
            try:
                title = str(complete_json(self.model, f"{prompts.TITLE}\n\n{turn.question[:500]}").get("title") or "")
            except AppError:
                pass
            title = (title.strip().strip('"') or turn.question.strip())[:60]
            conversation.title = title
            conversation.auto_title = False
            db.commit()
            yield sse("title", {"title": title})
