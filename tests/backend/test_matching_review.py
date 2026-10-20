"""Potential-match review workflow tests (human verification, no auto-ID)."""
from __future__ import annotations

import uuid as uuid_mod

from backend.app.db.session import SessionLocal
from backend.app.models import (
    MATCH_PENDING,
    MissingPersonCase,
    PotentialMatch,
    utcnow,
)


def _seed_match(db, case_id) -> PotentialMatch:
    import uuid as _uuid

    if not isinstance(case_id, _uuid.UUID):
        case_id = _uuid.UUID(str(case_id))
    m = PotentialMatch(
        source_type="photo_search",
        candidate_case_id=case_id,
        similarity_score=0.91,
        threshold_used=0.55,
        model_name="test-model",
        model_version="0.0-test",
        processing_timestamp=utcnow(),
        status=MATCH_PENDING,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def test_review_confirm_requires_notes(client, investigator_headers, sample_case):
    db = SessionLocal()
    try:
        m = _seed_match(db, sample_case["id"])
    finally:
        db.close()

    r = client.post(
        f"/api/v1/matches/{m.id}/review",
        json={"decision": "confirmed_for_investigation", "notes": "too short"},
        headers=investigator_headers,
    )
    assert r.status_code == 422

    r = client.post(
        f"/api/v1/matches/{m.id}/review",
        json={
            "decision": "confirmed_for_investigation",
            "notes": "Verified photo against case file; arranging in-person corroboration.",
        },
        headers=investigator_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["match"]["status"] == "confirmed_for_investigation"
    # Case status must NOT change automatically.
    assert body["case_status"] == sample_case["status"]


def test_review_reject_and_history(client, investigator_headers, sample_case):
    db = SessionLocal()
    try:
        m = _seed_match(db, sample_case["id"])
    finally:
        db.close()

    r = client.post(
        f"/api/v1/matches/{m.id}/review",
        json={"decision": "rejected", "notes": "Different person — jawline and age clearly differ."},
        headers=investigator_headers,
    )
    assert r.status_code == 200

    r = client.get(f"/api/v1/matches/{m.id}", headers=investigator_headers)
    body = r.json()
    assert body["status"] == "rejected"
    assert body["reviews"]
    assert body["reviews"][0]["decision"] == "rejected"
    assert body["reviews"][0]["reviewer_name"] == "Test Investigator"


def test_match_list_filters(client, investigator_headers, sample_case):
    db = SessionLocal()
    try:
        m = _seed_match(db, sample_case["id"])
    finally:
        db.close()

    r = client.get(
        "/api/v1/matches",
        params={"status": "pending", "min_score": 0.5},
        headers=investigator_headers,
    )
    assert r.status_code == 200
    ids = [i["id"] for i in r.json()["items"]]
    assert str(m.id) in ids

    r = client.get("/api/v1/matches", params={"case_id": str(uuid_mod.uuid4())}, headers=investigator_headers)
    assert r.json()["total"] == 0


def test_invalid_decision_rejected(client, investigator_headers, sample_case):
    db = SessionLocal()
    try:
        m = _seed_match(db, sample_case["id"])
    finally:
        db.close()
    r = client.post(
        f"/api/v1/matches/{m.id}/review",
        json={"decision": "identified", "notes": "x" * 20},
        headers=investigator_headers,
    )
    assert r.status_code == 422


def test_matching_job_not_found(client, investigator_headers):
    r = client.get(f"/api/v1/matching/jobs/{uuid_mod.uuid4()}", headers=investigator_headers)
    assert r.status_code == 404
