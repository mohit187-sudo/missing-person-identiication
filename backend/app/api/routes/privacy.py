"""Privacy & security settings: retention policies and correction requests."""
from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.deps import RequireAdmin, RequireAnyAuthed
from backend.app.core.exceptions import NotFoundError
from backend.app.db.session import get_db
from backend.app.models import CorrectionRequest, RetentionPolicy, User, utcnow
from backend.app.schemas.ops import (
    CorrectionRequestCreate,
    CorrectionRequestOut,
    RetentionPolicyOut,
    RetentionPolicyUpdate,
)
from backend.app.services.audit import log_action

router = APIRouter(prefix="/privacy", tags=["privacy"])

DEFAULT_POLICIES = [
    ("photos", 365, "delete", "Authorized case photographs"),
    ("videos", 180, "delete", "CCTV/video evidence files"),
    ("embeddings", 365, "delete", "Biometric face embeddings"),
    ("rejected_matches", 90, "delete", "Rejected potential-match candidates"),
    ("audit_logs", 730, "anonymize", "Security audit records"),
]


@router.get("/retention-policies")
def list_policies(
    user: User = RequireAnyAuthed, db: Session = Depends(get_db)
):
    rows = db.scalars(select(RetentionPolicy).order_by(RetentionPolicy.resource_type)).all()
    return [RetentionPolicyOut.model_validate(r).model_dump() for r in rows]


@router.put("/retention-policies/{resource_type}")
def update_policy(
    resource_type: str,
    payload: RetentionPolicyUpdate,
    request: Request,
    admin: User = RequireAdmin,
    db: Session = Depends(get_db),
):
    row = db.scalar(select(RetentionPolicy).where(RetentionPolicy.resource_type == resource_type))
    if row is None:
        raise NotFoundError("Retention policy", resource_type)
    row.retention_days = payload.retention_days
    row.action = payload.action
    row.is_active = payload.is_active
    row.description = payload.description
    db.commit()
    log_action(
        db,
        action="privacy.retention_updated",
        user_id=admin.id,
        resource_type="retention_policy",
        resource_id=resource_type,
        detail=payload.model_dump(),
        request=request,
    )
    return RetentionPolicyOut.model_validate(row).model_dump()


@router.post("/run-retention")
def run_retention(
    request: Request, admin: User = RequireAdmin, db: Session = Depends(get_db)
):
    """Secure-deletion pass driven by the active retention policies.

    Deletes expired private files and DB rows for soft-deleted/rejected data.
    """
    from backend.app.models import PersonPhoto, PotentialMatch
    from backend.app.models.matching import MATCH_REJECTED
    from backend.app.services.storage import delete_file_quiet

    now = utcnow()
    report = {"photos_deleted": 0, "videos_deleted": 0, "rejected_matches_purged": 0}

    photo_policy = db.scalar(
        select(RetentionPolicy).where(RetentionPolicy.resource_type == "photos")
    )
    if photo_policy and photo_policy.is_active:
        cutoff = now - timedelta(days=photo_policy.retention_days)
        rows = db.scalars(
            select(PersonPhoto).where(PersonPhoto.is_deleted.is_(True), PersonPhoto.deleted_at < cutoff)
        ).all()
        for p in rows:
            delete_file_quiet(p.file_path)
            db.delete(p)
            report["photos_deleted"] += 1

    match_policy = db.scalar(
        select(RetentionPolicy).where(RetentionPolicy.resource_type == "rejected_matches")
    )
    if match_policy and match_policy.is_active:
        cutoff = now - timedelta(days=match_policy.retention_days)
        rows = db.scalars(
            select(PotentialMatch).where(
                PotentialMatch.status == MATCH_REJECTED, PotentialMatch.updated_at < cutoff
            )
        ).all()
        for m in rows:
            db.delete(m)
            report["rejected_matches_purged"] += 1

    db.commit()
    log_action(
        db,
        action="privacy.retention_run",
        user_id=admin.id,
        detail=report,
        request=request,
    )
    return {"message": "Retention pass complete.", "report": report}


@router.post("/correction-requests", status_code=201)
def create_correction_request(
    payload: CorrectionRequestCreate,
    request: Request,
    user: User = RequireAnyAuthed,
    db: Session = Depends(get_db),
):
    """Documented process for correcting mistaken matches / data requests."""
    row = CorrectionRequest(
        requester_id=user.id,
        subject_reference=payload.subject_reference,
        request_type=payload.request_type,
        description=payload.description,
    )
    db.add(row)
    db.commit()
    log_action(
        db,
        action="privacy.correction_requested",
        user_id=user.id,
        resource_type="correction_request",
        resource_id=str(row.id),
        request=request,
    )
    return CorrectionRequestOut.model_validate(row).model_dump()


@router.get("/correction-requests")
def list_correction_requests(
    admin: User = RequireAdmin, db: Session = Depends(get_db)
):
    rows = db.scalars(
        select(CorrectionRequest).order_by(CorrectionRequest.created_at.desc())
    ).all()
    return [CorrectionRequestOut.model_validate(r).model_dump() for r in rows]


@router.patch("/correction-requests/{request_id}")
def resolve_correction_request(
    request_id: uuid.UUID,
    status: str = "resolved",
    resolution_note: str = "",
    admin: User = RequireAdmin,
    db: Session = Depends(get_db),
):
    row = db.get(CorrectionRequest, request_id)
    if row is None:
        raise NotFoundError("Correction request", request_id)
    row.status = status
    row.resolution_note = resolution_note
    db.commit()
    return CorrectionRequestOut.model_validate(row).model_dump()
