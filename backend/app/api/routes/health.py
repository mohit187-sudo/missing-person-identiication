"""Health and readiness endpoints (public — no sensitive data returned)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment,
        "demo_mode": settings.demo_mode,
    }


@router.get("/health/ready")
def ready(db: Session = Depends(get_db)):
    from backend.app.ai.registry import ai_status

    checks = {}
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = {"ok": True}
    except Exception as exc:
        checks["database"] = {"ok": False, "detail": str(exc)[:200]}

    ai = ai_status()
    checks["ai_model"] = {
        "ok": ai.available,
        "backend": ai.backend,
        "model": ai.model_name,
        "version": ai.model_version,
        "detail": ai.detail,
    }

    ok = checks["database"]["ok"]
    return {
        "status": "ready" if ok else "degraded",
        "checks": checks,
        "note": (
            "ai_model.ok=false does not block the API: case management and the "
            "non-biometric demo workflow remain fully functional. Matching "
            "endpoints return a structured 503 setup error — never fake scores."
        ),
    }
