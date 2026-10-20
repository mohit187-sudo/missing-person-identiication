"""In-app notifications with optional email delivery.

Notification content is deliberately minimal — never include full personally
identifiable case details. Emails contain authenticated links only.
"""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import Notification, User
from backend.app.services.email import send_email

logger = logging.getLogger("mpis.notifications")


def notify(
    db: Session,
    *,
    user_id: UUID,
    type: str,
    title: str,
    body: str = "",
    link: str = "",
    send_email_alert: bool = False,
) -> Notification:
    from backend.app.models.common import utcnow

    n = Notification(
        user_id=user_id,
        type=type,
        title=title[:255],
        body=body[:2000],
        link=link[:512],
        created_at=utcnow(),
    )
    db.add(n)
    db.commit()
    db.refresh(n)

    if send_email_alert:
        user = db.get(User, user_id)
        if user and user.email:
            try:
                send_email(
                    to=user.email,
                    subject=title,
                    body=(
                        f"{body}\n\nOpen the authenticated portal for details: {link}\n\n"
                        "This notification intentionally omits personal case details."
                    ),
                )
            except Exception as exc:  # email is best-effort / optional
                logger.warning("email delivery failed: %s", exc)
    return n


def notify_role(
    db: Session,
    *,
    role_name: str,
    type: str,
    title: str,
    body: str = "",
    link: str = "",
    exclude_user_id: Optional[UUID] = None,
) -> int:
    """Notify every active user holding a role. Returns number notified."""
    from backend.app.models import Role

    users = db.scalars(
        select(User).join(Role).where(Role.name == role_name, User.is_active.is_(True))
    ).all()
    count = 0
    for u in users:
        if exclude_user_id and u.id == exclude_user_id:
            continue
        notify(db, user_id=u.id, type=type, title=title, body=body, link=link)
        count += 1
    return count
