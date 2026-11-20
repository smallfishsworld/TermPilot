"""Shared fixtures: an in-memory database, demo campus data and a scripted model."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from termpilot import clock
from termpilot.api.deps import get_chat_model, get_gateway
from termpilot.campus.demo import DemoCampusGateway
from termpilot.db.session import new_session
from termpilot.llm.client import Completion, Delta, ToolCall
from termpilot.main import create_app
from termpilot.settings import Settings

CAMPUS_TZ = ZoneInfo("Asia/Shanghai")
# Wednesday of teaching week 6 in the autumn term that starts on Monday 2026-09-07.
FROZEN_AT = datetime(2026, 10, 14, 10, 0, tzinfo=CAMPUS_TZ)


class ScriptedModel:
    """Plays back prepared model turns; records every request it receives."""

    chat_model = "scripted-chat"
    reasoning_model = "scripted-reasoner"

    def __init__(self) -> None:
        self.rounds: list[Completion | str] = []
        self.json_replies: list[dict[str, Any]] = []
        self.requests: list[dict[str, Any]] = []

    def say(self, *rounds: Completion | str) -> ScriptedModel:
        self.rounds.extend(rounds)
        return self

    def stream(self, messages, *, model=None, tools=None):  # type: ignore[no-untyped-def]
        self.requests.append({"messages": messages, "model": model, "tools": tools})
        reply = self.rounds.pop(0) if self.rounds else "(no scripted reply)"
        if isinstance(reply, str):
            reply = Completion(text=reply)
        if reply.reasoning:
            yield Delta("reasoning", reply.reasoning)
        if reply.text:
            yield Delta("text", reply.text)
        yield reply

    def complete(self, messages, *, model=None, json_mode=False):  # type: ignore[no-untyped-def]
        self.requests.append({"messages": messages, "model": model, "json": json_mode})
        return Completion(text=json.dumps(self.json_replies.pop(0) if self.json_replies else {}))


def call(name: str, **arguments: Any) -> ToolCall:
    return ToolCall(id=f"call-{name}", name=name, arguments=json.dumps(arguments))


@pytest.fixture(autouse=True)
def frozen_clock() -> Iterator[datetime]:
    clock.freeze(FROZEN_AT)
    yield FROZEN_AT
    clock.freeze(None)


@pytest.fixture
def settings(tmp_path) -> Settings:  # type: ignore[no-untyped-def]
    return Settings(
        _env_file=None,
        environment="test",
        demo_mode=True,
        database_url="sqlite://",
        data_dir=tmp_path,
        secret_key="test-only-secret-key-with-enough-length-0123456789",
        timezone="Asia/Shanghai",
        term_start_override=None,
        cors_origins=["http://localhost:3000"],
    )


@pytest.fixture
def model() -> ScriptedModel:
    return ScriptedModel()


@pytest.fixture
def client(settings: Settings, model: ScriptedModel) -> Iterator[TestClient]:
    app = create_app(settings)
    app.dependency_overrides[get_chat_model] = lambda: model
    app.dependency_overrides[get_gateway] = lambda: DemoCampusGateway(settings)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/session", json={"username": "demo", "password": "demo"})
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


@pytest.fixture
def synced(client: TestClient, auth: dict[str, str]) -> dict[str, str]:
    response = client.post("/api/sync", json={}, headers=auth)
    assert response.status_code == 201, response.text
    assert response.json()["outcome"] == "ok", response.json()
    return auth


@pytest.fixture
def db(client: TestClient):  # type: ignore[no-untyped-def]
    session = new_session()
    yield session
    session.close()


def events(response) -> list[tuple[str, dict[str, Any]]]:  # type: ignore[no-untyped-def]
    """Parse a server-sent event stream into ``(event, data)`` pairs."""
    parsed = []
    for block in response.text.strip().split("\n\n"):
        name, data = "", "{}"
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: "):
                data = line[6:]
        parsed.append((name, json.loads(data)))
    return parsed
