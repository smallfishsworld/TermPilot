from datetime import datetime

from sqlalchemy import delete, select

from termpilot.db.models import CampusLink, Task, TimetableEntry
from tests.conftest import CAMPUS_TZ, FROZEN_AT


def test_sync_imports_every_source(client, synced):
    runs = client.get("/api/sync/runs", headers=synced).json()
    assert runs[0]["outcome"] == "ok"
    assert {step["source"] for step in runs[0]["steps"]} == {
        "profile",
        "grades",
        "timetable",
        "deadlines",
        "coursework",
        "materials",
    }
    timetable = client.get("/api/timetable", headers=synced).json()
    assert timetable["term"]["label"] == "Fall 2026" and timetable["term"]["current_week"] == 6
    assert len(timetable["entries"]) == 8
    academics = client.get("/api/academics", headers=synced).json()
    assert academics["gpa"] == 3.72 and academics["credits_total"] == 89.5
    assert len(client.get("/api/academics/materials", headers=synced).json()) == 6
    assert client.get("/api/me/photo", headers=synced).json()["data_url"].startswith("data:image/png;base64,")


def test_resync_keeps_student_choices_and_custom_entries(client, synced):
    tasks = client.get("/api/tasks", headers=synced).json()
    first = tasks[0]
    client.patch(f"/api/tasks/{first['id']}", json={"done": True, "priority": "high"}, headers=synced)
    client.post(
        "/api/timetable",
        json={"title": "Choir rehearsal", "weekday": 6, "starts_at": "10:00", "ends_at": "11:30"},
        headers=synced,
    )
    client.post("/api/sync", json={"sources": ["timetable", "deadlines"]}, headers=synced)
    after = {task["id"]: task for task in client.get("/api/tasks", headers=synced).json()}
    assert len(after) == len(tasks)
    assert after[first["id"]]["done"] is True and after[first["id"]]["priority"] == "high"
    titles = [entry["title"] for entry in client.get("/api/timetable", headers=synced).json()["entries"]]
    assert titles.count("Choir rehearsal") == 1 and titles.count("Linear Algebra") == 1


def test_sync_without_campus_session_reports_every_step(client, synced, db):
    db.execute(delete(CampusLink))
    db.commit()
    run = client.post("/api/sync", json={"sources": ["profile", "timetable"]}, headers=synced).json()
    assert run["outcome"] == "failed"
    assert all("Sign in again" in step["message"] for step in run["steps"])


def test_timetable_validation_and_ownership(client, synced, db):
    bad = client.post(
        "/api/timetable", json={"title": "X", "weekday": 2, "starts_at": "11:00", "ends_at": "10:00"}, headers=synced
    )
    assert bad.status_code == 422
    foreign = TimetableEntry(
        student_id=999, title="Not yours", weekday=1, starts_at=datetime.now().time(), ends_at=datetime.now().time()
    )
    from termpilot.db.models import Student

    db.add(Student(id=999, display_name="Someone else"))
    db.flush()
    db.add(foreign)
    db.commit()
    assert client.patch(f"/api/timetable/{foreign.id}", json={"title": "Mine now"}, headers=synced).status_code == 404
    assert client.delete(f"/api/timetable/{foreign.id}", headers=synced).status_code == 404


def test_editing_an_imported_course_protects_it_from_the_next_sync(client, synced):
    entries = client.get("/api/timetable", headers=synced).json()["entries"]
    course = next(entry for entry in entries if entry["title"] == "Computer Networks")
    client.patch(f"/api/timetable/{course['id']}", json={"location": "Online"}, headers=synced)
    client.post("/api/sync", json={"sources": ["timetable"]}, headers=synced)
    titles = [entry["title"] for entry in client.get("/api/timetable", headers=synced).json()["entries"]]
    assert titles.count("Computer Networks") == 2  # the edited copy plus the fresh import


def test_clashes_are_reported(client, synced):
    client.post(
        "/api/timetable",
        json={"title": "Club meeting", "weekday": 1, "starts_at": "11:00", "ends_at": "12:30", "weeks": [6, 7]},
        headers=synced,
    )
    clashes = client.get("/api/timetable", headers=synced).json()["clashes"]
    assert len(clashes) == 1
    assert clashes[0]["weeks"] == [6, 7]
    assert "Data Structures and Algorithms" in clashes[0]["description"]


def test_briefing_summarises_today(client, synced):
    briefing = client.get("/api/briefing", headers=synced).json()
    assert briefing["term"]["current_week"] == 6
    assert [entry["title"] for entry in briefing["classes_today"]] == ["Data Structures and Algorithms (Lab)"]
    assert {task["title"] for task in briefing["due_soon"]} == {"Problem Set 6: Graph Traversal"}
    assert [task["title"] for task in briefing["overdue"]] == ["Reading response 4"]
    assert briefing["classes_tomorrow"] == 1  # Thursday of an even week: networks, but no odd-week algebra


def test_task_crud_requires_aware_due_dates(client, synced):
    naive = client.post("/api/tasks", json={"title": "Essay", "due_at": "2026-10-20T12:00:00"}, headers=synced)
    assert naive.status_code == 422
    created = client.post(
        "/api/tasks",
        json={"title": "Essay", "due_at": "2026-10-20T12:00:00+08:00", "effort_minutes": 120},
        headers=synced,
    ).json()
    assert created["origin"] == "manual" and created["effort_minutes"] == 120
    assert client.delete(f"/api/tasks/{created['id']}", headers=synced).status_code == 204
    assert client.patch(f"/api/tasks/{created['id']}", json={"done": True}, headers=synced).status_code == 404


def test_study_planner_avoids_classes_and_deadlines(client, synced, db):
    blocks = client.post("/api/planner/suggestions", json={"days": 5, "block_minutes": 90}, headers=synced).json()
    assert blocks, "expected suggestions for the open demo tasks"
    entries = db.scalars(select(TimetableEntry)).all()
    tasks = {task.id: task for task in db.scalars(select(Task))}
    for block in blocks:
        day = datetime.fromisoformat(block["day"]).date()
        start = datetime.strptime(block["starts_at"], "%H:%M").time()
        end = datetime.strptime(block["ends_at"], "%H:%M").time()
        assert datetime.combine(day, end, CAMPUS_TZ) <= tasks[block["task_id"]].due_at
        assert datetime.combine(day, start, CAMPUS_TZ) >= FROZEN_AT
        week = (day - datetime(2026, 9, 7).date()).days // 7 + 1
        for entry in entries:
            if entry.weekday == day.isoweekday() and (not entry.weeks or week in entry.weeks):
                assert end <= entry.starts_at or start >= entry.ends_at, (block, entry.title)

    accepted = client.post("/api/planner/accept", json={"blocks": blocks[:2]}, headers=synced).json()
    assert {entry["kind"] for entry in accepted} == {"study"} and len(accepted[0]["weeks"]) == 1
    again = client.post("/api/planner/suggestions", json={"days": 5, "block_minutes": 90}, headers=synced).json()
    planned_task = blocks[0]["task_id"]
    before = sum(1 for b in blocks if b["task_id"] == planned_task)
    assert sum(1 for b in again if b["task_id"] == planned_task) < before


def test_calendar_feed(client, synced):
    link = client.get("/api/calendar/link", headers=synced).json()
    token = link["url"].split("token=")[1]
    feed = client.get(f"/api/calendar/feed.ics?token={token}")
    assert feed.status_code == 200 and feed.headers["content-type"].startswith("text/calendar")
    text = feed.text
    assert text.startswith("BEGIN:VCALENDAR\r\n") and text.endswith("END:VCALENDAR\r\n")
    assert text.count("BEGIN:VEVENT") == text.count("END:VEVENT") > 100
    assert "SUMMARY:Due: Problem Set 6: Graph Traversal" in text
    assert all(len(line.encode()) <= 75 for line in text.split("\r\n"))
    assert "Teaching Building 1\\, Room 203" in text  # commas are escaped
    assert client.get("/api/calendar/feed.ics?token=invalid").status_code == 401
    client.delete("/api/auth/session", headers=synced)
    assert client.get(f"/api/calendar/feed.ics?token={token}").status_code == 401


def test_planner_outside_term_returns_nothing(client):
    from termpilot import clock

    clock.freeze(datetime(2027, 1, 20, 9, 0, tzinfo=CAMPUS_TZ))
    token = client.post("/api/auth/session", json={"username": "demo", "password": "demo"}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.post("/api/planner/suggestions", json={}, headers=headers).json() == []
    briefing = client.get("/api/briefing", headers=headers).json()
    assert briefing["term"]["in_session"] is False
    assert any("not in session" in tip for tip in briefing["tips"])
