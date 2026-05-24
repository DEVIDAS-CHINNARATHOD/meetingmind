"""
ai/face_recognition/identity_db.py
Employee identity database backed by ChromaDB.

Each "identity" is a named person whose face embedding has been enrolled.
At match time we query the DB and return the closest identity above threshold.

Collections:
  face_identities  → one document per person, embedding = mean face embedding
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import numpy as np
import structlog

from config.settings import settings

log = structlog.get_logger(__name__)

_COLLECTION_NAME = "face_identities"
_MATCH_THRESHOLD = 0.45    # cosine similarity; tune per deployment


@dataclass
class IdentityRecord:
    id: str
    name: str
    email: str | None
    workspace_id: str
    embedding: list[float]
    photo_key: str | None     # storage key of the source photo


@dataclass
class MatchResult:
    identity_id: str
    name: str
    email: str | None
    similarity: float
    matched: bool


# ── ChromaDB client ───────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_collection():
    import chromadb
    client = chromadb.PersistentClient(path=settings.chroma_db_path)
    col = client.get_or_create_collection(
        name=_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    log.info("face_identity_collection_ready", count=col.count())
    return col


# ═══════════════════════════════════════════════════════════════
# Enrollment
# ═══════════════════════════════════════════════════════════════

def enroll_identity(
    name: str,
    workspace_id: str,
    embedding: list[float],
    email: str | None = None,
    photo_key: str | None = None,
    identity_id: str | None = None,
) -> str:
    """
    Enroll (or update) a person's face embedding in the identity DB.

    Args:
        name:         Full name of the person.
        workspace_id: Scope identities per workspace.
        embedding:    512-dim ArcFace embedding vector.
        email:        Optional email for cross-referencing with User records.
        photo_key:    Storage key of the reference photo.
        identity_id:  If provided, updates existing record; else creates new.

    Returns:
        identity_id (str UUID)
    """
    col = _get_collection()
    iid = identity_id or str(uuid.uuid4())

    col.upsert(
        ids=[iid],
        embeddings=[embedding],
        documents=[name],
        metadatas=[{
            "name": name,
            "email": email or "",
            "workspace_id": workspace_id,
            "photo_key": photo_key or "",
        }],
    )
    log.info("identity_enrolled", id=iid, name=name, workspace=workspace_id)
    return iid


def enroll_from_multiple_photos(
    name: str,
    workspace_id: str,
    embeddings: list[list[float]],
    email: str | None = None,
    identity_id: str | None = None,
) -> str:
    """
    Enroll using the mean of multiple face embeddings for better robustness.
    """
    if not embeddings:
        raise ValueError("At least one embedding required")

    mean_embedding = np.array(embeddings).mean(axis=0).tolist()
    return enroll_identity(
        name=name,
        workspace_id=workspace_id,
        embedding=mean_embedding,
        email=email,
        identity_id=identity_id,
    )


# ═══════════════════════════════════════════════════════════════
# Matching
# ═══════════════════════════════════════════════════════════════

def match_face(
    embedding: list[float],
    workspace_id: str,
    top_k: int = 3,
) -> MatchResult:
    """
    Find the closest known identity for a given face embedding.

    Returns a MatchResult with matched=True if similarity >= threshold.
    """
    col = _get_collection()

    if col.count() == 0:
        return MatchResult(
            identity_id="", name="Unknown", email=None,
            similarity=0.0, matched=False,
        )

    results = col.query(
        query_embeddings=[embedding],
        n_results=min(top_k, col.count()),
        where={"workspace_id": workspace_id},
        include=["documents", "metadatas", "distances"],
    )

    if not results["ids"][0]:
        return MatchResult(
            identity_id="", name="Unknown", email=None,
            similarity=0.0, matched=False,
        )

    # Closest match
    best_id = results["ids"][0][0]
    best_meta = results["metadatas"][0][0]
    best_dist = results["distances"][0][0]
    similarity = round(1.0 - best_dist, 4)   # cosine distance → similarity

    matched = similarity >= _MATCH_THRESHOLD
    log.debug(
        "face_match",
        name=best_meta.get("name"),
        similarity=similarity,
        matched=matched,
    )
    return MatchResult(
        identity_id=best_id,
        name=best_meta.get("name", "Unknown"),
        email=best_meta.get("email") or None,
        similarity=similarity,
        matched=matched,
    )


def match_cluster(
    cluster_embedding: list[float],
    workspace_id: str,
) -> MatchResult:
    """Match a face cluster's centroid embedding against the identity DB."""
    return match_face(cluster_embedding, workspace_id)


# ═══════════════════════════════════════════════════════════════
# CRUD
# ═══════════════════════════════════════════════════════════════

def list_identities(workspace_id: str) -> list[dict[str, Any]]:
    """List all enrolled identities for a workspace."""
    col = _get_collection()
    if col.count() == 0:
        return []

    results = col.get(
        where={"workspace_id": workspace_id},
        include=["metadatas"],
    )
    return [
        {
            "id": iid,
            "name": meta.get("name", ""),
            "email": meta.get("email") or None,
            "photo_key": meta.get("photo_key") or None,
        }
        for iid, meta in zip(results["ids"], results["metadatas"])
    ]


def delete_identity(identity_id: str) -> None:
    """Remove an identity from the DB."""
    col = _get_collection()
    col.delete(ids=[identity_id])
    log.info("identity_deleted", id=identity_id)


def get_identity(identity_id: str) -> dict | None:
    """Fetch a single identity record by ID."""
    col = _get_collection()
    try:
        r = col.get(ids=[identity_id], include=["metadatas", "embeddings"])
        if not r["ids"]:
            return None
        meta = r["metadatas"][0]
        return {
            "id": r["ids"][0],
            "name": meta.get("name", ""),
            "email": meta.get("email") or None,
            "photo_key": meta.get("photo_key") or None,
            "embedding": r["embeddings"][0] if r.get("embeddings") else None,
        }
    except Exception:
        return None
