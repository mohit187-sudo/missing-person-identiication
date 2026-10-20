"""Application configuration loaded from environment variables (.env supported).

Required variables are validated at startup. In development, missing secrets are
auto-generated with a loud warning so the local demo never needs real credentials.
In production, missing secrets abort startup.
"""
from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Core
    app_name: str = "Missing Person Identification System"
    environment: str = Field(default="development", alias="ENVIRONMENT")
    demo_mode: bool = Field(default=True, alias="DEMO_MODE")
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173", alias="CORS_ORIGINS"
    )
    frontend_url: str = Field(default="http://localhost:5173", alias="FRONTEND_URL")

    # Database
    database_url: str = Field(
        default="sqlite:///./storage/dev.db", alias="DATABASE_URL"
    )

    # Auth
    jwt_secret_key: str = Field(default="", alias="JWT_SECRET_KEY")
    jwt_access_token_minutes: int = Field(default=15, alias="JWT_ACCESS_TOKEN_MINUTES")
    jwt_refresh_token_days: int = Field(default=7, alias="JWT_REFRESH_TOKEN_DAYS")
    jwt_algorithm: str = "HS256"

    # AI
    ai_backend: str = Field(default="opencv_sface", alias="AI_BACKEND")
    ai_model_path: str = Field(default="./backend/models", alias="AI_MODEL_PATH")
    ai_model_name: str = Field(default="opencv_zoo_sface", alias="AI_MODEL_NAME")
    ai_match_threshold: float = Field(default=0.55, alias="AI_MATCH_THRESHOLD")
    ai_min_face_confidence: float = Field(default=0.6, alias="AI_MIN_FACE_CONFIDENCE")
    ai_min_face_size_px: int = Field(default=64, alias="AI_MIN_FACE_SIZE_PX")
    ai_max_blur_variance_below: float = Field(
        default=35.0, alias="AI_MAX_BLUR_VARIANCE_BELOW"
    )

    # Storage / uploads
    storage_dir: str = Field(default="./storage", alias="STORAGE_DIR")
    max_photo_upload_mb: int = Field(default=8, alias="MAX_PHOTO_UPLOAD_MB")
    max_video_upload_mb: int = Field(default=512, alias="MAX_VIDEO_UPLOAD_MB")
    video_frame_sample_seconds: float = Field(
        default=1.0, alias="VIDEO_FRAME_SAMPLE_SECONDS"
    )

    # Rate limiting
    rate_limit_enabled: bool = Field(default=True, alias="RATE_LIMIT_ENABLED")
    login_rate_limit_per_minute: int = Field(
        default=5, alias="LOGIN_RATE_LIMIT_PER_MINUTE"
    )
    api_rate_limit_per_minute: int = Field(
        default=120, alias="API_RATE_LIMIT_PER_MINUTE"
    )

    # Email (optional)
    email_provider_api_key: str = Field(default="", alias="EMAIL_PROVIDER_API_KEY")
    email_from_address: str = Field(default="", alias="EMAIL_FROM_ADDRESS")
    smtp_host: str = Field(default="", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: str = Field(default="", alias="SMTP_USER")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    smtp_tls: bool = Field(default=True, alias="SMTP_TLS")

    # Object storage (optional; local protected storage is the default)
    object_storage_endpoint: str = Field(default="", alias="OBJECT_STORAGE_ENDPOINT")
    object_storage_bucket: str = Field(default="", alias="OBJECT_STORAGE_BUCKET")
    object_storage_access_key: str = Field(default="", alias="OBJECT_STORAGE_ACCESS_KEY")
    object_storage_secret_key: str = Field(default="", alias="OBJECT_STORAGE_SECRET_KEY")

    # Startup validation -------------------------------------------------
    @field_validator("environment")
    @classmethod
    def _check_env(cls, v: str) -> str:
        allowed = {"development", "staging", "production", "test"}
        if v not in allowed:
            raise ValueError(f"ENVIRONMENT must be one of {sorted(allowed)}")
        return v

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def storage_path(self) -> Path:
        return Path(self.storage_dir).resolve()

    @property
    def ai_model_dir(self) -> Path:
        return Path(self.ai_model_path).resolve()

    def validate_startup(self) -> List[str]:
        """Validate required configuration. Returns warnings; raises on hard errors."""
        warnings: List[str] = []
        is_prod = self.environment == "production"

        if not self.jwt_secret_key:
            if is_prod:
                raise RuntimeError(
                    "JWT_SECRET_KEY is required in production. Generate one with:\n"
                    '  python -c "import secrets; print(secrets.token_urlsafe(64))"'
                )
            object.__setattr__(self, "jwt_secret_key", secrets.token_urlsafe(64))
            warnings.append(
                "JWT_SECRET_KEY was not set — generated an EPHEMERAL development "
                "secret. All sessions reset on restart. Set JWT_SECRET_KEY in .env."
            )

        if is_prod and self.demo_mode:
            warnings.append(
                "DEMO_MODE is enabled in production — synthetic demo records are "
                "kept in a separate demo namespace but consider disabling it."
            )

        if not self.database_url:
            raise RuntimeError("DATABASE_URL is required.")

        # Create private storage root.
        self.storage_path.mkdir(parents=True, exist_ok=True)
        (self.storage_path / "photos").mkdir(exist_ok=True)
        (self.storage_path / "videos").mkdir(exist_ok=True)
        (self.storage_path / "artifacts").mkdir(exist_ok=True)
        return warnings


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
