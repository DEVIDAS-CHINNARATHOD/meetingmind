"""
ai/transcription/whisper.py
Faster Whisper transcription with word-level timestamps.
Loaded once per worker process (model is heavy — cache it).
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterator

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings

log = structlog.get_logger(__name__)


@dataclass
class TranscriptWord:
    word: str
    start: float
    end: float
    probability: float


@dataclass
class TranscriptSegment:
    id: int
    text: str
    start: float
    end: float
    confidence: float
    words: list[TranscriptWord]


@dataclass
class TranscriptionResult:
    segments: list[TranscriptSegment]
    language: str
    language_probability: float
    duration_seconds: float
    word_count: int

    @property
    def full_text(self) -> str:
        return " ".join(s.text.strip() for s in self.segments)


@lru_cache(maxsize=1)
def _load_model():
    """
    Load Faster Whisper model once per process.
    lru_cache ensures the heavy model stays in RAM across tasks.
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise RuntimeError("faster-whisper not installed. Run: pip install faster-whisper")

    log.info(
        "loading_whisper_model",
        size=settings.whisper_model_size,
        device=settings.whisper_device,
        compute_type=settings.whisper_compute_type,
    )
    model = WhisperModel(
        settings.whisper_model_size,
        device=settings.whisper_device,
        compute_type=settings.whisper_compute_type,
    )
    log.info("whisper_model_loaded")
    return model


def transcribe_audio(audio_path: str) -> TranscriptionResult:
    """
    Synchronous transcription — called inside a Celery worker.

    Args:
        audio_path: Local filesystem path to a WAV/MP3/etc. file.

    Returns:
        TranscriptionResult with segments, language, duration.
    """
    if not Path(audio_path).exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    model = _load_model()
    t0 = time.perf_counter()

    log.info("transcription_start", path=audio_path)

    segments_iter, info = model.transcribe(
        audio_path,
        beam_size=5,
        word_timestamps=True,
        vad_filter=True,               # Voice Activity Detection — skip silence
        vad_parameters={"min_silence_duration_ms": 500},
        language=None,                 # auto-detect
    )

    segments: list[TranscriptSegment] = []
    for i, seg in enumerate(segments_iter):
        words = []
        if seg.words:
            words = [
                TranscriptWord(
                    word=w.word,
                    start=w.start,
                    end=w.end,
                    probability=w.probability,
                )
                for w in seg.words
            ]
        segments.append(
            TranscriptSegment(
                id=i,
                text=seg.text.strip(),
                start=seg.start,
                end=seg.end,
                confidence=seg.avg_logprob,  # log probability; closer to 0 = better
                words=words,
            )
        )

    elapsed = time.perf_counter() - t0
    word_count = sum(len(s.text.split()) for s in segments)

    log.info(
        "transcription_complete",
        duration_s=round(elapsed, 2),
        segments=len(segments),
        language=info.language,
        language_prob=round(info.language_probability, 3),
    )

    return TranscriptionResult(
        segments=segments,
        language=info.language,
        language_probability=info.language_probability,
        duration_seconds=info.duration,
        word_count=word_count,
    )
