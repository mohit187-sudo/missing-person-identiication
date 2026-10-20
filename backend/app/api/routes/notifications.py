"""In-app notifications."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.api.deps import paginate, pagination
from backend.app.db.session import get_db
from backend.app.models import Notification, User
from backend.app.api.deps import RequireAnyAuthed

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(
    unread_only: bool = Query(False),
    paging: tuple = Depends(pagination),
    user: User = RequireAnyAuthed,
    db: Session = Depends(get_db),
):
    page, page_size = paging
    stmt = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(Notification.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return paginate(
        [
            {
                "id": n.id,
                "type": n.type,
                "title": n.title,
                "body": n.body,
                "link": n.link,
                "is_read": n.is_read,
                "created_at": n.created_at,
            }
            for n in rows
        ],
        total,
        page,
        page_size,
    )


@router.get("/unread-count")
def unread_count(user: User = RequireAnyAuthed, db: Session = Depends(get_db)):
    count = db.scalar(
        select(func.count()).select_from(Notification).where(
            Notification.user_id == user.id, Notification.is_read.is_(False)
        )
    )
    return {"unread": count or 0}


@router.post("/{notification_id}/read")
def mark_read(
    notification_id: uuid.UUID,
    user: User = RequireAnyAuthed,
    db: Session = Depends(get_db),
):
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user.id:
        return {"message": "Notification not found."}
    n.is_read = True
    db.commit()
    return {"message": "Marked as read."}


@router.post("/read-all")
def mark_all_read(user: User = RequireAnyAuthed, db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Notification).where(Notification.user_id == user.id, Notification.is_read.is_(False))
    ).all()
    for n in rows:
        n.is_read = True
    db.commit()
    return {"message": f"Marked {len(rows)} notifications as read."}
