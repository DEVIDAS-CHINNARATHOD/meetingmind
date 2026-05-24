"""
tests/test_phase3.py
Phase 3 test suite — face recognition, identity DB, pipeline mapping.
Run: pytest tests/test_phase3.py -v
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch, AsyncMock

import numpy as np
import pytest


# ═══════════════════════════════════════════════════════════════
# Unit tests: cosine similarity
# ═══════════════════════════════════════════════════════════════

class TestCosineSimilarity:
    def test_identical_vectors(self):
        from ai.face_recognition.detector import cosine_similarity
        v = [1.0, 0.5, 0.3, 0.8]
        assert cosine_similarity(v, v) == pytest.approx(1.0, abs=1e-5)

    def test_orthogonal_vectors(self):
        from ai.face_recognition.detector import cosine_similarity
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0, abs=1e-5)

    def test_opposite_vectors(self):
        from ai.face_recognition.detector import cosine_similarity
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(-1.0, abs=1e-5)

    def test_zero_vector(self):
        from ai.face_recognition.detector import cosine_similarity
        assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0

    def test_similar_embeddings(self):
        from ai.face_recognition.detector import cosine_similarity
        rng = np.random.default_rng(42)
        base = rng.random(512).tolist()
        noisy = (np.array(base) + rng.random(512) * 0.05).tolist()
        sim = cosine_similarity(base, noisy)
        assert sim > 0.9   # very similar vectors


# ═══════════════════════════════════════════════════════════════
# Unit tests: face clustering
# ═══════════════════════════════════════════════════════════════

class TestFaceClustering:
    def _make_embedding(self, seed: int, noise: float = 0.0) -> list[float]:
        rng = np.random.default_rng(seed)
        base = rng.random(512)
        base = base / np.linalg.norm(base)
        if noise:
            n = rng.random(512) * noise
            base = base + n
            base = base / np.linalg.norm(base)
        return base.tolist()

    def test_cluster_identical_faces_together(self):
        from ai.face_recognition.detector import DetectedFace, FaceCluster, cluster_faces
        base_emb = self._make_embedding(1)
        faces = [
            DetectedFace(bbox=[0,0,100,100], embedding=self._make_embedding(1, 0.01),
                         confidence=0.95, frame_time=i*5.0, frame_index=i)
            for i in range(5)
        ]
        clusters = cluster_faces(faces, similarity_threshold=0.4)
        assert len(clusters) == 1
        assert len(clusters[0].faces) == 5

    def test_cluster_different_people_separately(self):
        from ai.face_recognition.detector import DetectedFace, cluster_faces
        faces = [
            DetectedFace(bbox=[0,0,100,100], embedding=self._make_embedding(1),
                         confidence=0.9, frame_time=0.0, frame_index=0),
            DetectedFace(bbox=[0,0,100,100], embedding=self._make_embedding(99),
                         confidence=0.9, frame_time=5.0, frame_index=1),
        ]
        clusters = cluster_faces(faces, similarity_threshold=0.4)
        assert len(clusters) == 2

    def test_cluster_centroid_updated(self):
        from ai.face_recognition.detector import DetectedFace, FaceCluster
        e1 = [1.0, 0.0]
        e2 = [0.0, 1.0]
        c = FaceCluster()
        c.add(DetectedFace(bbox=[], embedding=e1, confidence=0.9, frame_time=0.0, frame_index=0))
        c.add(DetectedFace(bbox=[], embedding=e2, confidence=0.9, frame_time=1.0, frame_index=1))
        centroid = c.centroid
        assert centroid is not None
        assert centroid[0] == pytest.approx(0.5)
        assert centroid[1] == pytest.approx(0.5)

    def test_empty_cluster_representative(self):
        from ai.face_recognition.detector import FaceCluster
        c = FaceCluster()
        assert c.representative_embedding == []

    def test_clusters_sorted_by_size(self):
        from ai.face_recognition.detector import DetectedFace, cluster_faces
        # Person A appears 3 times, Person B appears once
        rng = np.random.default_rng(1)
        base_a = (rng.random(512)); base_a /= np.linalg.norm(base_a)
        rng2 = np.random.default_rng(99)
        base_b = rng2.random(512); base_b /= np.linalg.norm(base_b)

        faces = [
            DetectedFace([], (base_a + rng.random(512)*0.01).tolist(), 0.9, i*5.0, i)
            for i in range(3)
        ] + [
            DetectedFace([], base_b.tolist(), 0.9, 20.0, 4)
        ]
        clusters = cluster_faces(faces, similarity_threshold=0.4)
        assert clusters[0].faces.__len__() >= clusters[-1].faces.__len__()


# ═══════════════════════════════════════════════════════════════
# Unit tests: identity DB (mocked ChromaDB)
# ═══════════════════════════════════════════════════════════════

class TestIdentityDB:
    def test_match_result_threshold(self):
        """MatchResult.matched reflects threshold correctly."""
        from ai.face_recognition.identity_db import MatchResult
        r_match = MatchResult("id1", "Priya", "p@x.com", 0.82, True)
        r_no    = MatchResult("",    "Unknown", None,   0.20, False)
        assert r_match.matched is True
        assert r_no.matched is False

    @patch("ai.face_recognition.identity_db._get_collection")
    def test_enroll_calls_upsert(self, mock_get_col):
        from ai.face_recognition.identity_db import enroll_identity
        mock_col = MagicMock()
        mock_get_col.return_value = mock_col

        iid = enroll_identity(
            name="Devidas K.",
            workspace_id="ws-123",
            embedding=[0.1] * 512,
            email="d@hkbk.edu",
        )
        mock_col.upsert.assert_called_once()
        assert isinstance(iid, str)

    @patch("ai.face_recognition.identity_db._get_collection")
    def test_match_empty_db_returns_unknown(self, mock_get_col):
        from ai.face_recognition.identity_db import match_face
        mock_col = MagicMock()
        mock_col.count.return_value = 0
        mock_get_col.return_value = mock_col

        result = match_face([0.1] * 512, "ws-123")
        assert result.matched is False
        assert result.name == "Unknown"

    @patch("ai.face_recognition.identity_db._get_collection")
    def test_delete_calls_collection_delete(self, mock_get_col):
        from ai.face_recognition.identity_db import delete_identity
        mock_col = MagicMock()
        mock_get_col.return_value = mock_col

        delete_identity("some-id")
        mock_col.delete.assert_called_once_with(ids=["some-id"])

    @patch("ai.face_recognition.identity_db._get_collection")
    def test_list_empty_workspace(self, mock_get_col):
        from ai.face_recognition.identity_db import list_identities
        mock_col = MagicMock()
        mock_col.count.return_value = 0
        mock_get_col.return_value = mock_col

        result = list_identities("ws-abc")
        assert result == []

    def test_enroll_multiple_photos_averages_embeddings(self):
        """Mean embedding should differ from any single embedding."""
        e1 = [1.0, 0.0, 0.0]
        e2 = [0.0, 1.0, 0.0]
        expected_mean = [0.5, 0.5, 0.0]

        with patch("ai.face_recognition.identity_db.enroll_identity") as mock_enroll:
            from ai.face_recognition.identity_db import enroll_from_multiple_photos
            enroll_from_multiple_photos("Test", "ws", [e1, e2])
            call_kwargs = mock_enroll.call_args
            actual_emb = call_kwargs[1]["embedding"]
            assert actual_emb == pytest.approx(expected_mean, abs=1e-5)


# ═══════════════════════════════════════════════════════════════
# Unit tests: speaker→identity mapping
# ═══════════════════════════════════════════════════════════════

class TestSpeakerMapping:
    def test_basic_temporal_mapping(self):
        from ai.face_recognition.pipeline import (
            FaceRecognitionResult, map_speakers_to_identities,
        )
        face_result = FaceRecognitionResult(
            speaker_map={
                "cluster_0": {
                    "name": "Priya Sharma",
                    "matched": True,
                    "face_count": 10,
                    "frame_times": [2.0, 7.0, 12.0],
                    "identity_id": "id-1",
                    "email": None,
                    "similarity": 0.87,
                }
            },
            face_count=10,
            cluster_count=1,
            identified_count=1,
        )
        # Speaker 00 talks from 0-15s, cluster_0 appears at 2, 7, 12 → inside window
        segs = [
            {"speaker_label": "SPEAKER_00", "start_time": 0.0, "end_time": 15.0}
        ]
        mapping = map_speakers_to_identities(segs, face_result)
        assert mapping.get("SPEAKER_00") == "Priya Sharma"

    def test_no_overlap_produces_empty_mapping(self):
        from ai.face_recognition.pipeline import (
            FaceRecognitionResult, map_speakers_to_identities,
        )
        face_result = FaceRecognitionResult(
            speaker_map={
                "cluster_0": {
                    "name": "Rahul Mehta", "matched": True, "face_count": 5,
                    "frame_times": [50.0, 55.0],  # speaker only active 0-10s
                    "identity_id": "id-2", "email": None, "similarity": 0.7,
                }
            },
            face_count=5, cluster_count=1, identified_count=1,
        )
        segs = [{"speaker_label": "SPEAKER_00", "start_time": 0.0, "end_time": 10.0}]
        mapping = map_speakers_to_identities(segs, face_result)
        assert "SPEAKER_00" not in mapping

    def test_unmatched_cluster_not_in_mapping(self):
        from ai.face_recognition.pipeline import (
            FaceRecognitionResult, map_speakers_to_identities,
        )
        face_result = FaceRecognitionResult(
            speaker_map={
                "cluster_0": {
                    "name": "Unknown Person 1", "matched": False,
                    "face_count": 3, "frame_times": [5.0],
                    "identity_id": None, "email": None, "similarity": 0.1,
                }
            },
            face_count=3, cluster_count=1, identified_count=0,
        )
        segs = [{"speaker_label": "SPEAKER_00", "start_time": 0.0, "end_time": 10.0}]
        mapping = map_speakers_to_identities(segs, face_result)
        # Unmatched clusters should not produce a mapping
        assert "SPEAKER_00" not in mapping

    def test_empty_face_result_returns_empty_dict(self):
        from ai.face_recognition.pipeline import (
            FaceRecognitionResult, map_speakers_to_identities,
        )
        face_result = FaceRecognitionResult(
            speaker_map={}, face_count=0, cluster_count=0, identified_count=0
        )
        mapping = map_speakers_to_identities([], face_result)
        assert mapping == {}


# ═══════════════════════════════════════════════════════════════
# API route registration
# ═══════════════════════════════════════════════════════════════

class TestIdentityRoutes:
    @pytest.mark.asyncio
    async def test_identity_routes_registered(self):
        from main import app
        routes = [r.path for r in app.routes]
        assert "/api/identities" in routes
        assert "/api/identities/enroll" in routes
        assert "/api/identities/{identity_id}" in routes
        assert "/api/identities/meetings/{meeting_id}/recognize" in routes

    @pytest.mark.asyncio
    async def test_enroll_requires_auth(self):
        from httpx import AsyncClient
        from main import app
        async with AsyncClient(app=app, base_url="http://test") as c:
            resp = await c.post("/api/identities/enroll")
            assert resp.status_code in (401, 422)

    @pytest.mark.asyncio
    async def test_list_identities_requires_auth(self):
        from httpx import AsyncClient
        from main import app
        async with AsyncClient(app=app, base_url="http://test") as c:
            resp = await c.get("/api/identities")
            assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════
# Task registration
# ═══════════════════════════════════════════════════════════════

class TestFaceTasks:
    def test_tasks_registered_in_celery(self):
        from workers.celery_app import celery_app
        registered = list(celery_app.tasks.keys())
        assert "workers.tasks.run_face_recognition_task" in registered
        assert "workers.tasks.extract_faces_for_enrollment" in registered
