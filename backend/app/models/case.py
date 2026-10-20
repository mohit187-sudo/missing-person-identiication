"""Missing-person cases, photos and status history."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.session import Base
from backend.app.models.common import SoftDeleteMixin, TimestampMixin, UUIDMixin, utcnow

# Case status machine
CASE_STATUS_MISSING = "missing"
CASE_STATUS_INVESTIGATING = "investigating"
CASE_STATUS_POTENTIAL_LEAD = "potential_lead"
CASE_STATUS_LOCATED = "located"
CASE_STATUS_CLOSED = "closed"
CASE_STATUS_ARCHIVED = "archived"
ALL_CASE_STATUSES = (
    CASE_STATUS_MISSING,
    CASE_STATUS_INVESTIGATING,
    CASE_STATUS_POTENTIAL_LEAD,
    CASE_STATUS_LOCATED,
    CASE_STATUS_CLOSED,
    CASE_STATUS_ARCHIVED,
)


class MissingPersonCase(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "missing_person_cases"
    __table_args__ = (
        Index("ix_cases_status_active", "status", "is_deleted"),
        Index("ix_cases_last_seen_date", "last_seen_date"),
    )

    # Server-generated human-readable identifier, e.g. MPI-2026-000123
    case_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name_unknown: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    age_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    age_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(32), nullable=True)

    last_seen_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_seen_location: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    physical_description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    clothing_description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    additional_notes: Mapped[str] = mapped_column(Text, default="", nullable=False)

    contact_agency: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    contact_info: Mapped[str] = mapped_column(String(255), default="", nullable=False)

    status: Mapped[str] = mapped_column(
        String(32), default=CASE_STATUS_MISSING, nullable=False, index=True
    )

    # Legal / consent records
    consent_recorded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    legal_basis: Mapped[str] = mapped_column(Text, default="", nullable=False)
    authorization_reference: Mapped[str] = mapped_column(String(255), default="", nullable=False)

    # Demo data is kept in an isolated namespace and clearly labelled.
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    owned_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    photos: Mapped[list["PersonPhoto"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    status_history: Mapped[list["CaseStatusHistory"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )


class PersonPhoto(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """Metadata for an authorized photograph stored in PRIVATE storage.

    Files never live in publicly served folders; retrieval goes through an
    authenticated API endpoint.
    """

    __tablename__ = "person_photos"

    case_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("missing_person_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    quality_score: Mapped[float | None] = mapped_column(nullable=True)
    blur_score: Mapped[float | None] = mapped_column(nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Malware-scan integration point: pending/clean/infected/unavailable
    malware_scan_status: Mapped[str] = mapped_column(String(32), default="unavailable", nullable=False)

    case: Mapped[MissingPersonCase] = relationship(back_populates="photos")
    embeddings: Mapped[list["FaceEmbedding"]] = relationship(  # noqa: F821
        back_populates="photo", cascade="all, delete-orphan"
    )


class CaseStatusHistory(Base, UUIDMixin):
    __tablename__ = "case_status_history"

    case_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("missing_person_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    case: Mapped[MissingPersonCase] = relationship(back_populates="status_history")
