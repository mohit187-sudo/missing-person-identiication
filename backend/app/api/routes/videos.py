"""Authorized CCTV/video evidence upload, processing, status, reports, cancellation."""
from __future__ import annotations

import csv
import io
import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.api.deps import RequireAnyAuthed, RequireInvestigator, paginate, pagination
from backend.app.core.config import settings
from backend.app.core.exceptions import NotFoundError, ValidationAppError
from backend.app.db.session import get_db
from backend.app.models import (
    DetectedFace,
    MissingPersonCase,
    PotentialMatch,
    User,
    VideoEvidence,
    VideoProcessingJob,
    utcnow,
)
from backend.app.models.matching import SOURCE_VIDEO_FRAME
from backend.app.schemas.evidence import ProcessRequest, VideoOut
from backend.app.schemas.matching import DetectedFaceOut, VideoJobOut
from backend.app.services.audit import log_action
from backend.app.tasks import runner
from backend.app.video.processor import probe_video, request_cancel, run_video_job

router = APIRouter(prefix="/videos", tags=["video-evidence"])

ALLOWED_PROCESSING_STATES = ("queued", "running", "completed", "failed", "cancelled")


def _video_out(v: VideoEvidence, db: Session) -> dict:
    out = VideoOut.model_validate(v).model_dump()
    latest = db.scalars(
        select(VideoProcessingJob)
        .where(VideoProcessingJob.video_id == v.id)
        .order_by(VideoProcessingJob.created_at.desc())
    ).first()
    out["latest_job_status"] = latest.status if latest else None
    out["latest_job_progress"] = latest.progress if latest else None
    return out


def _job_out(job: VideoProcessingJob) -> VideoJobOut:
    return VideoJobOut.model_validate(job)


@router.post("", status_code=201)
async def upload_video(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(...),
    description: str = Form(""),
    case_id: Optional[uuid.UUID] = Form(None),
    authorization_reference: str = Form(""),
    lawfully_obtained: bool = Form(False),
    user: User = RequireInvestigator,
    db: Session = Depends(get_db),
):
    """Upload authorized, lawfully obtained footage for case-related analysis."""
    from backend.app.services.storage import validate_and_save_video

    if not lawfully_obtained:
        raise ValidationAppError(
            "You must confirm the footage was lawfully obtained and is authorized "
            "for case-related analysis (set lawfully_obtained=true)."
        )
    if case_id is not None:
        case = db.get(MissingPersonCase, case_id)
        if case is None or case.is_deleted:
            raise NotFoundError("Case", case_id)

    data = await file.read()
    rel, sha, size, content_type = validate_and_save_video(data, file.filename or "video.mp4")

    video = VideoEvidence(
        title=title[:255],
        description=description[:8000],
        case_id=case_id,
        file_path=rel,
        original_filename=(file.filename or "video.mp4")[:255],
        content_type=content_type,
        file_size=size,
        sha256=sha,
        authorization_reference=authorization_reference[:255],
        lawfully_obtained=True,
        uploaded_by=user.id,
    )

    # Probe metadata; corrupt files are rejected with a clear error.
    from backend.app.services.storage import absolute_path

    tmp_path = absolute_path(rel)
    try:
        meta = probe_video(tmp_path)
    except ValueError as exc:
        from backend.app.services.storage import delete_file_quiet

        delete_file_quiet(rel)
        raise ValidationAppError(str(exc))
    video.duration_seconds = meta["duration_seconds"]
    video.width = meta["width"]
    video.height = meta["height"]
    video.fps = meta["fps"]

    db.add(video)
    db.commit()
    db.refresh(video)
    log_action(
        db,
        action="video.uploaded",
        user_id=user.id,
        resource_type="video",
        resource_id=str(video.id),
        detail={"filename": video.original_filename, "duration": meta["duration_seconds"]},
        request=request,
    )
    return _video_out(video, db)


@router.get("")
def list_videos(
    paging: tuple = Depends(pagination),
    user: User = RequireAnyAuthed,
    db: Session = Depends(get_db),
):
    page, page_size = paging
    stmt = select(VideoEvidence).where(VideoEvidence.is_deleted.is_(False))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(VideoEvidence.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return paginate([_video_out(v, db) for v in rows], total, page, page_size)


@router.get("/{video_id}", response_model=VideoOut)
def get_video(video_id: uuid.UUID, user: User = RequireAnyAuthed, db: Session = Depends(get_db)):
    v = db.get(VideoEvidence, video_id)
    if v is None or v.is_deleted:
        raise NotFoundError("Video", video_id)
    return _video_out(v, db)


@router.post("/{video_id}/process", status_code=202)
def process_video(
    video_id: uuid.UUID,
    payload: ProcessRequest,
    request: Request,
    user: User = RequireInvestigator,
    db: Session = Depends(get_db),
):
    v = db.get(VideoEvidence, video_id)
    if v is None or v.is_deleted:
        raise NotFoundError("Video", video_id)

    active = db.scalar(
        select(VideoProcessingJob).where(
            VideoProcessingJob.video_id == v.id,
            VideoProcessingJob.status.in_(("queued", "running")),
        )
    )
    if active:
        raise ValidationAppError(
            "A processing job is already running for this video.",
            {"job_id": str(active.id)},
        )

    job = VideoProcessingJob(
        video_id=v.id,
        status="queued",
        sampling_interval_seconds=payload.sampling_interval_seconds,
        created_by=user.id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    runner.submit(str(job.id), lambda: run_video_job(str(job.id)))
    log_action(
        db,
        action="video.process_started",
        user_id=user.id,
        resource_type="video_job",
        resource_id=str(job.id),
        detail={"video_id": str(v.id)},
        request=request,
    )
    return _job_out(job)


@router.get("/{video_id}/status")
def video_status(
    video_id: uuid.UUID, user: User = RequireAnyAuthed, db: Session = Depends(get_db)
):
    v = db.get(VideoEvidence, video_id)
    if v is None or v.is_deleted:
        raise NotFoundError("Video", video_id)
    jobs = db.scalars(
        select(VideoProcessingJob)
        .where(VideoProcessingJob.video_id == v.id)
        .order_by(VideoProcessingJob.created_at.desc())
    ).all()
    return {
        "video_id": v.id,
        "jobs": [_job_out(j).model_dump() for j in jobs],
        "latest": _job_out(jobs[0]).model_dump() if jobs else None,
    }


@router.get("/{video_id}/report")
def video_report(
    video_id: uuid.UUID,
    format: str = Query("json", pattern="^(json|csv|pdf)$"),
    user: User = RequireAnyAuthed,
    db: Session = Depends(get_db),
):
    """Review report: video ID, timestamp, candidate case ID, similarity, model."""
    v = db.get(VideoEvidence, video_id)
    if v is None or v.is_deleted:
        raise NotFoundError("Video", video_id)

    matches = db.scalars(
        select(PotentialMatch)
        .join(VideoProcessingJob, PotentialMatch.video_job_id == VideoProcessingJob.id)
        .where(VideoProcessingJob.video_id == v.id)
        .order_by(PotentialMatch.similarity_score.desc())
    ).all()

    rows = []
    for m in matches:
        case = db.get(MissingPersonCase, m.candidate_case_id)
        det = db.get(DetectedFace, m.detected_face_id) if m.detected_face_id else None
        rows.append(
            {
                "video_id": str(v.id),
                "video_title": v.title,
                "timestamp_seconds": m.source_timestamp_seconds,
                "frame_index": det.frame_index if det else None,
                "candidate_case_id": str(m.candidate_case_id),
                "candidate_case_number": case.case_number if case else "",
                "similarity_score": m.similarity_score,
                "threshold_used": m.threshold_used,
                "model_name": m.model_name,
                "model_version": m.model_version,
                "review_status": m.status,
                "is_demo": bool(m.is_demo),
                "processing_timestamp": m.processing_timestamp.isoformat(),
            }
        )

    disclaimer = (
        "Similarity scores are technical measurements, NOT identification "
        "probabilities. Human verification and independent corroboration are "
        "required. Never present these candidates as identifications."
    )

    if format == "csv":
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()) + ["disclaimer"] if rows else ["disclaimer"])
        writer.writeheader()
        for r in rows:
            writer.writerow({**r, "disclaimer": disclaimer})
        if not rows:
            writer.writerow({"disclaimer": disclaimer})
        buf.seek(0)
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="video_report_{v.id}.csv"'},
        )

    if format == "pdf":
        from backend.app.services.pdf import build_video_report_pdf

        pdf_bytes = build_video_report_pdf(v, rows, disclaimer)
        return StreamingResponse(
            iter([pdf_bytes]),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="video_report_{v.id}.pdf"'},
        )

    return {
        "video_id": str(v.id),
        "video_title": v.title,
        "generated_at": utcnow().isoformat(),
        "disclaimer": disclaimer,
        "rows": rows,
    }


@router.post("/jobs/{job_id}/cancel")
def cancel_job(
    job_id: uuid.UUID,
    request: Request,
    user: User = RequireInvestigator,
    db: Session = Depends(get_db),
):
    job = db.get(VideoProcessingJob, job_id)
    if job is None:
        raise NotFoundError("Processing job", job_id)
    if job.status not in ("queued", "running"):
        raise ValidationAppError(f"Job cannot be cancelled (status: {job.status}).")
    request_cancel(db, job.id)
    log_action(
        db,
        action="video.process_cancelled",
        user_id=user.id,
        resource_type="video_job",
        resource_id=str(job.id),
        request=request,
    )
    return {"message": "Cancellation requested. The job stops at the next frame boundary."}


@router.get("/{video_id}/faces")
def list_detected_faces(
    video_id: uuid.UUID,
    eligible_only: bool = Query(False),
    user: User = RequireInvestigator,
    db: Session = Depends(get_db),
):
    v = db.get(VideoEvidence, video_id)
    if v is None or v.is_deleted:
        raise NotFoundError("Video", video_id)
    stmt = select(DetectedFace).where(DetectedFace.video_id == v.id)
    if eligible_only:
        stmt = stmt.where(DetectedFace.eligible_for_matching.is_(True))
    rows = db.scalars(stmt.order_by(DetectedFace.timestamp_seconds)).limit(500).all()
    return {
        "items": [
            DetectedFaceOut(
                id=r.id,
                frame_index=r.frame_index,
                timestamp_seconds=r.timestamp_seconds,
                bbox=[r.bbox_x, r.bbox_y, r.bbox_w, r.bbox_h],
                face_confidence=r.face_confidence,
                blur_score=r.blur_score,
                quality_score=r.quality_score,
                eligible_for_matching=r.eligible_for_matching,
                rejection_reason=r.rejection_reason,
                thumbnail_url=f"/api/v1/videos/{v.id}/faces/{r.id}/thumbnail",
            ).model_dump()
            for r in rows
        ],
        "total": len(rows),
    }


@router.get("/{video_id}/faces/{face_id}/thumbnail")
def face_thumbnail(
    video_id: uuid.UUID,
    face_id: uuid.UUID,
    user: User = RequireInvestigator,
    db: Session = Depends(get_db),
):
    from fastapi.responses import FileResponse

    from backend.app.services.storage import absolute_path

    det = db.get(DetectedFace, face_id)
    if det is None or det.video_id != video_id or not det.thumbnail_path:
        raise NotFoundError("Detection thumbnail", face_id)
    path = absolute_path(det.thumbnail_path)
    if not path.exists():
        raise NotFoundError("Thumbnail on disk")
    return FileResponse(path, media_type="image/jpeg")
