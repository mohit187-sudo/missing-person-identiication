"""Potential matches, investigator reviews and matching search jobs."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.session import Base
from backend.app.models.common import TimestampMixin, UUIDMixin

# Review decisions — a human ALWAYS confirms; AI never declares an identification.
MATCH_PENDING = "pending"
MATCH_CONFIRMED = "confirmed_for_investigation"
MATCH_REJECTED = "rejected"
MATCH_MANUAL = "requires_manual_review"
ALL_MATCH_STATUSES = (MATCH_PENDING, MATCH_CONFIRMED, MATCH_REJECTED, MATCH_MANUAL)

SOURCE_PHOTO_SEARCH = "photo_search"
SOURCE_VIDEO_FRAME = "video_frame"


class MatchingJob(Base, UUIDMixin, TimestampMixin):
    """Traceability record for a photo-based face search."""

    __tablename__ = "matching_jobs"

    query_photo_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("person_photos.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(32), default="queued", nullable=False, index=True
    )  # queued | running | completed | failed | cancelled
    progress: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    threshold_used: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_name: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    candidates_returned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PotentialMatch(Base, UUIDMixin, TimestampMixin):
    """A ranked candidate produced by the face-matching engine.

    `similarity_score` is a TECHNICAL similarity measure between embeddings —
    it is NOT the probability that two images show the same person, and it never
    automatically changes a case status or identifies anyone.
    """

    __tablename__ = "potential_matches"

    source_type: Mapped[str] = mapped_column(String(32), nullable=False)  # photo_search | video_frame
    query_photo_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("person_photos.id", ondelete="SET NULL"), nullable=True, index=True
    )
    detected_face_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("detected_faces.id", ondelete="SET NULL"), nullable=True, index=True
    )
    matching_job_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("matching_jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    video_job_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("video_processing_jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Candidate case this face may belong to
    candidate_case_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("missing_person_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Reference photo of the candidate case that produced this score
    reference_photo_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("person_photos.id", ondelete="SET NULL"), nullable=True
    )
    reference_embedding_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("face_embeddings.id", ondelete="SET NULL"), nullable=True
    )

    similarity_score: Mapped[float] = mapped_column(Float, nullable=False)
    threshold_used: Mapped[float] = mapped_column(Float, nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    image_quality: Mapped[str] = mapped_column(Text, default="{}")  # JSON indicators

    status: Mapped[str] = mapped_column(
        String(32), default=MATCH_PENDING, nullable=False, index=True
    )
    source_timestamp_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    processing_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_demo: Mapped[bool] = mapped_column(Integer, default=0, nullable=False)

    reviews: Mapped[list["InvestigatorReview"]] = relationship(
        back_populates="match", cascade="all, delete-orphan"
    )
    candidate_case: Mapped["MissingPersonCase"] = relationship()  # noqa: F821


class InvestigatorReview(Base, UUIDMixin, TimestampMixin):
    """Human verification record for a potential match."""

    __tablename__ = "investigator_reviews"

    match_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("potential_matches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decision: Mapped[str] = mapped_column(String(64), nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)

    match: Mapped[PotentialMatch] = relationship(back_populates="reviews")
    reviewer: Mapped["User"] = relationship()  # noqa: F821
