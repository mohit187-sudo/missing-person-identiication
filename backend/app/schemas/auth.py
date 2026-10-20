"""Auth request/response schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=10)


class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: "UserBrief"


class UserBrief(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: str
    agency: str = ""
    is_active: bool = True


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=10, max_length=256)


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=10)
    new_password: str = Field(min_length=10, max_length=256)


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: str
    agency: str = ""
    phone: str = ""
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
