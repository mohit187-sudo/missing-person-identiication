"""Integration tests against the REAL OpenCV YuNet/SFace backend.

These run only when the documented model weights are installed
(`python scripts/download_models.py`). They verify the pipeline executes with
real inference — they make NO accuracy claims on synthetic test images.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app.core.config import settings  # noqa: E402,F401

# The conftest test env points AI_MODEL_PATH at an empty dir (to exercise the
# unavailable path). These integration tests use the repo's real weights dir.
MODEL_DIR = ROOT / "backend" / "models"
REAL_MODEL_AVAILABLE = (
    (MODEL_DIR / "face_detection_yunet_2023mar.onnx").exists()
    and (MODEL_DIR / "face_recognition_sface_2021dec.onnx").exists()
)

pytestmark = pytest.mark.skipif(
    not REAL_MODEL_AVAILABLE, reason="Real model weights not installed (scripts/download_models.py)"
)


@pytest.fixture()
def real_backend():
    from backend.app.ai.opencv_sface import OpenCVSFaceBackend

    backend = OpenCVSFaceBackend(model_dir=MODEL_DIR)
    if not backend.available():
        pytest.skip(backend.availability_detail())
    return backend


def test_model_info_and_license(real_backend):
    info = real_backend.info()
    assert info.embedding_dim == 128
    assert "Apache" in info.license
    assert real_backend.available()
    assert real_backend.availability_detail() == ""


def test_detection_runs_on_image(real_backend, make_image):
    from backend.app.ai.service import load_image_bgr

    img = load_image_bgr(make_image(size=(640, 480)))
    faces = real_backend.detect_faces(img)  # must not raise
    assert isinstance(faces, list)
    # Synthetic test images may or may not contain detectable faces — the test
    # asserts the pipeline RUNS, not any detection accuracy.


def test_embed_similarity_same_image(real_backend, make_image):
    from backend.app.ai.service import FaceMatchingService, load_image_bgr

    img = load_image_bgr(make_image(size=(640, 480)))
    observations = FaceMatchingService(real_backend).analyze_photo(img)
    usable = [o for o in observations if o.embedding is not None]
    if not usable:
        pytest.skip("Synthetic image produced no usable face embedding (expected for drawn images)")
    emb = usable[0].embedding
    assert emb.shape == (128,)
    assert abs(float(np.linalg.norm(emb)) - 1.0) < 1e-4  # L2-normalised
    assert real_backend.similarity(emb, emb) == pytest.approx(1.0)
