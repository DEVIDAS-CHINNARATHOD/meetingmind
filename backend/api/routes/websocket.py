"""
api/routes/websocket.py
WebSocket endpoint for real-time meeting transcription.

Protocol:
  Client → Server:  binary frames of raw PCM audio (int16, 16kHz, mono)
                    or JSON control messages: {"type": "start"|"stop"|"ping"}
  Server → Client:  JSON messages:
    {"type": "segment",  "text": "...", "start": 1.2, "end": 3.4,
     "is_final": true,  "meeting_id": "..."}
    {"type": "status",   "status": "connected"|"transcribing"|"stopped"}
    {"type": "error",    "message": "..."}
    {"type": "pong"}

Usage flow:
  1. Client opens WS: /api/ws/transcribe?meeting_id=<uuid>&token=<jwt>
  2. Server validates JWT and meeting ownership
  3. Client sends binary PCM chunks (e.g. 960 samples = 60ms @ 16kHz)
  4. Server accumulates, transcribes every ~3s, streams segments back
  5. Client sends {"type":"stop"} or closes connection to finalize
  6. Server saves all segments to DB and marks meeting completed
"""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select
import structlog

from config.settings import settings
from db.database import AsyncSessionLocal
from models.orm import Meeting, MeetingSource, MeetingStatus, TranscriptSegment
from services.auth import decode_access_token

log = structlog.get_logger(__name__)
router = APIRouter(tags=["websocket"])


# ═══════════════════════════════════════════════════════════════
# WebSocket transcription endpoint
# ═══════════════════════════════════════════════════════════════

@router.websocket("/ws/transcribe")
async def websocket_transcribe(
    websocket: WebSocket,
    meeting_id: str = Query(...),
    token: str = Query(...),
):
    """
    Real-time transcription WebSocket.

    Query params:
      meeting_id  UUID of an existing meeting (status=PENDING or PROCESSING)
      token       JWT access token (passed as query param since WS headers are limited)
    """
    # ── Auth ──────────────────────────────────────────────────
    try:
        from jose import JWTError
        payload = decode_access_token(token)
        user_id = uuid.UUID(payload["sub"])
        workspace_id = uuid.UUID(payload["workspace_id"])
    except Exception:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    # ── Validate meeting ownership ────────────────────────────
    async with AsyncSessionLocal() as db:
        r = await db.execute(
            select(Meeting).where(
                Meeting.id == uuid.UUID(meeting_id),
                Meeting.workspace_id == workspace_id,
            )
        )
        meeting = r.scalar_one_or_none()

    if not meeting:
        await websocket.close(code=4004, reason="Meeting not found")
        return

    await websocket.accept()
    log.info("ws_connected", meeting_id=meeting_id, user_id=str(user_id))

    # ── Update meeting status ──────────────────────────────────
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(Meeting).where(Meeting.id == uuid.UUID(meeting_id)))
        m = r.scalar_one()
        m.status = MeetingStatus.TRANSCRIBING
        await db.commit()

    await _send(websocket, {"type": "status", "status": "connected",
                            "meeting_id": meeting_id})

    # ── Collect all segments for DB persistence ───────────────
    all_segments: list[dict[str, Any]] = []
    segment_index = [0]

    def on_segment(seg):
        """Called by StreamingTranscriber thread — bridge to async via asyncio."""
        data = {
            "type": "segment",
            "text": seg.text,
            "start": seg.start_time,
            "end": seg.end_time,
            "is_final": seg.is_final,
            "meeting_id": meeting_id,
        }
        all_segments.append({
            "text": seg.text,
            "start_time": seg.start_time,
            "end_time": seg.end_time,
            "is_final": seg.is_final,
            "confidence": seg.confidence,
            "index": segment_index[0],
        })
        segment_index[0] += 1
        # Schedule send on the event loop
        asyncio.run_coroutine_threadsafe(
            _send(websocket, data),
            asyncio.get_event_loop(),
        )

    # ── Start transcriber ──────────────────────────────────────
    from ai.realtime.streaming_transcriber import StreamingTranscriber
    transcriber = StreamingTranscriber(on_segment=on_segment)

    await _send(websocket, {"type": "status", "status": "transcribing"})

    try:
        while True:
            raw = await asyncio.wait_for(websocket.receive(), timeout=30.0)

            # Binary frame = audio PCM
            if "bytes" in raw and raw["bytes"]:
                transcriber.feed(raw["bytes"])

            # Text frame = control message
            elif "text" in raw and raw["text"]:
                try:
                    msg = json.loads(raw["text"])
                except json.JSONDecodeError:
                    continue

                if msg.get("type") == "stop":
                    log.info("ws_stop_requested", meeting_id=meeting_id)
                    break
                elif msg.get("type") == "ping":
                    await _send(websocket, {"type": "pong"})

    except (WebSocketDisconnect, asyncio.TimeoutError):
        log.info("ws_disconnected", meeting_id=meeting_id)
    except Exception as e:
        log.error("ws_error", error=str(e))
        await _send(websocket, {"type": "error", "message": str(e)})
    finally:
        transcriber.stop()
        await _finalize_meeting(meeting_id, workspace_id, all_segments)
        log.info("ws_session_complete",
                 meeting_id=meeting_id, segments=len(all_segments))


async def _send(ws: WebSocket, data: dict) -> None:
    """Safe send — silently ignore if connection already closed."""
    try:
        await ws.send_json(data)
    except Exception:
        pass


async def _finalize_meeting(
    meeting_id: str,
    workspace_id: uuid.UUID,
    segments: list[dict],
) -> None:
    """
    After WebSocket closes:
    1. Save all transcript segments to DB
    2. Trigger async summarization + embedding pipeline
    """
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

        for i, seg in enumerate(final_segs):
            db.add(TranscriptSegment(
                meeting_id=m.id,
                text=seg["text"],
                start_time=seg["start_time"],
                end_time=seg["end_time"],
                confidence=seg.get("confidence"),
                segment_index=i,
                speaker_label=None,
                speaker_name=None,
            ))
        await db.commit()

    # Queue summarization + embedding via Celery
    from workers.tasks import finalize_live_meeting
    finalize_live_meeting.delay(meeting_id, str(workspace_id))

    log.info("ws_meeting_finalized",
             meeting_id=meeting_id, words=len(full_text.split()))
