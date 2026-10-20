"""Database bootstrap helpers: roles, retention policies, first administrator."""
from __future__ import annotations

import logging

from sqlalchemy import select

from backend.app.db.session import Base, SessionLocal, engine
from backend.app.models import ROLE_ADMIN, ROLE_INVESTIGATOR, ROLE_RESCUE, Role, User
from backend.app.models.common import utcnow

logger = logging.getLogger("mpis.db")

ROLE_DESCRIPTIONS = {
    ROLE_ADMIN: "Administrator — full access incl. user management and audit logs",
    ROLE_INVESTIGATOR: "Authorized investigator — cases, matching, reviews",
    ROLE_RESCUE: "Rescue-team user — case viewing and updates, no biometric search",
}

DEFAULT_POLICIES = [
    ("photos", 365, "delete", "Authorized case photographs"),
    ("videos", 180, "delete", "CCTV/video evidence files"),
    ("embeddings", 365, "delete", "Biometric face embeddings"),
    ("rejected_matches", 90, "delete", "Rejected potential-match candidates"),
    ("audit_logs", 730, "anonymize", "Security audit records"),
]


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for name, desc in ROLE_DESCRIPTIONS.items():
            if db.scalar(select(Role).where(Role.name == name)) is None:
                db.add(Role(name=name, description=desc))

        from backend.app.models import RetentionPolicy

        for resource, days, action, desc in DEFAULT_POLICIES:
            if db.scalar(select(RetentionPolicy).where(RetentionPolicy.resource_type == resource)) is None:
                db.add(
                    RetentionPolicy(
                        resource_type=resource,
                        retention_days=days,
                        action=action,
                        description=desc,
                        is_active=True,
                    )
                )
        db.commit()
    finally:
        db.close()


def create_admin(email: str, password: str, full_name: str = "Administrator") -> User:
    """Create (or return) an administrator account."""
    from backend.app.core.security import hash_password

    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == email.lower()))
        if user:
            return user
        role = db.scalar(select(Role).where(Role.name == ROLE_ADMIN))
        user = User(
            email=email.lower(),
            full_name=full_name,
            hashed_password=hash_password(password),
            role_id=role.id,
            password_changed_at=utcnow(),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info("administrator created: %s", email)
        return user
    finally:
        db.close()
