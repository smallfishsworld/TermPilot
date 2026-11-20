"""Conversations, streamed answers, attachments and approvals."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from termpilot.api import schemas
from termpilot.api.deps import AppSettings, CurrentStudent, DbSession, Model
from termpilot.assistant import approvals
from termpilot.assistant.runner import AnswerStream, Question
from termpilot.db.models import Attachment, PendingAction, Turn
from termpilot.services import conversations

router = APIRouter(tags=["assistant"])

SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


@router.get("/conversations", response_model=list[schemas.ConversationView])
def list_conversations(
    student: CurrentStudent, db: DbSession, q: str | None = Query(default=None, max_length=200)
) -> list[schemas.ConversationView]:
    return [
        schemas.ConversationView(
            id=conversation.id,
            title=conversation.title,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            turn_count=count,
        )
        for conversation, count in conversations.list_conversations(db, student, q)
    ]


@router.post("/conversations", response_model=schemas.ConversationView, status_code=status.HTTP_201_CREATED)
def create_conversation(
    body: schemas.ConversationCreate, student: CurrentStudent, db: DbSession
) -> schemas.ConversationView:
    conversation = conversations.create(db, student, body.title)
    return schemas.ConversationView.model_validate(conversation)


@router.get("/conversations/{conversation_id}", response_model=schemas.ConversationDetail)
def conversation_detail(conversation_id: str, student: CurrentStudent, db: DbSession) -> schemas.ConversationDetail:
    conversation = conversations.get(db, student, conversation_id)
    turns = list(db.scalars(select(Turn).where(Turn.conversation_id == conversation.id).order_by(Turn.created_at)))
    proposals = list(
        db.scalars(
            select(PendingAction)
            .where(PendingAction.conversation_id == conversation.id)
            .order_by(PendingAction.created_at)
        )
    )
    view = schemas.ConversationView.model_validate(conversation)
    view.turn_count = len(turns)
    return schemas.ConversationDetail(
        conversation=view,
        turns=[schemas.TurnView.model_validate(turn) for turn in turns],
        attachments=[schemas.AttachmentView.model_validate(item) for item in conversation.attachments],
        approvals=[schemas.ApprovalView.model_validate(item) for item in proposals],
    )


@router.patch("/conversations/{conversation_id}", response_model=schemas.ConversationView)
def rename_conversation(
    conversation_id: str, body: schemas.ConversationRename, student: CurrentStudent, db: DbSession
) -> schemas.ConversationView:
    return schemas.ConversationView.model_validate(conversations.rename(db, student, conversation_id, body.title))


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: str, student: CurrentStudent, db: DbSession) -> Response:
    conversations.delete(db, student, conversation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/conversations/{conversation_id}/ask")
def ask(
    conversation_id: str,
    body: schemas.AskRequest,
    student: CurrentStudent,
    db: DbSession,
    settings: AppSettings,
    model: Model,
) -> StreamingResponse:
    conversations.get(db, student, conversation_id)  # 404 before the stream starts
    stream = AnswerStream(
        settings, model, student.id, conversation_id, Question(body.question.strip(), body.mode, body.deep_think)
    )
    return StreamingResponse(iter(stream), media_type="text/event-stream", headers=SSE_HEADERS)


@router.post(
    "/conversations/{conversation_id}/attachments",
    response_model=schemas.AttachmentView,
    status_code=status.HTTP_201_CREATED,
)
def attach(
    conversation_id: str, file: UploadFile, student: CurrentStudent, db: DbSession, settings: AppSettings
) -> Attachment:
    data = file.file.read(settings.upload_max_mb * 1024 * 1024 + 1)
    return conversations.attach(db, settings, student, conversation_id, file.filename or "attachment.txt", data)


@router.delete("/conversations/{conversation_id}/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def detach(conversation_id: str, attachment_id: int, student: CurrentStudent, db: DbSession) -> Response:
    conversations.detach(db, student, conversation_id, attachment_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/approvals", response_model=list[schemas.ApprovalView])
def list_approvals(
    student: CurrentStudent, db: DbSession, state: Literal["pending", "all"] = "pending"
) -> list[PendingAction]:
    return approvals.list_actions(db, student, status="pending" if state == "pending" else None)


@router.post("/approvals/{action_id}/decision", response_model=schemas.ApprovalView)
def decide(
    action_id: str, body: schemas.DecisionRequest, student: CurrentStudent, db: DbSession, settings: AppSettings
) -> PendingAction:
    return approvals.decide(db, settings, student, action_id, body.approve)
