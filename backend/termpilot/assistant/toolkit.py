"""Tools the agent can call.

Each tool declares a JSON schema for its arguments and returns JSON-ready data
for the model plus a one-line summary for the progress trace. Reading tools
act immediately. Tools that would change something only create a pending
approval through :mod:`termpilot.assistant.approvals`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from termpilot.assistant import approvals, web
from termpilot.campus.periods import describe_weeks
from termpilot.clock import local_today, utcnow
from termpilot.db.models import CourseGrade, CreditSummary, PendingAction, Student, Task, TimetableEntry
from termpilot.errors import AppError, InvalidInput
from termpilot.knowledge.index import LibraryIndex
from termpilot.services import mailbox, study_planner, tasks, timetable
from termpilot.services.term_calendar import current_term
from termpilot.services.workspace import Workspace
from termpilot.settings import Settings

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


@dataclass
class ToolContext:
    db: Session
    settings: Settings
    student: Student
    conversation_id: str | None = None
    sources: list[dict[str, Any]] = field(default_factory=list)
    proposals: list[PendingAction] = field(default_factory=list)

    def cite(self, kind: str, title: str, excerpt: str, url: str | None = None) -> int:
        index = len(self.sources) + 1
        self.sources.append({"index": index, "kind": kind, "title": title, "excerpt": excerpt[:600], "url": url})
        return index

    def propose(self, **fields: Any) -> PendingAction:
        action = approvals.propose(self.db, self.settings, self.student, conversation_id=self.conversation_id, **fields)
        self.proposals.append(action)
        return action


@dataclass
class ToolOutcome:
    content: Any
    summary: str


@dataclass(frozen=True)
class Tool:
    name: str
    label: str
    description: str
    parameters: dict[str, Any]
    run: Callable[[ToolContext, dict[str, Any]], ToolOutcome]

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {"name": self.name, "description": self.description, "parameters": self.parameters},
        }


REGISTRY: dict[str, Tool] = {}


def tool(
    name: str, label: str, description: str, properties: dict[str, Any] | None = None, required: list[str] | None = None
):  # type: ignore[no-untyped-def]
    def register(
        function: Callable[[ToolContext, dict[str, Any]], ToolOutcome],
    ) -> Callable[[ToolContext, dict[str, Any]], ToolOutcome]:
        REGISTRY[name] = Tool(
            name=name,
            label=label,
            description=description,
            parameters={"type": "object", "properties": properties or {}, "required": required or []},
            run=function,
        )
        return function

    return register


# --- formatting helpers ------------------------------------------------------------
def _local(ctx: ToolContext, value: datetime) -> str:
    return value.astimezone(ctx.settings.tz).strftime("%Y-%m-%d %H:%M (%a)")


def _entry(entry: TimetableEntry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "title": entry.title,
        "kind": entry.kind,
        "weekday": WEEKDAYS[entry.weekday - 1],
        "time": f"{entry.starts_at:%H:%M}-{entry.ends_at:%H:%M}",
        "weeks": describe_weeks(entry.weeks),
        "location": entry.location,
        "instructor": entry.instructor,
    }


def _task(ctx: ToolContext, task: Task) -> dict[str, Any]:
    return {
        "id": task.id,
        "title": task.title,
        "due": _local(ctx, task.due_at),
        "course": task.course,
        "category": task.category,
        "done": task.done,
        "priority": task.priority,
        "effort_minutes": tasks.effort_of(task),
    }


def _parse_day(ctx: ToolContext, value: str | None) -> date | None:
    if not value:
        return None
    today = local_today(ctx.settings.tz)
    word = value.strip().lower()
    if word in {"today", "今天"}:
        return today
    if word in {"tomorrow", "明天"}:
        return today + timedelta(days=1)
    try:
        return date.fromisoformat(word[:10])
    except ValueError as exc:
        raise InvalidInput(f"Use a date like {today.isoformat()} or the word today.") from exc


def _parse_local_datetime(ctx: ToolContext, value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.strip().replace(" ", "T"))
    except ValueError as exc:
        raise InvalidInput("Use an ISO date and time such as 2026-05-01T23:59.") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=ctx.settings.tz)


# --- reading tools ------------------------------------------------------------------
@tool("get_profile", "Reading your profile", "The student's profile, GPA, rank, credits and the current teaching week.")
def get_profile(ctx: ToolContext, args: dict[str, Any]) -> ToolOutcome:
    student = ctx.student
    term = current_term(ctx.settings, student)
    credits = ctx.db.get(CreditSummary, student.id)
    data = {
        "name": student.display_name,
        "department": student.department,
        "class": student.class_name,
        "college": student.college,
        "email": student.email,
        "gpa": student.gpa,
        "rank": student.gpa_rank,
        "credits_total": credits.total if credits else None,
        "credits_by_category": credits.by_category if credits else {},
        "interests": student.interests,
        "term": term.label,
        "teaching_week": term.week_of(local_today(ctx.settings.tz)),
        "term_starts": term.start.isoformat(),
    }
    return ToolOutcome(data, "Loaded your profile")


@tool(
    "list_timetable",
    "Checking your timetable",
    "Timetable entries. With `day` only the entries taking place that day are returned.",
    {
        "day": {"type": "string", "description": "today, tomorrow or YYYY-MM-DD"},
        "weekday": {"type": "integer", "minimum": 1, "maximum": 7, "description": "1 = Monday"},
        "query": {"type": "string", "description": "Filter by title, location or instructor"},
    },
)
def list_timetable(ctx: ToolContext, args: dict[str, Any]) -> ToolOutcome:
    entries = timetable.list_entries(ctx.db, ctx.student)
    day = _parse_day(ctx, args.get("day"))
    if day is not None:
        entries = timetable.entries_on(entries, day, current_term(ctx.settings, ctx.student, day))
    if args.get("weekday"):
        entries = [entry for entry in entries if entry.weekday == int(args["weekday"])]
    needle = str(args.get("query") or "").strip().lower()
    if needle:
        entries = [
            entry
            for entry in entries
            if needle in " ".join(filter(None, [entry.title, entry.location, entry.instructor])).lower()
        ]
    scope = f" on {day.isoformat()}" if day else ""
    return ToolOutcome([_entry(entry) for entry in entries], f"Found {len(entries)} timetable entries{scope}")


@tool(
    "list_tasks",
    "Looking at your tasks",
    "Tasks and deadlines, sorted by due date.",
    {
        "status": {"type": "string", "enum": ["open", "done", "all"], "default": "open"},
        "within_days": {
            "type": "integer",
            "minimum": 1,
            "maximum": 120,
            "description": "Only tasks due within this many days",
        },
        "query": {"type": "string"},
    },
)
def list_tasks(ctx: ToolContext, args: dict[str, Any]) -> ToolOutcome:
    status = args.get("status") or "open"
    due_before = utcnow() + timedelta(days=int(args["within_days"])) if args.get("within_days") else None
    found = tasks.list_tasks(ctx.db, ctx.student, status=status, due_before=due_before, limit=100)
    needle = str(args.get("query") or "").strip().lower()
    if needle:
        found = [task for task in found if needle in f"{task.title} {task.course or ''}".lower()]
    return ToolOutcome([_task(ctx, task) for task in found], f"Found {len(found)} {status} tasks")


@tool(
    "get_grades",
    "Reading your grades",
    "Graded coursework items from the learning platform, plus GPA and rank.",
    {"course": {"type": "string", "description": "Optional course name filter"}},
)
def get_grades(ctx: ToolContext, args: dict[str, Any]) -> ToolOutcome:
    query = select(CourseGrade).where(CourseGrade.student_id == ctx.student.id)
    rows = list(ctx.db.scalars(query.order_by(CourseGrade.course_title, CourseGrade.item)))
    needle = str(args.get("course") or "").strip().lower()
    if needle:
        rows = [row for row in rows if needle in row.course_title.lower()]
    data = {
        "gpa": ctx.student.gpa,
        "rank": ctx.student.gpa_rank,
        "items": [{"course": row.course_title, "item": row.item, "score": row.score} for row in rows],
    }
    return ToolOutcome(data, f"Found {len(rows)} graded items")


@tool(
    "search_library",
    "Searching your documents",
    "Search the student's uploaded documents (lecture notes, handbooks, slides). Cite results as [n].",
    {"query": {"type": "string"}},
    ["query"],
)
def search_library(ctx: ToolContext, args: dict[str, Any]) -> ToolOutcome:
    passages = LibraryIndex(ctx.student.id).search(str(args["query"]), top_k=5)
    data = [
        {
            "cite": ctx.cite("library", passage.document, passage.text),
            "document": passage.document,
            "text": passage.text,
        }
        for passage in passages
    ]
    return ToolOutcome(data, f"Found {len(data)} passages")


@tool(
    "web_search",
    "Searching the web",
    "Search the public web for current information. Cite results as [n].",
    {"query": {"type": "string"}},
    ["query"],
)
def web_search(ctx: ToolContext, args: dict[str, Any]) -> ToolOutcome:
    found = web.search(ctx.settings, str(args["query"]), count=6)
    data = [
        {"cite": ctx.cite("web", item.title, item.snippet, item.url), "title": item.title, "snippet": item.snippet}
        for item in found.results
    ]
    return ToolOutcome(data, f"Found {len(data)} web results")


@tool(
    "search_mail",
    "Searching your mailbox",
    "Search synchronised email by subject or sender.",
    {
        "query": {"type": "string"},
        "unread_only": {"type": "boolean", "default": False},
        "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 8},
    },
)
def search_mail(ctx: ToolContext, args: dict[str, Any]) -> ToolOutcome:
    messages = mailbox.list_messages(
        ctx.db,
        ctx.student,
        query=args.get("query") or None,
        unread_only=bool(args.get("unread_only")),
        limit=int(args.get("limit") or 8),
    )
    data = [
        {
            "id": item.id,
            "subject": item.subject,
            "from": item.sender,
            "received": _local(ctx, item.received_at) if item.received_at else None,
            "preview": item.preview,
            "unread": not item.seen,
        }
        for item in messages
    ]
    return ToolOutcome(data, f"Found {len(data)} messages")


@tool(
    "read_mail",
    "Reading an email",
    "Full text of one email by id.",
    {"message_id": {"type": "integer"}},
    ["message_id"],
)
def read_mail(ctx: ToolContext, args: dict[str, Any]) -> ToolOutcome:
    item = mailbox.get_message(ctx.db, ctx.student, int(args["message_id"]))
    data = {"subject": item.subject, "from": item.sender, "to": item.recipients, "body": (item.body_text or "")[:6000]}
    return ToolOutcome(data, f"Read “{item.subject or '(no subject)'}”")


@tool(
    "list_files",
    "Listing your workspace",
    "Files in the student's private workspace.",
    {"folder": {"type": "string", "default": "."}},
)
def list_files(ctx: ToolContext, args: dict[str, Any]) -> ToolOutcome:
    items = Workspace(ctx.settings, ctx.student.id).listing(str(args.get("folder") or "."), limit=200)
    data = [{"path": item.path, "folder": item.is_dir, "bytes": item.size} for item in items]
    return ToolOutcome(data, f"Found {len(data)} items")


@tool("read_file", "Reading a file", "Read a text file from the workspace.", {"path": {"type": "string"}}, ["path"])
def read_file(ctx: ToolContext, args: dict[str, Any]) -> ToolOutcome:
    content, _ = Workspace(ctx.settings, ctx.student.id).read_text(str(args["path"]))
    return ToolOutcome({"path": args["path"], "content": content}, f"Read {args['path']}")


# --- proposing tools (all changes wait for the student's approval) ---------------------
def _proposed(action: PendingAction) -> ToolOutcome:
    return ToolOutcome(
        {"status": "waiting_for_approval", "proposal_id": action.id, "summary": action.summary},
        f"Proposed: {action.title}",
    )


@tool(
    "plan_study_time",
    "Planning study time",
    "Find free slots around classes for open tasks and propose study blocks. Nothing is booked until the student approves.",
    {
        "days": {"type": "integer", "minimum": 1, "maximum": 14, "default": 7},
        "block_minutes": {"type": "integer", "minimum": 30, "maximum": 180, "default": 90},
    },
)
def plan_study_time(ctx: ToolContext, args: dict[str, Any]) -> ToolOutcome:
    options = study_planner.PlannerOptions(
        days=int(args.get("days") or 7), block_minutes=int(args.get("block_minutes") or 90)
    )
    blocks = study_planner.suggest(ctx.db, ctx.settings, ctx.student, options)
    if not blocks:
        return ToolOutcome({"blocks": []}, "No study blocks needed or no free time found")
    lines = [
        f"{block.day:%a %d %b} {block.starts_at:%H:%M}-{block.ends_at:%H:%M}  {block.task_title}" for block in blocks
    ]
    action = ctx.propose(
        kind="study.schedule",
        title=f"Book {len(blocks)} study block(s)",
        summary=f"Add {len(blocks)} study sessions to your timetable for the next {options.days} days.",
        preview="\n".join(lines),
        payload={
            "blocks": [
                {
                    "task_id": b.task_id,
                    "day": b.day.isoformat(),
                    "starts_at": b.starts_at.isoformat("minutes"),
                    "ends_at": b.ends_at.isoformat("minutes"),
                }
                for b in blocks
            ]
        },
    )
    outcome = _proposed(action)
    outcome.content["blocks"] = lines
    return outcome


@tool(
    "propose_timetable_change",
    "Preparing a timetable change",
    "Propose adding, changing or removing a timetable entry. The student must approve it.",
    {
        "action": {"type": "string", "enum": ["create", "update", "delete"]},
        "entry_id": {"type": "integer", "description": "Required for update and delete"},
        "title": {"type": "string"},
        "kind": {"type": "string", "enum": list(timetable.KINDS)},
        "weekday": {"type": "integer", "minimum": 1, "maximum": 7},
        "starts_at": {"type": "string", "description": "HH:MM"},
        "ends_at": {"type": "string", "description": "HH:MM"},
        "weeks": {"type": "array", "items": {"type": "integer"}, "description": "Teaching weeks; empty for every week"},
        "location": {"type": "string"},
        "notes": {"type": "string"},
    },
    ["action"],
)
def propose_timetable_change(ctx: ToolContext, args: dict[str, Any]) -> ToolOutcome:
    action = args["action"]
    fields = {
        key: args[key]
        for key in ("title", "kind", "weekday", "starts_at", "ends_at", "weeks", "location", "notes")
        if key in args
    }
    for key in ("starts_at", "ends_at"):
        if key in fields:
            fields[key] = time.fromisoformat(str(fields[key])).isoformat("minutes")
    if action == "create":
        missing = [key for key in ("title", "weekday", "starts_at", "ends_at") if key not in fields]
        if missing:
            raise InvalidInput(f"Missing: {', '.join(missing)}.")
        when = f"{WEEKDAYS[int(fields['weekday']) - 1]} {fields['starts_at']}-{fields['ends_at']}"
        proposal = ctx.propose(
            kind="timetable.create",
            title=f"Add {fields['title']}",
            summary=f"Add {fields['title']} on {when}.",
            preview=None,
            payload={"fields": fields},
        )
        return _proposed(proposal)
    entry = timetable.get_entry(ctx.db, ctx.student, int(args.get("entry_id") or 0))
    if action == "delete":
        proposal = ctx.propose(
            kind="timetable.delete",
            title=f"Remove {entry.title}",
            summary=f"Remove {entry.title} ({WEEKDAYS[entry.weekday - 1]} {entry.starts_at:%H:%M}).",
            payload={"entry_id": entry.id},
        )
        return _proposed(proposal)
    if not fields:
        raise InvalidInput("Say what should change.")
    changes = ", ".join(f"{key} -> {value}" for key, value in fields.items())
    proposal = ctx.propose(
        kind="timetable.update",
        title=f"Change {entry.title}",
        summary=f"Update {entry.title}: {changes}.",
        payload={"entry_id": entry.id, "changes": fields},
    )
    return _proposed(proposal)


@tool(
    "propose_task",
    "Preparing a task",
    "Propose creating a task, editing one, or marking one done. The student must approve it.",
    {
        "action": {"type": "string", "enum": ["create", "update", "complete"]},
        "task_id": {"type": "integer"},
        "title": {"type": "string"},
        "due_at": {"type": "string", "description": "Local date and time, YYYY-MM-DDTHH:MM"},
        "course": {"type": "string"},
        "category": {"type": "string", "description": "assignment, exam, project, personal ..."},
        "priority": {"type": "string", "enum": list(tasks.PRIORITIES)},
        "effort_minutes": {"type": "integer"},
        "notes": {"type": "string"},
    },
    ["action"],
)
def propose_task(ctx: ToolContext, args: dict[str, Any]) -> ToolOutcome:
    fields = {
        key: args[key]
        for key in ("title", "course", "category", "priority", "effort_minutes", "notes")
        if args.get(key) is not None
    }
    if args.get("due_at"):
        fields["due_at"] = _parse_local_datetime(ctx, str(args["due_at"])).isoformat()
    if args["action"] == "create":
        if not fields.get("title") or not fields.get("due_at"):
            raise InvalidInput("A new task needs a title and due_at.")
        due = _local(ctx, datetime.fromisoformat(fields["due_at"]))
        return _proposed(
            ctx.propose(
                kind="task.create",
                title=f"Add task {fields['title']}",
                summary=f"Add {fields['title']}, due {due}.",
                payload={"fields": fields},
            )
        )
    task = tasks.get_task(ctx.db, ctx.student, int(args.get("task_id") or 0))
    if args["action"] == "complete":
        fields = {"done": True}
    if not fields:
        raise InvalidInput("Say what should change.")
    verb = "Mark done" if fields == {"done": True} else "Update"
    return _proposed(
        ctx.propose(
            kind="task.update",
            title=f"{verb}: {task.title}",
            summary=f"{verb} {task.title}.",
            payload={"task_id": task.id, "changes": fields},
        )
    )


@tool(
    "draft_email",
    "Drafting an email",
    "Prepare an email from the connected mailbox. It is only sent after the student approves the draft. Never invent addresses.",
    {
        "to": {"type": "array", "items": {"type": "string"}},
        "cc": {"type": "array", "items": {"type": "string"}},
        "subject": {"type": "string"},
        "body": {"type": "string"},
    },
    ["to", "subject", "body"],
)
def draft_email(ctx: ToolContext, args: dict[str, Any]) -> ToolOutcome:
    mailbox.require_link(ctx.db, ctx.student)
    message = mailbox.compose(
        args.get("to") or [], args.get("cc") or [], [], str(args.get("subject") or ""), str(args.get("body") or "")
    )
    proposal = ctx.propose(
        kind="email.send",
        title=f"Send “{message.subject}”",
        summary=f"Send to {', '.join(message.to)}" + (f", cc {', '.join(message.cc)}" if message.cc else ""),
        preview=message.body[:2000],
        payload={"to": message.to, "cc": message.cc, "bcc": [], "subject": message.subject, "body": message.body},
    )
    return _proposed(proposal)


@tool(
    "propose_file_change",
    "Preparing a file change",
    "Propose writing, appending to, editing or deleting a text file in the workspace. Needs approval.",
    {
        "operation": {"type": "string", "enum": ["write", "append", "replace", "delete"]},
        "path": {"type": "string"},
        "content": {"type": "string"},
        "old_text": {"type": "string"},
        "new_text": {"type": "string"},
    },
    ["operation", "path"],
)
def propose_file_change(ctx: ToolContext, args: dict[str, Any]) -> ToolOutcome:
    summary, preview, payload = Workspace(ctx.settings, ctx.student.id).propose(str(args["operation"]), args)
    return _proposed(ctx.propose(kind="files.change", title=summary, summary=summary, preview=preview, payload=payload))


@tool(
    "propose_rename",
    "Preparing to rename files",
    "Propose renaming several workspace files at once, e.g. to a submission naming scheme. Needs approval.",
    {
        "renames": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"from": {"type": "string"}, "to": {"type": "string"}},
                "required": ["from", "to"],
            },
        }
    },
    ["renames"],
)
def propose_rename(ctx: ToolContext, args: dict[str, Any]) -> ToolOutcome:
    summary, preview, payload = Workspace(ctx.settings, ctx.student.id).propose("rename", args)
    return _proposed(ctx.propose(kind="files.change", title=summary, summary=summary, preview=preview, payload=payload))


def available_tools(ctx: ToolContext) -> list[Tool]:
    """Tools whose backing service is configured for this deployment and student."""
    hidden: set[str] = set()
    if not ctx.settings.web_search_enabled:
        hidden.add("web_search")
    if not ctx.settings.embeddings_enabled:
        hidden.add("search_library")
    if mailbox.get_link(ctx.db, ctx.student) is None:
        hidden |= {"search_mail", "read_mail", "draft_email"}
    return [item for name, item in REGISTRY.items() if name not in hidden]


def run_tool(ctx: ToolContext, name: str, args: dict[str, Any]) -> tuple[ToolOutcome, bool]:
    """Execute a tool; errors become a message for the model instead of an exception."""
    item = REGISTRY.get(name)
    if item is None:
        return ToolOutcome({"error": f"Unknown tool {name}"}, f"Unknown tool {name}"), False
    try:
        return item.run(ctx, args), True
    except AppError as exc:
        ctx.db.rollback()
        return ToolOutcome({"error": exc.message}, exc.message), False
    except (KeyError, TypeError, ValueError) as exc:
        ctx.db.rollback()
        return ToolOutcome({"error": f"Invalid arguments: {exc}"}, "The tool arguments were invalid"), False
