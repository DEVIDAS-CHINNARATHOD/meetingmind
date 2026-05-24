"""
workers/face_tasks.py
Phase 3 Celery tasks for face recognition.

Separated from tasks.py to keep each file focused.
The main process_meeting task imports run_face_recognition_task
to optionally trigger face recognition after transcription+diarization.
"""
from __future__ import annotations

import asyncio
import shutil
import tempfile
import uuid
from pathlib import Path

import structlog
from sqlalchemy import select, update as sa_update

from workers.celery_app import celery_app

log = structlog.get_logger(__name__)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ═══════════════════════════════════════════════════════════════
# Standalone face recognition task
# Called on-demand via POST /identities/meetings/{id}/recognize
# ═══════════════════════════════════════════════════════════════

@celery_app.task(
    name="workers.tasks.run_face_recognition_task",
    bind=True,
    max_retries=1,
    time_limit=1800,   # 30 min
    soft_time_limit=1700,
)
def run_face_recognition_task(self, meeting_id: str, workspace_id: str) -> dict:
    """
    Run face recognition on a meeting's video file.
    Maps speaker labels → real names using the identity DB.
    Updates Participant and TranscriptSegment records.
    Triggers re-embedding so RAG uses real names.
    """
    from db.database import AsyncSessionLocal
    from models.orm import Meeting, Participant, TranscriptSegment
    from ai.face_recognition.pipeline import run_face_recognition, map_speakers_to_identities
    from services.storage import get_storage

    log.info("face_recognition_task_start", meeting_id=meeting_id)
    self.update_state(state="PROGRESS", meta={"step": "downloading_video", "progress": 5})

    tmp_dir = tempfile.mkdtemp(prefix="mm_faces_")

    try:
        storage = get_storage()

        # Fetch meeting
        async def _fetch():
            async with AsyncSessionLocal() as db:
                r = await db.execute(
                    select(Meeting).where(Meeting.id == uuid.UUID(meeting_id))
                )
                return r.scalar_one_or_none()

        meeting = _run(_fetch())
        if not meeting or not meeting.file_key:
            return {"error": "Meeting or video file not found"}

        # Download video to tmp
        video_path = _run(storage.get_local_path(meeting.file_key))
        frames_dir = str(Path(tmp_dir) / "frames")

        self.update_state(state="PROGRESS", meta={"step": "extracting_frames", "progress": 20})

        # Run face recognition
        face_result = run_face_recognition(
            video_path=video_path,
            workspace_id=workspace_id,
            frames_dir=frames_dir,
        )

        if face_result.identified_count == 0:
            log.info("face_recognition_no_matches", meeting_id=meeting_id)
            return {
                "meeting_id": meeting_id,
                "faces_detected": face_result.face_count,
                "clusters": face_result.cluster_count,
                "identified": 0,
                "message": "No faces matched enrolled identities",
            }

        self.update_state(state="PROGRESS", meta={"step": "mapping_speakers", "progress": 70})

        # Fetch diarization segments for temporal cross-reference
        async def _fetch_segments():
            async with AsyncSessionLocal() as db:
                r = await db.execute(
                    select(TranscriptSegment)
                    .where(TranscriptSegment.meeting_id == uuid.UUID(meeting_id))
                    .order_by(TranscriptSegment.segment_index)
                )
                return [
                    {
                        "speaker_label": s.speaker_label,
                        "start_time": s.start_time,
                        "end_time": s.end_time,
                    }
                    for s in r.scalars().all()
                ]

        segments = _run(_fetch_segments())

        # Map speaker labels to real names
        speaker_to_name = map_speakers_to_identities(segments, face_result)

        if not speaker_to_name:
            return {
                "meeting_id": meeting_id,
                "faces_detected": face_result.face_count,
                "clusters": face_result.cluster_count,
                "identified": face_result.identified_count,
                "message": "Could not map face clusters to diarization speakers",
            }

        self.update_state(state="PROGRESS", meta={"step": "updating_db", "progress": 85})

        # Update DB with real names
        async def _update_names():
            async with AsyncSessionLocal() as db:
                for label, name in speaker_to_name.items():
                    await db.execute(
                        sa_update(Participant)
                        .where(
                            Participant.meeting_id == uuid.UUID(meeting_id),
                            Participant.speaker_label == label,
                        )
                        .values(name=name)
                    )
                    await db.execute(
                        sa_update(TranscriptSegment)
                        .where(
                            TranscriptSegment.meeting_id == uuid.UUID(meeting_id),
                            TranscriptSegment.speaker_label == label,
                        )
                        .values(speaker_name=name)
                    )
                await db.commit()

        _run(_update_names())

        # Re-embed with real speaker names
        self.update_state(state="PROGRESS", meta={"step": "reembedding", "progress": 93})

        async def _fetch_for_embed():
            async with AsyncSessionLocal() as db:
                r = await db.execute(
                    select(TranscriptSegment)
                    .where(TranscriptSegment.meeting_id == uuid.UUID(meeting_id))
                    .order_by(TranscriptSegment.segment_index)
                )
                return [
                    {
                        "text": s.text,
                        "speaker_label": s.speaker_label,
                        "speaker_name": s.speaker_name,
                        "start_time": s.start_time,
                        "end_time": s.end_time,
                    }
                    for s in r.scalars().all()
                ]

        embed_segs = _run(_fetch_for_embed())
        from ai.embeddings.chroma import embed_meeting
        chunk_count = embed_meeting(
            meeting_id=meeting_id,
            meeting_title=meeting.title,
            workspace_id=workspace_id,
            transcript_segments=embed_segs,
        )

        log.info(
            "face_recognition_task_done",
            meeting_id=meeting_id,
            mapped=len(speaker_to_name),
            chunks=chunk_count,
        )
        return {
            "meeting_id": meeting_id,
            "faces_detected": face_result.face_count,
            "clusters": face_result.cluster_count,
            "identified": face_result.identified_count,
            "speaker_mappings": speaker_to_name,
            "chunks_reembedded": chunk_count,
        }

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════
# Batch enroll from meeting video frames
# (extracts faces seen in a meeting → proposes identities to admin)
# ═══════════════════════════════════════════════════════════════

@celery_app.task(name="workers.tasks.extract_faces_for_enrollment", max_retries=1)
def extract_faces_for_enrollment(
    meeting_id: str,
    workspace_id: str,
) -> dict:
    """
    Extract face clusters from a meeting video and return representative
    frame paths so admins can enroll them with names.

    Returns:
        {
          "clusters": [
            {"cluster_index": 0, "face_count": 12, "representative_frame_key": "..."},
            ...
          ]
        }
    """
    from db.database import AsyncSessionLocal
    from models.orm import Meeting
    from ai.face_recognition.detector import detect_faces_in_video, cluster_faces
    from services.storage import get_storage, make_report_key
    import cv2

    tmp_dir = tempfile.mkdtemp(prefix="mm_enroll_")

    try:
        storage = get_storage()

        async def _fetch():
            async with AsyncSessionLocal() as db:
                r = await db.execute(
                    select(Meeting).where(Meeting.id == uuid.UUID(meeting_id))
                )
                return r.scalar_one_or_none()

        meeting = _run(_fetch())
        if not meeting or not meeting.file_key:
            return {"error": "Meeting not found"}

        video_path = _run(storage.get_local_path(meeting.file_key))
        frames_dir = str(Path(tmp_dir) / "frames")

        all_faces = detect_faces_in_video(video_path, frames_dir, interval_sec=3.0)
        if not all_faces:
            return {"clusters": [], "message": "No faces detected"}

        clusters = cluster_faces(all_faces)
        cluster_data = []

        for i, cluster in enumerate(clusters):
            if not cluster.faces:
                continue

            # Find the highest-confidence face in the cluster
            best_face = max(cluster.faces, key=lambda f: f.confidence)
            frame_path = str(
                Path(frames_dir) / f"frame_{best_face.frame_index:04d}.jpg"
            )

            # Upload representative frame to storage
            rep_key = (
                f"workspaces/{workspace_id}/meetings/{meeting_id}"
                f"/face_clusters/cluster_{i}_representative.jpg"
            )
            if Path(frame_path).exists():
                with open(frame_path, "rb") as fp:
                    _run(storage.upload_file(fp, rep_key, "image/jpeg"))

            cluster_data.append({
                "cluster_index": i,
                "face_count": len(cluster.faces),
                "representative_frame_key": rep_key,
                "first_appearance_sec": min(f.frame_time for f in cluster.faces),
                "best_confidence": round(best_face.confidence, 3),
            })

        log.info("enrollment_extraction_done",
                 meeting_id=meeting_id, clusters=len(cluster_data))
        return {"clusters": cluster_data}

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
