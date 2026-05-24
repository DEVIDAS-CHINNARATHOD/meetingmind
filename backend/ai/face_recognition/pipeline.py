"""
ai/face_recognition/pipeline.py
High-level face recognition pipeline for a meeting video.

Given a video file and a workspace:
  1. Extract frames
  2. Detect + embed all faces
  3. Cluster faces by identity
  4. Match each cluster against the identity DB
  5. Return speaker_label → person_name mapping

This output is used in workers/tasks.py to upgrade speaker labels
("SPEAKER_00") to real names ("Priya Sharma").
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger(__name__)


@dataclass
class FaceRecognitionResult:
    """
    Maps diarization speaker labels to identified people.
    face_timeline: list of {frame_time, speaker_label (cluster index), name, similarity}
    speaker_map:   {cluster_index_str → {name, similarity, matched}}
    """
    speaker_map: dict[str, dict[str, Any]]    # cluster_N → {name, similarity, matched}
    face_count: int
    cluster_count: int
    identified_count: int


def run_face_recognition(
    video_path: str,
    workspace_id: str,
    frames_dir: str,
    interval_sec: float = 5.0,
    max_frames: int = 200,
) -> FaceRecognitionResult:
    """
    Full face recognition pipeline for a meeting video.

    Args:
        video_path:   Path to the original video file.
        workspace_id: Used to scope identity DB queries.
        frames_dir:   Temp directory for extracted frames.
        interval_sec: Frame extraction interval.
        max_frames:   Max frames to process.

    Returns:
        FaceRecognitionResult with speaker_map populated.
    """
    from ai.face_recognition.detector import (
        detect_faces_in_video, cluster_faces,
    )
    from ai.face_recognition.identity_db import match_cluster

    log.info("face_recognition_start", video=video_path, workspace=workspace_id)

    # 1. Detect all faces across video frames
    all_faces = detect_faces_in_video(
        video_path=video_path,
        frames_dir=frames_dir,
        interval_sec=interval_sec,
        max_frames=max_frames,
    )

    if not all_faces:
        log.warning("no_faces_detected", video=video_path)
        return FaceRecognitionResult(
            speaker_map={}, face_count=0, cluster_count=0, identified_count=0
        )

    # 2. Cluster faces by identity
    clusters = cluster_faces(all_faces)

    # 3. Match each cluster against identity DB
    speaker_map: dict[str, dict[str, Any]] = {}
    identified = 0

    for i, cluster in enumerate(clusters):
        cluster_key = f"cluster_{i}"
        match = match_cluster(cluster.representative_embedding, workspace_id)

        speaker_map[cluster_key] = {
            "name": match.name if match.matched else f"Unknown Person {i + 1}",
            "identity_id": match.identity_id if match.matched else None,
            "email": match.email if match.matched else None,
            "similarity": match.similarity,
            "matched": match.matched,
            "face_count": len(cluster.faces),
            "frame_times": [f.frame_time for f in cluster.faces[:5]],  # first 5 appearances
        }
        if match.matched:
            identified += 1

    log.info(
        "face_recognition_done",
        faces=len(all_faces),
        clusters=len(clusters),
        identified=identified,
    )
    return FaceRecognitionResult(
        speaker_map=speaker_map,
        face_count=len(all_faces),
        cluster_count=len(clusters),
        identified_count=identified,
    )


def map_speakers_to_identities(
    diarization_segments: list[dict],
    face_result: FaceRecognitionResult,
    frame_interval: float = 5.0,
) -> dict[str, str]:
    """
    Cross-reference diarization speaker labels with face recognition clusters
    using temporal co-occurrence.

    Strategy:
      For each diarization speaker label, find which face cluster appears
      most frequently during their speaking turns.

    Args:
        diarization_segments: [{speaker_label, start_time, end_time}, ...]
        face_result:          Output of run_face_recognition()
        frame_interval:       Frame extraction interval (must match recognition run)

    Returns:
        {speaker_label → person_name}  e.g. {"SPEAKER_00": "Priya Sharma"}
    """
    if not face_result.speaker_map:
        return {}

    # Build: cluster_key → list of frame_times
    cluster_times: dict[str, list[float]] = {
        k: v["frame_times"] for k, v in face_result.speaker_map.items()
    }

    # For each diarization speaker, tally cluster co-occurrences
    speaker_cluster_votes: dict[str, dict[str, int]] = {}

    for seg in diarization_segments:
        label = seg.get("speaker_label")
        if not label:
            continue
        start = seg.get("start_time", 0.0)
        end = seg.get("end_time", start)

        if label not in speaker_cluster_votes:
            speaker_cluster_votes[label] = {}

        for cluster_key, times in cluster_times.items():
            for t in times:
                if start <= t <= end:
                    speaker_cluster_votes[label][cluster_key] = (
                        speaker_cluster_votes[label].get(cluster_key, 0) + 1
                    )

    # Assign: speaker_label → best-matching cluster → person name
    speaker_to_name: dict[str, str] = {}
    for speaker_label, votes in speaker_cluster_votes.items():
        if not votes:
            continue
        best_cluster = max(votes, key=votes.get)
        cluster_info = face_result.speaker_map.get(best_cluster, {})
        if cluster_info.get("matched"):
            speaker_to_name[speaker_label] = cluster_info["name"]

    log.info(
        "speaker_identity_mapping_done",
        mapped=len(speaker_to_name),
        total_speakers=len(speaker_cluster_votes),
    )
    return speaker_to_name
