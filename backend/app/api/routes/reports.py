"""Reports, analytics and dashboard statistics (derived from real DB records)."""
from __future__ import annotations

import csv
import io
from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.api.deps import RequireAdmin, RequireAnyAuthed
from backend.app.db.session import get_db
from backend.app.models import (
    MissingPersonCase,
    PersonPhoto,
    PotentialMatch,
    User,
    VideoEvidence,
    VideoProcessingJob,
    utcnow,
)
from backend.app.schemas.ops import OverviewStats

router = APIRouter(tags=["reports"])


@router.get("/stats/overview", response_model=OverviewStats)
def overview_stats(user: User = RequireAnyAuthed, db: Session = Depends(get_db)):
    from backend.app.ai.registry import ai_status

    def count(model, *where):
        return db.scalar(select(func.count()).select_from(model).where(*where)) or 0

    now = utcnow()
    by_status = {}
    for status in ("missing", "investigating", "potential_lead", "located", "closed", "archived"):
        by_status[status] = count(
            MissingPersonCase,
            MissingPersonCase.status == status,
            MissingPersonCase.is_deleted.is_(False),
        )

    return OverviewStats(
        total_cases=count(MissingPersonCase, MissingPersonCase.is_deleted.is_(False)),
        active_cases=by_status["missing"] + by_status["investigating"] + by_status["potential_lead"],
        located_cases=by_status["located"],
        total_photos=count(PersonPhoto, PersonPhoto.is_deleted.is_(False)),
        total_videos=count(VideoEvidence, VideoEvidence.is_deleted.is_(False)),
        jobs_running=count(VideoProcessingJob, VideoProcessingJob.status.in_(("queued", "running"))),
        jobs_completed=count(VideoProcessingJob, VideoProcessingJob.status == "completed"),
        matches_pending_review=count(PotentialMatch, PotentialMatch.status == "pending"),
        matches_confirmed=count(PotentialMatch, PotentialMatch.status == "confirmed_for_investigation"),
        matches_rejected=count(PotentialMatch, PotentialMatch.status == "rejected"),
        demo_cases=count(MissingPersonCase, MissingPersonCase.is_demo.is_(True)),
        ai_available=ai_status().available,
        cases_by_status=by_status,
        matches_last_7_days=count(
            PotentialMatch, PotentialMatch.created_at >= now - timedelta(days=7)
        ),
        cases_last_30_days=count(
            MissingPersonCase, MissingPersonCase.created_at >= now - timedelta(days=30)
        ),
    )


REPORT_DISCLAIMER = (
    "Report data reflects registered records and technical similarity measures. "
    "Potential-match scores are NOT identification probabilities. All "
    "identifications require human verification and independent corroboration."
)


@router.get("/reports/cases")
def cases_report(
    format: str = Query("csv", pattern="^(csv|pdf)$"),
    user: User = RequireAdmin,
    db: Session = Depends(get_db),
):
    cases = db.scalars(
        select(MissingPersonCase)
        .where(MissingPersonCase.is_deleted.is_(False))
        .order_by(MissingPersonCase.created_at.desc())
    ).all()
    rows = []
    for c in cases:
        rows.append(
            {
                "case_number": c.case_number,
                "full_name": c.full_name or "(name unknown)",
                "status": c.status,
                "last_seen_date": str(c.last_seen_date or ""),
                "last_seen_location": c.last_seen_location,
                "photo_count": sum(1 for p in c.photos if not p.is_deleted),
                "is_demo": c.is_demo,
                "created_at": c.created_at.isoformat(),
            }
        )

    if format == "csv":
        buf = io.StringIO()
        fieldnames = list(rows[0].keys()) if rows else ["case_number"]
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        buf.seek(0)
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="cases_report.csv"'},
        )

    from backend.app.services.pdf import build_case_report_pdf

    pdf_bytes = build_case_report_pdf(rows, REPORT_DISCLAIMER)
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="cases_report.pdf"'},
    )


@router.get("/reports/activity-summary")
def activity_summary(user: User = RequireAdmin, db: Session = Depends(get_db)):
    """Investigation activity summary from audit records (30-day window)."""
    from backend.app.models import AuditLog

    since = utcnow() - timedelta(days=30)
    rows = db.execute(
        select(AuditLog.action, func.count())
        .where(AuditLog.created_at >= since)
        .group_by(AuditLog.action)
        .order_by(func.count().desc())
    ).all()
    return {
        "since": since.isoformat(),
        "actions": [{"action": a, "count": c} for a, c in rows],
        "disclaimer": REPORT_DISCLAIMER,
    }
