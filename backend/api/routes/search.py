"""
api/routes/search.py
Unified search: full-text over titles/transcripts + semantic vector search.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from db.database import get_db
from models.orm import Meeting, MeetingStatus, TranscriptSegment, User

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
async def search(
    q: str = Query(..., min_length=2, max_length=200),
    mode: str = Query(default="hybrid", regex="^(text|semantic|hybrid)$"),
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Search meetings using text match and/or semantic similarity.

    Modes:
      text     – PostgreSQL ILIKE over title + transcript
      semantic – ChromaDB vector search over embedded segments
      hybrid   – both, deduplicated and merged (default)
    """
    wid = current_user.workspace_id
    results: list[dict] = []
    seen_meeting_ids: set[str] = set()

    # ── Text search ───────────────────────────────────────────
    if mode in ("text", "hybrid"):
        pattern = f"%{q}%"
        rows = await db.execute(
            select(Meeting)
            .where(
                Meeting.workspace_id == wid,
                Meeting.status == MeetingStatus.COMPLETED,
                or_(
                    Meeting.title.ilike(pattern),
                    Meeting.transcript.ilike(pattern),
                    Meeting.summary.ilike(pattern),
                ),
            )
            .order_by(Meeting.created_at.desc())
            .limit(limit)
        )
        for m in rows.scalars().all():
            mid = str(m.id)
            seen_meeting_ids.add(mid)

            # Find the snippet of transcript that matched
            snippet = _extract_snippet(m.transcript or "", q)

            results.append({
                "meeting_id": mid,
                "title": m.title,
                "created_at": m.created_at.isoformat(),
                "match_type": "text",
                "snippet": snippet,
                "score": None,
            })

    # ── Semantic search ───────────────────────────────────────
    if mode in ("semantic", "hybrid"):
        try:
            from ai.embeddings.chroma import retrieve_chunks
            chunks = retrieve_chunks(
                query=q,
                workspace_id=str(wid),
                top_k=limit,
            )
            for chunk in chunks:
                mid = chunk.meeting_id
                if mid in seen_meeting_ids:
                    # Upgrade score on already-found result
                    for r in results:
                        if r["meeting_id"] == mid:
                            r["match_type"] = "hybrid"
                            r["score"] = round(1 - chunk.score, 3)
                    continue

                seen_meeting_ids.add(mid)
                # Fetch meeting title from DB
                mr = await db.execute(
                    select(Meeting.title, Meeting.created_at).where(
                        Meeting.id == __import__("uuid").UUID(mid)
                    )
                )
                row = mr.first()
                results.append({
                    "meeting_id": mid,
                    "title": row.title if row else chunk.meeting_title,
                    "created_at": row.created_at.isoformat() if row else None,
                    "match_type": "semantic",
                    "snippet": chunk.text[:200],
                    "speaker": chunk.speaker,
                    "timestamp_seconds": chunk.start_time,
                    "score": round(1 - chunk.score, 3),
                })
        except Exception:
            pass   # ChromaDB may be empty; silently skip semantic

    # Sort: hybrid > text > semantic, then by score desc
    order = {"hybrid": 0, "text": 1, "semantic": 2}
    results.sort(key=lambda r: (order.get(r["match_type"], 9), -(r["score"] or 0)))

    return {
        "query": q,
        "mode": mode,
        "count": len(results),
        "results": results[:limit],
    }


def _extract_snippet(text: str, query: str, window: int = 150) -> str:
    """Extract a window of text around the first occurrence of query."""
    if not text:
        return ""
    idx = text.lower().find(query.lower())
    if idx == -1:
        return text[:window] + "..."
    start = max(0, idx - window // 2)
    end = min(len(text), idx + window // 2)
    snippet = text[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet
