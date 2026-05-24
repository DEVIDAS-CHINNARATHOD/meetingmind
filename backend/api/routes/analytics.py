"""
api/routes/analytics.py
Workspace and per-meeting analytics endpoints.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from db.database import get_db
from models.orm import (
    ActionItem, Meeting, MeetingStatus, Participant, TranscriptSegment, User,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


# ── Workspace overview ────────────────────────────────────────

@router.get("/overview")
async def workspace_overview(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """High-level KPIs for the workspace dashboard."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    wid = current_user.workspace_id

    # Total meetings
    total_q = await db.execute(
        select(func.count(Meeting.id)).where(
            Meeting.workspace_id == wid,
            Meeting.status == MeetingStatus.COMPLETED,
        )
    )
    total_meetings = total_q.scalar_one()

    # Meetings in window
    recent_q = await db.execute(
        select(func.count(Meeting.id)).where(
            Meeting.workspace_id == wid,
            Meeting.status == MeetingStatus.COMPLETED,
            Meeting.created_at >= since,
        )
    )
    recent_meetings = recent_q.scalar_one()

    # Total recorded hours
    hours_q = await db.execute(
        select(func.sum(Meeting.duration_seconds)).where(
            Meeting.workspace_id == wid,
            Meeting.status == MeetingStatus.COMPLETED,
        )
    )
    total_seconds = hours_q.scalar_one() or 0

    # Total word count (proxy for content volume)
    words_q = await db.execute(
        select(func.sum(Meeting.word_count)).where(
            Meeting.workspace_id == wid,
            Meeting.status == MeetingStatus.COMPLETED,
        )
    )
    total_words = words_q.scalar_one() or 0

    # Open action items
    open_actions_q = await db.execute(
        select(func.count(ActionItem.id)).join(
            Meeting, Meeting.id == ActionItem.meeting_id
        ).where(
            Meeting.workspace_id == wid,
            ActionItem.is_completed == False,
        )
    )
    open_actions = open_actions_q.scalar_one()

    # Completed action items
    done_actions_q = await db.execute(
        select(func.count(ActionItem.id)).join(
            Meeting, Meeting.id == ActionItem.meeting_id
        ).where(
            Meeting.workspace_id == wid,
            ActionItem.is_completed == True,
        )
    )
    done_actions = done_actions_q.scalar_one()

    total_actions = open_actions + done_actions
    completion_rate = round(done_actions / total_actions * 100, 1) if total_actions else 0

    # Average meeting duration
    avg_dur_q = await db.execute(
        select(func.avg(Meeting.duration_seconds)).where(
            Meeting.workspace_id == wid,
            Meeting.status == MeetingStatus.COMPLETED,
            Meeting.duration_seconds.isnot(None),
        )
    )
    avg_dur = avg_dur_q.scalar_one() or 0

    return {
        "period_days": days,
        "total_meetings": total_meetings,
        "meetings_in_period": recent_meetings,
        "total_hours_recorded": round(total_seconds / 3600, 1),
        "total_words_transcribed": total_words,
        "avg_meeting_minutes": round(avg_dur / 60, 1),
        "open_action_items": open_actions,
        "completed_action_items": done_actions,
        "action_completion_rate_pct": completion_rate,
    }


# ── Meeting frequency (time series) ──────────────────────────

@router.get("/meeting-frequency")
async def meeting_frequency(
    days: int = Query(default=30, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns daily meeting counts for charting.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    wid = current_user.workspace_id

    rows = await db.execute(
        select(
            func.date_trunc("day", Meeting.created_at).label("day"),
            func.count(Meeting.id).label("count"),
        ).where(
            Meeting.workspace_id == wid,
            Meeting.status == MeetingStatus.COMPLETED,
            Meeting.created_at >= since,
        ).group_by("day").order_by("day")
    )
    data = [
        {"date": str(r.day.date()), "meetings": r.count}
        for r in rows.all()
    ]
    return {"data": data, "period_days": days}


# ── Speaker analytics (workspace-wide) ───────────────────────

@router.get("/speakers")
async def speaker_analytics(
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Aggregate talk time and word count per named speaker across all meetings.
    """
    wid = current_user.workspace_id

    rows = await db.execute(
        select(
            Participant.name,
            func.sum(Participant.talk_time_seconds).label("total_talk_time"),
            func.sum(Participant.word_count).label("total_words"),
            func.count(Participant.meeting_id).label("meetings_attended"),
        ).join(Meeting, Meeting.id == Participant.meeting_id)
        .where(Meeting.workspace_id == wid)
        .group_by(Participant.name)
        .order_by(func.sum(Participant.talk_time_seconds).desc())
        .limit(limit)
    )

    speakers = [
        {
            "name": r.name,
            "total_talk_time_seconds": round(r.total_talk_time or 0, 1),
            "total_talk_time_minutes": round((r.total_talk_time or 0) / 60, 1),
            "total_words": r.total_words or 0,
            "meetings_attended": r.meetings_attended,
        }
        for r in rows.all()
    ]

    # Compute participation % relative to the top speaker
    if speakers:
        max_tt = speakers[0]["total_talk_time_seconds"] or 1
        for s in speakers:
            s["participation_pct"] = round(s["total_talk_time_seconds"] / max_tt * 100, 1)

    return {"speakers": speakers}


# ── Per-meeting speaker breakdown ─────────────────────────────

@router.get("/meetings/{meeting_id}/speakers")
async def meeting_speaker_breakdown(
    meeting_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Talk time and participation breakdown for a single meeting."""
    wid = current_user.workspace_id

    # Verify ownership
    mr = await db.execute(
        select(Meeting).where(
            Meeting.id == meeting_id,
            Meeting.workspace_id == wid,
        )
    )
    meeting = mr.scalar_one_or_none()
    if not meeting:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Meeting not found")

    rows = await db.execute(
        select(Participant).where(Participant.meeting_id == meeting_id)
        .order_by(Participant.talk_time_seconds.desc())
    )
    participants = rows.scalars().all()

    total_talk = sum(p.talk_time_seconds or 0 for p in participants)

    speakers = [
        {
            "name": p.name,
            "speaker_label": p.speaker_label,
            "talk_time_seconds": round(p.talk_time_seconds or 0, 1),
            "talk_time_minutes": round((p.talk_time_seconds or 0) / 60, 1),
            "word_count": p.word_count or 0,
            "talk_pct": round((p.talk_time_seconds or 0) / total_talk * 100, 1)
            if total_talk else 0,
        }
        for p in participants
    ]

    return {
        "meeting_id": str(meeting_id),
        "meeting_title": meeting.title,
        "total_duration_seconds": meeting.duration_seconds,
        "total_talk_time_seconds": round(total_talk, 1),
        "speakers": speakers,
    }


# ── Action item analytics ─────────────────────────────────────

@router.get("/action-items")
async def action_item_analytics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Action item completion rates and per-assignee breakdown."""
    wid = current_user.workspace_id

    rows = await db.execute(
        select(
            ActionItem.assigned_to,
            func.count(ActionItem.id).label("total"),
            func.sum(func.cast(ActionItem.is_completed, sqlalchemy_int())).label("done"),
        ).join(Meeting, Meeting.id == ActionItem.meeting_id)
        .where(Meeting.workspace_id == wid)
        .group_by(ActionItem.assigned_to)
        .order_by(func.count(ActionItem.id).desc())
    )

    assignees = []
    for r in rows.all():
        total = r.total or 0
        done = int(r.done or 0)
        assignees.append({
            "assignee": r.assigned_to or "Unassigned",
            "total": total,
            "completed": done,
            "pending": total - done,
            "completion_rate_pct": round(done / total * 100, 1) if total else 0,
        })

    return {"assignees": assignees}


def sqlalchemy_int():
    from sqlalchemy import Integer
    return Integer
