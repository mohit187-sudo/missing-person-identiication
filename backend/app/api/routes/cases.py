"""Missing-person case management: CRUD, search, photos, status history."""
from __future__ import annotations

import io
import json
import uuid
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from backend.app.api.deps import (
    RequireAdmin,
    RequireAnyAuthed,
    RequireInvestigator,
    get_current_user,
    paginate,
    pagination,
)
from backend.app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationAppError
from backend.app.db.session import get_db
from backend.app.models import (
    CASE_STATUS_ARCHIVED,
    ALL_CASE_STATUSES,
    CaseStatusHistory,
    MissingPersonCase,
    PersonPhoto,
    User,
    utcnow,
)
from backend.app.schemas.case import (
    CaseCreate,
    CaseListItem,
    CaseOut,
    CaseUpdate,
    DuplicateWarning,
    PhotoOut,
)
from backend.app.services.audit import log_action
from backend.app.services.storage import absolute_path, validate_and_save_photo

router = APIRouter(prefix="/cases", tags=["cases"])


def _get_case(db: Session, case_id: uuid.UUID) -> MissingPersonCase:
    case = db.get(MissingPersonCase, case_id)
    if case is None or case.is_deleted:
        raise NotFoundError("Case", case_id)
    return case


def _case_to_out(case: MissingPersonCase) -> dict:
    photos = []
    for p in sorted(case.photos, key=lambda x: x.created_at):
        if p.is_deleted:
            continue
        photos.append(
            PhotoOut(
                id=p.id,
                case_id=p.case_id,
                original_filename=p.original_filename,
                content_type=p.content_type,
                file_size=p.file_size,
                is_primary=p.is_primary,
                quality_score=p.quality_score,
                blur_score=p.blur_score,
                width=p.width,
                height=p.height,
                embedding_count=len(p.embeddings),
                created_at=p.created_at,
            )
        )
    history = sorted(case.status_history, key=lambda h: h.created_at)
    out = CaseOut.model_validate(case)
    out.photos = photos
    out.status_history = [h for h in history]  # pydantic validates attrs
    return out.model_dump()


@router.post("", status_code=201)
def create_case(
    payload: CaseCreate,
    request: Request,
    user: User = RequireInvestigator,
    db: Session = Depends(get_db),
):
    # Duplicate warning: same/similar name + last-seen date already registered.
    if payload.full_name and not payload.acknowledge_duplicate_warning:
        q = select(MissingPersonCase).where(
            MissingPersonCase.is_deleted.is_(False),
            func.lower(MissingPersonCase.full_name) == payload.full_name.strip().lower(),
        )
        if payload.last_seen_date:
            q = q.where(MissingPersonCase.last_seen_date == payload.last_seen_date)
        dupes = db.scalars(q.limit(5)).all()
        if dupes:
            return JSONResponse(
                status_code=200,
                content={
                    "duplicate_warning": True,
                    "warning": "A case with the same name (and last-seen date) already exists. "
                    "Review potential duplicates before creating another record.",
                    "possible_duplicates": [
                        CaseListItem.model_validate(c).model_dump(mode="json") for c in dupes
                    ],
                },
            )

    case = MissingPersonCase(
        case_number=_next_case_number(db),
        full_name=None if payload.name_unknown else payload.full_name,
        name_unknown=payload.name_unknown,
        age_min=payload.age_min,
        age_max=payload.age_max,
        gender=payload.gender,
        last_seen_date=payload.last_seen_date,
        last_seen_location=payload.last_seen_location,
        physical_description=payload.physical_description,
        clothing_description=payload.clothing_description,
        additional_notes=payload.additional_notes,
        contact_agency=payload.contact_agency,
        contact_info=payload.contact_info,
        status=payload.status,
        consent_recorded=payload.consent_recorded,
        legal_basis=payload.legal_basis,
        authorization_reference=payload.authorization_reference,
        created_by=user.id,
        owned_by=user.id,
    )
    db.add(case)
    db.flush()
    db.add(
        CaseStatusHistory(
            case_id=case.id,
            from_status=None,
            to_status=case.status,
            note="Case registered.",
            changed_by=user.id,
            created_at=utcnow(),
        )
    )
    db.commit()
    db.refresh(case)
    log_action(
        db,
        action="case.created",
        user_id=user.id,
        resource_type="case",
        resource_id=str(case.id),
        detail={"case_number": case.case_number},
        request=request,
    )
    return _case_to_out(case)


def _next_case_number(db: Session) -> str:
    year = utcnow().year
    prefix = f"MPI-{year}-"
    last = db.scalar(
        select(MissingPersonCase.case_number)
        .where(MissingPersonCase.case_number.like(prefix + "%"))
        .order_by(MissingPersonCase.case_number.desc())
        .limit(1)
    )
    seq = 1
    if last:
        try:
            seq = int(last.split("-")[-1]) + 1
        except ValueError:
            seq = 1
    return f"{prefix}{seq:06d}"


@router.get("")
def list_cases(
    q: Optional[str] = Query(None, max_length=255),
    status: Optional[str] = Query(None),
    include_demo: bool = Query(True),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    sort: str = Query("created_desc", pattern="^(created_desc|created_asc|name_asc|last_seen_desc)$"),
    paging: tuple = Depends(pagination),
    user: User = RequireAnyAuthed,
    db: Session = Depends(get_db),
):
    page, page_size = paging
    stmt = select(MissingPersonCase).where(MissingPersonCase.is_deleted.is_(False))
    if not include_demo:
        stmt = stmt.where(MissingPersonCase.is_demo.is_(False))
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                MissingPersonCase.case_number.ilike(like),
                MissingPersonCase.full_name.ilike(like),
                MissingPersonCase.last_seen_location.ilike(like),
                MissingPersonCase.physical_description.ilike(like),
            )
        )
    if status:
        if status not in ALL_CASE_STATUSES:
            raise ValidationAppError("Unknown status filter.", {"allowed": list(ALL_CASE_STATUSES)})
        stmt = stmt.where(MissingPersonCase.status == status)
    if date_from:
        stmt = stmt.where(MissingPersonCase.last_seen_date >= date_from)
    if date_to:
        stmt = stmt.where(MissingPersonCase.last_seen_date <= date_to)

    order = {
        "created_desc": MissingPersonCase.created_at.desc(),
        "created_asc": MissingPersonCase.created_at.asc(),
        "name_asc": MissingPersonCase.full_name.asc().nulls_last(),
        "last_seen_desc": MissingPersonCase.last_seen_date.desc().nulls_last(),
    }[sort]

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(order).offset((page - 1) * page_size).limit(page_size)).all()
    items = []
    for c in rows:
        item = CaseListItem.model_validate(c)
        item.photo_count = sum(1 for p in c.photos if not p.is_deleted)
        items.append(item.model_dump())
    return paginate(items, total, page, page_size)


@router.get("/{case_id}")
def get_case(case_id: uuid.UUID, user: User = RequireAnyAuthed, db: Session = Depends(get_db)):
    return _case_to_out(_get_case(db, case_id))


@router.patch("/{case_id}")
def update_case(
    case_id: uuid.UUID,
    payload: CaseUpdate,
    request: Request,
    user: User = RequireInvestigator,
    db: Session = Depends(get_db),
):
    case = _get_case(db, case_id)
    data = payload.model_dump(exclude_unset=True)
    new_status = data.pop("status", None)
    status_note = data.pop("status_note", "") or ""
    for k, v in data.items():
        setattr(case, k, v)

    if new_status and new_status != case.status:
        prev = case.status
        if new_status not in ALL_CASE_STATUSES:
            raise ValidationAppError("Unknown status.")
        # Status changes based on matches require human review first — enforced
        # by workflow here: moving to 'located' requires a note referencing review.
        if new_status == "located" and not status_note.strip():
            raise ValidationAppError(
                "Changing status to 'located' requires a status_note documenting "
                "the human verification and independent corroboration."
            )
        case.status = new_status
        db.add(
            CaseStatusHistory(
                case_id=case.id,
                from_status=prev,
                to_status=new_status,
                note=status_note,
                changed_by=user.id,
                created_at=utcnow(),
            )
        )
    elif status_note.strip():
        db.add(
            CaseStatusHistory(
                case_id=case.id,
                from_status=case.status,
                to_status=case.status,
                note=status_note,
                changed_by=user.id,
                created_at=utcnow(),
            )
        )

    db.commit()
    db.refresh(case)
    log_action(
        db,
        action="case.updated",
        user_id=user.id,
        resource_type="case",
        resource_id=str(case.id),
        detail={"fields": list(payload.model_dump(exclude_unset=True).keys())},
        request=request,
    )
    return _case_to_out(case)


@router.delete("/{case_id}")
def archive_case(
    case_id: uuid.UUID,
    request: Request,
    user: User = RequireInvestigator,
    db: Session = Depends(get_db),
):
    """Soft-delete / archive. Records are retained per the retention policy."""
    case = _get_case(db, case_id)
    case.is_deleted = True
    case.deleted_at = utcnow()
    case.status = CASE_STATUS_ARCHIVED
    db.add(
        CaseStatusHistory(
            case_id=case.id,
            from_status=None,
            to_status=CASE_STATUS_ARCHIVED,
            note="Case archived (soft delete).",
            changed_by=user.id,
            created_at=utcnow(),
        )
    )
    db.commit()
    log_action(
        db,
        action="case.archived",
        user_id=user.id,
        resource_type="case",
        resource_id=str(case.id),
        request=request,
    )
    return {"message": "Case archived."}


@router.get("/{case_id}/duplicates", response_model=DuplicateWarning)
def check_duplicates(
    case_id: uuid.UUID, user: User = RequireInvestigator, db: Session = Depends(get_db)
):
    case = _get_case(db, case_id)
    stmt = select(MissingPersonCase).where(
        MissingPersonCase.is_deleted.is_(False), MissingPersonCase.id != case.id
    )
    if case.full_name:
        stmt = stmt.where(func.lower(MissingPersonCase.full_name) == case.full_name.lower())
    else:
        stmt = stmt.where(
            MissingPersonCase.age_min == case.age_min,
            MissingPersonCase.last_seen_date == case.last_seen_date,
        )
    dupes = db.scalars(stmt.limit(5)).all()
    return DuplicateWarning(
        possible_duplicates=[CaseListItem.model_validate(c) for c in dupes],
        warning="Potential duplicates based on matching name / age / last-seen date. Review manually.",
    )


# --- photos -----------------------------------------------------------------
@router.post("/{case_id}/photos", status_code=201)
async def upload_photo(
    case_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    is_primary: bool = Form(False),
    user: User = RequireInvestigator,
    db: Session = Depends(get_db),
):
    case = _get_case(db, case_id)
    data = await file.read()
    rel, sha, size, meta = validate_and_save_photo(data, file.filename or "upload.jpg")

    existing = db.scalar(
        select(PersonPhoto).where(PersonPhoto.sha256 == sha, PersonPhoto.is_deleted.is_(False))
    )
    if existing:
        raise ConflictError(
            "This exact image is already registered.",
            {"existing_photo_id": str(existing.id), "existing_case_id": str(existing.case_id)},
        )

    photo = PersonPhoto(
        case_id=case.id,
        file_path=rel,
        original_filename=(file.filename or "upload.jpg")[:255],
        content_type=meta["content_type"],
        file_size=size,
        sha256=sha,
        is_primary=is_primary,
        width=meta.get("width"),
        height=meta.get("height"),
        uploaded_by=user.id,
    )
    if is_primary:
        for p in case.photos:
            p.is_primary = False
    db.add(photo)
    db.commit()
    db.refresh(photo)

    # Best-effort: generate an embedding if the model is available.
    ai_info = {"embedding_generated": False, "reason": ""}
    try:
        from backend.app.ai.registry import get_backend
        from backend.app.ai.service import FaceMatchingService, load_image_bgr, pack_embedding
        from backend.app.models import FaceEmbedding

        backend = get_backend()
        if backend.available():
            service = FaceMatchingService(backend)
            img = load_image_bgr(data)
            emb_vec, obs = service.embed_primary_face(img)
            info = backend.info()
            db.add(
                FaceEmbedding(
                    photo_id=photo.id,
                    case_id=case.id,
                    model_name=info.name,
                    model_version=info.version,
                    dim=int(emb_vec.size),
                    embedding=pack_embedding(emb_vec),
                    face_confidence=obs.face.confidence,
                    face_bbox=json.dumps([obs.face.x, obs.face.y, obs.face.w, obs.face.h]),
                    quality_score=obs.quality.quality_score,
                )
            )
            photo.quality_score = obs.quality.quality_score
            photo.blur_score = obs.quality.blur_score
            db.commit()
            ai_info = {"embedding_generated": True, "reason": ""}
        else:
            ai_info = {
                "embedding_generated": False,
                "reason": backend.availability_detail() or "AI model unavailable",
            }
    except Exception as exc:
        db.rollback()
        ai_info = {"embedding_generated": False, "reason": str(exc)[:500]}

    log_action(
        db,
        action="case.photo_uploaded",
        user_id=user.id,
        resource_type="photo",
        resource_id=str(photo.id),
        detail={"case_id": str(case.id), "sha256": sha},
        request=request,
    )
    out = PhotoOut.model_validate(photo)
    out.embedding_count = len(photo.embeddings)
    dumped = out.model_dump()
    dumped["ai"] = ai_info
    return dumped


@router.get("/{case_id}/photos/{photo_id}/file")
def get_photo_file(
    case_id: uuid.UUID,
    photo_id: uuid.UUID,
    user: User = RequireAnyAuthed,
    db: Session = Depends(get_db),
):
    """Authenticated photo retrieval — files are never publicly served."""
    photo = db.get(PersonPhoto, photo_id)
    if photo is None or photo.is_deleted or photo.case_id != case_id:
        raise NotFoundError("Photo", photo_id)
    path = absolute_path(photo.file_path)
    if not path.exists():
        raise NotFoundError("Photo file on disk")
    return FileResponse(path, media_type=photo.content_type, filename=photo.original_filename)


@router.delete("/{case_id}/photos/{photo_id}")
def delete_photo(
    case_id: uuid.UUID,
    photo_id: uuid.UUID,
    request: Request,
    user: User = RequireInvestigator,
    db: Session = Depends(get_db),
):
    photo = db.get(PersonPhoto, photo_id)
    if photo is None or photo.is_deleted or photo.case_id != case_id:
        raise NotFoundError("Photo", photo_id)
    photo.is_deleted = True
    photo.deleted_at = utcnow()
    db.commit()
    log_action(
        db,
        action="case.photo_deleted",
        user_id=user.id,
        resource_type="photo",
        resource_id=str(photo_id),
        request=request,
    )
    return {"message": "Photo removed from the case (retained per retention policy)."}
