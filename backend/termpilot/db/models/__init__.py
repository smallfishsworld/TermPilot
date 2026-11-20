"""All mapped classes; importing this package registers them with the metadata."""

from termpilot.db.models.academics import CourseGrade, CourseMaterial, CreditSummary
from termpilot.db.models.assistant import Attachment, Conversation, PendingAction, Turn
from termpilot.db.models.library import LibraryDocument
from termpilot.db.models.mail import MailItem, MailLink
from termpilot.db.models.planner import Task, TimetableEntry
from termpilot.db.models.student import CampusLink, Student, SyncRun

__all__ = [
    "Attachment",
    "CampusLink",
    "Conversation",
    "CourseGrade",
    "CourseMaterial",
    "CreditSummary",
    "LibraryDocument",
    "MailItem",
    "MailLink",
    "PendingAction",
    "Student",
    "SyncRun",
    "Task",
    "TimetableEntry",
    "Turn",
]
