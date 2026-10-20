"""AI matching, potential matches and review schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MatchOut(BaseModel):
    id: uuid.UUID
    source_type: str
    candidate_case_id: uuid.UUID
    candidate_case_number: str = ""
    candidate_name: Optional[str] = None
    query_photo_id: Optional[uuid.UUID] = None
    detected_face_id: Optional[uuid.UUID] = None
    similarity_score: float
    threshold_used: float
    model_name: str
    model_version: str
    image_quality: Dict[str, Any] = {}
    status: str
    source_timestamp_seconds: Optional[float] = None
    processing_timestamp: datetime
    is_demo: bool = False
    created_at: datetime


class ReviewRequest(BaseModel):
    decision: str = Field(
        pattern="^(confirmed_for_investigation|rejected|requires_manual_review)$"
    )
    notes: str = Field(default="", max_length=8000)


class ReviewOut(BaseModel):
    id: uuid.UUID
    match_id: uuid.UUID
    reviewer_id: Optional[uuid.UUID]
    reviewer_name: str = ""
    decision: str
    notes: str
    created_at: datetime


class MatchDetailOut(MatchOut):
    reviews: List[ReviewOut] = []


class SearchResult(BaseModel):
    job_id: uuid.UUID
    status: str
    model_name: str
    model_version: str
    threshold_used: float
    matches: List[MatchOut]
    faces_detected: int
    quality: Dict[str, Any] = {}
    disclaimer: str = (
        "Similarity scores are technical measurements between facial embeddings. "
        "They are NOT the probability that two images show the same person. "
        "No person is identified until an authorized investigator verifies the "
        "match with independent corroborating evidence."
    )


class MatchingJobOut(BaseModel):
    id: uuid.UUID
    status: str
    progress: float
    threshold_used: Optional[float]
    model_name: str
    model_version: str
    candidates_returned: int
    error_message: str
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]

    model_config = {"from_attributes": True}


class VideoJobOut(BaseModel):
    id: uuid.UUID
    video_id: uuid.UUID
    status: str
    progress: float
    sampling_interval_seconds: float
    frames_sampled: int
    faces_detected: int
    matches_found: int
    error_message: str
    cancel_requested: bool
    model_name: str
    model_version: str
    threshold_used: Optional[float]
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]

    model_config = {"from_attributes": True}


class DetectedFaceOut(BaseModel):
    id: uuid.UUID
    frame_index: int
    timestamp_seconds: float
    bbox: List[int]
    face_confidence: Optional[float]
    blur_score: Optional[float]
    quality_score: Optional[float]
    eligible_for_matching: bool
    rejection_reason: str
    thumbnail_url: str = ""
