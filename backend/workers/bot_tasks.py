"""
workers/bot_tasks.py
Phase 4 Celery tasks: Zoom bot, Google Meet bot, live meeting finalization.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from pathlib import Path

import structlog
from sqlalchemy import select

from workers.celery_app import celery_app

log = structlog.get_logger(__name__)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ═══════════════════════════════════════════════════════════════
# Zoom bot task
# ═══════════════════════════════════════════════════════════════

@celery_app.task(
    name="workers.tasks.join_zoom_meeting",
    bind=True,
    time_limit=14400,       # 4 hours max
    soft_time_limit=14100,
    max_retries=0,          # don't retry bot tasks
)
def join_zoom_meeting(
    self,
    meeting_id: str,           # MeetingMind DB meeting UUID
    workspace_id: str,
    zoom_meeting_number: str,
    zoom_password: str,
) -> dict:
    """
    Launch Zoom bot for a meeting.
    Captures audio, feeds to StreamingTranscriber, saves transcript.
    """
    from db.database import AsyncSessionLocal
    from models.orm import Meeting, MeetingStatus, MeetingSource
    from ai.realtime.streaming_transcriber import StreamingTranscriber
    from bots.zoom.zoom_bot import ZoomBotConfig, join_and_record, fetch_meeting_participants
    from services.storage import get_storage

    log.info("zoom_task_start", meeting_id=meeting_id, zoom_number=zoom_meeting_number)
    self.update_state(state="PROGRESS", meta={"step": "joining_zoom", "progress": 5})

    all_segments: list[dict] = []
    seg_idx = [0]

    def on_segment(seg):
        all_segments.append({
            "text": seg.text,
            "start_time": seg.start_time,
            "end_time": seg.end_time,
            "is_final": seg.is_final,
            "confidence": seg.confidence,
            "index": seg_idx[0],
        })
        seg_idx[0] += 1

    transcriber = StreamingTranscriber(on_segment=on_segment)

    def on_audio(pcm_bytes: bytes):
        transcriber.feed(pcm_bytes)

    async def _set_status(status):
        async with AsyncSessionLocal() as db:
            r = await db.execute(select(Meeting).where(Meeting.id == uuid.UUID(meeting_id)))
            m = r.scalar_one_or_none()
            if m:
                m.status = status
                await db.commit()

    _run(_set_status(MeetingStatus.PROCESSING))

    try:
        config = ZoomBotConfig(
            meeting_number=zoom_meeting_number,
            meeting_password=zoom_password,
            display_name="MeetingMind Bot 🎙️",
        )
        result = join_and_record(config, on_audio)
        transcriber.stop()

        # Fetch participant list from Zoom API
        participants = _run(fetch_meeting_participants(zoom_meeting_number))

        self.update_state(state="PROGRESS", meta={"step": "finalizing", "progress": 85})
        _run(_save_and_process(meeting_id, workspace_id, all_segments, participants))

        return {
            "meeting_id": meeting_id,
            "status": "completed",
            "zoom_result": result,
            "segments": len(all_segments),
            "participants": len(participants),
        }
    except Exception as exc:
        transcriber.stop()
        log.exception("zoom_task_failed", meeting_id=meeting_id)
        _run(_set_status(MeetingStatus.FAILED))
        return {"error": str(exc)}


# ═══════════════════════════════════════════════════════════════
# Google Meet bot task
# ═══════════════════════════════════════════════════════════════

@celery_app.task(
    name="workers.tasks.join_google_meet",
    bind=True,
    time_limit=14400,
    soft_time_limit=14100,
    max_retries=0,
)
def join_google_meet(
    self,
    meeting_id: str,
    workspace_id: str,
    meet_url: str,
) -> dict:
    """
    Launch Google Meet Playwright bot.
    Captures audio, transcribes in real-time, saves to DB.
    """
    from db.database import AsyncSessionLocal
    from models.orm import Meeting, MeetingStatus
    from ai.realtime.streaming_transcriber import StreamingTranscriber
    from bots.meet.meet_bot import MeetBotConfig, join_and_record

    log.info("meet_task_start", meeting_id=meeting_id, url=meet_url)
    self.update_state(state="PROGRESS", meta={"step": "joining_meet", "progress": 5})

    all_segments: list[dict] = []
    seg_idx = [0]

    def on_segment(seg):
        all_segments.append({
            "text": seg.text,
            "start_time": seg.start_time,
            "end_time": seg.end_time,
            "is_final": seg.is_final,
            "confidence": seg.confidence,
            "index": seg_idx[0],
        })
        seg_idx[0] += 1

    transcriber = StreamingTranscriber(on_segment=on_segment)

    async def _run_bot():
        config = MeetBotConfig(meet_url=meet_url)
        stop_evt = asyncio.Event()
        return await join_and_record(config, lambda b: transcriber.feed(b), stop_evt)

    async def _set_status(status):
        async with AsyncSessionLocal() as db:
            r = await db.execute(select(Meeting).where(Meeting.id == uuid.UUID(meeting_id)))
            m = r.scalar_one_or_none()
            if m:
                m.status = status
                await db.commit()

    _run(_set_status(MeetingStatus.PROCESSING))

    try:
        result = _run(_run_bot())
        transcriber.stop()

        self.update_state(state="PROGRESS", meta={"step": "finalizing", "progress": 85})
        _run(_save_and_process(meeting_id, workspace_id, all_segments, []))

        return {
            "meeting_id": meeting_id,
            "status": "completed",
            "bot_result": result,
            "segments": len(all_segments),
        }
    except Exception as exc:
        transcriber.stop()
        log.exception("meet_task_failed", meeting_id=meeting_id)
        _run(_set_status(MeetingStatus.FAILED))
        return {"error": str(exc)}


# ═══════════════════════════════════════════════════════════════
# Finalize live meeting (after WS or bot session ends)
# ═══════════════════════════════════════════════════════════════

@celery_app.task(name="workers.tasks.finalize_live_meeting", max_retries=2)
def finalize_live_meeting(meeting_id: str, workspace_id: str) -> dict:
    """
    After a live meeting ends (WebSocket or bot):
    1. Generate summary + action items
    2. Generate MoM
    3. Embed transcript for RAG
    4. Mark meeting COMPLETED
    """
    from db.database import AsyncSessionLocal
    from models.orm import ActionItem, Meeting, MeetingStatus, Report, ReportType
    from ai.summarization.groq_llm import generate_summary, generate_mom
    from ai.embeddings.chroma import embed_meeting
    from sqlalchemy import select

    log.info("finalize_live_start", meeting_id=meeting_id)

    async def _run_finalize():
        async with AsyncSessionLocal() as db:
            r = await db.execute(
                select(Meeting).where(Meeting.id == uuid.UUID(meeting_id))
            )
            m = r.scalar_one_or_none()
            if not m or not m.transcript:
                return {"error": "No transcript to finalize"}

            # LLM summary
            sr = generate_summary(m.transcript, title=m.title)
            mr = generate_mom(
                m.transcript, m.title, [],
                f"{int((m.duration_seconds or 0) // 60)}m"
            )

            m.summary = sr.summary
            m.mom = mr.markdown
            m.key_decisions = sr.key_decisions
            m.topics = sr.topics
            m.status = MeetingStatus.COMPLETED

            for item in sr.action_items:
                db.add(ActionItem(
                    meeting_id=m.id,
                    task=item.task,
                    assigned_to=item.assigned_to,
                    deadline=item.deadline,
                    priority=item.priority,
                ))
            db.add(Report(meeting_id=m.id, report_type=ReportType.MOM, format="md"))
            await db.commit()

            return m.transcript

    transcript = _run(_run_finalize())
    if isinstance(transcript, dict):
        return transcript  # error dict

    # Embed for RAG (needs segments with speaker info)
    async def _get_segs():
        from models.orm import TranscriptSegment
        async with AsyncSessionLocal() as db:
            r = await db.execute(
                select(TranscriptSegment)
                .where(TranscriptSegment.meeting_id == uuid.UUID(meeting_id))
                .order_by(TranscriptSegment.segment_index)
            )
            return [{"text": s.text, "speaker_label": s.speaker_label,
                     "speaker_name": s.speaker_name,
                     "start_time": s.start_time, "end_time": s.end_time}
                    for s in r.scalars().all()]

    segs = _run(_get_segs())

    async def _get_title():
        async with AsyncSessionLocal() as db:
            r = await db.execute(select(Meeting.title).where(
                Meeting.id == uuid.UUID(meeting_id)))
            return r.scalar_one()

    title = _run(_get_title())
    chunks = embed_meeting(meeting_id, title, workspace_id, segs)

    log.info("finalize_live_done", meeting_id=meeting_id, chunks=chunks)
    return {"meeting_id": meeting_id, "status": "completed", "chunks": chunks}


# ═══════════════════════════════════════════════════════════════
# Shared helper: save segments + trigger processing
# ═══════════════════════════════════════════════════════════════

async def _save_and_process(
    meeting_id: str,
    workspace_id: str,
    segments: list[dict],
    zoom_participants: list[dict],
) -> None:
    """Persist live-meeting segments then queue finalization."""
    from db.database import AsyncSessionLocal
    from models.orm import Meeting, MeetingStatus, Participant, TranscriptSegment
    from sqlalchemy import select

    if not segments:
        return

    final_segs = [s for s in segments if s.get("is_final", True)]
    full_text = " ".join(s["text"] for s in final_segs)

    async with AsyncSessionLocal() as db:
        r = await db.execute(select(Meeting).where(Meeting.id == uuid.UUID(meeting_id)))
        m = r.scalar_one_or_none()
        if not m:
            return

        m.transcript = full_text
        m.word_count = len(full_text.split())
        m.status = MeetingStatus.SUMMARIZING

        for seg in final_segs:
            db.add(TranscriptSegment(
                meeting_id=m.id,
                text=seg["text"],
                start_time=seg["start_time"],
                end_time=seg["end_time"],
                confidence=seg.get("confidence"),
                segment_index=seg["index"],
                speaker_label=None,
                speaker_name=None,
            ))

        # Add participants from Zoom API (if available)
        for p in zoom_participants:
            db.add(Participant(
                meeting_id=m.id,
                name=p.get("name", "Unknown"),
                email=p.get("user_email"),
                speaker_label=None,
            ))

        await db.commit()

    # Queue finalization (summary, MoM, embeddings)
    finalize_live_meeting.delay(meeting_id, workspace_id)
