from datetime import timedelta

from sqlalchemy import select

from termpilot import clock
from termpilot.db.models import PendingAction, Task, Turn
from termpilot.llm.client import Completion
from tests.conftest import FROZEN_AT, call, events


def _conversation(client, headers):
    return client.post("/api/conversations", json={}, headers=headers).json()["id"]


def test_agent_uses_tools_then_answers(client, synced, model, db):
    model.say(
        Completion(tool_calls=[call("list_tasks", status="open", within_days=7)]),
        "You have three deadlines this week.",
    )
    model.json_replies = [{"questions": ["What should I start with?"]}, {"title": "Deadlines this week"}]
    conversation = _conversation(client, synced)
    response = client.post(
        f"/api/conversations/{conversation}/ask", json={"question": "What is due this week?"}, headers=synced
    )
    stream = events(response)
    names = [name for name, _ in stream]
    assert names[0] == "turn" and names[-1] == "done"
    steps = [data for name, data in stream if name == "step"]
    assert [step["status"] for step in steps] == ["running", "done"]
    assert steps[1]["detail"].startswith("Found")
    assert "".join(data["text"] for name, data in stream if name == "answer") == "You have three deadlines this week."
    assert ("title", {"title": "Deadlines this week"}) in stream

    tool_message = model.requests[1]["messages"][-1]
    assert tool_message["role"] == "tool" and "Problem Set 6" in tool_message["content"]
    assert model.requests[0]["tools"], "the first round must offer tools"

    turn = db.scalars(select(Turn)).one()
    assert turn.answer == "You have three deadlines this week."
    assert turn.trace[0]["tool"] == "list_tasks" and turn.suggestions == ["What should I start with?"]
    detail = client.get(f"/api/conversations/{conversation}", headers=synced).json()
    assert detail["conversation"]["title"] == "Deadlines this week" and len(detail["turns"]) == 1


def test_history_is_sent_with_follow_up_questions(client, synced, model):
    conversation = _conversation(client, synced)
    model.say("First answer.", "Second answer.")
    client.post(f"/api/conversations/{conversation}/ask", json={"question": "First?", "mode": "ask"}, headers=synced)
    client.post(f"/api/conversations/{conversation}/ask", json={"question": "Second?", "mode": "ask"}, headers=synced)
    second = [request for request in model.requests if "tools" in request][-1]["messages"]
    assert [m["content"] for m in second if m["role"] in ("user", "assistant")] == [
        "First?",
        "First answer.",
        "Second?",
    ]


def test_proposed_task_waits_for_approval(client, synced, model, db):
    model.say(
        Completion(
            tool_calls=[call("propose_task", action="create", title="Book lab slot", due_at="2026-10-16T12:00")]
        ),
        "I prepared the task. Approve it to add it.",
    )
    conversation = _conversation(client, synced)
    stream = events(
        client.post(
            f"/api/conversations/{conversation}/ask",
            json={"question": "Remind me to book a lab slot by Friday noon"},
            headers=synced,
        )
    )
    approval = next(data for name, data in stream if name == "approval")
    assert approval["kind"] == "task.create" and approval["status"] == "pending"
    assert db.scalar(select(Task).where(Task.title == "Book lab slot")) is None

    pending = client.get("/api/approvals", headers=synced).json()
    assert [item["id"] for item in pending] == [approval["id"]]
    decided = client.post(f"/api/approvals/{approval['id']}/decision", json={"approve": True}, headers=synced).json()
    assert decided["status"] == "done" and "Book lab slot" in decided["outcome"]
    task = db.scalar(select(Task).where(Task.title == "Book lab slot"))
    assert task is not None and task.origin == "assistant"
    assert task.due_at.astimezone(FROZEN_AT.tzinfo).hour == 12

    again = client.post(f"/api/approvals/{approval['id']}/decision", json={"approve": True}, headers=synced)
    assert again.status_code == 409


def test_rejected_and_expired_proposals_change_nothing(client, synced, model, db):
    model.say(
        Completion(
            tool_calls=[
                call(
                    "propose_timetable_change",
                    action="create",
                    title="Gym",
                    weekday=6,
                    starts_at="09:00",
                    ends_at="10:00",
                )
            ]
        ),
        "Proposed.",
        Completion(
            tool_calls=[
                call(
                    "propose_timetable_change",
                    action="create",
                    title="Swim",
                    weekday=7,
                    starts_at="09:00",
                    ends_at="10:00",
                )
            ]
        ),
        "Proposed again.",
    )
    conversation = _conversation(client, synced)
    first = next(
        d
        for n, d in events(
            client.post(f"/api/conversations/{conversation}/ask", json={"question": "gym"}, headers=synced)
        )
        if n == "approval"
    )
    rejected = client.post(f"/api/approvals/{first['id']}/decision", json={"approve": False}, headers=synced).json()
    assert rejected["status"] == "rejected"

    second = next(
        d
        for n, d in events(
            client.post(f"/api/conversations/{conversation}/ask", json={"question": "swim"}, headers=synced)
        )
        if n == "approval"
    )
    clock.freeze(FROZEN_AT + timedelta(minutes=30))
    token = client.post("/api/auth/session", json={"username": "demo", "password": "demo"}).json()["token"]
    late = client.post(
        f"/api/approvals/{second['id']}/decision", json={"approve": True}, headers={"Authorization": f"Bearer {token}"}
    )
    assert late.status_code == 409 and "expired" in late.json()["error"]["message"]
    titles = [
        entry["title"]
        for entry in client.get("/api/timetable", headers={"Authorization": f"Bearer {token}"}).json()["entries"]
    ]
    assert "Gym" not in titles and "Swim" not in titles


def test_failed_tool_is_reported_to_the_model(client, synced, model):
    model.say(Completion(tool_calls=[call("read_file", path="../secrets.txt")]), "I cannot read that file.")
    conversation = _conversation(client, synced)
    stream = events(client.post(f"/api/conversations/{conversation}/ask", json={"question": "read it"}, headers=synced))
    assert [d["status"] for n, d in stream if n == "step"] == ["running", "failed"]
    assert "workspace" in model.requests[1]["messages"][-1]["content"]


def test_study_plan_proposal_books_blocks_after_approval(client, synced, model):
    model.say(Completion(tool_calls=[call("plan_study_time", days=4)]), "Here is a plan.")
    conversation = _conversation(client, synced)
    stream = events(
        client.post(f"/api/conversations/{conversation}/ask", json={"question": "plan my week"}, headers=synced)
    )
    approval = next(d for n, d in stream if n == "approval")
    assert approval["kind"] == "study.schedule" and approval["preview"]
    result = client.post(f"/api/approvals/{approval['id']}/decision", json={"approve": True}, headers=synced).json()
    assert result["status"] == "done"
    kinds = [entry["kind"] for entry in client.get("/api/timetable", headers=synced).json()["entries"]]
    assert "study" in kinds


def test_deep_think_answers_with_the_reasoning_model(client, synced, model):
    model.say(
        Completion(tool_calls=[call("get_profile")]),
        "draft that is not shown",
        Completion(text="Final.", reasoning="Thinking..."),
    )
    conversation = _conversation(client, synced)
    stream = events(
        client.post(
            f"/api/conversations/{conversation}/ask",
            json={"question": "How am I doing?", "deep_think": True},
            headers=synced,
        )
    )
    assert "".join(d["text"] for n, d in stream if n == "answer") == "Final."
    assert [d["text"] for n, d in stream if n == "reasoning"] == ["Thinking..."]
    final_request = [r for r in model.requests if "tools" in r][-1]
    assert (
        final_request["model"] == "scripted-reasoner"
        and "Evidence gathered" in final_request["messages"][-1]["content"]
    )


def test_unconfigured_model_reports_a_clear_error(client, synced, settings):
    from termpilot.api.deps import get_chat_model
    from termpilot.llm.client import UnconfiguredModel

    client.app.dependency_overrides[get_chat_model] = lambda: UnconfiguredModel()
    conversation = _conversation(client, synced)
    stream = events(client.post(f"/api/conversations/{conversation}/ask", json={"question": "hi"}, headers=synced))
    error = next(d for n, d in stream if n == "error")
    assert "TP_LLM_API_KEY" in error["message"] and stream[-1][0] == "done"


def test_attachments_feed_grounded_answers(client, synced, model):
    conversation = _conversation(client, synced)
    upload = client.post(
        f"/api/conversations/{conversation}/attachments",
        files={"file": ("notes.md", b"# Heaps\nA binary heap keeps the smallest key at the root.", "text/markdown")},
        headers=synced,
    )
    assert upload.status_code == 201
    model.say("The root holds the smallest key [1].")
    stream = events(
        client.post(
            f"/api/conversations/{conversation}/ask",
            json={"question": "What is at the root?", "mode": "ask"},
            headers=synced,
        )
    )
    sources = next(d for n, d in stream if n == "sources")["items"]
    assert sources[0]["kind"] == "attachment" and sources[0]["title"] == "notes.md"
    assert "smallest key" in model.requests[0]["messages"][0]["content"]
    bad = client.post(
        f"/api/conversations/{conversation}/attachments",
        files={"file": ("x.exe", b"MZ", "application/octet-stream")},
        headers=synced,
    )
    assert bad.status_code == 422


def test_conversations_are_private(client, synced, db):
    conversation = _conversation(client, synced)
    from termpilot.db.models import Conversation, Student

    db.add(Student(id=31, display_name="Other"))
    db.flush()
    other = Conversation(student_id=31, title="Theirs")
    db.add(other)
    db.commit()
    assert client.get(f"/api/conversations/{other.id}", headers=synced).status_code == 404
    assert client.post(f"/api/conversations/{other.id}/ask", json={"question": "x"}, headers=synced).status_code == 404
    listed = [item["id"] for item in client.get("/api/conversations", headers=synced).json()]
    assert listed == [conversation]
    assert db.scalars(select(PendingAction)).all() == []
