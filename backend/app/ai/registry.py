"""Backend registry — selects the configured face backend and reports status.

If no compatible model is installed the system exposes a CLEAR setup error and
falls back to non-biometric demo features. It NEVER fabricates scores.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from backend.app.ai.base import FaceAIBackend
from backend.app.core.config import settings
from backend.app.core.exceptions import AIModelUnavailableError
from backend.app.schemas.common import AIStatus

SETUP_STEPS = [
    "python scripts/download_models.py   # downloads YuNet + SFace ONNX weights (Apache-2.0)",
    "Set AI_MODEL_PATH=./backend/models in .env (default)",
    "Restart the backend and verify GET /api/health shows ai.available=true",
]


class _UnavailableBackend(FaceAIBackend):
    """Explicit placeholder when AI_BACKEND=none — never produces scores."""

    def info(self):
        from backend.app.ai.base import FaceAIBackendInfo

        return FaceAIBackendInfo(
            name="none", version="-", embedding_dim=0, license="-", model_files=[]
        )

    def available(self) -> bool:
        return False

    def availability_detail(self) -> str:
        return "AI_BACKEND=none — biometric matching disabled by configuration."

    def detect_faces(self, image_bgr):
        raise AIModelUnavailableError(self.availability_detail(), SETUP_STEPS)

    def embed(self, image_bgr, face):
        raise AIModelUnavailableError(self.availability_detail(), SETUP_STEPS)


@lru_cache
def get_backend() -> FaceAIBackend:
    name = (settings.ai_backend or "none").lower()
    if name in ("none", "off", "disabled"):
        return _UnavailableBackend()
    if name == "opencv_sface":
        from backend.app.ai.opencv_sface import OpenCVSFaceBackend

        return OpenCVSFaceBackend()
    # Unknown backend configured — behave as unavailable with a clear message.
    return _UnavailableBackend()


def clear_backend_cache() -> None:
    get_backend.cache_clear()


def ai_status() -> AIStatus:
    backend = get_backend()
    available = False
    detail = ""
    try:
        available = backend.available()
        if not available:
            detail = backend.availability_detail()
    except Exception as exc:
        detail = str(exc)
    info = backend.info()
    return AIStatus(
        backend=settings.ai_backend,
        available=available,
        model_name=info.name if available else "",
        model_version=info.version if available else "",
        embedding_dim=info.embedding_dim if available else None,
        license=info.license if available else "",
        detail=detail,
        setup_steps=[] if available else SETUP_STEPS,
    )


def require_backend() -> FaceAIBackend:
    """Return the backend or raise a structured 503 with setup instructions."""
    backend = get_backend()
    if not backend.available():
        raise AIModelUnavailableError(backend.availability_detail() or "model unavailable", SETUP_STEPS)
    return backend
