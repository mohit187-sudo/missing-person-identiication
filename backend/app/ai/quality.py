"""Image / face quality gates used before embedding generation.

Guards against very small, blurred, over/under-exposed or unsuitable inputs.
No demographic inference of any kind is performed here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import cv2
import numpy as np

from backend.app.core.config import settings


@dataclass
class QualityReport:
    ok: bool
    blur_score: float
    brightness: float
    face_size_px: int
    quality_score: float
    rejection_reason: str = ""


def blur_variance(gray: np.ndarray) -> float:
    """Laplacian variance — higher is sharper."""
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def assess_face_quality(
    gray_crop: np.ndarray, face_size_px: int, confidence: float
) -> QualityReport:
    b = blur_variance(gray_crop)
    brightness = float(np.mean(gray_crop))

    reasons = []
    if face_size_px < settings.ai_min_face_size_px:
        reasons.append(f"face too small ({face_size_px}px < {settings.ai_min_face_size_px}px)")
    if b < settings.ai_max_blur_variance_below:
        reasons.append(f"image blurred (laplacian var {b:.1f})")
    if brightness < 25:
        reasons.append("image too dark")
    elif brightness > 235:
        reasons.append("image over-exposed")
    if confidence < settings.ai_min_face_confidence:
        reasons.append(f"low detection confidence ({confidence:.2f})")

    # Composite quality score in [0,1] for reporting only.
    size_score = min(1.0, face_size_px / float(settings.ai_min_face_size_px * 2))
    blur_score_n = min(1.0, b / 150.0)
    bright_score = max(0.0, 1.0 - abs(brightness - 127.0) / 127.0)
    quality = round(0.4 * blur_score_n + 0.3 * size_score + 0.3 * bright_score, 4)

    return QualityReport(
        ok=not reasons,
        blur_score=round(b, 2),
        brightness=round(brightness, 2),
        face_size_px=face_size_px,
        quality_score=quality,
        rejection_reason="; ".join(reasons),
    )


def assess_whole_image(image_bgr: np.ndarray) -> Tuple[bool, dict, str]:
    """Validate an uploaded photo before face detection."""
    h, w = image_bgr.shape[:2]
    if w < 64 or h < 64:
        return False, {"width": w, "height": h}, "Image resolution too small for face analysis (min 64x64)."
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    b = blur_variance(gray)
    brightness = float(np.mean(gray))
    meta = {"width": w, "height": h, "blur_score": round(b, 2), "brightness": round(brightness, 2)}
    if b < 5:
        return False, meta, "Image is severely blurred or lacks detail."
    return True, meta, ""
