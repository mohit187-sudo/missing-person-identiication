"""Structured application errors and FastAPI exception handlers.

All error responses follow:  {"error": {"code": ..., "message": ..., "details": ...}}
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError


class AppError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}

    def to_response(self) -> JSONResponse:
        return JSONResponse(
            status_code=self.status_code,
            content={"error": {"code": self.code, "message": self.message, "details": self.details}},
        )


class NotFoundError(AppError):
    def __init__(self, resource: str, identifier: Any = None):
        super().__init__(
            status.HTTP_404_NOT_FOUND,
            "not_found",
            f"{resource} not found" + (f": {identifier}" if identifier else ""),
        )


class ForbiddenError(AppError):
    def __init__(self, message: str = "You do not have permission to perform this action."):
        super().__init__(status.HTTP_403_FORBIDDEN, "forbidden", message)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Authentication required.", details: Optional[Dict[str, Any]] = None):
        super().__init__(status.HTTP_401_UNAUTHORIZED, "unauthorized", message, details)


class ConflictError(AppError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(status.HTTP_409_CONFLICT, "conflict", message, details)


class ValidationAppError(AppError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(status.HTTP_422_UNPROCESSABLE_ENTITY, "validation_error", message, details)


class RateLimitError(AppError):
    def __init__(self, retry_after_seconds: int):
        super().__init__(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "rate_limited",
            "Too many requests. Please slow down and try again.",
            {"retry_after_seconds": retry_after_seconds},
        )


class AIModelUnavailableError(AppError):
    """Raised when no compatible face model is configured.

    The system NEVER substitutes random or simulated scores. Clients get a clear
    setup error plus a pointer to the non-biometric demo features.
    """

    def __init__(self, detail: str, setup_steps: Optional[list] = None):
        super().__init__(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "ai_model_unavailable",
            "Facial matching engine is not configured. No simulated scores are "
            "generated. Run `python scripts/download_models.py` to install the "
            "documented OpenCV YuNet/SFace model weights, or set AI_BACKEND=none "
            "and use the non-biometric demo features (case registry, metadata "
            "search, review workflow).",
            {
                "detail": detail,
                "setup_steps": setup_steps
                or [
                    "python scripts/download_models.py",
                    "Ensure AI_MODEL_PATH points at the downloaded .onnx files",
                    "Restart the backend and check GET /api/health",
                ],
                "demo_alternative": "Non-biometric demo mode: case registry, "
                "metadata search, upload validation, video job status and the "
                "human review workflow all work without the AI model.",
            },
        )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return exc.to_response()

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        from fastapi.encoders import jsonable_encoder

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed.",
                    "details": {"issues": jsonable_encoder(exc.errors())},
                }
            },
        )

    @app.exception_handler(IntegrityError)
    async def _integrity(_: Request, exc: IntegrityError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": {
                    "code": "integrity_error",
                    "message": "The request conflicts with existing data.",
                    "details": {"reason": str(exc.orig)},
                }
            },
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected error occurred.",
                    "details": {"reason": str(exc)},
                }
            },
        )
