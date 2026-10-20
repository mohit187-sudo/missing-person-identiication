"""Users, roles and refresh tokens."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.session import Base
from backend.app.models.common import TimestampMixin, UUIDMixin, utcnow

# Canonical role names — enforced on every protected backend endpoint.
ROLE_ADMIN = "administrator"
ROLE_INVESTIGATOR = "investigator"
ROLE_RESCUE = "rescue_team"
ALL_ROLES = (ROLE_ADMIN, ROLE_INVESTIGATOR, ROLE_RESCUE)


class Role(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)

    users: Mapped[list["User"]] = relationship(back_populates="role")


class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    agency: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    phone: Mapped[str] = mapped_column(String(64), default="", nullable=False)

    # Login security
    failed_login_count: Mapped[int] = mapped_column(default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Password reset workflow (token stored hashed, single use)
    reset_token_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reset_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    role: Mapped[Role] = relationship(back_populates="users", lazy="joined")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def role_name(self) -> str:
        return self.role.name if self.role else ""


class RefreshToken(Base, UUIDMixin):
    """Opaque refresh token, stored only as a SHA-256 hash, with rotation families.

    Reuse of a rotated (already-revoked) token revokes the entire family —
    classic refresh-token-rotation theft detection.
    """

    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    family_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("refresh_tokens.id", ondelete="SET NULL"), nullable=True
    )
    revoked_reason: Mapped[str] = mapped_column(String(255), default="", nullable=False)

    user: Mapped[User] = relationship(back_populates="refresh_tokens")
