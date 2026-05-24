"""
ai/realtime/streaming_transcriber.py
Chunked real-time transcription for live meeting audio.

Strategy:
  - Audio arrives as raw PCM bytes (16kHz, mono, int16)
  - We buffer chunks until we have enough audio (~3 seconds)
  - Each buffer is transcribed independently by Faster Whisper
  - Segments are emitted with running timestamps
  - A sliding overlap window prevents words being cut at chunk boundaries
"""
from __future__ import annotations

import io
import struct
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import structlog

log = structlog.get_logger(__name__)

# Audio constants — must match capture settings
SAMPLE_RATE = 16_000        # Hz
BYTES_PER_SAMPLE = 2        # int16
CHANNELS = 1

# Chunk settings
CHUNK_DURATION_SEC = 3.0    # transcribe every N seconds
OVERLAP_DURATION_SEC = 0.5  # overlap to avoid boundary cuts
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_DURATION_SEC)
OVERLAP_SAMPLES = int(SAMPLE_RATE * OVERLAP_DURATION_SEC)
SILENCE_THRESHOLD = 200     # RMS below this = silence


@dataclass
class RealtimeSegment:
    text: str
    start_time: float        # seconds from meeting start
    end_time: float
    is_final: bool           # False = in-progress, True = confirmed segment
    confidence: float | None = None


@dataclass
class StreamingTranscriberState:
    buffer: bytearray = field(default_factory=bytearray)
    elapsed_seconds: float = 0.0
    segment_counter: int = 0
    last_overlap: bytearray = field(default_factory=bytearray)


class StreamingTranscriber:
    """
    Thread-safe streaming transcriber.
    Call feed(pcm_bytes) as audio arrives.
    Pass on_segment callback to receive RealtimeSegment emissions.
    """

    def __init__(self, on_segment: Callable[[RealtimeSegment], None]):
        self._on_segment = on_segment
        self._state = StreamingTranscriberState()
        self._lock = threading.Lock()
        self._running = True
        self._model = None

    def _get_model(self):
        if self._model is None:
            from ai.transcription.whisper import _load_model
            self._model = _load_model()
        return self._model

    def feed(self, pcm_bytes: bytes) -> None:
        """
        Feed raw PCM audio bytes (int16, 16kHz mono).
        Thread-safe — can be called from any thread.
        """
        if not self._running:
            return
        with self._lock:
            self._state.buffer.extend(pcm_bytes)
            if len(self._state.buffer) >= CHUNK_SAMPLES * BYTES_PER_SAMPLE:
                self._flush_chunk()

    def flush(self) -> None:
        """Force-transcribe any remaining audio in the buffer."""
        with self._lock:
            if len(self._state.buffer) > SAMPLE_RATE * BYTES_PER_SAMPLE:
                self._flush_chunk(final=True)

    def stop(self) -> None:
        self.flush()
        self._running = False

    def _flush_chunk(self, final: bool = False) -> None:
        """Internal — must be called with self._lock held."""
        state = self._state
        chunk_bytes = bytes(state.last_overlap) + bytes(state.buffer)
        chunk_size = CHUNK_SAMPLES * BYTES_PER_SAMPLE

        audio_to_process = chunk_bytes[:chunk_size]
        state.last_overlap = bytearray(chunk_bytes[chunk_size - OVERLAP_SAMPLES * BYTES_PER_SAMPLE:chunk_size])
        state.buffer = bytearray(chunk_bytes[chunk_size:])

        # Convert PCM bytes → float32 numpy array for Whisper
        pcm_int16 = np.frombuffer(audio_to_process, dtype=np.int16)
        audio_float = pcm_int16.astype(np.float32) / 32768.0

        # Skip near-silent chunks
        rms = float(np.sqrt(np.mean(pcm_int16.astype(np.float64) ** 2)))
        if rms < SILENCE_THRESHOLD and not final:
            state.elapsed_seconds += CHUNK_DURATION_SEC
            return

        chunk_start = state.elapsed_seconds
        state.elapsed_seconds += CHUNK_DURATION_SEC

        try:
            self._transcribe_chunk(audio_float, chunk_start, is_final=final)
        except Exception as e:
            log.warning("realtime_transcription_error", error=str(e))

    def _transcribe_chunk(
        self,
        audio: np.ndarray,
        chunk_start: float,
        is_final: bool,
    ) -> None:
        import tempfile, os, soundfile as sf

        # Write to tmp WAV (Whisper needs a file path)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_path = f.name
        try:
            sf.write(tmp_path, audio, SAMPLE_RATE)
            model = self._get_model()
            segments_iter, info = model.transcribe(
                tmp_path,
                beam_size=3,        # faster than beam_size=5 for real-time
                word_timestamps=False,
                vad_filter=True,
                language=None,
            )
            for seg in segments_iter:
                if not seg.text.strip():
                    continue
                segment = RealtimeSegment(
                    text=seg.text.strip(),
                    start_time=chunk_start + seg.start,
                    end_time=chunk_start + seg.end,
                    is_final=is_final,
                    confidence=seg.avg_logprob,
                )
                self._on_segment(segment)
        finally:
            os.unlink(tmp_path)
