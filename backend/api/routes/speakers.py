"""
api/routes/speakers.py
Speaker management: rename labels, list per meeting, bulk rename.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from api.deps import get_current_user
from db.database import get_db
from models.orm import Meeting, Participant, TranscriptSegment, User

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/speakers", tags=["speakers"])


class RenameSpeakerRequest(BaseModel):
    speaker_label: str    # e.g. "SPEAKER_00"
    new_name: str         # e.g. "Priya Sharma"


class BulkRenameRequest(BaseModel):
    """Map of {speaker_label: new_name} pairs."""
    mappings: dict[str, str]


@router.get("/meetings/{meeting_id}")
async def list_meeting_speakers(
    meeting_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all identified speakers for a meeting with their stats."""
    mr = await db.execute(
        select(Meeting).where(
            Meeting.id == meeting_id,
            Meeting.workspace_id == current_user.workspace_id,
        )
    )
    meeting = mr.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    rows = await db.execute(
        select(Participant)
        .where(Participant.meeting_id == meeting_id)
        .order_by(Participant.talk_time_seconds.desc())
    )
    participants = rows.scalars().all()

    return {
        "meeting_id": str(meeting_id),
        "speakers": [
            {
                "id": str(p.id),
                "speaker_label": p.speaker_label,
                "name": p.name,
                "talk_time_seconds": round(p.talk_time_seconds or 0, 1),
                "word_count": p.word_count or 0,
                "is_named": p.name != p.speaker_label,  # has been given a real name
            }
            for p in participants
        ],
    }


@router.post("/meetings/{meeting_id}/rename")
async def rename_speaker(
    meeting_id: uuid.UUID,
    body: RenameSpeakerRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Rename a speaker label to a real name.
    Triggers a background re-embedding task so RAG uses the new name.
    """
    mr = await db.execute(
        select(Meeting).where(
            Meeting.id == meeting_id,
            Meeting.workspace_id == current_user.workspace_id,
        )
    )
    meeting = mr.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    # Update in DB
    await db.execute(
        sa_update(Participant)
        .where(
            Participant.meeting_id == meeting_id,
            Participant.speaker_label == body.speaker_label,
        )
        .values(name=body.new_name)
    )
    await db.execute(
        sa_update(TranscriptSegment)
        .where(
            TranscriptSegment.meeting_id == meeting_id,
            TranscriptSegment.speaker_label == body.speaker_label,
        )
        .values(speaker_name=body.new_name)
    )
    await db.commit()

    # Queue re-embedding in background
    from workers.tasks import rename_speaker as rename_task
    task = rename_task.delay(
        str(meeting_id),
        body.speaker_label,
        body.new_name,
        str(current_user.workspace_id),
    )

    log.info(
        "speaker_rename_queued",
        meeting_id=str(meeting_id),
        label=body.speaker_label,
        name=body.new_name,
        task_id=task.id,
    )
    return {
        "message": f"Speaker '{body.speaker_label}' renamed to '{body.new_name}'",
        "reembedding_task_id": task.id,
    }


@router.post("/meetings/{meeting_id}/bulk-rename")
async def bulk_rename_speakers(
    meeting_id: uuid.UUID,
    body: BulkRenameRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rename multiple speaker labels in one request."""
    mr = await db.execute(
        select(Meeting).where(
            Meeting.id == meeting_id,
            Meeting.workspace_id == current_user.workspace_id,
        )
    )
    if not mr.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Meeting not found")

    for label, new_name in body.mappings.items():
        await db.execute(
            sa_update(Participant)
            .where(Participant.meeting_id == meeting_id,
                   Participant.speaker_label == label)
            .values(name=new_name)
        )
        await db.execute(
            sa_update(TranscriptSegment)
            .where(TranscriptSegment.meeting_id == meeting_id,
                   TranscriptSegment.speaker_label == label)
            .values(speaker_name=new_name)
        )
    await db.commit()

    # Single re-embed after all renames
    from workers.tasks import rename_speaker as rename_task
    task = rename_task.delay(
        str(meeting_id),
        list(body.mappings.keys())[0],  # trigger task to re-embed all
        list(body.mappings.values())[0],
        str(current_user.workspace_id),
    )

    return {
        "renamed": len(body.mappings),
        "mappings": body.mappings,
        "reembedding_task_id": task.id,
    }
