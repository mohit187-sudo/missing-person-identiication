"""OpenCV YuNet (detection) + SFace (embedding) backend.

Model provenance
----------------
* Detector:  YuNet — `face_detection_yunet_2023mar.onnx` from the
  opencv/opencv_zoo project (Apache-2.0).
* Recognizer: SFace — `face_recognition_sface_2021dec.onnx` from the
  opencv/opencv_zoo project (Apache-2.0).
* Both ship with OpenCV's Zoo and run through `cv2.FaceDetectorYN` and
  `cv2.FaceRecognizerSF` (OpenCV >= 4.5.4, Apache-2.0).

Download via `python scripts/download_models.py` (official GitHub raw URLs).

Embedding: 128-d SFace descriptor, L2-normalised.
Similarity: cosine similarity (see FaceAIBackend.similarity).
"""
from __future__ import annotations

from pathlib import Path
from typing import List

import numpy as np

from backend.app.ai.base import DetectedFace, FaceAIBackend, FaceAIBackendInfo
from backend.app.core.config import settings

YUNET_FILE = "face_detection_yunet_2023mar.onnx"
SFACE_FILE = "face_recognition_sface_2021dec.onnx"

MODEL_LICENSE = (
    "OpenCV Zoo (opencv/opencv_zoo) — Apache License 2.0. "
    "YuNet and SFace ONNX weights are distributed by the OpenCV project."
)


class OpenCVSFaceBackend(FaceAIBackend):
    def __init__(self, model_dir: Path | None = None) -> None:
        self.model_dir = Path(model_dir or settings.ai_model_dir)
        self._detector = None
        self._recognizer = None
        self._load_error = ""

    # -- lifecycle ----------------------------------------------------------
    def _try_load(self) -> bool:
        if self._detector is not None and self._recognizer is not None:
            return True
        yunet = self.model_dir / YUNET_FILE
        sface = self.model_dir / SFACE_FILE
        missing = [str(p) for p in (yunet, sface) if not p.exists()]
        if missing:
            self._load_error = f"Model weights not found: {missing}. Run scripts/download_models.py"
            return False
        try:
            import cv2

            self._detector = cv2.FaceDetectorYN.create(
                str(yunet), "", (320, 320), score_threshold=float(settings.ai_min_face_confidence)
            )
            self._recognizer = cv2.FaceRecognizerSF.create(str(sface), "")
            self._load_error = ""
            return True
        except Exception as exc:  # pragma: no cover - depends on local OpenCV build
            self._load_error = f"Failed to load model weights: {exc}"
            self._detector = None
            self._recognizer = None
            return False

    def available(self) -> bool:
        return self._try_load()

    def availability_detail(self) -> str:
        return self._load_error or ""

    def info(self) -> FaceAIBackendInfo:
        return FaceAIBackendInfo(
            name=settings.ai_model_name,
            version="sface-2021dec/yunet-2023mar",
            embedding_dim=128,
            license=MODEL_LICENSE,
            model_files=[YUNET_FILE, SFACE_FILE],
            extra={"similarity_metric": "cosine"},
        )

    # -- inference ----------------------------------------------------------
    def detect_faces(self, image_bgr: np.ndarray) -> List[DetectedFace]:
        if not self._try_load():
            raise RuntimeError(self._load_error or "model unavailable")
        import cv2

        h, w = image_bgr.shape[:2]
        self._detector.setInputSize((w, h))
        _, faces = self._detector.detect(image_bgr)
        results: List[DetectedFace] = []
        if faces is None:
            return results
        for row in faces:
            x, y, fw, fh = row[:4]
            score = float(row[-1])
            x0, y0 = max(0, int(x)), max(0, int(y))
            x1, y1 = min(w, int(x + fw)), min(h, int(y + fh))
            if x1 <= x0 or y1 <= y0:
                continue
            landmarks = row[4:14].reshape(5, 2) if len(row) >= 14 else None
            results.append(
                DetectedFace(x=x0, y=y0, w=x1 - x0, h=y1 - y0, confidence=score, landmarks=landmarks)
            )
        results.sort(key=lambda f: f.confidence, reverse=True)
        return results

    def embed(self, image_bgr: np.ndarray, face: DetectedFace) -> np.ndarray:
        if not self._try_load():
            raise RuntimeError(self._load_error or "model unavailable")
        import cv2

        aligned = self._recognizer.alignCrop(image_bgr, self._to_face_row(face))
        feat = self._recognizer.feature(aligned)
        vec = np.asarray(feat, dtype=np.float32).reshape(-1)
        norm = float(np.linalg.norm(vec))
        if norm == 0.0:
            raise ValueError("degenerate embedding")
        return vec / norm

    @staticmethod
    def _to_face_row(face: DetectedFace) -> np.ndarray:
        """YuNet expects a 15-element row: x,y,w,h,score + 10 landmark values."""
        row = np.zeros(15, dtype=np.float32)
        row[0:4] = [face.x, face.y, face.w, face.h]
        row[4] = face.confidence
        if face.landmarks is not None:
            row[5:15] = face.landmarks.reshape(-1)
        return row
