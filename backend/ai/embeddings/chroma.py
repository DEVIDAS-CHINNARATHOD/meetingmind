"""
ai/embeddings/chroma.py
Sentence-Transformer embeddings + ChromaDB vector store.
Handles chunking, upsert, and RAG retrieval for the AI chat.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import structlog

from config.settings import settings

log = structlog.get_logger(__name__)

_CHUNK_SIZE = 400        # characters per chunk
_CHUNK_OVERLAP = 80      # overlap between consecutive chunks


# ═══════════════════════════════════════════════════════════════
# Data classes
# ═══════════════════════════════════════════════════════════════

@dataclass
class RetrievedChunk:
    text: str
    meeting_id: str
    meeting_title: str
    speaker: str | None
    start_time: float | None
    score: float           # cosine distance (lower = more similar)


# ═══════════════════════════════════════════════════════════════
# Lazy-loaded singletons
# ═══════════════════════════════════════════════════════════════

@lru_cache(maxsize=1)
def _get_embedding_model():
    from sentence_transformers import SentenceTransformer
    log.info("loading_embedding_model", model=settings.embedding_model)
    model = SentenceTransformer(settings.embedding_model)
    log.info("embedding_model_loaded")
    return model


@lru_cache(maxsize=1)
def _get_chroma_collection():
    import chromadb
    client = chromadb.PersistentClient(path=settings.chroma_db_path)
    collection = client.get_or_create_collection(
        name=settings.chroma_collection_transcripts,
        metadata={"hnsw:space": "cosine"},
    )
    log.info(
        "chroma_collection_ready",
        name=settings.chroma_collection_transcripts,
        count=collection.count(),
    )
    return collection


# ═══════════════════════════════════════════════════════════════
# Chunking
# ═══════════════════════════════════════════════════════════════

def _chunk_text(text: str) -> list[str]:
    """
    Split text into overlapping character-level chunks.
    Tries to break on sentence boundaries ('. ', '? ', '! ').
    """
    if len(text) <= _CHUNK_SIZE:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + _CHUNK_SIZE, len(text))
        # Try to end at a sentence boundary
        if end < len(text):
            for sep in (". ", "? ", "! ", "\n"):
                pos = text.rfind(sep, start, end)
                if pos != -1 and pos > start + _CHUNK_SIZE // 2:
                    end = pos + len(sep)
                    break
        chunks.append(text[start:end].strip())
        start = end - _CHUNK_OVERLAP
    return [c for c in chunks if c]


# ═══════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════

def embed_meeting(
    meeting_id: str,
    meeting_title: str,
    workspace_id: str,
    transcript_segments: list[dict[str, Any]],
) -> int:
    """
    Chunk and embed all transcript segments for a meeting.
    Each segment dict: {text, speaker_label, speaker_name, start_time, end_time}

    Returns number of chunks stored.
    """
    model = _get_embedding_model()
    collection = _get_chroma_collection()

    # Delete existing embeddings for this meeting (idempotent re-processing)
    try:
        collection.delete(where={"meeting_id": meeting_id})
    except Exception:
        pass   # collection may be empty

    ids: list[str] = []
    texts: list[str] = []
    metadatas: list[dict] = []

    for seg in transcript_segments:
        seg_text = seg.get("text", "").strip()
        if not seg_text:
            continue
        chunks = _chunk_text(seg_text)
        for i, chunk in enumerate(chunks):
            chunk_id = str(uuid.uuid4())
            ids.append(chunk_id)
            texts.append(chunk)
            metadatas.append({
                "meeting_id": meeting_id,
                "meeting_title": meeting_title,
                "workspace_id": workspace_id,
                "speaker": seg.get("speaker_name") or seg.get("speaker_label") or "",
                "start_time": float(seg.get("start_time", 0)),
                "end_time": float(seg.get("end_time", 0)),
                "chunk_index": i,
            })

    if not ids:
        log.warning("embed_meeting_no_chunks", meeting_id=meeting_id)
        return 0

    # Embed in batches of 64
    batch_size = 64
    for batch_start in range(0, len(texts), batch_size):
        batch_texts = texts[batch_start : batch_start + batch_size]
        batch_ids = ids[batch_start : batch_start + batch_size]
        batch_metas = metadatas[batch_start : batch_start + batch_size]
        embeddings = model.encode(batch_texts, show_progress_bar=False).tolist()
        collection.upsert(
            ids=batch_ids,
            embeddings=embeddings,
            documents=batch_texts,
            metadatas=batch_metas,
        )

    log.info("embed_meeting_done", meeting_id=meeting_id, chunks=len(ids))
    return len(ids)


def retrieve_chunks(
    query: str,
    workspace_id: str,
    meeting_ids: list[str] | None = None,
    top_k: int = 5,
) -> list[RetrievedChunk]:
    """
    Semantic search over embedded meeting transcripts.

    Args:
        query:        Natural language question.
        workspace_id: Scope retrieval to this workspace.
        meeting_ids:  Optional list of meeting IDs to filter.
        top_k:        Number of results to return.

    Returns:
        List of RetrievedChunk sorted by relevance.
    """
    model = _get_embedding_model()
    collection = _get_chroma_collection()

    query_embedding = model.encode([query], show_progress_bar=False).tolist()[0]

    where: dict[str, Any] = {"workspace_id": workspace_id}
    if meeting_ids and len(meeting_ids) == 1:
        where["meeting_id"] = meeting_ids[0]
    elif meeting_ids:
        where["meeting_id"] = {"$in": meeting_ids}

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, collection.count() or 1),
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    chunks: list[RetrievedChunk] = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        chunks.append(
            RetrievedChunk(
                text=doc,
                meeting_id=meta.get("meeting_id", ""),
                meeting_title=meta.get("meeting_title", ""),
                speaker=meta.get("speaker") or None,
                start_time=meta.get("start_time"),
                score=dist,
            )
        )

    log.debug("rag_retrieve", query=query[:60], results=len(chunks))
    return chunks


def delete_meeting_embeddings(meeting_id: str) -> None:
    """Remove all chunks for a meeting (called on meeting deletion)."""
    try:
        collection = _get_chroma_collection()
        collection.delete(where={"meeting_id": meeting_id})
        log.info("embeddings_deleted", meeting_id=meeting_id)
    except Exception as e:
        log.warning("embeddings_delete_failed", meeting_id=meeting_id, error=str(e))
