"""
api/routes/reports.py
Report generation and download endpoints.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from api.deps import get_current_user
from db.database import get_db
from models.orm import Meeting, MeetingStatus, Report, ReportType, User

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/reports", tags=["reports"])

_MIME = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain",
    "md": "text/markdown",
}


@router.post("/{meeting_id}/generate")
async def request_report(
    meeting_id: uuid.UUID,
    fmt: str = Query(default="pdf", regex="^(pdf|docx|txt)$"),
    report_type: str = Query(default="mom", regex="^(mom|transcript|analytics)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Queue a report generation task. Returns the Celery task ID.
    For small meetings, you can poll GET /reports/{meeting_id}/download?fmt=...
    """
    result = await db.execute(
        select(Meeting).where(
            Meeting.id == meeting_id,
            Meeting.workspace_id == current_user.workspace_id,
            Meeting.status == MeetingStatus.COMPLETED,
        )
    )
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found or not yet processed")

    from workers.tasks import generate_report
    task = generate_report.delay(
        str(meeting_id), report_type, fmt, str(current_user.workspace_id)
    )
    log.info("report_queued", meeting_id=str(meeting_id), fmt=fmt, task_id=task.id)
    return {"task_id": task.id, "status": "queued"}


@router.get("/{meeting_id}/download")
async def download_report(
    meeting_id: uuid.UUID,
    fmt: str = Query(default="pdf", regex="^(pdf|docx|txt|md)$"),
    report_type: str = Query(default="mom"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Synchronously generate (if needed) and stream a report file.
    For small reports this is fast enough; for large ones use the async queue.
    """
    result = await db.execute(
        select(Meeting).where(
            Meeting.id == meeting_id,
            Meeting.workspace_id == current_user.workspace_id,
        )
    )
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if meeting.status != MeetingStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Meeting processing not complete")

    # Check for cached report
    cached = await db.execute(
        select(Report).where(
            Report.meeting_id == meeting_id,
            Report.format == fmt,
            Report.report_type == ReportType(report_type),
        )
    )
    report_row = cached.scalar_one_or_none()

    if report_row and report_row.file_key:
        from services.storage import get_storage
        storage = get_storage()
        if await storage.exists(report_row.file_key):
            file_bytes = await storage.download_bytes(report_row.file_key)
            await db.execute(
                update(Report).where(Report.id == report_row.id)
                .values(download_count=Report.download_count + 1)
            )
            await db.commit()
            filename = f"{meeting.title.replace(' ', '_')}_{report_type}.{fmt}"
            return Response(
                content=file_bytes,
                media_type=_MIME.get(fmt, "application/octet-stream"),
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

    # Generate on-the-fly
    if fmt == "txt":
        content_bytes = (meeting.transcript or "No transcript available.").encode("utf-8")
    elif fmt == "md":
        content_bytes = (meeting.mom or "MoM not generated yet.").encode("utf-8")
    elif fmt == "pdf":
        from services.report_generator import generate_pdf_mom
        content_bytes = generate_pdf_mom(meeting.title, meeting.mom or "", meeting.created_at)
    elif fmt == "docx":
        from services.report_generator import generate_docx_mom
        content_bytes = generate_docx_mom(meeting.title, meeting.mom or "")
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {fmt}")

    filename = f"{meeting.title.replace(' ', '_')}_{report_type}.{fmt}"
    return Response(
        content=content_bytes,
        media_type=_MIME.get(fmt, "application/octet-stream"),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
