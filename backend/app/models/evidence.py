"""Face embeddings, video evidence, processing jobs and detected faces."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.session import Base
from backend.app.models.common import SoftDeleteMixin, TimestampMixin, UUIDMixin


class FaceEmbedding(Base, UUIDMixin, TimestampMixin):
    """Biometric reference data — access restricted to authorized roles and
    deleted according to approved retention policies.

    Embeddings are stored as packed little-endian float32 bytes plus the
    dimension and model provenance. See docs/PGVECTOR.md for enabling optional
    pgvector similarity search on PostgreSQL deployments.
    """

    __tablename__ = "face_embeddings"

    photo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("person_photos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("missing_person_cases.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    dim: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    face_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    face_bbox: Mapped[str] = mapped_column(Text, default="{}")  # JSON [x,y,w,h]
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    photo: Mapped["PersonPhoto"] = relationship(back_populates="embeddings")  # noqa: F821


class VideoEvidence(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """Authorized, lawfully obtained CCTV/video footage (private storage)."""

    __tablename__ = "video_evidence"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("missing_person_cases.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Legal record: who authorized use of this footage
    authorization_reference: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    lawfully_obtained: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    jobs: Mapped[list["VideoProcessingJob"]] = relationship(
        back_populates="video", cascade="all, delete-orphan"
    )


class VideoProcessingJob(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "video_processing_jobs"

    video_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("video_evidence.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32), default="queued", nullable=False, index=True
    )  # queued | running | completed | failed | cancelled
    progress: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    sampling_interval_seconds: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    frames_sampled: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    faces_detected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    matches_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    threshold_used: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    video: Mapped[VideoEvidence] = relationship(back_populates="jobs")
    detected_faces: Mapped[list["DetectedFace"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class DetectedFace(Base, UUIDMixin, TimestampMixin):
    """A face detected in a sampled video frame (with quality gates applied)."""

    __tablename__ = "detected_faces"

    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("video_processing_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    video_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("video_evidence.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    frame_index: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_x: Mapped[int] = mapped_column(Integer, nullable=False)
    bbox_y: Mapped[int] = mapped_column(Integer, nullable=False)
    bbox_w: Mapped[int] = mapped_column(Integer, nullable=False)
    bbox_h: Mapped[int] = mapped_column(Integer, nullable=False)
    face_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    blur_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    eligible_for_matching: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    rejection_reason: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    thumbnail_path: Mapped[str] = mapped_column(String(1024), default="", nullable=False)
    embedding_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("face_embeddings.id", ondelete="SET NULL"), nullable=True
    )

    job: Mapped[VideoProcessingJob] = relationship(back_populates="detected_faces")
