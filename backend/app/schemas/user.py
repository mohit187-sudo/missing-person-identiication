"""Admin user-management schemas."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from backend.app.schemas.auth import UserOut


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=10, max_length=256)
    role: str = Field(pattern="^(administrator|investigator|rescue_team)$")
    agency: str = Field(default="", max_length=255)
    phone: str = Field(default="", max_length=64)


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    role: Optional[str] = Field(
        default=None, pattern="^(administrator|investigator|rescue_team)$"
    )
    agency: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=64)
    is_active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=10, max_length=256)


class UserListOut(BaseModel):
    items: list[UserOut]
    total: int
