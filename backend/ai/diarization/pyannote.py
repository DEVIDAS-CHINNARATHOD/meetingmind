"""
ai/diarization/pyannote.py
Speaker diarization using pyannote.audio 3.x.

Diarization answers: "who spoke when?"
It produces time-stamped speaker segments (SPEAKER_00, SPEAKER_01, ...)
which are then merged with Whisper transcript segments.

Requirements:
  - pip install pyannote.audio
  - A HuggingFace token with access to:
      pyannote/speaker-diarization-3.1
      pyannote/segmentation-3.0
  Set HUGGINGFACE_TOKEN in .env
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import structlog

from config.settings import settings

log = structlog.get_logger(__name__)


# ═══════════════════════════════════════════════════════════════
# Data classes
# ═══════════════════════════════════════════════════════════════

@dataclass
class DiarizedSegment:
    speaker: str          # "SPEAKER_00", "SPEAKER_01", ...
    start: float          # seconds
    end: float


@dataclass
class DiarizationResult:
    segments: list[DiarizedSegment]
    num_speakers: int

    @property
    def speakers(self) -> list[str]:
        return sorted({s.speaker for s in self.segments})


# ═══════════════════════════════════════════════════════════════
# Model loader (cached per process)
# ═══════════════════════════════════════════════════════════════

@lru_cache(maxsize=1)
def _load_pipeline():
    try:
        from pyannote.audio import Pipeline
        import torch
    except ImportError:
        raise RuntimeError(
            "pyannote.audio not installed. Run: pip install pyannote.audio"
        )

    token = getattr(settings, "huggingface_token", None)
    if not token:
        raise RuntimeError(
            "HUGGINGFACE_TOKEN is required for pyannote diarization. "
            "Get one at huggingface.co and accept the pyannote model license."
        )

    log.info("loading_diarization_pipeline")
    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        use_auth_token=token,
    )

    # Use GPU if available
    try:
        if torch.cuda.is_available():
            pipeline = pipeline.to(torch.device("cuda"))
            log.info("diarization_using_gpu")
        else:
            log.info("diarization_using_cpu")
    except Exception:
        pass

    log.info("diarization_pipeline_loaded")
    return pipeline


# ═══════════════════════════════════════════════════════════════
# Core diarization
# ═══════════════════════════════════════════════════════════════

def diarize_audio(
    audio_path: str,
    min_speakers: int | None = None,
    max_speakers: int | None = None,
) -> DiarizationResult:
    """
    Run speaker diarization on a WAV file.

    Args:
        audio_path:   Path to 16kHz mono WAV file (output of ffmpeg.extract_audio).
        min_speakers: Optional hint for minimum expected speakers.
        max_speakers: Optional hint for maximum expected speakers.

    Returns:
        DiarizationResult with a list of (speaker, start, end) segments.
    """
    if not Path(audio_path).exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    pipeline = _load_pipeline()

    kwargs: dict = {}
    if min_speakers:
        kwargs["min_speakers"] = min_speakers
    if max_speakers:
        kwargs["max_speakers"] = max_speakers

    log.info("diarization_start", path=audio_path, **kwargs)

    diarization = pipeline(audio_path, **kwargs)

    segments: list[DiarizedSegment] = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        segments.append(DiarizedSegment(
            speaker=speaker,
            start=round(turn.start, 3),
            end=round(turn.end, 3),
        ))

    # Sort by start time
    segments.sort(key=lambda s: s.start)
    num_speakers = len({s.speaker for s in segments})

    log.info(
        "diarization_done",
        num_speakers=num_speakers,
        segments=len(segments),
    )
    return DiarizationResult(segments=segments, num_speakers=num_speakers)


# ═══════════════════════════════════════════════════════════════
# Merge diarization with Whisper transcript segments
# ═══════════════════════════════════════════════════════════════

def assign_speakers_to_transcript(
    transcript_segments: list[dict],
    diarization: DiarizationResult,
) -> list[dict]:
    """
    Assign a speaker label to each Whisper transcript segment
    using the diarization timeline.

    Strategy: for each transcript segment, find the diarization segment
    that has the maximum overlap with its [start, end] window.

    Args:
        transcript_segments: list of dicts with {text, start_time, end_time, ...}
        diarization: DiarizationResult from diarize_audio()

    Returns:
        Same list with 'speaker_label' field populated.
    """
    enriched = []
    for seg in transcript_segments:
        t_start = seg.get("start_time", seg.get("start", 0.0))
        t_end = seg.get("end_time", seg.get("end", t_start + 1.0))

        best_speaker: str | None = None
        best_overlap = 0.0

        for d_seg in diarization.segments:
            # Overlap between [t_start, t_end] and [d_seg.start, d_seg.end]
            overlap_start = max(t_start, d_seg.start)
            overlap_end = min(t_end, d_seg.end)
            overlap = max(0.0, overlap_end - overlap_start)

            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = d_seg.speaker

        enriched.append({
            **seg,
            "speaker_label": best_speaker,
        })

    return enriched


def compute_speaker_stats(
    transcript_segments: list[dict],
) -> dict[str, dict]:
    """
    Compute per-speaker talk time and word count from enriched segments.

    Returns:
        {
          "SPEAKER_00": {"talk_time_seconds": 142.3, "word_count": 312},
          ...
        }
    """
    stats: dict[str, dict] = {}
    for seg in transcript_segments:
        label = seg.get("speaker_label")
        if not label:
            continue
        if label not in stats:
            stats[label] = {"talk_time_seconds": 0.0, "word_count": 0}

        t_start = seg.get("start_time", seg.get("start", 0.0))
        t_end = seg.get("end_time", seg.get("end", t_start))
        stats[label]["talk_time_seconds"] += round(t_end - t_start, 3)
        stats[label]["word_count"] += len(seg.get("text", "").split())

    return stats
