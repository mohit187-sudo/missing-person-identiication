"""Face matching service: detection, embedding, comparison and ranked search.

Documented behaviour
--------------------
* Similarity metric: cosine similarity between L2-normalised embeddings.
* A similarity score is a TECHNICAL measure of embedding closeness. It is NOT
  the probability that two images show the same person. Thresholds must be
  tested on representative, lawfully obtained data; false positives and false
  negatives always exist (see README "Limitations").
* The engine never declares a person identified and never triggers any
  law-enforcement action. Humans review every candidate.
* No demographic characteristics are used to infer identity.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from backend.app.ai.base import DetectedFace, FaceAIBackend
from backend.app.ai.quality import assess_face_quality, assess_whole_image
from backend.app.core.config import settings
from backend.app.core.exceptions import AIModelUnavailableError, ValidationAppError

# --- embedding serialization (portable across SQLite / PostgreSQL) -----------


def pack_embedding(vec: np.ndarray) -> bytes:
    return np.asarray(vec, dtype="<f4").tobytes()


def unpack_embedding(blob: bytes, dim: Optional[int] = None) -> np.ndarray:
    arr = np.frombuffer(blob, dtype="<f4")
    if dim is not None and arr.size != dim:
        raise ValueError(f"embedding size {arr.size} != dim {dim}")
    return arr


@dataclass
class FaceObservation:
    face: DetectedFace
    quality: Any  # QualityReport
    embedding: Optional[np.ndarray]


@dataclass
class CandidateMatch:
    case_id: Any
    reference_photo_id: Any
    reference_embedding_id: Any
    similarity_score: float
    image_quality: Dict[str, Any]


def load_image_bgr(data: bytes) -> np.ndarray:
    import cv2

    if not data:
        raise ValidationAppError("Empty image payload.")
    img = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValidationAppError("Could not decode image — corrupt or unsupported file.")
    return img


class FaceMatchingService:
    """Facade over a pluggable FaceAIBackend."""

    def __init__(self, backend: FaceAIBackend) -> None:
        self.backend = backend

    # --- A/B: detection + quality validation -------------------------------
    def analyze_photo(self, image_bgr: np.ndarray) -> List[FaceObservation]:
        ok, meta, reason = assess_whole_image(image_bgr)
        if not ok:
            raise ValidationAppError(reason, meta)

        observations: List[FaceObservation] = []
        for face in self.backend.detect_faces(image_bgr):
            gray = _crop_gray(image_bgr, face)
            size_px = max(face.w, face.h)
            quality = assess_face_quality(gray, size_px, face.confidence)
            emb: Optional[np.ndarray] = None
            if quality.ok:
                try:
                    emb = self.backend.embed(image_bgr, face)
                except Exception:
                    emb = None
            observations.append(FaceObservation(face=face, quality=quality, embedding=emb))
        return observations

    # --- C: embedding for one face ----------------------------------------
    def embed_primary_face(self, image_bgr: np.ndarray) -> Tuple[np.ndarray, FaceObservation]:
        observations = self.analyze_photo(image_bgr)
        if not observations:
            raise ValidationAppError(
                "No face detected in the image. Use a clear, frontal photograph."
            )
        usable = [o for o in observations if o.embedding is not None]
        if not usable:
            best = observations[0]
            raise ValidationAppError(
                "Detected face failed quality checks and cannot be used for matching.",
                {"reason": best.quality.rejection_reason,
                 "blur_score": best.quality.blur_score,
                 "quality_score": best.quality.quality_score},
            )
        # Largest usable face (usually the subject of the photo).
        primary = max(usable, key=lambda o: o.face.w * o.face.h)
        return primary.embedding, primary

    # --- D/E: comparison + ranked candidates -------------------------------
    def rank_candidates(
        self,
        query_embedding: np.ndarray,
        gallery: Sequence[Tuple[Any, Any, Any, np.ndarray, Dict[str, Any]]],
        threshold: Optional[float] = None,
        top_k: int = 20,
    ) -> List[CandidateMatch]:
        """Rank gallery rows (case_id, photo_id, embedding_id, vec, quality)."""
        thr = settings.ai_match_threshold if threshold is None else threshold
        scored: List[CandidateMatch] = []
        for case_id, photo_id, emb_id, vec, quality in gallery:
            score = self.backend.similarity(query_embedding, vec)
            if score >= thr:
                scored.append(
                    CandidateMatch(
                        case_id=case_id,
                        reference_photo_id=photo_id,
                        reference_embedding_id=emb_id,
                        similarity_score=round(score, 6),
                        image_quality=quality or {},
                    )
                )
        scored.sort(key=lambda c: c.similarity_score, reverse=True)

        # Keep the best reference photo per case to avoid duplicates flooding the list.
        best_per_case: Dict[Any, CandidateMatch] = {}
        for c in scored:
            if c.case_id not in best_per_case:
                best_per_case[c.case_id] = c
        ranked = sorted(best_per_case.values(), key=lambda c: c.similarity_score, reverse=True)
        return ranked[:top_k]


def _crop_gray(image_bgr: np.ndarray, face: DetectedFace):
    import cv2

    h, w = image_bgr.shape[:2]
    x0, y0 = max(0, face.x), max(0, face.y)
    x1, y1 = min(w, face.x + face.w), min(h, face.y + face.h)
    crop = image_bgr[y0:y1, x0:x1]
    if crop.size == 0:
        crop = image_bgr
    return cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
