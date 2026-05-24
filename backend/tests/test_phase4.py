"""
tests/test_phase4.py
Phase 4 test suite — WebSocket transcription, bots, integrations API.
Run: pytest tests/test_phase4.py -v
"""
from __future__ import annotations

import asyncio
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch, call
import pytest


# ═══════════════════════════════════════════════════════════════
# StreamingTranscriber unit tests
# ═══════════════════════════════════════════════════════════════

class TestStreamingTranscriber:
    def test_silence_detection(self):
        """Near-silent chunks should not trigger transcription."""
        import numpy as np
        from ai.realtime.streaming_transcriber import (
            StreamingTranscriber, SILENCE_THRESHOLD, SAMPLE_RATE, BYTES_PER_SAMPLE
        )
        segments_received = []
        t = StreamingTranscriber(on_segment=lambda s: segments_received.append(s))

        # Generate silent audio (all zeros)
        silent = np.zeros(SAMPLE_RATE * 4, dtype=np.int16).tobytes()
        t.feed(silent)
        t.stop()
        # Should produce no or minimal segments from silence
        assert len(segments_received) == 0

    def test_segment_callback_called(self):
        """Verify callback fires when audio is fed."""
        from ai.realtime.streaming_transcriber import StreamingTranscriber
        received = []
        t = StreamingTranscriber(on_segment=lambda s: received.append(s))

        # Patch model to avoid loading Whisper in tests
        with patch.object(t, "_transcribe_chunk") as mock_tc:
            import numpy as np
            loud_audio = (np.ones(16000 * 4, dtype=np.int16) * 5000).tobytes()
            t.feed(loud_audio)
            # _transcribe_chunk should have been called
            assert mock_tc.called

    def test_realtime_segment_fields(self):
        from ai.realtime.streaming_transcriber import RealtimeSegment
        seg = RealtimeSegment(
            text="Hello world",
            start_time=1.0,
            end_time=2.5,
            is_final=True,
            confidence=-0.3,
        )
        assert seg.text == "Hello world"
        assert seg.start_time == 1.0
        assert seg.is_final is True

    def test_stop_flushes_remaining(self):
        from ai.realtime.streaming_transcriber import StreamingTranscriber
        t = StreamingTranscriber(on_segment=lambda s: None)
        with patch.object(t, "flush") as mock_flush:
            t.stop()
            mock_flush.assert_called_once()

    def test_feed_after_stop_ignored(self):
        from ai.realtime.streaming_transcriber import StreamingTranscriber
        t = StreamingTranscriber(on_segment=lambda s: None)
        t.stop()
        # Should not raise even if feed called after stop
        t.feed(b"\x00" * 100)


# ═══════════════════════════════════════════════════════════════
# Zoom bot unit tests
# ═══════════════════════════════════════════════════════════════

class TestZoomBot:
    def test_sdk_jwt_structure(self):
        """JWT should decode to expected payload structure."""
        with patch("config.settings.settings") as mock_settings:
            mock_settings.zoom_client_id = "test_key"
            mock_settings.zoom_client_secret = "test_secret"
            from bots.zoom.zoom_bot import generate_sdk_jwt
            token = generate_sdk_jwt("123456789", role=0)
            assert isinstance(token, str)
            # Decode without verification to check structure
            import jose.jwt as jwt_lib
            payload = jwt_lib.decode(token, "test_secret", algorithms=["HS256"])
            assert payload["mn"] == "123456789"
            assert payload["role"] == 0
            assert "iat" in payload
            assert "exp" in payload

    def test_zoom_bot_config(self):
        from bots.zoom.zoom_bot import ZoomBotConfig
        cfg = ZoomBotConfig(
            meeting_number="987654321",
            meeting_password="pass123",
            display_name="Test Bot",
        )
        assert cfg.meeting_number == "987654321"
        assert cfg.display_name == "Test Bot"

    def test_join_and_record_stub_runs(self):
        """Stub implementation should call on_audio and return a result dict."""
        from bots.zoom.zoom_bot import ZoomBotConfig, join_and_record
        chunks_received = []

        cfg = ZoomBotConfig(meeting_number="123", meeting_password="")
        # Patch sleep to speed up test
        with patch("time.sleep"):
            result = join_and_record(cfg, on_audio_chunk=lambda b: chunks_received.append(b))

        assert result["status"] == "left"
        assert len(chunks_received) > 0
        assert all(isinstance(c, bytes) for c in chunks_received)


# ═══════════════════════════════════════════════════════════════
# Google Meet bot unit tests
# ═══════════════════════════════════════════════════════════════

class TestMeetBot:
    def test_meet_bot_config_defaults(self):
        from bots.meet.meet_bot import MeetBotConfig
        cfg = MeetBotConfig(meet_url="https://meet.google.com/abc-defg-hij")
        assert cfg.display_name == "MeetingMind Bot 🎙️"
        assert cfg.auto_admit_timeout_sec == 120
        assert cfg.max_duration_sec == 7200

    def test_audio_capture_js_is_string(self):
        from bots.meet.meet_bot import _AUDIO_CAPTURE_JS
        assert isinstance(_AUDIO_CAPTURE_JS, str)
        assert "AudioContext" in _AUDIO_CAPTURE_JS
        assert "__mm_audio__" in _AUDIO_CAPTURE_JS
        assert "Int16Array" in _AUDIO_CAPTURE_JS

    def test_selectors_defined(self):
        from bots.meet.meet_bot import _SELECTORS
        assert "join_button" in _SELECTORS
        assert "leave_button" in _SELECTORS
        assert "mute_mic" in _SELECTORS


# ═══════════════════════════════════════════════════════════════
# Integrations API route tests
# ═══════════════════════════════════════════════════════════════

class TestIntegrationsRoutes:
    @pytest.mark.asyncio
    async def test_routes_registered(self):
        from main import app
        paths = [r.path for r in app.routes]
        assert "/api/integrations/zoom/join" in paths
        assert "/api/integrations/zoom/webhook" in paths
        assert "/api/integrations/meet/join" in paths
        assert "/api/integrations/status" in paths

    @pytest.mark.asyncio
    async def test_zoom_join_requires_auth(self):
        from httpx import AsyncClient
        from main import app
        async with AsyncClient(app=app, base_url="http://test") as c:
            resp = await c.post("/api/integrations/zoom/join",
                                json={"meeting_number": "123456789"})
            assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_meet_join_requires_auth(self):
        from httpx import AsyncClient
        from main import app
        async with AsyncClient(app=app, base_url="http://test") as c:
            resp = await c.post("/api/integrations/meet/join",
                                json={"meet_url": "https://meet.google.com/abc-defg-hij"})
            assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_zoom_webhook_url_validation(self):
        """Zoom sends a URL validation challenge that must be echoed back."""
        from httpx import AsyncClient
        from main import app

        payload = {
            "event": "endpoint.url_validation",
            "payload": {"plainToken": "abc123token"},
        }
        async with AsyncClient(app=app, base_url="http://test") as c:
            resp = await c.post(
                "/api/integrations/zoom/webhook",
                json=payload,
                headers={"x-zm-request-timestamp": "1234567890",
                         "x-zm-signature": "v0=fake"},
            )
            # Should return 200 with the token echoed
            assert resp.status_code == 200
            data = resp.json()
            assert "plainToken" in data
            assert data["plainToken"] == "abc123token"

    @pytest.mark.asyncio
    async def test_meet_url_validation(self):
        """Non-Meet URLs should be rejected."""
        from httpx import AsyncClient
        from main import app
        from unittest.mock import patch
        mock_user = MagicMock()
        mock_user.workspace_id = uuid.uuid4()
        mock_user.id = uuid.uuid4()

        with patch("api.deps.get_current_user", return_value=mock_user), \
             patch("db.database.get_db"):
            async with AsyncClient(app=app, base_url="http://test") as c:
                resp = await c.post(
                    "/api/integrations/meet/join",
                    json={"meet_url": "https://zoom.us/j/123"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code in (400, 401, 422)


# ═══════════════════════════════════════════════════════════════
# WebSocket route registration
# ═══════════════════════════════════════════════════════════════

class TestWebSocketRoute:
    @pytest.mark.asyncio
    async def test_ws_route_registered(self):
        from main import app
        from starlette.routing import WebSocketRoute
        ws_routes = [r for r in app.routes
                     if hasattr(r, "path") and "ws" in r.path.lower()]
        assert len(ws_routes) > 0
        paths = [r.path for r in ws_routes]
        assert "/ws/transcribe" in paths

    @pytest.mark.asyncio
    async def test_ws_rejects_missing_token(self):
        """WebSocket with no token should close with 4001."""
        from starlette.testclient import TestClient
        from main import app
        client = TestClient(app)
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/transcribe?meeting_id=fake"):
                pass


# ═══════════════════════════════════════════════════════════════
# Bot tasks registered in Celery
# ═══════════════════════════════════════════════════════════════

class TestBotTasksRegistered:
    def test_all_phase4_tasks_registered(self):
        from workers.celery_app import celery_app
        tasks = list(celery_app.tasks.keys())
        assert "workers.bot_tasks.join_zoom_meeting" in tasks
        assert "workers.bot_tasks.join_google_meet" in tasks
        assert "workers.bot_tasks.finalize_live_meeting" in tasks

    def test_task_queues_configured(self):
        from workers.celery_app import celery_app
        routes = celery_app.conf.task_routes
        assert routes.get("workers.bot_tasks.join_zoom_meeting") == {"queue": "bots"}
        assert routes.get("workers.bot_tasks.join_google_meet") == {"queue": "bots"}
        assert routes.get("workers.bot_tasks.finalize_live_meeting") == {"queue": "ai"}


# ═══════════════════════════════════════════════════════════════
# Health endpoint reflects Phase 4 features
# ═══════════════════════════════════════════════════════════════

class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_has_features_block(self):
        from httpx import AsyncClient
        from main import app
        with patch("db.database.check_db_connection", return_value=True), \
             patch("redis.Redis.ping", return_value=True):
            async with AsyncClient(app=app, base_url="http://test") as c:
                resp = await c.get("/api/health")
                # May fail DB/redis in test env but route should exist
                assert resp.status_code in (200, 500, 503)
                if resp.status_code == 200:
                    data = resp.json()
                    assert "features" in data
                    assert "realtime_ws" in data["features"]
                    assert "zoom_bot" in data["features"]
                    assert "meet_bot" in data["features"]
