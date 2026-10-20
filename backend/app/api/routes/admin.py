"""Administration: user management and audit logs."""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.api.deps import RequireAdmin, paginate, pagination
from backend.app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from backend.app.core.security import hash_password
from backend.app.db.session import get_db
from backend.app.models import AuditLog, Role, User, utcnow
from backend.app.schemas.ops import AuditLogOut
from backend.app.schemas.user import UserCreate, UserOut, UserUpdate
from backend.app.services.audit import log_action, serialize_audit

router = APIRouter(prefix="/admin", tags=["administration"])


def _user_out(u: User) -> dict:
    return UserOut(
        id=u.id,
        email=u.email,
        full_name=u.full_name,
        role=u.role_name,
        agency=u.agency,
        phone=u.phone,
        is_active=u.is_active,
        created_at=u.created_at,
        last_login_at=u.last_login_at,
    ).model_dump()


@router.get("/users")
def list_users(
    q: Optional[str] = Query(None, max_length=255),
    paging: tuple = Depends(pagination),
    admin: User = RequireAdmin,
    db: Session = Depends(get_db),
):
    page, page_size = paging
    stmt = select(User)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(User.email.ilike(like) | User.full_name.ilike(like))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return paginate([_user_out(u) for u in rows], total, page, page_size)


@router.post("/users", status_code=201)
def create_user(
    payload: UserCreate, request: Request, admin: User = RequireAdmin, db: Session = Depends(get_db)
):
    existing = db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing:
        raise ConflictError("A user with that email already exists.")
    role = db.scalar(select(Role).where(Role.name == payload.role))
    if role is None:
        raise ValidationAppError("Unknown role.", {"allowed": ["administrator", "investigator", "rescue_team"]})

    user = User(
        email=payload.email.lower(),
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role_id=role.id,
        agency=payload.agency,
        phone=payload.phone,
        password_changed_at=utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log_action(
        db,
        action="admin.user_created",
        user_id=admin.id,
        resource_type="user",
        resource_id=str(user.id),
        detail={"email": user.email, "role": user.role_name},
        request=request,
    )
    return _user_out(user)


@router.patch("/users/{user_id}")
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    request: Request,
    admin: User = RequireAdmin,
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User", user_id)
    data = payload.model_dump(exclude_unset=True)

    if "role" in data and data["role"]:
        role = db.scalar(select(Role).where(Role.name == data.pop("role")))
        if role is None:
            raise ValidationAppError("Unknown role.")
        user.role_id = role.id
    if "password" in data and data["password"]:
        user.hashed_password = hash_password(data.pop("password"))
        user.password_changed_at = utcnow()
    if "is_active" in data and data["is_active"] is False and user.id == admin.id:
        raise ValidationAppError("You cannot deactivate your own account.")
    for k, v in data.items():
        setattr(user, k, v)
    db.commit()
    db.refresh(user)
    log_action(
        db,
        action="admin.user_updated",
        user_id=admin.id,
        resource_type="user",
        resource_id=str(user.id),
        detail={"fields": list(payload.model_dump(exclude_unset=True).keys())},
        request=request,
    )
    return _user_out(user)


@router.get("/audit-logs")
def list_audit_logs(
    action: Optional[str] = Query(None, max_length=128),
    resource_type: Optional[str] = Query(None, max_length=64),
    user_id: Optional[uuid.UUID] = Query(None),
    paging: tuple = Depends(pagination),
    admin: User = RequireAdmin,
    db: Session = Depends(get_db),
):
    page, page_size = paging
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()

    emails = {u.id: u.email for u in db.scalars(select(User)).all()}
    return paginate(
        [
            AuditLogOut(**serialize_audit(r, emails.get(r.user_id, ""))).model_dump()
            for r in rows
        ],
        total,
        page,
        page_size,
    )
