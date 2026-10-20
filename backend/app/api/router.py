"""API router assembly — all versioned endpoints live under /api/v1."""
from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.routes import (
    admin,
    auth,
    cases,
    health,
    matching,
    notifications,
    privacy,
    reports,
    videos,
)

api_router = APIRouter()
api_router.include_router(health.router, prefix="/api")
api_router.include_router(auth.router, prefix="/api/v1")
api_router.include_router(cases.router, prefix="/api/v1")
api_router.include_router(matching.router, prefix="/api/v1")
api_router.include_router(videos.router, prefix="/api/v1")
api_router.include_router(admin.router, prefix="/api/v1")
api_router.include_router(notifications.router, prefix="/api/v1")
api_router.include_router(reports.router, prefix="/api/v1")
api_router.include_router(privacy.router, prefix="/api/v1")
