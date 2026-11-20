"""An offline stand-in for an OpenAI-compatible model API, for demos and UI work.

    python scripts/fake_model_server.py            # listens on 127.0.0.1:8100
    TP_LLM_BASE_URL=http://127.0.0.1:8100/v1 TP_LLM_API_KEY=offline python -m termpilot

It answers chat completions with canned, streamed replies and calls one tool
the way a real model would: ``plan_study_time`` when the question mentions
planning or studying, ``list_tasks`` otherwise. ``/v1/embeddings`` returns
deterministic hash-based vectors so the library pipeline can run end to end.
It is not a model; it only exercises the plumbing.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Iterator
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI(title="TermPilot offline model")


def _chunk(delta: dict[str, Any], finish: str | None = None) -> str:
    body = {
        "id": "offline",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": "offline",
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }
    return f"data: {json.dumps(body)}\n\n"


def _call_tool(name: str, arguments: dict[str, Any]) -> Iterator[str]:
    encoded = json.dumps(arguments)
    yield _chunk(
        {
            "role": "assistant",
            "tool_calls": [
                {"index": 0, "id": "call_offline", "type": "function", "function": {"name": name, "arguments": ""}}
            ],
        }
    )
    for start in range(0, len(encoded), 16):
        yield _chunk({"tool_calls": [{"index": 0, "function": {"arguments": encoded[start : start + 16]}}]})
    yield _chunk({}, "tool_calls")
    yield "data: [DONE]\n\n"


def _say(text: str, reasoning: str | None = None) -> Iterator[str]:
    for word in (reasoning or "").split():
        time.sleep(0.01)
        yield _chunk({"reasoning_content": word + " "})
    for word in text.split(" "):
        time.sleep(0.02)
        yield _chunk({"content": word + " "})
    yield _chunk({}, "stop")
    yield "data: [DONE]\n\n"


def _json_reply(prompt: str) -> dict[str, Any]:
    # Order matters: the extraction prompt also mentions "title" in its JSON example.
    if "actionable" in prompt:
        due = time.strftime("%Y-%m-%dT17:00", time.localtime(time.time() + 2 * 86400))
        return {
            "tasks": [{"title": "Submit the course drop request", "due_at": due, "category": "admin", "notes": None}]
        }
    if "follow-up" in prompt:
        return {
            "questions": [
                "Which task should I start with?",
                "Can you book study time for it?",
                "What is due next week?",
            ]
        }
    if "title" in prompt:
        return {"title": "Planning the week"}
    return {}


def _answer(messages: list[dict[str, Any]]) -> str:
    results = [message for message in messages if message.get("role") == "tool"]
    if not results:
        return "This is the offline demo model. Connect a real model with TP_LLM_API_KEY for genuine answers."
    content = results[-1].get("content") or ""
    if '"blocks": []' in content:
        return "Your open tasks already have enough study time booked before their deadlines, so there is nothing new to add."
    if "waiting_for_approval" in content:
        return "I found free time around your classes and prepared **study blocks**. Approve the proposal below to add them to your timetable."
    try:
        titles = [item["title"] for item in json.loads(content)][:4]
    except (ValueError, TypeError, KeyError):
        titles = []
    listed = "\n".join(f"- **{title}**" for title in titles) or "- nothing open"
    return f"Here is what is still open:\n\n{listed}\n\nStart with the one due first and block time for it today."


@app.post("/v1/chat/completions")
async def chat(request: Request):  # type: ignore[no-untyped-def]
    body = await request.json()
    messages = body.get("messages", [])
    last = messages[-1] if messages else {}
    if body.get("response_format", {}).get("type") == "json_object":
        content = json.dumps(_json_reply(str(last.get("content") or "")))
        return JSONResponse(
            {
                "id": "offline",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": "offline",
                "choices": [
                    {"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
                ],
            }
        )
    if body.get("tools") and last.get("role") == "user":
        question = str(last.get("content") or "").lower()
        if any(word in question for word in ("plan", "study", "time for")):
            stream = _call_tool("plan_study_time", {"days": 5, "block_minutes": 90})
        else:
            stream = _call_tool("list_tasks", {"status": "open", "within_days": 7})
        return StreamingResponse(stream, media_type="text/event-stream")
    reasoning = "Ordering the open work by due date." if "reason" in str(body.get("model")) else None
    return StreamingResponse(_say(_answer(messages), reasoning), media_type="text/event-stream")


@app.post("/v1/embeddings")
async def embeddings(request: Request):  # type: ignore[no-untyped-def]
    body = await request.json()
    texts = body["input"] if isinstance(body["input"], list) else [body["input"]]
    size = int(body.get("dimensions") or 1024)
    data = []
    for index, text in enumerate(texts):
        seed = hashlib.sha256(str(text).encode()).digest()
        vector = [((seed[i % len(seed)] / 255.0) - 0.5) for i in range(size)]
        data.append({"object": "embedding", "index": index, "embedding": vector})
    return {"object": "list", "data": data, "model": "offline", "usage": {"prompt_tokens": 0, "total_tokens": 0}}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8100, log_level="warning")
