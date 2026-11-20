"""A small, testable wrapper around OpenAI-compatible chat completions.

``ChatModel.stream`` yields :class:`Delta` items while the model writes and
finishes with one :class:`Completion` holding the full text, any reasoning
and the tool calls assembled from streamed fragments. Tests substitute a
scripted implementation of the same protocol.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from openai import OpenAI, OpenAIError

from termpilot.errors import FeatureUnavailable, UpstreamFailure
from termpilot.settings import Settings

logger = logging.getLogger(__name__)

Message = dict[str, Any]


@dataclass(frozen=True)
class Delta:
    kind: Literal["text", "reasoning"]
    text: str


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str

    def parsed_arguments(self) -> dict[str, Any]:
        try:
            value = json.loads(self.arguments or "{}")
        except json.JSONDecodeError:
            return {}
        return value if isinstance(value, dict) else {}


@dataclass
class Completion:
    text: str = ""
    reasoning: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str | None = None

    def as_message(self) -> Message:
        message: Message = {"role": "assistant", "content": self.text or None}
        if self.tool_calls:
            message["tool_calls"] = [
                {"id": call.id, "type": "function", "function": {"name": call.name, "arguments": call.arguments}}
                for call in self.tool_calls
            ]
        return message


class ChatModel(Protocol):
    chat_model: str
    reasoning_model: str

    def stream(
        self, messages: list[Message], *, model: str | None = None, tools: list[dict[str, Any]] | None = None
    ) -> Iterator[Delta | Completion]: ...

    def complete(self, messages: list[Message], *, model: str | None = None, json_mode: bool = False) -> Completion: ...


class OpenAICompatibleModel:
    def __init__(self, settings: Settings) -> None:
        assert settings.llm_api_key is not None
        self.client = OpenAI(
            api_key=settings.llm_api_key.get_secret_value(),
            base_url=settings.llm_base_url,
            timeout=settings.llm_timeout_seconds,
        )
        self.chat_model = settings.llm_chat_model
        self.reasoning_model = settings.llm_reasoning_model

    def stream(
        self, messages: list[Message], *, model: str | None = None, tools: list[dict[str, Any]] | None = None
    ) -> Iterator[Delta | Completion]:
        options: dict[str, Any] = {"model": model or self.chat_model, "messages": messages, "stream": True}
        if tools:
            options["tools"] = tools
        try:
            response = self.client.chat.completions.create(**options)
            text: list[str] = []
            reasoning: list[str] = []
            calls: dict[int, dict[str, str]] = {}
            finish: str | None = None
            for chunk in response:
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                delta = choice.delta
                thought = getattr(delta, "reasoning_content", None)
                if thought:
                    reasoning.append(thought)
                    yield Delta("reasoning", thought)
                if delta.content:
                    text.append(delta.content)
                    yield Delta("text", delta.content)
                for fragment in delta.tool_calls or []:
                    call = calls.setdefault(fragment.index, {"id": "", "name": "", "arguments": ""})
                    if fragment.id:
                        call["id"] = fragment.id
                    if fragment.function and fragment.function.name:
                        call["name"] += fragment.function.name
                    if fragment.function and fragment.function.arguments:
                        call["arguments"] += fragment.function.arguments
                finish = choice.finish_reason or finish
        except OpenAIError as exc:
            logger.warning("Model call failed: %s", exc)
            raise UpstreamFailure("The language model did not respond. Please try again.") from exc
        yield Completion(
            text="".join(text),
            reasoning="".join(reasoning),
            tool_calls=[
                ToolCall(id=call["id"] or f"call_{index}", name=call["name"], arguments=call["arguments"])
                for index, call in sorted(calls.items())
                if call["name"]
            ],
            finish_reason=finish,
        )

    def complete(self, messages: list[Message], *, model: str | None = None, json_mode: bool = False) -> Completion:
        options: dict[str, Any] = {"model": model or self.chat_model, "messages": messages}
        if json_mode:
            options["response_format"] = {"type": "json_object"}
        try:
            response = self.client.chat.completions.create(**options)
        except OpenAIError as exc:
            logger.warning("Model call failed: %s", exc)
            raise UpstreamFailure("The language model did not respond. Please try again.") from exc
        choice = response.choices[0]
        return Completion(
            text=choice.message.content or "",
            reasoning=getattr(choice.message, "reasoning_content", None) or "",
            finish_reason=choice.finish_reason,
        )


class UnconfiguredModel:
    chat_model = "unconfigured"
    reasoning_model = "unconfigured"

    def _fail(self) -> FeatureUnavailable:
        return FeatureUnavailable("The assistant needs a language model. Set TP_LLM_API_KEY.")

    def stream(
        self, messages: list[Message], *, model: str | None = None, tools: list[dict[str, Any]] | None = None
    ) -> Iterator[Delta | Completion]:
        raise self._fail()

    def complete(self, messages: list[Message], *, model: str | None = None, json_mode: bool = False) -> Completion:
        raise self._fail()


def build_chat_model(settings: Settings) -> ChatModel:
    return OpenAICompatibleModel(settings) if settings.llm_enabled else UnconfiguredModel()


def complete_json(model: ChatModel, prompt: str, *, system: str | None = None) -> dict[str, Any]:
    """Ask for a JSON object; malformed output yields an empty dict."""
    messages: list[Message] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    raw = model.complete(messages, json_mode=True).text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`").removeprefix("json").strip()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        try:
            value = json.loads(raw[start : end + 1]) if start != -1 and end > start else {}
        except json.JSONDecodeError:
            value = {}
    return value if isinstance(value, dict) else {}
