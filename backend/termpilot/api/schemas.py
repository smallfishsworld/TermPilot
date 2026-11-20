"""Request and response models of the HTTP API."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator

ClockTime = Annotated[time, PlainSerializer(lambda value: value.strftime("%H:%M"), return_type=str)]


class View(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- accounts ---------------------------------------------------------------------
class SignInRequest(BaseModel):
    username: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=1, max_length=200)


class StudentView(View):
    id: int
    display_name: str
    pinyin_name: str | None
    email: str | None
    phone: str | None
    gender: str | None
    birth_date: date | None
    college: str | None
    department: str | None
    class_name: str | None
    dormitory: str | None
    gpa: float | None
    gpa_rank: str | None
    interests: str | None
    term_start: date | None
    is_demo: bool


class SessionView(BaseModel):
    token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    first_visit: bool
    student: StudentView


class PreferencesUpdate(BaseModel):
    interests: str | None = Field(default=None, max_length=2000)
    term_start: date | None = None
    clear_term_start: bool = False


class TermView(BaseModel):
    today: date  # campus-local date, which may differ from the browser's
    label: str
    academic_year: str
    start: date
    end: date
    weeks: int
    current_week: int
    in_session: bool


class FeaturesView(BaseModel):
    demo_mode: bool
    assistant: bool
    library: bool
    web_search: bool


class PhotoView(BaseModel):
    data_url: str | None


# --- timetable and tasks ----------------------------------------------------------
class EntryView(View):
    id: int
    title: str
    kind: str
    origin: str
    weekday: int
    starts_at: ClockTime
    ends_at: ClockTime
    first_period: int | None
    last_period: int | None
    weeks: list[int]
    week_label: str | None
    location: str | None
    instructor: str | None
    notes: str | None
    color: str | None
    task_id: int | None


class EntryInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    kind: Literal["course", "study", "activity", "meeting", "other"] = "activity"
    weekday: int = Field(ge=1, le=7)
    starts_at: time
    ends_at: time
    weeks: list[int] = Field(default_factory=list)
    location: str | None = Field(default=None, max_length=160)
    instructor: str | None = Field(default=None, max_length=160)
    notes: str | None = Field(default=None, max_length=2000)
    color: str | None = Field(default=None, max_length=16)


class EntryPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    kind: Literal["course", "study", "activity", "meeting", "other"] | None = None
    weekday: int | None = Field(default=None, ge=1, le=7)
    starts_at: time | None = None
    ends_at: time | None = None
    weeks: list[int] | None = None
    location: str | None = None
    instructor: str | None = None
    notes: str | None = None
    color: str | None = None


class ClashView(BaseModel):
    first_id: int
    second_id: int
    weekday: int
    weeks: list[int]
    starts_at: ClockTime
    ends_at: ClockTime
    description: str


class TimetableView(BaseModel):
    term: TermView
    entries: list[EntryView]
    clashes: list[ClashView]


class TaskView(View):
    id: int
    title: str
    due_at: datetime
    course: str | None
    category: str | None
    origin: str
    done: bool
    priority: str
    effort_minutes: int | None
    notes: str | None
    color: str | None


class TaskInput(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    due_at: datetime
    course: str | None = Field(default=None, max_length=200)
    category: str | None = Field(default=None, max_length=40)
    priority: Literal["low", "normal", "high"] = "normal"
    effort_minutes: int | None = Field(default=None, ge=1, le=6000)
    notes: str | None = Field(default=None, max_length=4000)
    color: str | None = Field(default=None, max_length=16)

    @field_validator("due_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("include a time zone offset, e.g. 2026-05-01T23:59:00+08:00")
        return value


class TaskPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    due_at: datetime | None = None
    course: str | None = None
    category: str | None = None
    done: bool | None = None
    priority: Literal["low", "normal", "high"] | None = None
    effort_minutes: int | None = Field(default=None, ge=1, le=6000)
    notes: str | None = None
    color: str | None = None

    @field_validator("due_at")
    @classmethod
    def _aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("include a time zone offset")
        return value


class PlannerRequest(BaseModel):
    days: int = Field(default=7, ge=1, le=14)
    block_minutes: int = Field(default=90, ge=30, le=180)
    day_start: time = time(8, 0)
    day_end: time = time(22, 0)


class StudyBlockView(BaseModel):
    task_id: int
    task_title: str
    day: date
    week: int
    starts_at: ClockTime
    ends_at: ClockTime


class AcceptBlocksRequest(BaseModel):
    blocks: list[StudyBlockPick] = Field(min_length=1, max_length=40)


class StudyBlockPick(BaseModel):
    task_id: int
    day: date
    starts_at: time
    ends_at: time


AcceptBlocksRequest.model_rebuild()


class BriefingView(BaseModel):
    day: date
    term: TermView
    now: datetime
    classes_today: list[EntryView]
    next_class: EntryView | None
    classes_tomorrow: int
    due_soon: list[TaskView]
    overdue: list[TaskView]
    clashes: list[ClashView]
    unread_mail: int
    pending_approvals: int
    library_documents: int
    last_sync_at: datetime | None
    last_sync_outcome: str | None
    tips: list[str]


class FeedLinkView(BaseModel):
    url: str
    expires_in_days: int


# --- academics -------------------------------------------------------------------------
class GradeItemView(BaseModel):
    item: str
    score: str


class CourseGradesView(BaseModel):
    course: str
    items: list[GradeItemView]


class AcademicsView(BaseModel):
    gpa: float | None
    rank: str | None
    credits_total: float | None
    credits_by_category: dict[str, float]
    credits_refreshed_at: datetime | None
    courses: list[CourseGradesView]


class MaterialView(View):
    id: int
    course_title: str
    section: str | None
    title: str
    url: str


class SyncRequest(BaseModel):
    sources: list[Literal["profile", "grades", "timetable", "deadlines", "coursework", "materials"]] | None = None


class SyncStepView(BaseModel):
    source: str
    ok: bool
    message: str


class SyncRunView(View):
    id: int
    trigger: str
    outcome: str
    started_at: datetime
    finished_at: datetime | None
    steps: list[SyncStepView]


# --- mail ------------------------------------------------------------------------------------
class MailAccountRequest(BaseModel):
    provider: str = Field(default="qq", max_length=20)
    address: str = Field(min_length=3, max_length=255)
    secret: str = Field(min_length=1, max_length=255)


class MailAccountView(BaseModel):
    connected: bool
    provider: str | None = None
    address: str | None = None
    linked_at: datetime | None = None
    last_synced_at: datetime | None = None
    providers: list[str]


class MailSyncRequest(BaseModel):
    folder: str = Field(default="INBOX", max_length=120)
    limit: int = Field(default=30, ge=1, le=100)
    unread_only: bool = False


class MailSyncView(BaseModel):
    folder: str
    fetched: int
    added: int
    updated: int


class MailSummaryView(View):
    id: int
    folder: str
    subject: str | None
    sender: str | None
    received_at: datetime | None
    preview: str | None
    seen: bool
    has_attachments: bool


class MailDetailView(MailSummaryView):
    recipients: str | None
    cc: str | None
    body_text: str | None
    body_html: str | None


class MailSendRequest(BaseModel):
    to: list[str] = Field(min_length=1)
    cc: list[str] = Field(default_factory=list)
    bcc: list[str] = Field(default_factory=list)
    subject: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=50_000)


class MailSentView(BaseModel):
    message_id: str


class TaskCandidateView(BaseModel):
    title: str
    due_at: datetime
    category: str | None
    notes: str | None


# --- assistant ------------------------------------------------------------------------------
class ConversationView(View):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    turn_count: int = 0


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class ConversationRename(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class TurnView(View):
    id: str
    mode: str
    question: str
    answer: str
    reasoning: str | None
    sources: list[dict[str, Any]]
    suggestions: list[str]
    trace: list[dict[str, Any]]
    failed: bool
    created_at: datetime


class AttachmentView(View):
    id: int
    filename: str
    media_type: str
    size_bytes: int
    truncated: bool
    created_at: datetime


class ApprovalView(View):
    id: str
    conversation_id: str | None
    kind: str
    title: str
    summary: str
    preview: str | None
    status: str
    outcome: str | None
    created_at: datetime
    expires_at: datetime
    decided_at: datetime | None


class ConversationDetail(BaseModel):
    conversation: ConversationView
    turns: list[TurnView]
    attachments: list[AttachmentView]
    approvals: list[ApprovalView]


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=8000)
    mode: Literal["ask", "research", "agent"] = "agent"
    deep_think: bool = False


class DecisionRequest(BaseModel):
    approve: bool


# --- library and workspace -------------------------------------------------------------------
class DocumentView(View):
    id: int
    filename: str
    media_type: str
    size_bytes: int
    chunks: int
    status: str
    error: str | None
    created_at: datetime


class LibraryView(BaseModel):
    available: bool
    reason: str | None
    documents: list[DocumentView]


class UploadFailure(BaseModel):
    filename: str
    reason: str


class UploadReport(BaseModel):
    uploaded: list[DocumentView]
    failed: list[UploadFailure]


class StudyAidRequest(BaseModel):
    kind: Literal["summary", "quiz", "flashcards"] = "summary"


class FileView(BaseModel):
    path: str
    is_dir: bool
    size: int
    modified: datetime


class WorkspaceView(BaseModel):
    files: list[FileView]
    usage_bytes: int
    quota_bytes: int


class HealthView(BaseModel):
    status: str
    version: str
    database: bool
    search: bool | None
    assistant: bool
