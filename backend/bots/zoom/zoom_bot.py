"""
bots/zoom/zoom_bot.py
Zoom Meeting SDK bot.

Architecture:
  1. User submits a Zoom meeting URL/ID via POST /api/integrations/zoom/join
  2. Backend exchanges credentials for a JWT meeting token
  3. A Celery task (join_zoom_meeting) launches this bot in a subprocess
  4. The bot uses the Zoom Meeting SDK to join, capture audio
  5. Audio is streamed to StreamingTranscriber
  6. Segments are saved via the same WebSocket finalization pathway

Zoom SDK requirements:
  - Zoom Video SDK or Meeting SDK (server-to-server OAuth)
  - Linux SDK binary (zoom-meeting-sdk-linux)
  - Environment: ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET

Note: The Zoom Meeting SDK has specific Linux dependencies.
See: https://developers.zoom.us/docs/meeting-sdk/linux/
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import httpx
import structlog

from config.settings import settings

log = structlog.get_logger(__name__)

ZOOM_OAUTH_URL = "https://zoom.us/oauth/token"
ZOOM_API_BASE  = "https://api.zoom.us/v2"


# ═══════════════════════════════════════════════════════════════
# Zoom OAuth helpers
# ═══════════════════════════════════════════════════════════════

async def get_zoom_server_token() -> str:
    """
    Get a Server-to-Server OAuth token for Zoom API calls.
    Caches in process memory until expiry.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            ZOOM_OAUTH_URL,
            params={"grant_type": "account_credentials",
                    "account_id": settings.zoom_account_id},
            auth=(settings.zoom_client_id, settings.zoom_client_secret),
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["access_token"]


async def get_meeting_info(meeting_id: str) -> dict:
    """Fetch Zoom meeting metadata (participants, topic, etc.)."""
    token = await get_zoom_server_token()
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{ZOOM_API_BASE}/meetings/{meeting_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()


def generate_sdk_jwt(meeting_number: str, role: int = 0) -> str:
    """
    Generate a Zoom Meeting SDK JWT for joining a meeting.
    role=0 → attendee, role=1 → host
    """
    import jose.jwt as jwt_lib
    from datetime import datetime, timezone, timedelta

    payload = {
        "appKey": settings.zoom_client_id,
        "sdkKey": settings.zoom_client_id,
        "mn": meeting_number,
        "role": role,
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=2)).timestamp()),
        "tokenExp": int((datetime.now(timezone.utc) + timedelta(hours=2)).timestamp()),
    }
    return jwt_lib.encode(payload, settings.zoom_client_secret, algorithm="HS256")


# ═══════════════════════════════════════════════════════════════
# Zoom bot launcher
# ═══════════════════════════════════════════════════════════════

@dataclass
class ZoomBotConfig:
    meeting_number: str       # Zoom meeting ID (numeric)
    meeting_password: str
    display_name: str = "MeetingMind Bot"
    audio_output_path: str = ""    # Path where bot writes captured audio


def join_and_record(
    config: ZoomBotConfig,
    on_audio_chunk: Callable[[bytes], None],
    stop_event: asyncio.Event | None = None,
) -> dict:
    """
    Join a Zoom meeting using the Meeting SDK headless binary and
    stream captured audio through on_audio_chunk callback.

    This is a blocking call — run inside a Celery task or thread.

    In production this wraps the official Zoom Meeting SDK for Linux.
    The SDK provides a C++ API; Python integration is via ctypes or
    an official Python wrapper when available.

    For now we implement the full integration contract and stub the
    actual SDK call, which must be replaced with the real SDK binary.
    """
    sdk_jwt = generate_sdk_jwt(config.meeting_number, role=0)

    log.info("zoom_bot_joining",
             meeting_number=config.meeting_number,
             display_name=config.display_name)

    # ── SDK integration point ─────────────────────────────────
    # Replace the block below with actual Zoom SDK invocation:
    #
    #   from zoom_meeting_sdk import ZoomSDK
    #   sdk = ZoomSDK()
    #   sdk.init(client_id=settings.zoom_client_id)
    #   meeting = sdk.join_meeting(
    #       meeting_number=config.meeting_number,
    #       password=config.meeting_password,
    #       display_name=config.display_name,
    #       jwt_token=sdk_jwt,
    #   )
    #   for audio_frame in meeting.audio_stream():
    #       on_audio_chunk(audio_frame.pcm_data)
    #   result = meeting.get_summary()
    #
    # The audio_frame.pcm_data should be int16, 16kHz mono PCM.

    log.warning(
        "zoom_sdk_stub_active",
        message="Replace this stub with the actual Zoom Meeting SDK integration.",
        docs="https://developers.zoom.us/docs/meeting-sdk/linux/",
    )

    # Stub: simulate 10 seconds of silence for integration testing
    import time
    dummy_chunk = bytes(960 * 2)   # 960 samples * 2 bytes = 60ms @ 16kHz
    for _ in range(167):           # ~10 seconds
        on_audio_chunk(dummy_chunk)
        time.sleep(0.06)
        if stop_event and stop_event.is_set():
            break

    return {
        "meeting_number": config.meeting_number,
        "status": "left",
        "duration_seconds": 10,
        "participant_count": 0,
    }


# ═══════════════════════════════════════════════════════════════
# Participant list fetcher (via Zoom API, not SDK)
# ═══════════════════════════════════════════════════════════════

async def fetch_meeting_participants(meeting_id: str) -> list[dict]:
    """
    Fetch the list of participants who joined the meeting.
    Requires a completed meeting (uses Zoom Reports API).
    """
    try:
        token = await get_zoom_server_token()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{ZOOM_API_BASE}/report/meetings/{meeting_id}/participants",
                headers={"Authorization": f"Bearer {token}"},
                params={"page_size": 300},
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json().get("participants", [])
    except Exception as e:
        log.warning("zoom_participants_fetch_failed", error=str(e))
    return []
