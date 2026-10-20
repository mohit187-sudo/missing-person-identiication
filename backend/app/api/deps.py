"""Shared FastAPI dependencies: authentication, role enforcement, pagination.

Authorization is enforced HERE on every protected endpoint — frontend role
checks are UX only and are never trusted.
"""
from __future__ import annotations

import math
from typing import Callable, List, Optional, Tuple

import jwt as pyjwt
from fastapi import Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.app.core.exceptions import ForbiddenError, UnauthorizedError
from backend.app.core.security import decode_access_token
from backend.app.db.session import get_db
from backend.app.models import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("Missing bearer token.")
    try:
        payload = decode_access_token(credentials.credentials)
    except pyjwt.ExpiredSignatureError:
        raise UnauthorizedError("Access token expired.", {"code": "token_expired"})
    except pyjwt.PyJWTError:
        raise UnauthorizedError("Invalid access token.")

    user_id = payload.get("sub")
    try:
        import uuid as _uuid

        user_id = _uuid.UUID(str(user_id))
    except (ValueError, TypeError):
        raise UnauthorizedError("Invalid access token.")
    user = db.get(User, user_id)
    if user is None:
        raise UnauthorizedError("User no longer exists.")
    if not user.is_active:
        raise ForbiddenError("Account is deactivated. Contact an administrator.")
    return user


def require_roles(*roles: str) -> Callable:
    allowed: Tuple[str, ...] = roles

    def _checker(user: User = Depends(get_current_user)) -> User:
        if user.role_name not in allowed:
            raise ForbiddenError(
                f"This action requires one of these roles: {', '.join(allowed)}."
            )
        return user

    return _checker


# Frequently used role combinations
RequireAdmin = Depends(require_roles("administrator"))
RequireInvestigator = Depends(require_roles("administrator", "investigator"))
RequireAnyAuthed = Depends(get_current_user)

# Users allowed to see biometric data / run matching.
BIOMETRIC_ROLES = ("administrator", "investigator")


def require_biometric(user: User = Depends(get_current_user)) -> User:
    if user.role_name not in BIOMETRIC_ROLES:
        raise ForbiddenError(
            "Access to biometric matching is restricted to administrators and "
            "authorized investigators."
        )
    return user


RequireBiometric = Depends(require_biometric)


def pagination(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)
) -> Tuple[int, int]:
    return page, page_size


def paginate(items: List, total: int, page: int, page_size: int) -> dict:
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, math.ceil(total / page_size)) if page_size else 1,
    }
