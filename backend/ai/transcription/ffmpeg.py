"""
ai/transcription/ffmpeg.py
Extract clean 16kHz mono WAV audio from any video/audio file.
Whisper performs best on 16kHz mono PCM WAV.
"""
from __future__ import annotations

import subprocess
import shutil
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)

# Target audio spec that Whisper performs best on
_SAMPLE_RATE = 16000
_CHANNELS = 1
_FORMAT = "wav"


def _ffmpeg_path() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise RuntimeError(
            "ffmpeg not found in PATH. Install with: apt install ffmpeg"
        )
    return path


def extract_audio(input_path: str, output_path: str | None = None) -> str:
    """
    Extract audio from input_path and write a 16kHz mono WAV.

    Args:
        input_path:  Path to source video or audio file.
        output_path: Destination WAV path. If None, replaces extension with .wav
                     in the same directory.

    Returns:
        Absolute path to the extracted WAV file.
    """
    src = Path(input_path)
    if not src.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    if output_path is None:
        output_path = str(src.with_suffix(".wav"))

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        _ffmpeg_path(),
        "-y",                          # overwrite without asking
        "-i", str(src),
        "-vn",                         # drop video stream
        "-acodec", "pcm_s16le",        # PCM 16-bit little-endian
        "-ar", str(_SAMPLE_RATE),      # 16 kHz sample rate
        "-ac", str(_CHANNELS),         # mono
        "-f", _FORMAT,
        str(out),
    ]

    log.info("ffmpeg_extract_start", src=str(src), dst=str(out))

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=600,   # 10-minute hard timeout
    )

    if result.returncode != 0:
        log.error("ffmpeg_failed", stderr=result.stderr[-500:])
        raise RuntimeError(f"ffmpeg extraction failed:\n{result.stderr[-400:]}")

    log.info("ffmpeg_extract_done", output=str(out), size_mb=out.stat().st_size // 1024 // 1024)
    return str(out)


def get_duration_seconds(input_path: str) -> float:
    """
    Use ffprobe to get the duration of an audio/video file in seconds.
    Returns 0.0 if it fails.
    """
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return 0.0

    cmd = [
        ffprobe, "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        input_path,
    ]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True, timeout=30)
        return float(out.strip())
    except Exception:
        return 0.0
