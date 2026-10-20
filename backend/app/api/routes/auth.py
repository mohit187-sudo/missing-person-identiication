"""Authentication: login (rate limited), refresh rotation, logout, me,
password change and password-reset workflow."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.config import settings
from backend.app.core.exceptions import UnauthorizedError, ValidationAppError
from backend.app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    password_needs_rehash,
    refresh_expiry,
    verify_password,
)
from backend.app.db.session import get_db
from backend.app.models import RefreshToken, Role, User, as_utc, utcnow
from backend.app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    PasswordChangeRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshRequest,
    TokenResponse,
    UserBrief,
)
from backend.app.security.rate_limit import RateLimiter
from backend.app.services.audit import log_action

router = APIRouter(prefix="/auth", tags=["authentication"])

_login_limiter = RateLimiter(
    settings.login_rate_limit_per_minute, 60, scope="login"
)


def _apply_login_rate_limit(request: Request) -> None:
    # Read limits from live settings so operators can tune without restart.
    limiter = RateLimiter(settings.login_rate_limit_per_minute, 60, scope="login")
    limiter(request)
MAX_FAILED_LOGINS = 10
LOCKOUT_MINUTES = 15


def _brief(user: User) -> UserBrief:
    return UserBrief(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role_name,
        agency=user.agency,
        is_active=user.is_active,
    )


def _issue_tokens(db: Session, user: User, family_id: str | None = None) -> dict:
    access = create_access_token(user.id, user.role_name)
    raw_refresh = generate_refresh_token()
    fam = family_id or secrets.token_hex(12)
    row = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw_refresh),
        family_id=fam,
        created_at=utcnow(),
        expires_at=refresh_expiry(),
    )
    db.add(row)
    db.commit()
    return {
        "access_token": access,
        "refresh_token": raw_refresh,
        "token_type": "bearer",
        "expires_in": settings.jwt_access_token_minutes * 60,
        "user": _brief(user),
    }


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    _apply_login_rate_limit(request)

    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    generic_error = UnauthorizedError("Invalid email or password.")

    if user is None:
        log_action(
            db,
            action="auth.login_failed",
            detail={"email": payload.email, "reason": "unknown_user"},
            request=request,
        )
        raise generic_error

    if user.locked_until and as_utc(user.locked_until) > as_utc(utcnow()):
        raise UnauthorizedError(
            "Account temporarily locked due to failed login attempts. Try again later.",
            {"locked_until": user.locked_until.isoformat()},
        )

    if not verify_password(payload.password, user.hashed_password):
        user.failed_login_count += 1
        if user.failed_login_count >= MAX_FAILED_LOGINS:
            user.locked_until = utcnow() + timedelta(minutes=LOCKOUT_MINUTES)
            user.failed_login_count = 0
        db.commit()
        log_action(
            db,
            action="auth.login_failed",
            user_id=user.id,
            detail={"email": payload.email, "reason": "bad_password"},
            request=request,
        )
        raise generic_error

    if not user.is_active:
        raise UnauthorizedError("Account is deactivated. Contact an administrator.")

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = utcnow()
    if password_needs_rehash(user.hashed_password):
        user.hashed_password = hash_password(payload.password)
    db.commit()

    log_action(db, action="auth.login", user_id=user.id, request=request)
    return _issue_tokens(db, user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, request: Request, db: Session = Depends(get_db)):
    token_hash = hash_token(payload.refresh_token)
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if row is None:
        raise UnauthorizedError("Invalid refresh token.")

    now = utcnow()
    if row.revoked_at is not None:
        # Rotation reuse ⇒ assume theft ⇒ revoke the entire family.
        family = db.scalars(
            select(RefreshToken).where(
                RefreshToken.family_id == row.family_id, RefreshToken.revoked_at.is_(None)
            )
        ).all()
        for t in family:
            t.revoked_at = now
            t.revoked_reason = "family_revoked_after_reuse"
        db.commit()
        log_action(
            db,
            action="auth.refresh_reuse_detected",
            user_id=row.user_id,
            detail={"family_id": row.family_id},
            request=request,
        )
        raise UnauthorizedError("Refresh token reuse detected — all sessions revoked.")

    if as_utc(row.expires_at) < as_utc(now):
        row.revoked_at = now
        row.revoked_reason = "expired"
        db.commit()
        raise UnauthorizedError("Refresh token expired.")

    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("User account unavailable.")

    # Rotate: revoke current, issue new in the same family.
    result = _issue_tokens(db, user, family_id=row.family_id)
    new_hash = hash_token(result["refresh_token"])
    new_row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == new_hash))
    row.revoked_at = now
    row.revoked_reason = "rotated"
    row.replaced_by_id = new_row.id if new_row else None
    db.commit()
    return result


@router.post("/logout")
def logout(
    payload: LogoutRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.refresh_token:
        row = db.scalar(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_token(payload.refresh_token)
            )
        )
        if row and row.user_id == user.id:
            for t in db.scalars(
                select(RefreshToken).where(
                    RefreshToken.family_id == row.family_id,
                    RefreshToken.revoked_at.is_(None),
                )
            ).all():
                t.revoked_at = utcnow()
                t.revoked_reason = "logout"
            db.commit()
    log_action(db, action="auth.logout", user_id=user.id, request=request)
    return {"message": "Logged out."}


@router.get("/me", response_model=UserBrief)
def me(user: User = Depends(get_current_user)):
    return _brief(user)


@router.post("/change-password")
def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, user.hashed_password):
        raise ValidationAppError("Current password is incorrect.")
    if len(payload.new_password) < 10:
        raise ValidationAppError("New password must be at least 10 characters.")
    user.hashed_password = hash_password(payload.new_password)
    user.password_changed_at = utcnow()
    # Revoke all refresh sessions after a password change.
    for t in db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)
        )
    ).all():
        t.revoked_at = utcnow()
        t.revoked_reason = "password_changed"
    db.commit()
    log_action(db, action="auth.password_changed", user_id=user.id, request=request)
    return {"message": "Password changed. All other sessions were signed out."}


@router.post("/request-password-reset")
def request_password_reset(
    payload: PasswordResetRequest, request: Request, db: Session = Depends(get_db)
):
    """Starts the reset workflow. The response is generic to avoid account
    enumeration; in a configured deployment the token is emailed; in local demo
    mode the token is returned in the response (clearly marked)."""
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user and user.is_active:
        token = secrets.token_urlsafe(32)
        user.reset_token_hash = hash_token(token)
        user.reset_token_expires_at = utcnow() + timedelta(hours=1)
        db.commit()
        log_action(db, action="auth.reset_requested", user_id=user.id, request=request)
        from backend.app.services.email import email_configured, send_email

        if email_configured():
            send_email(
                to=user.email,
                subject="Password reset",
                body=f"Use this token within 1 hour to reset your password: {token}",
            )
            return {"message": "If that account exists, a reset token has been sent."}
        # Local demo / unconfigured email: return the token to the caller.
        return {
            "message": "Email delivery is not configured — reset token returned for local demo use only.",
            "demo_reset_token": token,
            "demo": True,
        }
    return {"message": "If that account exists, a reset token has been sent."}


@router.post("/confirm-password-reset")
def confirm_password_reset(
    payload: PasswordResetConfirm, request: Request, db: Session = Depends(get_db)
):
    th = hash_token(payload.token)
    user = db.scalar(select(User).where(User.reset_token_hash == th))
    if (
        user is None
        or user.reset_token_expires_at is None
        or as_utc(user.reset_token_expires_at) < as_utc(utcnow())
    ):
        raise ValidationAppError("Reset token is invalid or expired.")
    if len(payload.new_password) < 10:
        raise ValidationAppError("New password must be at least 10 characters.")
    user.hashed_password = hash_password(payload.new_password)
    user.reset_token_hash = None
    user.reset_token_expires_at = None
    user.password_changed_at = utcnow()
    for t in db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)
        )
    ).all():
        t.revoked_at = utcnow()
        t.revoked_reason = "password_reset"
    db.commit()
    log_action(db, action="auth.password_reset_completed", user_id=user.id, request=request)
    return {"message": "Password reset complete. Please sign in."}
