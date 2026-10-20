"""Abstract face-AI backend interface.

The matching engine is deliberately replaceable: implement this interface to
evaluate alternative detection/embedding models. Nothing in the API layer
depends on a specific model.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np


@dataclass
class DetectedFace:
    """A single detected face in an image (coordinates in pixels)."""

    x: int
    y: int
    w: int
    h: int
    confidence: float
    landmarks: Optional[np.ndarray] = None  # optional 5-point landmarks


@dataclass
class FaceAIBackendInfo:
    name: str
    version: str
    embedding_dim: int
    license: str
    model_files: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)


class FaceAIBackend(ABC):
    """Contract every face backend must satisfy."""

    @abstractmethod
    def info(self) -> FaceAIBackendInfo: ...

    @abstractmethod
    def available(self) -> bool:
        """True when model weights are loaded and inference is possible."""

    @abstractmethod
    def availability_detail(self) -> str:
        """Human-readable explanation when unavailable (setup hints)."""

    @abstractmethod
    def detect_faces(self, image_bgr: np.ndarray) -> List[DetectedFace]:
        """Detect faces. Returns [] when none found."""

    @abstractmethod
    def embed(self, image_bgr: np.ndarray, face: DetectedFace) -> np.ndarray:
        """Return an L2-normalised embedding vector for one face."""

    # --- similarity ---------------------------------------------------------
    @staticmethod
    def similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Documented similarity metric: cosine similarity of embeddings.

        score = (a . b) / (||a|| ||b||)  in [-1, 1]; embeddings are
        L2-normalised so this reduces to the dot product. A score is a
        TECHNICAL similarity measure — never an identity probability.
        """
        if a.shape != b.shape or a.size == 0:
            raise ValueError("embedding dimension mismatch")
        denom = float(np.linalg.norm(a) * np.linalg.norm(b))
        if denom == 0.0:
            raise ValueError("zero-norm embedding")
        return float(np.dot(a, b) / denom)
