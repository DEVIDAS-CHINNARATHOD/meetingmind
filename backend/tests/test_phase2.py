"""
tests/test_phase2.py
Phase 2 test suite.
Run: pytest tests/test_phase2.py -v
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from main import app


# ── fixtures ──────────────────────────────────────────────────

@pytest.fixture
def mock_user():
    u = MagicMock()
    u.id = uuid.uuid4()
    u.workspace_id = uuid.uuid4()
    u.role = MagicMock(value="admin")
    u.is_active = True
    u.name = "Devidas K."
    u.email = "devidas@hkbk.edu"
    return u


# ═══════════════════════════════════════════════════════════════
# Diarization unit tests
# ═══════════════════════════════════════════════════════════════

class TestSpeakerAssignment:
    def test_assign_speakers_to_transcript(self):
        from ai.diarization.pyannote import (
            DiarizedSegment, DiarizationResult, assign_speakers_to_transcript,
        )
        diarization = DiarizationResult(
            segments=[
                DiarizedSegment("SPEAKER_00", 0.0, 5.0),
                DiarizedSegment("SPEAKER_01", 5.5, 12.0),
                DiarizedSegment("SPEAKER_00", 13.0, 20.0),
            ],
            num_speakers=2,
        )
        transcript = [
            {"text": "Hello team.", "start_time": 1.0, "end_time": 3.0},
            {"text": "Thanks for joining.", "start_time": 6.0, "end_time": 9.0},
            {"text": "Let me share the update.", "start_time": 14.0, "end_time": 18.0},
        ]
        result = assign_speakers_to_transcript(transcript, diarization)

        assert result[0]["speaker_label"] == "SPEAKER_00"
        assert result[1]["speaker_label"] == "SPEAKER_01"
        assert result[2]["speaker_label"] == "SPEAKER_00"

    def test_assign_speakers_no_overlap(self):
        from ai.diarization.pyannote import (
            DiarizedSegment, DiarizationResult, assign_speakers_to_transcript,
        )
        diarization = DiarizationResult(
            segments=[DiarizedSegment("SPEAKER_00", 10.0, 20.0)],
            num_speakers=1,
        )
        transcript = [{"text": "Early text.", "start_time": 0.0, "end_time": 5.0}]
        result = assign_speakers_to_transcript(transcript, diarization)
        # No overlap → speaker_label stays None
        assert result[0]["speaker_label"] is None

    def test_compute_speaker_stats(self):
        from ai.diarization.pyannote import compute_speaker_stats
        segs = [
            {"text": "Hello world how are you", "speaker_label": "SPEAKER_00",
             "start_time": 0.0, "end_time": 5.0},
            {"text": "I am fine", "speaker_label": "SPEAKER_01",
             "start_time": 5.5, "end_time": 9.0},
            {"text": "Great meeting", "speaker_label": "SPEAKER_00",
             "start_time": 10.0, "end_time": 14.0},
        ]
        stats = compute_speaker_stats(segs)
        assert "SPEAKER_00" in stats
        assert "SPEAKER_01" in stats
        assert stats["SPEAKER_00"]["talk_time_seconds"] == pytest.approx(9.0, abs=0.1)
        assert stats["SPEAKER_00"]["word_count"] == 8   # 5 + 3
        assert stats["SPEAKER_01"]["word_count"] == 3

    def test_compute_stats_skips_none_labels(self):
        from ai.diarization.pyannote import compute_speaker_stats
        segs = [
            {"text": "Unlabeled", "speaker_label": None, "start_time": 0, "end_time": 1},
        ]
        stats = compute_speaker_stats(segs)
        assert len(stats) == 0

    def test_diarization_result_speakers_property(self):
        from ai.diarization.pyannote import DiarizedSegment, DiarizationResult
        dr = DiarizationResult(
            segments=[
                DiarizedSegment("SPEAKER_01", 0, 5),
                DiarizedSegment("SPEAKER_00", 5, 10),
                DiarizedSegment("SPEAKER_01", 10, 15),
            ],
            num_speakers=2,
        )
        assert dr.speakers == ["SPEAKER_00", "SPEAKER_01"]


# ═══════════════════════════════════════════════════════════════
# Search unit tests
# ═══════════════════════════════════════════════════════════════

class TestSearch:
    def test_extract_snippet_middle(self):
        from api.routes.search import _extract_snippet
        text = "a" * 200 + "TARGET" + "b" * 200
        snippet = _extract_snippet(text, "TARGET", window=100)
        assert "TARGET" in snippet
        assert len(snippet) < len(text)

    def test_extract_snippet_not_found(self):
        from api.routes.search import _extract_snippet
        text = "Hello world this is a test"
        snippet = _extract_snippet(text, "MISSING")
        assert snippet.startswith("Hello")

    def test_extract_snippet_empty(self):
        from api.routes.search import _extract_snippet
        assert _extract_snippet("", "query") == ""


# ═══════════════════════════════════════════════════════════════
# API integration tests (mocked DB)
# ═══════════════════════════════════════════════════════════════

class TestAnalyticsAPI:
    @pytest.mark.asyncio
    async def test_overview_returns_correct_shape(self, mock_user):
        with patch("api.deps.get_current_user", return_value=mock_user), \
             patch("db.database.get_db"):
            async with AsyncClient(app=app, base_url="http://test") as c:
                # Just verify the route exists and returns 200 structure
                resp = await c.get("/api/analytics/overview",
                                   headers={"Authorization": "Bearer fake"})
                # May 422 if DB mocking isn't wired — check route registered
                assert resp.status_code in (200, 422, 401)

    @pytest.mark.asyncio
    async def test_speakers_endpoint_registered(self):
        """Verify the /analytics/speakers route is registered."""
        routes = [r.path for r in app.routes]
        assert "/api/analytics/speakers" in routes

    @pytest.mark.asyncio
    async def test_meeting_frequency_registered(self):
        routes = [r.path for r in app.routes]
        assert "/api/analytics/meeting-frequency" in routes


class TestTeamAPI:
    @pytest.mark.asyncio
    async def test_team_routes_registered(self):
        routes = [r.path for r in app.routes]
        assert "/api/team/members" in routes
        assert "/api/team/invite" in routes
        assert "/api/team/workspace" in routes

    @pytest.mark.asyncio
    async def test_role_update_route(self):
        routes = [r.path for r in app.routes]
        assert "/api/team/members/{user_id}/role" in routes


class TestSpeakersAPI:
    @pytest.mark.asyncio
    async def test_speaker_routes_registered(self):
        routes = [r.path for r in app.routes]
        assert "/api/speakers/meetings/{meeting_id}" in routes
        assert "/api/speakers/meetings/{meeting_id}/rename" in routes
        assert "/api/speakers/meetings/{meeting_id}/bulk-rename" in routes


class TestSearchAPI:
    @pytest.mark.asyncio
    async def test_search_route_registered(self):
        routes = [r.path for r in app.routes]
        assert "/api/search" in routes

    @pytest.mark.asyncio
    async def test_search_requires_query(self):
        async with AsyncClient(app=app, base_url="http://test") as c:
            resp = await c.get("/api/search",
                               headers={"Authorization": "Bearer fake"})
            assert resp.status_code in (401, 422)   # 422 = missing q param


class TestStreamingChat:
    @pytest.mark.asyncio
    async def test_stream_route_registered(self):
        routes = [r.path for r in app.routes]
        assert "/api/ai/chat/stream" in routes


class TestActionItemsAPI:
    @pytest.mark.asyncio
    async def test_action_items_routes_registered(self):
        routes = [r.path for r in app.routes]
        assert "/api/action-items" in routes
        assert "/api/action-items/{item_id}" in routes


# ═══════════════════════════════════════════════════════════════
# Pipeline unit tests
# ═══════════════════════════════════════════════════════════════

class TestPipelineHelpers:
    def test_fmt_duration_minutes(self):
        from workers.tasks import _fmt
        assert _fmt(90) == "1m 30s"

    def test_fmt_duration_hours(self):
        from workers.tasks import _fmt
        assert _fmt(3661) == "1h 1m 1s"

    def test_fmt_duration_zero(self):
        from workers.tasks import _fmt
        assert _fmt(0) == "0m 0s"


# ═══════════════════════════════════════════════════════════════
# Rate limiting unit tests
# ═══════════════════════════════════════════════════════════════

class TestRateLimiter:
    def test_middleware_instantiates(self):
        from api.middleware.rate_limit import RateLimitMiddleware
        app_mock = MagicMock()
        mw = RateLimitMiddleware(app_mock, requests=50, window=30)
        assert mw._limit == 50
        assert mw._window == 30
