"""
api/routes/identities.py
Employee identity management:
  - Enroll a person with a reference photo
  - List / delete enrolled identities
  - Trigger face recognition on an already-processed meeting
"""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from api.deps import get_current_user, require_manager_or_above
from db.database import get_db
from models.orm import Meeting, MeetingStatus, User
from services.storage import get_storage

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/identities", tags=["identities"])

_ALLOWED_PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


# ── Schemas ───────────────────────────────────────────────────

class IdentityOut(BaseModel):
    id: str
    name: str
    email: str | None
    photo_url: str | None
    workspace_id: str


# ── List ──────────────────────────────────────────────────────

@router.get("", response_model=list[IdentityOut])
async def list_identities(
    current_user: User = Depends(get_current_user),
):
    """List all enrolled identities for the workspace."""
    from ai.face_recognition.identity_db import list_identities as _list

    records = _list(str(current_user.workspace_id))
    storage = get_storage()

    result = []
    for r in records:
        photo_url = None
        if r.get("photo_key"):
            try:
                photo_url = await storage.get_url(r["photo_key"], expires_in=3600)
            except Exception:
                pass
        result.append(IdentityOut(
            id=r["id"],
            name=r["name"],
            email=r.get("email"),
            photo_url=photo_url,
            workspace_id=str(current_user.workspace_id),
        ))
    return result


# ── Enroll ────────────────────────────────────────────────────

@router.post("/enroll", response_model=IdentityOut, status_code=status.HTTP_201_CREATED)
async def enroll_identity(
    name: str = Form(..., min_length=2, max_length=120),
    email: str = Form(default=""),
    photo: UploadFile = File(...),
    current_user: User = Depends(require_manager_or_above),
):
    """
    Enroll a person by uploading their reference photo.

    The photo is:
      1. Uploaded to storage
      2. Passed through InsightFace to extract a 512-dim embedding
      3. Stored in the face identity ChromaDB collection
    """
    ext = Path(photo.filename or "photo.jpg").suffix.lower()
    if ext not in _ALLOWED_PHOTO_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported photo format. Allowed: {', '.join(_ALLOWED_PHOTO_EXTS)}",
        )

    content = await photo.read()
    if len(content) > 10 * 1024 * 1024:    # 10 MB limit for photos
        raise HTTPException(status_code=413, detail="Photo exceeds 10 MB limit")

    identity_id = str(uuid.uuid4())
    wid = str(current_user.workspace_id)

    # Upload photo to storage
    photo_key = f"workspaces/{wid}/identities/{identity_id}/photo{ext}"
    storage = get_storage()
    await storage.upload_bytes(content, photo_key, photo.content_type or "image/jpeg")

    # Extract face embedding from photo
    embedding = await _extract_embedding_from_bytes(content)
    if embedding is None:
        # Clean up uploaded photo
        await storage.delete(photo_key)
        raise HTTPException(
            status_code=422,
            detail="No face detected in the uploaded photo. Please use a clear frontal face photo.",
        )

    # Enroll in identity DB
    from ai.face_recognition.identity_db import enroll_identity as _enroll
    _enroll(
        name=name,
        workspace_id=wid,
        embedding=embedding,
        email=email or None,
        photo_key=photo_key,
        identity_id=identity_id,
    )

    photo_url = await storage.get_url(photo_key, expires_in=3600)
    log.info("identity_enrolled_via_api", name=name, workspace=wid)

    return IdentityOut(
        id=identity_id,
        name=name,
        email=email or None,
        photo_url=photo_url,
        workspace_id=wid,
    )


# ── Delete ────────────────────────────────────────────────────

@router.delete("/{identity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_identity(
    identity_id: str,
    current_user: User = Depends(require_manager_or_above),
):
    from ai.face_recognition.identity_db import (
        delete_identity as _delete, get_identity,
    )

    record = get_identity(identity_id)
    if not record:
        raise HTTPException(status_code=404, detail="Identity not found")

    # Delete photo from storage
    if record.get("photo_key"):
        try:
            await get_storage().delete(record["photo_key"])
        except Exception:
            pass

    _delete(identity_id)
    log.info("identity_deleted_via_api", id=identity_id)


# ── Trigger face recognition on a meeting ────────────────────

@router.post("/meetings/{meeting_id}/recognize")
async def recognize_faces_in_meeting(
    meeting_id: uuid.UUID,
    current_user: User = Depends(require_manager_or_above),
    db: AsyncSession = Depends(get_db),
):
    """
    (Re-)run face recognition on an already-transcribed meeting.
    Queues a Celery task — returns task ID for polling.
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
    if meeting.status != MeetingStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Meeting not yet processed")
    if not meeting.file_key:
        raise HTTPException(status_code=400, detail="No video file associated with meeting")

    from workers.tasks import run_face_recognition_task
    task = run_face_recognition_task.delay(
        str(meeting_id),
        str(current_user.workspace_id),
    )
    return {"task_id": task.id, "status": "queued", "meeting_id": str(meeting_id)}


# ── Helper ────────────────────────────────────────────────────

async def _extract_embedding_from_bytes(image_bytes: bytes) -> list[float] | None:
    """
    Extract ArcFace embedding from raw image bytes.
    Runs in thread pool to avoid blocking the event loop.
    """
    import asyncio

    def _sync_extract():
        import cv2
        import numpy as np
        from ai.face_recognition.detector import _load_app

        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return None

        app = _load_app()
        faces = app.get(img)

        if not faces:
            return None

        # Use the face with highest detection confidence
        best = max(faces, key=lambda f: f.det_score)
        if best.det_score < 0.5 or best.embedding is None:
            return None

        return best.embedding.tolist()

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_extract)
