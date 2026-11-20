"""The document library and the private workspace."""

from __future__ import annotations

from fastapi import APIRouter, Query, Response, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse

from termpilot.api import schemas
from termpilot.api.deps import AppSettings, CurrentStudent, DbSession, Model
from termpilot.api.routes.assistant import SSE_HEADERS
from termpilot.assistant.helpers import stream_study_aid
from termpilot.errors import AppError, InvalidInput
from termpilot.knowledge.index import LibraryIndex
from termpilot.services import library
from termpilot.services.workspace import Workspace

router = APIRouter(tags=["files"])


@router.get("/library/documents", response_model=schemas.LibraryView)
def documents(student: CurrentStudent, db: DbSession, settings: AppSettings) -> schemas.LibraryView:
    reason = None
    if not settings.embeddings_enabled:
        reason = "Set TP_EMBEDDING_API_KEY to enable the document library."
    elif not LibraryIndex(student.id).ready():
        reason = f"The search cluster at {settings.search_url} is not reachable."
    return schemas.LibraryView(
        available=reason is None,
        reason=reason,
        documents=[schemas.DocumentView.model_validate(item) for item in library.list_documents(db, student)],
    )


@router.post("/library/documents", response_model=schemas.UploadReport, status_code=status.HTTP_201_CREATED)
def upload_documents(
    files: list[UploadFile], student: CurrentStudent, db: DbSession, settings: AppSettings
) -> schemas.UploadReport:
    report = schemas.UploadReport(uploaded=[], failed=[])
    for upload in files:
        name = upload.filename or "document"
        try:
            data = upload.file.read(settings.upload_max_mb * 1024 * 1024 + 1)
            document = library.upload(db, settings, student, name, data)
        except AppError as exc:
            db.rollback()
            report.failed.append(schemas.UploadFailure(filename=name, reason=exc.message))
            continue
        if document.status == "failed":
            report.failed.append(schemas.UploadFailure(filename=name, reason=document.error or "Processing failed."))
        else:
            report.uploaded.append(schemas.DocumentView.model_validate(document))
    return report


@router.delete("/library/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: int, student: CurrentStudent, db: DbSession, settings: AppSettings) -> Response:
    library.delete(db, settings, student, document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/library/documents/{document_id}/study-aid")
def study_aid(
    document_id: int, body: schemas.StudyAidRequest, student: CurrentStudent, db: DbSession, model: Model
) -> StreamingResponse:
    document = library.get_document(db, student, document_id)
    text = library.document_text(student, document)
    return StreamingResponse(
        stream_study_aid(model, document.filename, text, body.kind), media_type="text/event-stream", headers=SSE_HEADERS
    )


@router.get("/workspace/files", response_model=schemas.WorkspaceView)
def workspace_files(student: CurrentStudent, settings: AppSettings, folder: str = ".") -> schemas.WorkspaceView:
    space = Workspace(settings, student.id)
    return schemas.WorkspaceView(
        files=[
            schemas.FileView(path=f.path, is_dir=f.is_dir, size=f.size, modified=f.modified)
            for f in space.listing(folder)
        ],
        usage_bytes=space.usage(),
        quota_bytes=space.quota_bytes,
    )


@router.post("/workspace/files", response_model=schemas.FileView, status_code=status.HTTP_201_CREATED)
def workspace_upload(
    file: UploadFile, student: CurrentStudent, settings: AppSettings, folder: str = ".", replace: bool = False
) -> schemas.FileView:
    data = file.file.read(settings.upload_max_mb * 1024 * 1024 + 1)
    if len(data) > settings.upload_max_mb * 1024 * 1024:
        raise InvalidInput(f"Files are limited to {settings.upload_max_mb} MB.")
    info = Workspace(settings, student.id).save_upload(folder, file.filename or "upload", data, replace=replace)
    return schemas.FileView(path=info.path, is_dir=info.is_dir, size=info.size, modified=info.modified)


@router.get("/workspace/download")
def workspace_download(student: CurrentStudent, settings: AppSettings, path: str = Query(min_length=1)) -> FileResponse:
    target = Workspace(settings, student.id).download_path(path)
    return FileResponse(target, filename=target.name)


@router.delete("/workspace/files", status_code=status.HTTP_204_NO_CONTENT)
def workspace_delete(student: CurrentStudent, settings: AppSettings, path: str = Query(min_length=1)) -> Response:
    Workspace(settings, student.id).remove(path)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
