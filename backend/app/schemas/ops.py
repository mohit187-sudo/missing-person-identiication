"""Notification, audit, retention and admin schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class NotificationOut(BaseModel):
    id: uuid.UUID
    type: str
    title: str
    body: str
    link: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogOut(BaseModel):
    id: uuid.UUID
    user_id: Optional[uuid.UUID]
    user_email: str = ""
    action: str
    resource_type: str
    resource_id: str
    detail: Dict[str, Any] = {}
    ip_address: str
    user_agent: str
    created_at: datetime

    model_config = {"from_attributes": True}


class RetentionPolicyOut(BaseModel):
    id: uuid.UUID
    resource_type: str
    retention_days: int
    action: str
    is_active: bool
    description: str

    model_config = {"from_attributes": True}


class RetentionPolicyUpdate(BaseModel):
    retention_days: int = Field(ge=1, le=36500)
    action: str = Field(pattern="^(delete|anonymize)$")
    is_active: bool = True
    description: str = Field(default="", max_length=4000)


class CorrectionRequestCreate(BaseModel):
    subject_reference: str = Field(default="", max_length=255)
    request_type: str = Field(pattern="^(correction|deletion|access)$")
    description: str = Field(min_length=10, max_length=8000)


class CorrectionRequestOut(BaseModel):
    id: uuid.UUID
    subject_reference: str
    request_type: str
    description: str
    status: str
    resolution_note: str
    created_at: datetime

    model_config = {"from_attributes": True}


class OverviewStats(BaseModel):
    total_cases: int
    active_cases: int
    located_cases: int
    total_photos: int
    total_videos: int
    jobs_running: int
    jobs_completed: int
    matches_pending_review: int
    matches_confirmed: int
    matches_rejected: int
    demo_cases: int
    ai_available: bool
    cases_by_status: Dict[str, int]
    matches_last_7_days: int
    cases_last_30_days: int
