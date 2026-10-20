"""AI service tests: similarity math, embeddings, quality gates, ranked search,
and the structured setup error when model weights are unavailable."""
from __future__ import annotations

import numpy as np
import pytest

from backend.app.ai.base import DetectedFace, FaceAIBackend
from backend.app.ai.quality import assess_face_quality, assess_whole_image, blur_variance
from backend.app.ai.service import (
    FaceMatchingService,
    load_image_bgr,
    pack_embedding,
    unpack_embedding,
)
from backend.app.core.exceptions import AIModelUnavailableError, ValidationAppError


# --- documented similarity metric ------------------------------------------
def test_cosine_similarity_values():
    a = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    b = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    c = np.array([0.0, 1.0, 0.0], dtype=np.float32)
    assert FaceAIBackend.similarity(a, b) == pytest.approx(1.0)
    assert FaceAIBackend.similarity(a, c) == pytest.approx(0.0)
    d = np.array([-1.0, 0.0, 0.0], dtype=np.float32)
    assert FaceAIBackend.similarity(a, d) == pytest.approx(-1.0)


def test_cosine_similarity_rejects_bad_inputs():
    with pytest.raises(ValueError):
        FaceAIBackend.similarity(np.zeros(3, dtype=np.float32), np.zeros(4, dtype=np.float32))
    with pytest.raises(ValueError):
        FaceAIBackend.similarity(np.zeros(3, dtype=np.float32), np.zeros(3, dtype=np.float32))


def test_embedding_roundtrip():
    vec = np.random.default_rng(0).standard_normal(128).astype(np.float32)
    blob = pack_embedding(vec)
    out = unpack_embedding(blob, 128)
    assert np.allclose(vec, out)
    with pytest.raises(ValueError):
        unpack_embedding(blob, 64)


# --- quality gates ----------------------------------------------------------
def test_blur_metric_detects_blur(make_image):
    sharp = load_image_bgr(make_image(blur=False))
    blurry = load_image_bgr(make_image(blur=True))
    assert blur_variance(_gray(sharp)) > blur_variance(_gray(blurry))


def _gray(img):
    import cv2

    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def test_face_quality_rejects_tiny_faces(make_image):
    gray = _gray(load_image_bgr(make_image()))
    report = assess_face_quality(gray, face_size_px=12, confidence=0.9)
    assert not report.ok
    assert "too small" in report.rejection_reason


def test_face_quality_rejects_dark(make_image):
    gray = np.full((64, 64), 5, dtype=np.uint8)
    report = assess_face_quality(gray, face_size_px=128, confidence=0.9)
    assert not report.ok
    assert "dark" in report.rejection_reason


def test_whole_image_validation(make_image):
    ok, meta, reason = assess_whole_image(load_image_bgr(make_image(size=(640, 480))))
    assert ok and meta["width"] == 640

    ok, _, reason = assess_whole_image(load_image_bgr(make_image(size=(32, 32))))
    assert not ok

    with pytest.raises(ValidationAppError):
        load_image_bgr(b"not-an-image")


# --- pluggable backend + ranked search -------------------------------------
class FakeBackend(FaceAIBackend):
    """Deterministic backend for unit tests (test-only, never used in prod)."""

    def info(self):
        from backend.app.ai.base import FaceAIBackendInfo

        return FaceAIBackendInfo(name="fake", version="0", embedding_dim=3, license="test")

    def available(self):
        return True

    def availability_detail(self):
        return ""

    def detect_faces(self, image_bgr):
        h, w = image_bgr.shape[:2]
        return [DetectedFace(x=w // 4, y=h // 4, w=w // 2, h=h // 2, confidence=0.95)]

    def embed(self, image_bgr, face):
        return np.array([1.0, 0.0, 0.0], dtype=np.float32)


def test_rank_candidates_threshold_and_order():
    service = FaceMatchingService(FakeBackend())
    query = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    gallery = [
        ("case-a", "photo-a", "emb-a", np.array([1.0, 0.0, 0.0], dtype=np.float32), {}),
        ("case-b", "photo-b", "emb-b", np.array([0.9, 0.4359, 0.0], dtype=np.float32), {}),
        ("case-c", "photo-c", "emb-c", np.array([0.0, 1.0, 0.0], dtype=np.float32), {}),
        ("case-a", "photo-a2", "emb-a2", np.array([0.8, 0.6, 0.0], dtype=np.float32), {}),
    ]
    ranked = service.rank_candidates(query, gallery, threshold=0.5)
    ids = [c.case_id for c in ranked]
    assert ids[0] == "case-a"
    assert "case-c" not in ids  # below threshold
    assert len([i for i in ids if i == "case-a"]) == 1  # deduped per case
    assert ranked[0].similarity_score == pytest.approx(1.0)


def test_rank_candidates_respects_top_k():
    service = FaceMatchingService(FakeBackend())
    query = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    gallery = [
        (f"case-{i}", f"p-{i}", f"e-{i}", np.array([1.0, 0.0, 0.0], dtype=np.float32), {})
        for i in range(10)
    ]
    ranked = service.rank_candidates(query, gallery, threshold=0.1, top_k=3)
    assert len(ranked) == 3


def test_analyze_photo_with_fake_backend(make_image):
    service = FaceMatchingService(FakeBackend())
    img = load_image_bgr(make_image(size=(320, 320)))
    observations = service.analyze_photo(img)
    assert len(observations) == 1
    assert observations[0].embedding is not None


# --- clear setup error when weights are missing (no fake scores!) -----------
def test_matching_search_returns_structured_setup_error(client, investigator_headers, make_image):
    r = client.post(
        "/api/v1/matching/search",
        files={"file": ("query.jpg", make_image(), "image/jpeg")},
        headers=investigator_headers,
    )
    # Model weights are not installed in the test environment -> 503
    assert r.status_code == 503
    body = r.json()["error"]
    assert body["code"] == "ai_model_unavailable"
    assert "download_models.py" in body["message"]
    assert body["details"]["setup_steps"]
    assert body["details"]["demo_alternative"]


def test_ai_status_endpoint(client, investigator_headers):
    r = client.get("/api/v1/matching/ai-status", headers=investigator_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["backend"] == "opencv_sface"
    assert body["available"] is False
    assert body["setup_steps"]


def test_health_reports_ai_status(client):
    body = client.get("/api/health/ready").json()
    assert body["checks"]["database"]["ok"] is True
    assert body["checks"]["ai_model"]["ok"] is False
