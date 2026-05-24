"""
bots/meet/meet_bot.py
Google Meet bot using Playwright browser automation.

Architecture:
  - Launches a headless Chromium browser with a fake microphone/camera
  - Navigates to the Google Meet URL
  - Joins the meeting (auto-dismisses dialogs, mutes mic/camera)
  - Intercepts audio output via Chrome's MediaRecorder API (injected JS)
  - Streams PCM audio back to Python for real-time transcription

Requirements:
  pip install playwright
  playwright install chromium

Permissions note:
  - Uses Google OAuth token to join meetings where the bot is invited
  - Or joins public meetings without auth (guest mode)
  - Audio capture uses Web Audio API injected into the browser page

Audio pipeline:
  Browser AudioContext → ScriptProcessor → PCM chunks →
  window.postMessage → Playwright page.on("console") →
  Python bytes → StreamingTranscriber
"""
from __future__ import annotations

import asyncio
import base64
import json
import time
import uuid
from dataclasses import dataclass
from typing import Callable

import structlog

log = structlog.get_logger(__name__)


# ═══════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════

@dataclass
class MeetBotConfig:
    meet_url: str
    display_name: str = "MeetingMind Bot 🎙️"
    auto_admit_timeout_sec: int = 120   # wait up to 2 min to be admitted
    max_duration_sec: int = 7200        # 2-hour safety cutoff


# ═══════════════════════════════════════════════════════════════
# Audio capture injection script
# ═══════════════════════════════════════════════════════════════

# JavaScript injected into the Meet page to capture audio output
# via Web Audio API and ship it back to Python as base64 PCM
_AUDIO_CAPTURE_JS = """
(function() {
  if (window.__meetingmind_capturing) return;
  window.__meetingmind_capturing = true;
  window.__meetingmind_chunks = [];

  const audioCtx = new (window.AudioContext || window.webkitAudioContext)({
    sampleRate: 16000
  });

  // Capture all audio output (remote participants) by hooking the destination
  const dest = audioCtx.destination;
  const processor = audioCtx.createScriptProcessor(2048, 1, 1);

  processor.onaudioprocess = function(e) {
    const inputData = e.inputBuffer.getChannelData(0);
    // Convert float32 → int16 PCM
    const pcm = new Int16Array(inputData.length);
    for (let i = 0; i < inputData.length; i++) {
      pcm[i] = Math.max(-32768, Math.min(32767, inputData[i] * 32768));
    }
    const b64 = btoa(String.fromCharCode(...new Uint8Array(pcm.buffer)));
    console.log('__mm_audio__' + b64);
  };

  // Hook into Meet's internal audio output
  const origCreateMediaStreamDestination =
    AudioContext.prototype.createMediaStreamDestination;
  AudioContext.prototype.createMediaStreamDestination = function() {
    const node = origCreateMediaStreamDestination.apply(this, arguments);
    this.createMediaStreamSource(node.stream).connect(processor);
    processor.connect(audioCtx.destination);
    return node;
  };

  console.log('__mm_audio_ready__');
})();
"""

# CSS selectors for Google Meet UI elements (updated periodically)
_SELECTORS = {
    "join_button":      '[data-prism-action="joinAction"], [jsname="Qx7uuf"]',
    "dismiss_button":   '[jsname="EszDEe"], [aria-label*="Dismiss"]',
    "mute_mic":         '[data-tooltip*="microphone"], [aria-label*="microphone"]',
    "turn_off_camera":  '[data-tooltip*="camera"], [aria-label*="camera"]',
    "leave_button":     '[data-tooltip="Leave call"], [aria-label="Leave call"]',
    "participant_count":'[data-tooltip*="people"], [class*="participants"]',
}


# ═══════════════════════════════════════════════════════════════
# Bot implementation
# ═══════════════════════════════════════════════════════════════

async def join_and_record(
    config: MeetBotConfig,
    on_audio_chunk: Callable[[bytes], None],
    stop_event: asyncio.Event | None = None,
) -> dict:
    """
    Main bot coroutine. Joins Google Meet, captures audio, calls on_audio_chunk.

    Args:
        config:         MeetBotConfig with URL and settings.
        on_audio_chunk: Called with raw PCM bytes (int16, 16kHz, mono).
        stop_event:     Set this to gracefully stop the bot.

    Returns:
        Summary dict with duration, participant_count, etc.
    """
    try:
        from playwright.async_api import async_playwright, TimeoutError as PWTimeout
    except ImportError:
        raise RuntimeError(
            "playwright not installed. Run: pip install playwright && playwright install chromium"
        )

    start_time = time.time()
    audio_chunks_received = [0]
    participants: set[str] = set()

    async with async_playwright() as pw:
        # Launch headless Chromium with fake media devices
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--use-fake-ui-for-media-stream",    # auto-allow microphone/camera
                "--use-fake-device-for-media-stream",
                "--disable-web-security",
                "--allow-running-insecure-content",
                "--autoplay-policy=no-user-gesture-required",
            ],
        )

        context = await browser.new_context(
            permissions=["microphone", "camera"],
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        # ── Audio capture via console messages ───────────────
        def handle_console(msg):
            text = msg.text
            if text.startswith("__mm_audio__"):
                b64_data = text[len("__mm_audio__"):]
                try:
                    pcm_bytes = base64.b64decode(b64_data)
                    on_audio_chunk(pcm_bytes)
                    audio_chunks_received[0] += 1
                except Exception:
                    pass
            elif text == "__mm_audio_ready__":
                log.info("meet_audio_capture_active", url=config.meet_url)

        page.on("console", handle_console)

        # ── Navigate to Meet ──────────────────────────────────
        log.info("meet_bot_navigating", url=config.meet_url)
        await page.goto(config.meet_url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        # ── Set display name ──────────────────────────────────
        try:
            name_input = await page.wait_for_selector(
                'input[placeholder*="name"], input[aria-label*="name"]',
                timeout=5000,
            )
            await name_input.fill(config.display_name)
        except Exception:
            pass   # name field may not appear if already signed in

        # ── Dismiss pre-join dialogs ──────────────────────────
        for _ in range(3):
            try:
                dismiss = await page.query_selector(_SELECTORS["dismiss_button"])
                if dismiss:
                    await dismiss.click()
                    await asyncio.sleep(0.5)
            except Exception:
                break

        # ── Mute mic and camera before joining ────────────────
        for selector in [_SELECTORS["mute_mic"], _SELECTORS["turn_off_camera"]]:
            try:
                btn = await page.query_selector(selector)
                if btn:
                    await btn.click()
                    await asyncio.sleep(0.3)
            except Exception:
                pass

        # ── Click Join ────────────────────────────────────────
        try:
            join_btn = await page.wait_for_selector(
                _SELECTORS["join_button"],
                timeout=15000,
            )
            await join_btn.click()
            log.info("meet_bot_join_clicked")
        except Exception as e:
            log.error("meet_bot_join_failed", error=str(e))
            await browser.close()
            return {"status": "failed", "error": "Could not click Join button"}

        # ── Wait to be admitted from lobby ────────────────────
        admitted = False
        for _ in range(config.auto_admit_timeout_sec // 5):
            await asyncio.sleep(5)
            # Check if we're past the lobby by looking for in-meeting elements
            try:
                leave_btn = await page.query_selector(_SELECTORS["leave_button"])
                if leave_btn:
                    admitted = True
                    break
            except Exception:
                pass
            if stop_event and stop_event.is_set():
                break

        if not admitted:
            log.warning("meet_bot_not_admitted", url=config.meet_url)
            await browser.close()
            return {"status": "not_admitted", "error": "Bot was not admitted from lobby"}

        log.info("meet_bot_in_meeting", url=config.meet_url)

        # ── Inject audio capture script ───────────────────────
        await page.evaluate(_AUDIO_CAPTURE_JS)

        # ── Stay in meeting until stop signal ─────────────────
        meeting_end_time = start_time + config.max_duration_sec

        while time.time() < meeting_end_time:
            await asyncio.sleep(5)

            if stop_event and stop_event.is_set():
                log.info("meet_bot_stop_requested")
                break

            # Check if meeting ended (Meet shows "The meeting has ended")
            try:
                page_text = await page.inner_text("body")
                if "meeting has ended" in page_text.lower():
                    log.info("meet_bot_meeting_ended")
                    break
            except Exception:
                pass

        # ── Leave meeting ─────────────────────────────────────
        try:
            leave_btn = await page.query_selector(_SELECTORS["leave_button"])
            if leave_btn:
                await leave_btn.click()
        except Exception:
            pass

        await asyncio.sleep(2)
        await browser.close()

    duration = round(time.time() - start_time)
    log.info("meet_bot_done",
             duration_sec=duration,
             audio_chunks=audio_chunks_received[0])

    return {
        "status": "completed",
        "duration_seconds": duration,
        "audio_chunks_received": audio_chunks_received[0],
        "meet_url": config.meet_url,
    }
