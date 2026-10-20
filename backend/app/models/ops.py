"""Operational tables: notifications, audit logs and retention policies."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.session import Base
from backend.app.models.common import TimestampMixin, UUIDMixin, utcnow


class Notification(Base, UUIDMixin):
    """In-app notification. Content stays minimal — no full PII in alerts."""

    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(64), nullable=False)  # job_completed | match_review | ...
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    link: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class AuditLog(Base, UUIDMixin):
    """Append-only audit trail for sensitive operations (including rejected
    match candidates, retained only as long as the approved policy requires)."""

    __tablename__ = "audit_logs"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(64), default="", nullable=False, index=True)
    resource_id: Mapped[str] = mapped_column(String(64), default="", nullable=False, index=True)
    detail: Mapped[str] = mapped_column(Text, default="{}")  # JSON
    ip_address: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    user_agent: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)


class RetentionPolicy(Base, UUIDMixin, TimestampMixin):
    """Configurable retention schedules per resource type."""

    __tablename__ = "retention_policies"

    resource_type: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )  # photos | videos | embeddings | rejected_matches | audit_logs
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(32), default="delete")  # delete | anonymize
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)


class CorrectionRequest(Base, UUIDMixin, TimestampMixin):
    """Documented process for correcting mistaken matches / data-subject requests."""

    __tablename__ = "correction_requests"

    requester_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    subject_reference: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    request_type: Mapped[str] = mapped_column(String(64), nullable=False)  # correction | deletion | access
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)  # open | in_review | resolved
    resolution_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
