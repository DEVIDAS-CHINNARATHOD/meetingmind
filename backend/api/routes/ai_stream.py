"""
api/routes/ai_stream.py
Streaming AI chat via Server-Sent Events (SSE).
The client receives tokens as they arrive from Groq instead of waiting
for the full response — much better UX for long answers.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from api.deps import get_current_user
from config.settings import settings
from db.database import get_db
from models.orm import Meeting, MeetingStatus, User
from ai.embeddings.chroma import retrieve_chunks

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/ai", tags=["ai-stream"])


class StreamChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    meeting_ids: list[uuid.UUID] | None = None
    top_k: int = Field(default=5, ge=1, le=20)


def _sse(data: dict) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(data)}\n\n"


async def _stream_answer(
    question: str,
    workspace_id: str,
    meeting_ids: list[str] | None,
    top_k: int,
) -> AsyncIterator[str]:
    """
    Async generator that:
    1. Retrieves RAG context chunks
    2. Streams the Groq response token-by-token via SSE
    """
    # ── 1. Retrieve context ───────────────────────────────────
    try:
        chunks = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: retrieve_chunks(
                query=question,
                workspace_id=workspace_id,
                meeting_ids=meeting_ids,
                top_k=top_k,
            ),
        )
    except Exception as e:
        yield _sse({"type": "error", "message": f"Retrieval failed: {str(e)}"})
        return

    if not chunks:
        yield _sse({
            "type": "content",
            "text": "I couldn't find relevant information in your meeting transcripts for that question."
        })
        yield _sse({"type": "done", "sources": []})
        return

    # Build context block
    context_parts = []
    for c in chunks:
        prefix = f"[{c.speaker}] " if c.speaker else ""
        time_s = f"[{c.start_time:.0f}s] " if c.start_time else ""
        context_parts.append(f"**{c.meeting_title}** — {time_s}{prefix}{c.text}")
    context = "\n\n".join(context_parts[:_max_context_chars(context_parts)])

    # ── 2. Stream from Groq ───────────────────────────────────
    try:
        from groq import Groq
        client = Groq(api_key=settings.groq_api_key)

        system_msg = (
            "You are MeetingMind AI, an intelligent meeting assistant. "
            "Answer questions based ONLY on the provided meeting transcript context. "
            "Be specific — quote names, numbers, and decisions from the context. "
            "Format your response with bullet points where appropriate."
        )
        user_msg = (
            f"CONTEXT FROM MEETINGS:\n{context}\n\n"
            f"QUESTION: {question}\n\n"
            "Provide a clear, specific answer based on the meeting context above."
        )

        # Send a "thinking" event first
        yield _sse({"type": "thinking", "sources_count": len(chunks)})

        # Groq streaming completion
        stream = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=1500,
            temperature=0.1,
            stream=True,
        )

        for chunk_resp in stream:
            delta = chunk_resp.choices[0].delta
            if delta and delta.content:
                yield _sse({"type": "content", "text": delta.content})
                await asyncio.sleep(0)   # yield control to event loop

        # ── 3. Send sources ───────────────────────────────────
        sources = [
            {
                "meeting_id": c.meeting_id,
                "meeting_title": c.meeting_title,
                "speaker": c.speaker,
                "timestamp_seconds": c.start_time,
                "excerpt": c.text[:120] + "..." if len(c.text) > 120 else c.text,
                "relevance": round(1 - c.score, 3),
            }
            for c in chunks[:3]
        ]
        yield _sse({"type": "done", "sources": sources, "model": settings.groq_model})

    except Exception as e:
        log.error("stream_chat_error", error=str(e))
        yield _sse({"type": "error", "message": "LLM streaming failed. Please try again."})


def _max_context_chars(parts: list[str], limit: int = 6000) -> int:
    """Return how many parts fit within the character limit."""
    total = 0
    for i, p in enumerate(parts):
        total += len(p)
        if total > limit:
            return i
    return len(parts)


@router.post("/chat/stream")
async def stream_chat(
    body: StreamChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Server-Sent Events endpoint for streaming AI chat responses.

    Connect with:
      const es = new EventSource('/api/ai/chat/stream', {method:'POST', ...})

    Or via fetch with ReadableStream:
      const res = await fetch('/api/ai/chat/stream', {method:'POST', body:...})
      const reader = res.body.getReader()

    Each SSE event has a JSON payload with:
      {"type": "thinking", "sources_count": N}   — retrieval done, about to stream
      {"type": "content",  "text": "...token..."}  — streaming token
      {"type": "done",     "sources": [...]}       — finished, with citations
      {"type": "error",    "message": "..."}       — something went wrong
    """
    # Validate meeting_ids belong to this workspace
    meeting_id_strs: list[str] | None = None
    if body.meeting_ids:
        rows = await db.execute(
            select(Meeting.id).where(
                Meeting.id.in_(body.meeting_ids),
                Meeting.workspace_id == current_user.workspace_id,
                Meeting.status == MeetingStatus.COMPLETED,
            )
        )
        valid = {str(r[0]) for r in rows.all()}
        meeting_id_strs = [str(mid) for mid in body.meeting_ids if str(mid) in valid]

    return StreamingResponse(
        _stream_answer(
            question=body.question,
            workspace_id=str(current_user.workspace_id),
            meeting_ids=meeting_id_strs,
            top_k=body.top_k,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering
        },
    )
