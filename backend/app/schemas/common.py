"""Shared response schemas."""
from __future__ import annotations

from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Message(BaseModel):
    message: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict = {}


class ErrorResponse(BaseModel):
    error: ErrorBody


class Page(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
    pages: int


class AIStatus(BaseModel):
    backend: str
    available: bool
    model_name: str = ""
    model_version: str = ""
    embedding_dim: Optional[int] = None
    license: str = ""
    detail: str = ""
    setup_steps: List[str] = []
