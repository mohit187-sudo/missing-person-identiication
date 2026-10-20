"""Audit logging for sensitive operations."""
from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from backend.app.models import AuditLog


def client_ip(request: Optional[Request]) -> str:
    if request is None:
        return ""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


def log_action(
    db: Session,
    *,
    action: str,
    user_id=None,
    resource_type: str = "",
    resource_id: str = "",
    detail: Optional[dict[str, Any]] = None,
    request: Optional[Request] = None,
) -> AuditLog:
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id else "",
        detail=json.dumps(detail or {}, default=str),
        ip_address=client_ip(request),
        user_agent=(request.headers.get("user-agent", "")[:255] if request else ""),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def serialize_audit(entry: AuditLog, user_email: str = "") -> dict:
    try:
        detail = json.loads(entry.detail or "{}")
    except json.JSONDecodeError:
        detail = {"raw": entry.detail}
    return {
        "id": entry.id,
        "user_id": entry.user_id,
        "user_email": user_email,
        "action": entry.action,
        "resource_type": entry.resource_type,
        "resource_id": entry.resource_id,
        "detail": detail,
        "ip_address": entry.ip_address,
        "user_agent": entry.user_agent,
        "created_at": entry.created_at,
    }
