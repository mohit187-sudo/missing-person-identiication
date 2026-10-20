"""Video-evidence schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class VideoCreateMeta(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=8000)
    case_id: Optional[uuid.UUID] = None
    authorization_reference: str = Field(default="", max_length=255)
    lawfully_obtained: bool = False


class VideoOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    case_id: Optional[uuid.UUID]
    original_filename: str
    content_type: str
    file_size: int
    duration_seconds: Optional[float]
    width: Optional[int]
    height: Optional[int]
    fps: Optional[float]
    authorization_reference: str
    lawfully_obtained: bool
    is_demo: bool
    uploaded_by: Optional[uuid.UUID]
    created_at: datetime
    latest_job_status: Optional[str] = None
    latest_job_progress: Optional[float] = None

    model_config = {"from_attributes": True}


class ProcessRequest(BaseModel):
    sampling_interval_seconds: float = Field(default=1.0, gt=0.1, le=30.0)
