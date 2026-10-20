"""Case, photo and status-history schemas."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

from backend.app.models.case import ALL_CASE_STATUSES


class CaseBase(BaseModel):
    full_name: Optional[str] = Field(default=None, max_length=255)
    name_unknown: bool = False
    age_min: Optional[int] = Field(default=None, ge=0, le=130)
    age_max: Optional[int] = Field(default=None, ge=0, le=130)
    gender: Optional[str] = Field(default=None, max_length=32)
    last_seen_date: Optional[date] = None
    last_seen_location: str = Field(default="", max_length=512)
    physical_description: str = Field(default="", max_length=8000)
    clothing_description: str = Field(default="", max_length=8000)
    additional_notes: str = Field(default="", max_length=8000)
    contact_agency: str = Field(default="", max_length=255)
    contact_info: str = Field(default="", max_length=255)
    consent_recorded: bool = False
    legal_basis: str = Field(default="", max_length=8000)
    authorization_reference: str = Field(default="", max_length=255)

    @model_validator(mode="after")
    def _check_age_range_and_name(self):
        if self.age_min is not None and self.age_max is not None and self.age_max < self.age_min:
            raise ValueError("age_max must be greater than or equal to age_min")
        if not self.name_unknown and not (self.full_name or "").strip():
            raise ValueError("Provide full_name or set name_unknown=true")
        return self


class CaseCreate(CaseBase):
    status: str = Field(default="missing", pattern="^(missing|investigating)$")
    # Duplicate-warning acknowledgement
    acknowledge_duplicate_warning: bool = False


class CaseUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, max_length=255)
    name_unknown: Optional[bool] = None
    age_min: Optional[int] = Field(default=None, ge=0, le=130)
    age_max: Optional[int] = Field(default=None, ge=0, le=130)
    gender: Optional[str] = Field(default=None, max_length=32)
    last_seen_date: Optional[date] = None
    last_seen_location: Optional[str] = Field(default=None, max_length=512)
    physical_description: Optional[str] = Field(default=None, max_length=8000)
    clothing_description: Optional[str] = Field(default=None, max_length=8000)
    additional_notes: Optional[str] = Field(default=None, max_length=8000)
    contact_agency: Optional[str] = Field(default=None, max_length=255)
    contact_info: Optional[str] = Field(default=None, max_length=255)
    status: Optional[str] = Field(default=None, pattern="^(" + "|".join(ALL_CASE_STATUSES) + ")$")
    status_note: Optional[str] = Field(default=None, max_length=4000)
    consent_recorded: Optional[bool] = None
    legal_basis: Optional[str] = Field(default=None, max_length=8000)
    authorization_reference: Optional[str] = Field(default=None, max_length=255)


class PhotoOut(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    original_filename: str
    content_type: str
    file_size: int
    is_primary: bool
    quality_score: Optional[float] = None
    blur_score: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    embedding_count: int = 0  # count of generated embeddings
    created_at: datetime

    model_config = {"from_attributes": True}


class StatusHistoryOut(BaseModel):
    id: uuid.UUID
    from_status: Optional[str]
    to_status: str
    note: str
    changed_by: Optional[uuid.UUID]
    created_at: datetime

    model_config = {"from_attributes": True}


class CaseOut(BaseModel):
    id: uuid.UUID
    case_number: str
    full_name: Optional[str]
    name_unknown: bool
    age_min: Optional[int]
    age_max: Optional[int]
    gender: Optional[str]
    last_seen_date: Optional[date]
    last_seen_location: str
    physical_description: str
    clothing_description: str
    additional_notes: str
    contact_agency: str
    contact_info: str
    status: str
    consent_recorded: bool
    legal_basis: str
    authorization_reference: str
    is_demo: bool
    created_by: Optional[uuid.UUID]
    owned_by: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime
    photos: List[PhotoOut] = []
    status_history: List[StatusHistoryOut] = []

    model_config = {"from_attributes": True}


class CaseListItem(BaseModel):
    id: uuid.UUID
    case_number: str
    full_name: Optional[str]
    name_unknown: bool
    age_min: Optional[int]
    age_max: Optional[int]
    last_seen_date: Optional[date]
    last_seen_location: str
    status: str
    is_demo: bool
    photo_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class DuplicateWarning(BaseModel):
    possible_duplicates: List[CaseListItem]
    warning: str


class CaseReportRow(BaseModel):
    case_number: str
    full_name: Optional[str]
    status: str
    last_seen_date: Optional[date]
    last_seen_location: str
    photo_count: int
    created_at: datetime
