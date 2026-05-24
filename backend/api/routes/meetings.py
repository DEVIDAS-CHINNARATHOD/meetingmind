"""
api/routes/meetings.py
Meeting CRUD + file upload endpoint.
"""
from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path

from fastapi import (
    APIRouter, Depends, File, Form, HTTPException,
    Query, UploadFile, status,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import structlog

from api.deps import get_current_user
from config.settings import settings
from db.database import get_db
from models.orm import Meeting, MeetingSource, MeetingStatus, User
from models.schemas import (
    MeetingDetailOut, MeetingListOut, MeetingOut, MeetingUpdate, ProcessingStatusOut,
)
from services.storage import get_storage, make_upload_key

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/meetings", tags=["meetings"])


# ── helpers ───────────────────────────────────────────────────

def _validate_file_format(filename: str) -> None:
    ext = Path(filename).suffix.lstrip(".").lower()
    if ext not in settings.all_allowed_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{ext}'. Allowed: {', '.join(settings.all_allowed_formats)}",
        )


async def _get_meeting_or_404(
    meeting_id: uuid.UUID,
    db: AsyncSession,
    workspace_id: uuid.UUID,
    *,
    with_relations: bool = False,
) -> Meeting:
    q = select(Meeting).where(
        Meeting.id == meeting_id,
        Meeting.workspace_id == workspace_id,
    )
    if with_relations:
        q = q.options(
            selectinload(Meeting.participants),
            selectinload(Meeting.action_items),
            selectinload(Meeting.transcript_segments),
        )
    result = await db.execute(q)
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting


# ── List ──────────────────────────────────────────────────────

@router.get("", response_model=MeetingListOut)
async def list_meetings(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(Meeting).where(Meeting.workspace_id == current_user.workspace_id)
    if status_filter:
        try:
            q = q.where(Meeting.status == MeetingStatus(status_filter))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status_filter}")

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    q = q.order_by(Meeting.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(q)).scalars().all()

    return MeetingListOut(
        items=[MeetingOut.model_validate(m) for m in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, -(-total // page_size)),
    )


# ── Upload ────────────────────────────────────────────────────

@router.post("/upload", response_model=MeetingOut, status_code=status.HTTP_202_ACCEPTED)
async def upload_meeting(
    file: UploadFile = File(...),
    title: str = Form(..., min_length=1, max_length=255),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _validate_file_format(file.filename or "recording.mp4")

    # Enforce upload size limit
    content = await file.read()
    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {settings.max_upload_size_mb} MB limit",
        )

    # Create DB record
    meeting = Meeting(
        title=title,
        status=MeetingStatus.UPLOADING,
        source=MeetingSource.UPLOAD,
        original_filename=file.filename,
        file_size_bytes=len(content),
        workspace_id=current_user.workspace_id,
        created_by=current_user.id,
    )
    db.add(meeting)
    await db.flush()   # get meeting.id

    # Upload to storage
    file_key = make_upload_key(
        str(current_user.workspace_id),
        str(meeting.id),
        file.filename or "recording.mp4",
    )
    storage = get_storage()
    import io
    await storage.upload_bytes(content, file_key, file.content_type or "application/octet-stream")

    meeting.file_key = file_key
    meeting.status = MeetingStatus.PENDING

    # Kick off Celery pipeline
    from workers.tasks import process_meeting
    task = process_meeting.delay(str(meeting.id), str(current_user.workspace_id))
    meeting.celery_task_id = task.id

    await db.commit()

    log.info(
        "meeting_upload_queued",
        meeting_id=str(meeting.id),
        task_id=task.id,
        size_mb=len(content) // 1024 // 1024,
    )
    return MeetingOut.model_validate(meeting)


# ── Get one ───────────────────────────────────────────────────

@router.get("/{meeting_id}", response_model=MeetingDetailOut)
async def get_meeting(
    meeting_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    meeting = await _get_meeting_or_404(
        meeting_id, db, current_user.workspace_id, with_relations=True
    )
    return MeetingDetailOut.model_validate(meeting)


# ── Status polling ────────────────────────────────────────────

@router.get("/{meeting_id}/status", response_model=ProcessingStatusOut)
async def get_meeting_status(
    meeting_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    meeting = await _get_meeting_or_404(meeting_id, db, current_user.workspace_id)

    progress_map = {
        MeetingStatus.PENDING: 5,
        MeetingStatus.UPLOADING: 10,
        MeetingStatus.PROCESSING: 25,
        MeetingStatus.TRANSCRIBING: 50,
        MeetingStatus.SUMMARIZING: 75,
        MeetingStatus.COMPLETED: 100,
        MeetingStatus.FAILED: None,
    }

    # Optionally enrich with live Celery task state
    step = meeting.status.value
    if meeting.celery_task_id and meeting.status not in (
        MeetingStatus.COMPLETED, MeetingStatus.FAILED
    ):
        from workers.celery_app import celery_app
        task_result = celery_app.AsyncResult(meeting.celery_task_id)
        if task_result.info and isinstance(task_result.info, dict):
            step = task_result.info.get("step", step)

    return ProcessingStatusOut(
        meeting_id=meeting.id,
        status=meeting.status.value,
        progress_percent=progress_map.get(meeting.status),
        current_step=step,
        error=meeting.processing_error,
    )


# ── Update ────────────────────────────────────────────────────

@router.patch("/{meeting_id}", response_model=MeetingOut)
async def update_meeting(
    meeting_id: uuid.UUID,
    body: MeetingUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    meeting = await _get_meeting_or_404(meeting_id, db, current_user.workspace_id)
    if body.title is not None:
        meeting.title = body.title
    await db.commit()
    return MeetingOut.model_validate(meeting)


# ── Delete ────────────────────────────────────────────────────

@router.delete("/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meeting(
    meeting_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    meeting = await _get_meeting_or_404(meeting_id, db, current_user.workspace_id)

    # Delete storage files
    storage = get_storage()
    for key in filter(None, [meeting.file_key, meeting.audio_extracted_key]):
        try:
            await storage.delete(key)
        except Exception:
            pass

    # Delete ChromaDB embeddings
    from ai.embeddings.chroma import delete_meeting_embeddings
    delete_meeting_embeddings(str(meeting_id))

    await db.delete(meeting)
    await db.commit()
    log.info("meeting_deleted", meeting_id=str(meeting_id))
