import pytest

from termpilot.errors import Conflict, InvalidInput
from termpilot.mail.parsing import normalise_recipients, parse_message
from termpilot.services.workspace import Workspace


@pytest.fixture
def space(settings):
    return Workspace(settings, 7)


@pytest.mark.parametrize(
    "path", ["../escape.txt", "/etc/passwd", "C:/Windows/x.txt", "a/../../b.txt", ".trash/old.txt"]
)
def test_paths_outside_the_workspace_are_rejected(space, path):
    with pytest.raises(InvalidInput):
        space.resolve(path)


def test_proposed_edit_applies_only_to_the_unchanged_file(space):
    space.save_upload("notes", "todo.md", b"- buy coffee\n")
    summary, preview, payload = space.propose("append", {"path": "notes/todo.md", "content": "- revise heaps"})
    assert summary == "Append to notes/todo.md" and "revise heaps" in preview
    assert space.apply(payload) == "Appended to notes/todo.md."
    assert space.read_text("notes/todo.md")[0] == "- buy coffee\n- revise heaps"

    _, _, stale = space.propose("replace", {"path": "notes/todo.md", "old_text": "coffee", "new_text": "tea"})
    (space.root / "notes" / "todo.md").write_text("edited elsewhere", encoding="utf-8")
    with pytest.raises(Conflict):
        space.apply(stale)


def test_batch_rename_is_all_or_nothing(space):
    for name in ("notes-a.md", "notes-b.md"):
        space.save_upload("algorithms", name, b"# notes")
    _, preview, payload = space.propose(
        "rename",
        {
            "renames": [
                {"from": "algorithms/notes-a.md", "to": "algorithms/week05-heaps.md"},
                {"from": "algorithms/notes-b.md", "to": "algorithms/week06-graphs.md"},
            ]
        },
    )
    assert preview.count("->") == 2
    (space.root / "algorithms" / "notes-b.md").unlink()  # disappears before approval
    with pytest.raises(Conflict):
        space.apply(payload)
    assert (space.root / "algorithms" / "notes-a.md").exists()  # first rename was rolled back


def test_rename_targets_must_be_unique_and_new(space):
    space.save_upload(".", "a.txt", b"a")
    space.save_upload(".", "b.txt", b"b")
    with pytest.raises(Conflict):
        space.propose("rename", {"renames": [{"from": "a.txt", "to": "b.txt"}]})
    with pytest.raises(Conflict):
        space.propose("rename", {"renames": [{"from": "a.txt", "to": "c.txt"}, {"from": "b.txt", "to": "c.txt"}]})


def test_delete_moves_files_to_the_trash(space):
    space.save_upload(".", "old.md", b"x")
    space.remove("old.md")
    assert [item.path for item in space.listing()] == []
    assert any((space.root / ".trash").rglob("old.md"))


def test_workspace_api_upload_download_delete(client, auth):
    uploaded = client.post(
        "/api/workspace/files?folder=reports", files={"file": ("lab.md", b"# Lab", "text/markdown")}, headers=auth
    )
    assert uploaded.status_code == 201 and uploaded.json()["path"] == "reports/lab.md"
    duplicate = client.post(
        "/api/workspace/files?folder=reports", files={"file": ("lab.md", b"x", "text/markdown")}, headers=auth
    )
    assert duplicate.status_code == 409
    listing = client.get("/api/workspace/files", headers=auth).json()
    assert {item["path"] for item in listing["files"]} == {"reports", "reports/lab.md"}
    assert client.get("/api/workspace/download?path=reports/lab.md", headers=auth).content == b"# Lab"
    assert client.get("/api/workspace/download?path=../../etc/passwd", headers=auth).status_code == 422
    assert client.delete("/api/workspace/files?path=reports/lab.md", headers=auth).status_code == 204


def test_mailbox_flow_in_demo_mode(client, auth, model):
    assert client.get("/api/mail/account", headers=auth).json()["connected"] is False
    assert client.get("/api/mail/messages", headers=auth).status_code == 404
    rejected = client.put(
        "/api/mail/account", json={"provider": "demo", "address": "me@example.edu", "secret": "nope"}, headers=auth
    )
    assert rejected.status_code == 401
    account = client.put(
        "/api/mail/account", json={"provider": "demo", "address": "me@example.edu", "secret": "demo"}, headers=auth
    ).json()
    assert account["connected"] is True

    first = client.post("/api/mail/sync", json={}, headers=auth).json()
    second = client.post("/api/mail/sync", json={}, headers=auth).json()
    assert (first["added"], second["added"], second["updated"]) == (4, 0, 4)
    unread = client.get("/api/mail/messages?unread_only=true", headers=auth).json()
    assert len(unread) == 2
    found = client.get("/api/mail/messages?q=drop", headers=auth).json()
    assert [item["subject"] for item in found] == ["Course drop deadline this Friday"]

    model.json_replies = [
        {"tasks": [{"title": "Drop request", "due_at": "2026-10-16T17:00", "category": "admin"}, {"title": "no date"}]}
    ]
    candidates = client.post(f"/api/mail/messages/{found[0]['id']}/tasks", headers=auth).json()
    assert candidates == [
        {"title": "Drop request", "due_at": "2026-10-16T17:00:00+08:00", "category": "admin", "notes": None}
    ]

    sent = client.post(
        "/api/mail/send", json={"to": ["prof@example.edu"], "subject": "Question", "body": "Hello"}, headers=auth
    )
    assert sent.status_code == 200 and sent.json()["message_id"].startswith("<demo-")
    invalid = client.post("/api/mail/send", json={"to": ["not-an-address"], "subject": "x", "body": "y"}, headers=auth)
    assert invalid.status_code == 422
    assert client.delete("/api/mail/account", headers=auth).status_code == 204
    assert client.get("/api/briefing", headers=auth).json()["unread_mail"] == 0


def test_message_parsing():
    raw = (
        b"From: =?utf-8?B?5byg5LiJ?= <zhang@example.edu>\r\nTo: me@example.edu\r\nSubject: =?utf-8?Q?Lab_=E9=80=9A=E7=9F=A5?=\r\n"
        b"Date: Wed, 14 Oct 2026 09:30:00 +0800\r\nMIME-Version: 1.0\r\nContent-Type: text/html; charset=utf-8\r\n\r\n"
        b"<p>Lab moved to <b>Room 402</b>.</p>"
    )
    parsed = parse_message("9", raw, "FLAGS (\\Seen)")
    assert parsed.sender == "张三 <zhang@example.edu>" and parsed.subject == "Lab 通知"
    assert parsed.body_text == "Lab moved to\nRoom 402\n." and parsed.seen is True
    assert parsed.received_at.isoformat() == "2026-10-14T01:30:00+00:00"
    assert normalise_recipients(["A <a@x.io>", "a@x.io", "b@y.org"]) == ["a@x.io", "b@y.org"]
    with pytest.raises(ValueError):
        normalise_recipients(["broken@"])
