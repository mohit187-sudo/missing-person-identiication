"""AI face matching: photo search, jobs, potential matches, investigator review."""
from __future__ import annotations

import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.api.deps import RequireAnyAuthed, RequireBiometric, paginate, pagination
from backend.app.core.config import settings
from backend.app.core.exceptions import AIModelUnavailableError, NotFoundError, ValidationAppError
from backend.app.db.session import get_db
from backend.app.models import (
    FaceEmbedding,
    InvestigatorReview,
    MatchingJob,
    MissingPersonCase,
    PersonPhoto,
    PotentialMatch,
    User,
    utcnow,
)
from backend.app.models.matching import MATCH_PENDING, SOURCE_PHOTO_SEARCH
from backend.app.schemas.matching import (
    MatchDetailOut,
    MatchOut,
    MatchingJobOut,
    ReviewOut,
    ReviewRequest,
    SearchResult,
)
from backend.app.services.audit import log_action
from backend.app.services.notifications import notify_role

router = APIRouter(tags=["ai-matching"])


def _match_out(m: PotentialMatch, db: Session) -> dict:
    case = db.get(MissingPersonCase, m.candidate_case_id)
    try:
        quality = json.loads(m.image_quality or "{}")
    except json.JSONDecodeError:
        quality = {}
    return MatchOut(
        id=m.id,
        source_type=m.source_type,
        candidate_case_id=m.candidate_case_id,
        candidate_case_number=case.case_number if case else "",
        candidate_name=case.full_name if case else None,
        query_photo_id=m.query_photo_id,
        detected_face_id=m.detected_face_id,
        similarity_score=m.similarity_score,
        threshold_used=m.threshold_used,
        model_name=m.model_name,
        model_version=m.model_version,
        image_quality=quality,
        status=m.status,
        source_timestamp_seconds=m.source_timestamp_seconds,
        processing_timestamp=m.processing_timestamp,
        is_demo=bool(m.is_demo),
        created_at=m.created_at,
    ).model_dump()


@router.post("/matching/search", response_model=SearchResult)
async def face_search(
    request: Request,
    file: UploadFile = File(...),
    threshold: Optional[float] = Form(None),
    top_k: int = Form(20),
    user: User = RequireBiometric,
    db: Session = Depends(get_db),
):
    """Detect faces in an uploaded photograph and rank potential case matches.

    Returns candidates with similarity scores clearly labelled as technical
    similarity measures. Never identifies anyone automatically.
    """
    from backend.app.ai.registry import require_backend
    from backend.app.ai.service import (
        FaceMatchingService,
        load_image_bgr,
        pack_embedding,
        unpack_embedding,
    )
    from backend.app.services.storage import validate_and_save_photo

    backend = require_backend()  # 503 + setup instructions when unavailable
    service = FaceMatchingService(backend)

    data = await file.read()
    # Validate + store the query image privately for auditability.
    rel, sha, size, meta = validate_and_save_photo(data, file.filename or "query.jpg")

    job = MatchingJob(
        status="running",
        started_at=utcnow(),
        created_by=user.id,
        threshold_used=threshold if threshold is not None else settings.ai_match_threshold,
        model_name=backend.info().name,
        model_version=backend.info().version,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        img = load_image_bgr(data)
        observations = service.analyze_photo(img)
        faces_detected = len(observations)
        usable = [o for o in observations if o.embedding is not None]

        if not observations:
            raise ValidationAppError(
                "No face detected in the uploaded image. Provide a clear photograph containing a face."
            )
        if not usable:
            best = observations[0]
            raise ValidationAppError(
                "Detected face(s) failed quality checks.",
                {"reason": best.quality.rejection_reason},
            )

        query_photo = PersonPhoto(
            case_id=_internal_case_id(db),
            file_path=rel,
            original_filename=(file.filename or "query.jpg")[:255],
            content_type=meta["content_type"],
            file_size=size,
            sha256=sha,
            uploaded_by=user.id,
            width=meta.get("width"),
            height=meta.get("height"),
        )
        db.add(query_photo)
        db.flush()

        thr = threshold if threshold is not None else settings.ai_match_threshold
        gallery = []
        for e in db.scalars(select(FaceEmbedding).where(FaceEmbedding.case_id.isnot(None))).all():
            try:
                vec = unpack_embedding(e.embedding, e.dim)
            except Exception:
                continue
            gallery.append((e.case_id, e.photo_id, e.id, vec, {"quality_score": e.quality_score}))

        candidates = service.rank_candidates(
            usable[0].embedding, gallery, threshold=thr, top_k=max(1, min(top_k, 50))
        )

        matches = []
        for c in candidates:
            case = db.get(MissingPersonCase, c.case_id)
            pm = PotentialMatch(
                source_type=SOURCE_PHOTO_SEARCH,
                query_photo_id=query_photo.id,
                matching_job_id=job.id,
                candidate_case_id=c.case_id,
                reference_photo_id=c.reference_photo_id,
                reference_embedding_id=c.reference_embedding_id,
                similarity_score=c.similarity_score,
                threshold_used=thr,
                model_name=backend.info().name,
                model_version=backend.info().version,
                image_quality=json.dumps(
                    {
                        **c.image_quality,
                        "query_blur_score": usable[0].quality.blur_score,
                        "query_quality_score": usable[0].quality.quality_score,
                    }
                ),
                processing_timestamp=utcnow(),
                is_demo=1 if (case and case.is_demo) else 0,
            )
            db.add(pm)
            db.flush()
            matches.append(_match_out(pm, db))

        job.status = "completed"
        job.progress = 1.0
        job.finished_at = utcnow()
        job.candidates_returned = len(matches)
        db.commit()

        log_action(
            db,
            action="matching.search",
            user_id=user.id,
            resource_type="matching_job",
            resource_id=str(job.id),
            detail={"faces_detected": faces_detected, "candidates": len(matches)},
            request=request,
        )
        if matches:
            notify_role(
                db,
                role_name="investigator",
                type="match_review",
                title="Potential matches require review",
                body=f"{len(matches)} potential match candidate(s) need investigator review.",
                link="/matches",
                exclude_user_id=user.id,
            )

        quality_summary = {
            "faces_detected": faces_detected,
            "usable_faces": len(usable),
            "query_quality": {
                "blur_score": usable[0].quality.blur_score,
                "brightness": usable[0].quality.brightness,
                "face_size_px": usable[0].quality.face_size_px,
                "quality_score": usable[0].quality.quality_score,
            },
        }
        return SearchResult(
            job_id=job.id,
            status=job.status,
            model_name=job.model_name,
            model_version=job.model_version,
            threshold_used=thr,
            matches=[MatchOut(**m) for m in matches],
            faces_detected=faces_detected,
            quality=quality_summary,
        )
    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)[:2000]
        job.finished_at = utcnow()
        db.commit()
        raise


def _internal_case_id(db: Session) -> uuid.UUID:
    from backend.app.video.processor import _any_case_id

    return _any_case_id(db)


@router.get("/matching/jobs/{job_id}", response_model=MatchingJobOut)
def get_matching_job(job_id: uuid.UUID, user: User = RequireBiometric, db: Session = Depends(get_db)):
    job = db.get(MatchingJob, job_id)
    if job is None:
        raise NotFoundError("Matching job", job_id)
    return MatchingJobOut.model_validate(job)


@router.get("/matching/ai-status")
def matching_ai_status(user: User = RequireAnyAuthed):
    """Current AI engine status with setup instructions when unavailable."""
    from backend.app.ai.registry import ai_status

    return ai_status().model_dump()


@router.get("/matches")
def list_matches(
    status: Optional[str] = Query(None),
    case_id: Optional[uuid.UUID] = Query(None),
    min_score: Optional[float] = Query(None, ge=0.0, le=1.0),
    include_demo: bool = Query(True),
    paging: tuple = Depends(pagination),
    user: User = RequireBiometric,
    db: Session = Depends(get_db),
):
    page, page_size = paging
    stmt = select(PotentialMatch)
    if status:
        stmt = stmt.where(PotentialMatch.status == status)
    if case_id:
        stmt = stmt.where(PotentialMatch.candidate_case_id == case_id)
    if min_score is not None:
        stmt = stmt.where(PotentialMatch.similarity_score >= min_score)
    if not include_demo:
        stmt = stmt.where(PotentialMatch.is_demo == 0)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(PotentialMatch.similarity_score.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return paginate([_match_out(m, db) for m in rows], total, page, page_size)


@router.get("/matches/{match_id}", response_model=MatchDetailOut)
def get_match(match_id: uuid.UUID, user: User = RequireBiometric, db: Session = Depends(get_db)):
    m = db.get(PotentialMatch, match_id)
    if m is None:
        raise NotFoundError("Potential match", match_id)
    out = MatchDetailOut(**_match_out(m, db))
    out.reviews = [
        ReviewOut(
            id=r.id,
            match_id=r.match_id,
            reviewer_id=r.reviewer_id,
            reviewer_name=(db.get(User, r.reviewer_id).full_name if r.reviewer_id else ""),
            decision=r.decision,
            notes=r.notes,
            created_at=r.created_at,
        )
        for r in sorted(m.reviews, key=lambda x: x.created_at)
    ]
    return out


@router.post("/matches/{match_id}/review")
def review_match(
    match_id: uuid.UUID,
    payload: ReviewRequest,
    request: Request,
    user: User = RequireBiometric,
    db: Session = Depends(get_db),
):
    """Human verification step — required before any case status change."""
    m = db.get(PotentialMatch, match_id)
    if m is None:
        raise NotFoundError("Potential match", match_id)

    if payload.decision == "confirmed_for_investigation" and len(payload.notes.strip()) < 10:
        raise ValidationAppError(
            "Confirming a match requires investigator notes (min 10 chars) documenting "
            "the verification and planned corroborating steps."
        )

    review = InvestigatorReview(
        match_id=m.id,
        reviewer_id=user.id,
        decision=payload.decision,
        notes=payload.notes,
    )
    db.add(review)
    m.status = payload.decision
    db.commit()

    log_action(
        db,
        action="match.reviewed",
        user_id=user.id,
        resource_type="potential_match",
        resource_id=str(m.id),
        detail={"decision": payload.decision},
        request=request,
    )
    notify_role(
        db,
        role_name="administrator",
        type="match_review",
        title="Potential match reviewed",
        body=f"A potential match was marked '{payload.decision.replace('_', ' ')}'.",
        link=f"/matches?id={m.id}",
        exclude_user_id=user.id,
    )

    case = db.get(MissingPersonCase, m.candidate_case_id)
    return {
        "message": "Review recorded. Case status is never changed automatically — use the case page with a verification note if appropriate.",
        "match": _match_out(m, db),
        "case_status": case.status if case else None,
    }


@router.get("/matches/{match_id}/photo")
def get_match_photo(
    match_id: uuid.UUID, user: User = RequireBiometric, db: Session = Depends(get_db)
):
    """Preview of the authorized case photo for a candidate match."""
    from fastapi.responses import FileResponse

    from backend.app.services.storage import absolute_path

    m = db.get(PotentialMatch, match_id)
    if m is None or not m.reference_photo_id:
        raise NotFoundError("Match photo", match_id)
    photo = db.get(PersonPhoto, m.reference_photo_id)
    if photo is None or photo.is_deleted:
        raise NotFoundError("Photo", m.reference_photo_id)
    path = absolute_path(photo.file_path)
    if not path.exists():
        raise NotFoundError("Photo file on disk")
    return FileResponse(path, media_type=photo.content_type)
