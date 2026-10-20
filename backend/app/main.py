"""FastAPI application factory: middleware, security headers, CORS, error handlers.

Run locally:
    uvicorn backend.app.main:app --reload --port 8000
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.router import api_router
from backend.app.core.config import settings
from backend.app.core.exceptions import register_exception_handlers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mpis")

# Secure HTTP headers applied to every response (HTTPS-ready production config).
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "0",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Content-Security-Policy": (
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    ),
    # Enable in production behind TLS:
    # "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    warnings = settings.validate_startup()
    for w in warnings:
        logger.warning("CONFIG: %s", w)

    # Ensure database schema + baseline roles exist (Alembic owns migrations in
    # deployed environments; create_all keeps local demo/tests zero-friction).
    from backend.app.db.init_db import init_db

    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description=(
            "AI-assisted missing-person identification API. Facial similarity "
            "scores are technical measures only — never identification "
            "probabilities. Human verification is mandatory."
        ),
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # CORS allowlist (no wildcard origins — credentials never sent cross-origin).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
        max_age=600,
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response: Response = await call_next(request)
        for k, v in SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        return response

    # Note: authentication uses short-lived Bearer access tokens (not cookies),
    # which are immune to CSRF; a CSRF layer is unnecessary here. If cookie auth
    # is ever introduced, add double-submit CSRF tokens in front of it.
    register_exception_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
