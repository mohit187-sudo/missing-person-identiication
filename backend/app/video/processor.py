"""CCTV video processing pipeline (authorized, lawfully obtained footage only).

Pipeline: probe -> sample frames -> detect faces -> quality gate -> embed ->
compare against authorized case records -> store detections + potential matches.

Strictly bounded to approved case-related footage. No live-feed connection, no
covert tracking, no cross-camera identity tracking is implemented or allowed.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from backend.app.ai.quality import assess_face_quality
from backend.app.ai.registry import get_backend
from backend.app.ai.service import FaceMatchingService, pack_embedding
from backend.app.core.config import settings
from backend.app.db.session import SessionLocal
from backend.app.models import (
    DetectedFace,
    FaceEmbedding,
    MissingPersonCase,
    PotentialMatch,
    VideoProcessingJob,
    VideoEvidence,
    new_uuid,
    utcnow,
)
from backend.app.models.matching import SOURCE_VIDEO_FRAME
from backend.app.services import notifications as notify_service
from backend.app.services.storage import absolute_path

logger = logging.getLogger("mpis.video")

MAX_FRAME_DIM = 1280  # downscale large frames for speed
THUMB_MAX = 160


def probe_video(path: Path) -> dict:
    """Read basic metadata; raises ValueError for corrupt/unsupported files."""
    import cv2

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError("Corrupt or unsupported video file (cannot open).")
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    finally:
        cap.release()

    if width <= 0 or height <= 0 or frame_count <= 0:
        raise ValueError("Corrupt video: no readable frames.")
    duration = frame_count / fps if fps > 0 else 0.0
    if duration <= 0:
        raise ValueError("Corrupt video: zero duration.")
    if duration > 6 * 3600:
        raise ValueError("Video exceeds the maximum supported duration of 6 hours.")
    return {
        "fps": fps,
        "frame_count": frame_count,
        "width": width,
        "height": height,
        "duration_seconds": round(duration, 3),
    }


def request_cancel(db: Session, job_id) -> None:
    job = db.get(VideoProcessingJob, job_id)
    if job and job.status in ("queued", "running"):
        job.cancel_requested = True
        db.commit()


def run_video_job(job_id: str) -> None:
    """Entry point executed by the background runner."""
    db = SessionLocal()
    try:
        _run_video_job(db, job_id)
    except Exception as exc:
        logger.exception("video job %s failed", job_id)
        job = db.get(VideoProcessingJob, uuid_of(job_id))
        if job:
            job.status = "failed"
            job.error_message = str(exc)[:2000]
            job.finished_at = utcnow()
            db.commit()
            _notify_job_end(db, job)
    finally:
        db.close()


def uuid_of(job_id: str):
    import uuid as _uuid

    return _uuid.UUID(job_id)


def _notify_job_end(db: Session, job: VideoProcessingJob) -> None:
    if job.created_by:
        status_word = job.status.replace("_", " ")
        notify_service.notify(
            db,
            user_id=job.created_by,
            type="job_completed",
            title=f"Video processing {status_word}",
            body=f"Job for video {job.video_id} finished with status: {job.status}.",
            link=f"/videos/{job.video_id}",
        )


def _run_video_job(db: Session, job_id: str) -> None:
    job = db.get(VideoProcessingJob, uuid_of(job_id))
    if job is None:
        return
    video = db.get(VideoEvidence, job.video_id)
    if video is None:
        job.status = "failed"
        job.error_message = "Video record missing."
        job.finished_at = utcnow()
        db.commit()
        return

    job.status = "running"
    job.started_at = utcnow()
    db.commit()

    # Check model availability up-front so the failure is explicit.
    backend = get_backend()
    if not backend.available():
        job.status = "failed"
        job.error_message = (
            "AI model unavailable: "
            + (backend.availability_detail() or "no compatible model installed")
            + " — run scripts/download_models.py. No simulated matches were generated."
        )
        job.finished_at = utcnow()
        db.commit()
        _notify_job_end(db, job)
        return

    service = FaceMatchingService(backend)
    info = backend.info()
    job.model_name = info.name
    job.model_version = info.version
    job.threshold_used = settings.ai_match_threshold
    db.commit()

    import cv2

    video_path = absolute_path(video.file_path)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        job.status = "failed"
        job.error_message = "Corrupt or unsupported video file (cannot open)."
        job.finished_at = utcnow()
        db.commit()
        _notify_job_end(db, job)
        return

    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0) or 25.0
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        step_frames = max(1, int(round(fps * job.sampling_interval_seconds)))

        # Gallery: embeddings of non-demo and demo cases both allowed (demo rows
        # are flagged on the resulting matches so the UI can label them).
        gallery = _load_gallery(db)

        frame_idx = 0
        sampled = 0
        faces_total = 0
        matches_total = 0
        thumb_dir = settings.storage_path / "artifacts" / str(job.id)
        thumb_dir.mkdir(parents=True, exist_ok=True)

        while True:
            if job.cancel_requested:
                db.refresh(job)
                if job.cancel_requested:
                    job.status = "cancelled"
                    job.finished_at = utcnow()
                    db.commit()
                    _notify_job_end(db, job)
                    return

            ok, frame = cap.read()
            if not ok:
                break
            if frame_idx % step_frames == 0:
                sampled += 1
                ts = frame_idx / fps if fps else 0.0
                small = _downscale(frame)
                try:
                    faces = backend.detect_faces(small)
                except Exception as exc:
                    logger.warning("detection failed at frame %s: %s", frame_idx, exc)
                    faces = []

                for face in faces:
                    faces_total += 1
                    gray = cv2.cvtColor(
                        small[max(0, face.y): face.y + face.h, max(0, face.x): face.x + face.w],
                        cv2.COLOR_BGR2GRAY,
                    )
                    if gray.size == 0:
                        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
                    quality = assess_face_quality(gray, max(face.w, face.h), face.confidence)

                    det = DetectedFace(
                        job_id=job.id,
                        video_id=video.id,
                        frame_index=frame_idx,
                        timestamp_seconds=round(ts, 3),
                        bbox_x=face.x,
                        bbox_y=face.y,
                        bbox_w=face.w,
                        bbox_h=face.h,
                        face_confidence=face.confidence,
                        blur_score=quality.blur_score,
                        quality_score=quality.quality_score,
                        eligible_for_matching=quality.ok,
                        rejection_reason=quality.rejection_reason[:255],
                    )
                    # Save a small thumbnail of the detection for human review.
                    thumb_path = thumb_dir / f"{det.id}.jpg"
                    crop = small[max(0, face.y): face.y + face.h, max(0, face.x): face.x + face.w]
                    if crop.size:
                        cv2.imwrite(str(thumb_path), _downscale(crop, THUMB_MAX))
                        det.thumbnail_path = str(thumb_path.relative_to(settings.storage_path)).replace("\\", "/")
                    db.add(det)
                    db.flush()

                    if not quality.ok:
                        continue

                    try:
                        emb_vec = backend.embed(small, face)
                    except Exception as exc:
                        logger.warning("embedding failed at frame %s: %s", frame_idx, exc)
                        continue

                    emb = FaceEmbedding(
                        photo_id=_ensure_placeholder_photo(db, video.id),
                        case_id=None,
                        model_name=info.name,
                        model_version=info.version,
                        dim=int(emb_vec.size),
                        embedding=pack_embedding(emb_vec),
                        face_confidence=face.confidence,
                        face_bbox=json.dumps([face.x, face.y, face.w, face.h]),
                        quality_score=quality.quality_score,
                    )
                    db.add(emb)
                    db.flush()
                    det.embedding_id = emb.id

                    from backend.app.ai.service import unpack_embedding

                    for case_id, photo_id, emb_id, vec, qmeta in gallery:
                        score = backend.similarity(emb_vec, vec)
                        if score >= settings.ai_match_threshold:
                            matches_total += 1
                            case = db.get(MissingPersonCase, case_id)
                            db.add(
                                PotentialMatch(
                                    source_type=SOURCE_VIDEO_FRAME,
                                    detected_face_id=det.id,
                                    video_job_id=job.id,
                                    candidate_case_id=case_id,
                                    reference_photo_id=photo_id,
                                    reference_embedding_id=emb_id,
                                    similarity_score=round(score, 6),
                                    threshold_used=settings.ai_match_threshold,
                                    model_name=info.name,
                                    model_version=info.version,
                                    image_quality=json.dumps(
                                        {
                                            "blur_score": quality.blur_score,
                                            "quality_score": quality.quality_score,
                                            "face_confidence": face.confidence,
                                        }
                                    ),
                                    source_timestamp_seconds=round(ts, 3),
                                    processing_timestamp=utcnow(),
                                    is_demo=1 if (case and case.is_demo) else 0,
                                )
                            )

                job.frames_sampled = sampled
                job.faces_detected = faces_total
                job.matches_found = matches_total
                if frame_count > 0:
                    job.progress = round(min(1.0, frame_idx / frame_count), 4)
                else:
                    job.progress = 0.5
                db.commit()

            frame_idx += 1

        job.status = "completed"
        job.progress = 1.0
        job.finished_at = utcnow()
        db.commit()
        _notify_job_end(db, job)
    finally:
        cap.release()


def _load_gallery(db: Session):
    """All stored reference embeddings as comparable numpy rows."""
    from backend.app.ai.service import unpack_embedding

    rows = db.query(FaceEmbedding).filter(FaceEmbedding.case_id.isnot(None)).all()
    gallery = []
    for e in rows:
        try:
            vec = unpack_embedding(e.embedding, e.dim)
        except Exception:
            continue
        gallery.append((e.case_id, e.photo_id, e.id, vec, {"quality_score": e.quality_score}))
    return gallery


def _ensure_placeholder_photo(db: Session, video_id) -> str:
    """Detected-face embeddings reference a synthetic 'video frame' photo row so
    the FK graph stays valid without inventing case photos."""
    import uuid as _uuid

    # Stable pseudo-photo id derived from the video id.
    from backend.app.models import PersonPhoto

    existing = (
        db.query(PersonPhoto)
        .filter(PersonPhoto.original_filename == f"__video_frames__/{video_id}")
        .first()
    )
    if existing:
        return existing.id
    photo = PersonPhoto(
        case_id=_any_case_id(db),
        file_path="artifacts/none",
        original_filename=f"__video_frames__/{video_id}",
        content_type="application/x-frame-metadata",
        file_size=0,
        sha256="-",
    )
    db.add(photo)
    db.flush()
    return photo.id


def _any_case_id(db: Session):
    """Video-frame embeddings are case-less; person_photos.case_id is NOT NULL,
    so attach placeholders to a dedicated internal archive case when present."""
    from backend.app.models import MissingPersonCase

    case = (
        db.query(MissingPersonCase)
        .filter(MissingPersonCase.case_number == "INTERNAL-FRAME-ARCHIVE")
        .first()
    )
    if case:
        return case.id
    case = MissingPersonCase(
        case_number="INTERNAL-FRAME-ARCHIVE",
        name_unknown=True,
        full_name=None,
        status="archived",
        is_demo=False,
        additional_notes="Internal archive holder for video-frame embeddings. Not an investigation case.",
    )
    db.add(case)
    db.flush()
    return case.id


def _downscale(frame, max_dim: int = MAX_FRAME_DIM):
    import cv2

    h, w = frame.shape[:2]
    scale = max_dim / max(h, w)
    if scale >= 1.0:
        return frame
    return cv2.resize(frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
