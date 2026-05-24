"""
api/routes/ai.py
AI endpoints: RAG chat, re-summarize, re-generate MoM.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from api.deps import get_current_user
from db.database import get_db
from models.orm import Meeting, MeetingStatus, User
from models.schemas import (
    ChatRequest, ChatResponse, GenerateMomRequest, SummarizeRequest,
)

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/ai", tags=["ai"])


# ── Chat ─────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    RAG-powered chat: ask questions about your meetings.
    """
    from ai.chat.rag_chat import answer_question

    # Validate that provided meeting_ids belong to this workspace
    if body.meeting_ids:
        rows = await db.execute(
            select(Meeting.id).where(
                Meeting.id.in_(body.meeting_ids),
                Meeting.workspace_id == current_user.workspace_id,
                Meeting.status == MeetingStatus.COMPLETED,
            )
        )
        valid_ids = {str(r[0]) for r in rows.all()}
        meeting_id_strs = [str(mid) for mid in body.meeting_ids]
        invalid = [mid for mid in meeting_id_strs if mid not in valid_ids]
        if invalid:
            raise HTTPException(status_code=400, detail=f"Invalid meeting IDs: {invalid}")
    else:
        meeting_id_strs = None

    result = answer_question(
        question=body.question,
        workspace_id=str(current_user.workspace_id),
        meeting_ids=meeting_id_strs,
        top_k=body.top_k,
    )

    return ChatResponse(
        answer=result.answer,
        sources=result.sources,
        model_used=result.model_used,
    )


# ── Re-summarize ──────────────────────────────────────────────

@router.post("/summarize", response_model=dict)
async def summarize(
    body: SummarizeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    (Re-)generate summary and action items for a completed meeting.
    """
    from ai.summarization.groq_llm import generate_summary
    from models.orm import ActionItem

    result = await db.execute(
        select(Meeting).where(
            Meeting.id == body.meeting_id,
            Meeting.workspace_id == current_user.workspace_id,
        )
    )
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if meeting.status != MeetingStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Meeting not yet processed")
    if not meeting.transcript:
        raise HTTPException(status_code=400, detail="No transcript available")
    if meeting.summary and not body.regenerate:
        return {"message": "Summary already exists. Use regenerate=true to overwrite."}

    summary_result = generate_summary(meeting.transcript, title=meeting.title)

    meeting.summary = summary_result.summary
    meeting.key_decisions = summary_result.key_decisions
    meeting.topics = summary_result.topics

    if body.regenerate:
        # Delete old action items
        old = await db.execute(
            select(ActionItem).where(ActionItem.meeting_id == meeting.id)
        )
        for item in old.scalars().all():
            await db.delete(item)

    for item in summary_result.action_items:
        db.add(ActionItem(
            meeting_id=meeting.id,
            task=item.task,
            assigned_to=item.assigned_to,
            deadline=item.deadline,
            priority=item.priority,
        ))

    await db.commit()
    log.info("summary_regenerated", meeting_id=str(meeting.id))
    return {
        "summary": meeting.summary,
        "key_decisions": meeting.key_decisions,
        "topics": meeting.topics,
        "action_items_count": len(summary_result.action_items),
    }


# ── Generate MoM ─────────────────────────────────────────────

@router.post("/generate-mom", response_model=dict)
async def generate_mom_endpoint(
    body: GenerateMomRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    (Re-)generate Minutes of Meeting markdown for a completed meeting.
    """
    from ai.summarization.groq_llm import generate_mom
    from models.orm import Participant

    result = await db.execute(
        select(Meeting).where(
            Meeting.id == body.meeting_id,
            Meeting.workspace_id == current_user.workspace_id,
        )
    )
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if not meeting.transcript:
        raise HTTPException(status_code=400, detail="No transcript available")
    if meeting.mom and not body.regenerate:
        return {"message": "MoM already exists. Use regenerate=true to overwrite.", "mom": meeting.mom}

    # Get participant names
    parts_result = await db.execute(
        select(Participant).where(Participant.meeting_id == meeting.id)
    )
    participants = [p.name for p in parts_result.scalars().all()]

    from utils.time_fmt import fmt_duration
    duration_str = fmt_duration(meeting.duration_seconds) if meeting.duration_seconds else ""

    mom_result = generate_mom(
        transcript=meeting.transcript,
        title=meeting.title,
        participants=participants,
        duration_str=duration_str,
    )
    meeting.mom = mom_result.markdown
    await db.commit()

    log.info("mom_generated", meeting_id=str(meeting.id))
    return {"mom": meeting.mom, "chars": len(meeting.mom)}
