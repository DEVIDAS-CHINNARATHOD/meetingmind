"""
ai/face_recognition/detector.py
Face detection and embedding extraction using InsightFace.

InsightFace provides:
  - Face detection (bounding boxes, landmarks)
  - Face embedding (512-dim vector per face)

These embeddings are stored in the employee database and matched
against faces extracted from meeting video frames.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import structlog

log = structlog.get_logger(__name__)


# ═══════════════════════════════════════════════════════════════
# Data classes
# ═══════════════════════════════════════════════════════════════

@dataclass
class DetectedFace:
    bbox: list[float]          # [x1, y1, x2, y2] in pixels
    embedding: list[float]     # 512-dimensional face embedding
    confidence: float          # detection confidence score
    frame_index: int           # which video frame this came from
    timestamp_seconds: float   # video timestamp


@dataclass
class FaceMatchResult:
    employee_id: str
    employee_name: str
    similarity: float          # cosine similarity 0..1 (higher = better match)
    is_match: bool             # True if similarity >= threshold


# ═══════════════════════════════════════════════════════════════
# Model loader
# ═══════════════════════════════════════════════════════════════

@lru_cache(maxsize=1)
def _load_face_app():
    """Load InsightFace ArcFace model (cached per process)."""
    try:
        import insightface
        from insightface.app import FaceAnalysis
    except ImportError:
        raise RuntimeError(
            "insightface not installed. Run: pip install insightface onnxruntime"
        )

    log.info("loading_insightface_model")
    face_app = FaceAnalysis(
        name="buffalo_l",          # ArcFace R100 model
        providers=["CPUExecutionProvider"],   # swap to CUDAExecutionProvider for GPU
    )
    face_app.prepare(ctx_id=0, det_size=(640, 640))
    log.info("insightface_model_loaded")
    return face_app


# ═══════════════════════════════════════════════════════════════
# Frame extraction from video
# ═══════════════════════════════════════════════════════════════

def extract_frames(
    video_path: str,
    sample_rate_fps: float = 0.5,    # 1 frame every 2 seconds
    max_frames: int = 120,           # cap at 120 frames (~4 min of sampling)
) -> list[tuple[np.ndarray, int, float]]:
    """
    Extract sampled frames from a video file using OpenCV.

    Args:
        video_path:      Path to video file.
        sample_rate_fps: How many frames per second to sample.
        max_frames:      Hard cap on number of frames extracted.

    Returns:
        List of (frame_bgr, frame_index, timestamp_seconds)
    """
    try:
        import cv2
    except ImportError:
        raise RuntimeError("opencv-python not installed. Run: pip install opencv-python-headless")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    video_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / video_fps

    # Calculate which frame indices to sample
    sample_interval = max(1, int(video_fps / sample_rate_fps))
    sample_indices = list(range(0, total_frames, sample_interval))[:max_frames]

    frames: list[tuple[np.ndarray, int, float]] = []
    for idx in sample_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            continue
        timestamp = idx / video_fps
        frames.append((frame, idx, timestamp))

    cap.release()
    log.info(
        "frames_extracted",
        video=video_path,
        total_video_frames=total_frames,
        sampled=len(frames),
        duration_s=round(duration, 1),
    )
    return frames


# ═══════════════════════════════════════════════════════════════
# Face detection on frames
# ═══════════════════════════════════════════════════════════════

def detect_faces_in_frames(
    frames: list[tuple[np.ndarray, int, float]],
    min_face_size: int = 40,          # minimum face bounding-box dimension (pixels)
    min_confidence: float = 0.6,
) -> list[DetectedFace]:
    """
    Run InsightFace detection on sampled frames.
    Returns all detected faces with embeddings.
    """
    face_app = _load_face_app()
    detected: list[DetectedFace] = []

    for frame_bgr, frame_idx, timestamp in frames:
        try:
            faces = face_app.get(frame_bgr)
        except Exception as e:
            log.warning("face_detection_frame_error", frame=frame_idx, error=str(e))
            continue

        for face in faces:
            # Filter tiny / low-confidence detections
            bbox = face.bbox.tolist()
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            if w < min_face_size or h < min_face_size:
                continue
            if face.det_score < min_confidence:
                continue

            embedding = face.normed_embedding.tolist()   # 512-dim L2-normalized
            detected.append(DetectedFace(
                bbox=bbox,
                embedding=embedding,
                confidence=float(face.det_score),
                frame_index=frame_idx,
                timestamp_seconds=timestamp,
            ))

    log.info("face_detection_done", frames=len(frames), faces_found=len(detected))
    return detected


# ═══════════════════════════════════════════════════════════════
# Cosine similarity matching
# ═══════════════════════════════════════════════════════════════

def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two L2-normalised embedding vectors."""
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    # InsightFace returns normed embeddings, so dot product == cosine sim
    return float(np.dot(va, vb))


def match_face_to_employees(
    face_embedding: list[float],
    employee_embeddings: list[dict],   # [{employee_id, name, embedding}]
    threshold: float = 0.45,           # ArcFace typical threshold for same-person
) -> FaceMatchResult | None:
    """
    Find the best-matching employee for a detected face embedding.

    Args:
        face_embedding:      512-dim embedding from detected face.
        employee_embeddings: List of known employee face embeddings from DB.
        threshold:           Minimum similarity to count as a match.

    Returns:
        FaceMatchResult if a match is found, None otherwise.
    """
    if not employee_embeddings:
        return None

    best_score = -1.0
    best_employee: dict | None = None

    for emp in employee_embeddings:
        score = cosine_similarity(face_embedding, emp["embedding"])
        if score > best_score:
            best_score = score
            best_employee = emp

    if best_employee is None:
        return None

    return FaceMatchResult(
        employee_id=best_employee["employee_id"],
        employee_name=best_employee["name"],
        similarity=round(best_score, 4),
        is_match=best_score >= threshold,
    )


# ═══════════════════════════════════════════════════════════════
# Aggregate: most likely person per speaker segment
# ═══════════════════════════════════════════════════════════════

def identify_speakers_by_face(
    detected_faces: list[DetectedFace],
    speaker_segments: list[dict],       # [{speaker_label, start_time, end_time}]
    employee_embeddings: list[dict],
    threshold: float = 0.45,
) -> dict[str, str]:
    """
    For each speaker label, collect all face detections that occurred
    during that speaker's talk time, match them to employees, and
    return the most-voted identity.

    Returns:
        {speaker_label: employee_name}  (only for matched speakers)
    """
    from collections import Counter, defaultdict

    # Group face timestamps by speaker label
    speaker_face_matches: dict[str, list[str]] = defaultdict(list)

    for face in detected_faces:
        # Find which speaker was talking at this face's timestamp
        t = face.timestamp_seconds
        for seg in speaker_segments:
            if seg["start_time"] <= t <= seg["end_time"]:
                label = seg.get("speaker_label")
                if not label:
                    continue
                match = match_face_to_employees(
                    face.embedding, employee_embeddings, threshold
                )
                if match and match.is_match:
                    speaker_face_matches[label].append(match.employee_name)
                break

    # Majority vote per speaker
    result: dict[str, str] = {}
    for label, names in speaker_face_matches.items():
        if names:
            most_common, count = Counter(names).most_common(1)[0]
            # Only accept if at least 2 face matches agree (reduces false positives)
            if count >= 2 or len(names) == 1:
                result[label] = most_common
                log.info(
                    "speaker_identified",
                    label=label,
                    name=most_common,
                    votes=count,
                    total=len(names),
                )

    return result
