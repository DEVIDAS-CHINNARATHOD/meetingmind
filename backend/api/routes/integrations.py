"""
api/routes/integrations.py
Phase 4: Zoom + Google Meet integration endpoints.

Endpoints:
  POST /integrations/zoom/join       → schedule Zoom bot
  POST /integrations/zoom/webhook    → receive Zoom event webhooks
  POST /integrations/meet/join       → schedule Google Meet bot
  GET  /integrations/status          → list active bot sessions
  POST /integrations/{meeting_id}/stop → stop a running bot
"""
from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, HttpUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from api.deps import get_current_user
from config.settings import settings
from db.database import get_db
from models.orm import Meeting, MeetingSource, MeetingStatus, User

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/integrations", tags=["integrations"])


# ── Schemas ───────────────────────────────────────────────────

class ZoomJoinRequest(BaseModel):
    meeting_number: str          # Zoom meeting ID (numeric string)
    password: str = ""
    title: str = ""              # override auto-generated title
    scheduled_at: datetime | None = None   # future join time (None = immediate)


class MeetJoinRequest(BaseModel):
    meet_url: str                # https://meet.google.com/xxx-xxxx-xxx
    title: str = ""


class BotSession(BaseModel):
    meeting_id: str
    platform: str
    title: str
    status: str
    celery_task_id: str | None
    created_at: datetime


# ── Zoom: join ────────────────────────────────────────────────

@router.post("/zoom/join", response_model=BotSession, status_code=status.HTTP_202_ACCEPTED)
async def zoom_join(
    body: ZoomJoinRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Send MeetingMind bot to join a Zoom meeting.
    Creates a Meeting record and queues the Celery bot task.
    """
    if not settings.zoom_client_id or not settings.zoom_client_secret:
        raise HTTPException(
            status_code=503,
            detail="Zoom integration not configured. Set ZOOM_CLIENT_ID and ZOOM_CLIENT_SECRET.",
        )

    title = body.title or f"Zoom Meeting {body.meeting_number}"
    meeting = Meeting(
        title=title,
        status=MeetingStatus.PENDING,
        source=MeetingSource.ZOOM,
        external_meeting_id=body.meeting_number,
        workspace_id=current_user.workspace_id,
        created_by=current_user.id,
    )
    db.add(meeting)
    await db.flush()

    from workers.bot_tasks import join_zoom_meeting
    task = join_zoom_meeting.apply_async(
        args=[str(meeting.id), str(current_user.workspace_id),
              body.meeting_number, body.password],
        eta=body.scheduled_at,   # None = immediate
    )
    meeting.celery_task_id = task.id
    await db.commit()

    log.info("zoom_bot_queued", meeting_id=str(meeting.id),
             zoom_number=body.meeting_number, task_id=task.id)

    return BotSession(
        meeting_id=str(meeting.id),
        platform="zoom",
        title=title,
        status="queued",
        celery_task_id=task.id,
        created_at=meeting.created_at,
    )


# ── Zoom: webhook ─────────────────────────────────────────────

@router.post("/zoom/webhook", status_code=200)
async def zoom_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Receive Zoom event webhooks.

    Zoom sends:
      - meeting.started   → could trigger auto-join
      - meeting.ended     → finalize transcript
      - recording.completed → (Phase 5: pull cloud recording)

    Zoom webhook verification:
      https://developers.zoom.us/docs/api/rest/webhook-reference/
    """
    body_bytes = await request.body()

    # ── Verify Zoom signature ──────────────────────────────────
    ts = request.headers.get("x-zm-request-timestamp", "")
    signature = request.headers.get("x-zm-signature", "")

    if settings.zoom_webhook_secret:
        msg = f"v0:{ts}:{body_bytes.decode()}"
        expected = "v0=" + hmac.new(
            settings.zoom_webhook_secret.encode(),
            msg.encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise HTTPException(status_code=401, detail="Invalid Zoom webhook signature")

    import json
    try:
        payload = json.loads(body_bytes)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event = payload.get("event", "")
    log.info("zoom_webhook_received", event=event)

    # ── URL validation challenge (required by Zoom) ────────────
    if event == "endpoint.url_validation":
        plain = payload.get("payload", {}).get("plainToken", "")
        enc = hmac.new(
            settings.zoom_webhook_secret.encode() if settings.zoom_webhook_secret else b"",
            plain.encode(),
            hashlib.sha256,
        ).hexdigest()
        return {"plainToken": plain, "encryptedToken": enc}

    # ── Meeting ended → finalize if we have a bot session ─────
    if event == "meeting.ended":
        zoom_meeting_id = str(payload.get("payload", {}).get("object", {}).get("id", ""))
        if zoom_meeting_id:
            background_tasks.add_task(_finalize_zoom_meeting, zoom_meeting_id, db)

    return {"status": "ok"}


async def _finalize_zoom_meeting(zoom_meeting_id: str, db: AsyncSession) -> None:
    """Look up our Meeting record by external Zoom ID and trigger finalization."""
    r = await db.execute(
        select(Meeting).where(
            Meeting.external_meeting_id == zoom_meeting_id,
            Meeting.source == MeetingSource.ZOOM,
            Meeting.status == MeetingStatus.PROCESSING,
        )
    )
    meeting = r.scalar_one_or_none()
    if meeting:
        log.info("zoom_meeting_ended_webhook", meeting_id=str(meeting.id))
        # The running bot task will handle finalization on its own;
        # this is a safety net if the bot missed the end signal.


# ── Google Meet: join ─────────────────────────────────────────

@router.post("/meet/join", response_model=BotSession, status_code=status.HTTP_202_ACCEPTED)
async def meet_join(
    body: MeetJoinRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send MeetingMind bot to join a Google Meet."""
    # Basic URL validation
    if "meet.google.com" not in body.meet_url:
        raise HTTPException(
            status_code=400,
            detail="URL must be a Google Meet link (meet.google.com/...)",
        )

    title = body.title or f"Google Meet — {body.meet_url.split('/')[-1]}"
    meeting = Meeting(
        title=title,
        status=MeetingStatus.PENDING,
        source=MeetingSource.GOOGLE_MEET,
        external_join_url=body.meet_url,
        workspace_id=current_user.workspace_id,
        created_by=current_user.id,
    )
    db.add(meeting)
    await db.flush()

    from workers.bot_tasks import join_google_meet
    task = join_google_meet.delay(
        str(meeting.id),
        str(current_user.workspace_id),
        body.meet_url,
    )
    meeting.celery_task_id = task.id
    await db.commit()

    log.info("meet_bot_queued", meeting_id=str(meeting.id), url=body.meet_url)

    return BotSession(
        meeting_id=str(meeting.id),
        platform="google_meet",
        title=title,
        status="queued",
        celery_task_id=task.id,
        created_at=meeting.created_at,
    )


# ── Active bot sessions ───────────────────────────────────────

@router.get("/status", response_model=list[BotSession])
async def integration_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all active or recent bot sessions for this workspace."""
    rows = await db.execute(
        select(Meeting).where(
            Meeting.workspace_id == current_user.workspace_id,
            Meeting.source.in_([MeetingSource.ZOOM, MeetingSource.GOOGLE_MEET]),
        ).order_by(Meeting.created_at.desc()).limit(20)
    )
    meetings = rows.scalars().all()

    sessions = []
    for m in meetings:
        # Enrich with live Celery task state
        task_status = m.status.value
        if m.celery_task_id and m.status == MeetingStatus.PROCESSING:
            try:
                from workers.celery_app import celery_app
                res = celery_app.AsyncResult(m.celery_task_id)
                if res.info and isinstance(res.info, dict):
                    task_status = res.info.get("step", task_status)
            except Exception:
                pass

        sessions.append(BotSession(
            meeting_id=str(m.id),
            platform=m.source.value,
            title=m.title,
            status=task_status,
            celery_task_id=m.celery_task_id,
            created_at=m.created_at,
        ))
    return sessions


# ── Stop bot ──────────────────────────────────────────────────

@router.post("/{meeting_id}/stop", status_code=200)
async def stop_bot(
    meeting_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Gracefully stop a running bot session.
    Revokes the Celery task and finalizes whatever was captured so far.
    """
    r = await db.execute(
        select(Meeting).where(
            Meeting.id == meeting_id,
            Meeting.workspace_id == current_user.workspace_id,
        )
    )
    meeting = r.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    if meeting.celery_task_id:
        try:
            from workers.celery_app import celery_app
            celery_app.control.revoke(meeting.celery_task_id, terminate=True, signal="SIGTERM")
            log.info("bot_task_revoked", task_id=meeting.celery_task_id)
        except Exception as e:
            log.warning("bot_revoke_failed", error=str(e))

    # Queue finalization with whatever transcript we have
    if meeting.transcript:
        from workers.bot_tasks import finalize_live_meeting
        finalize_live_meeting.delay(str(meeting_id), str(current_user.workspace_id))

    return {"message": "Bot stop signal sent", "meeting_id": str(meeting_id)}
