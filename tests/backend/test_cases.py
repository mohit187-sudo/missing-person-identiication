"""Case CRUD, validation, duplicate warnings, photo uploads, status history."""
from __future__ import annotations

import io

from PIL import Image


def _case_payload(**overrides):
    payload = {
        "full_name": "John Q Testcase",
        "age_min": 25,
        "age_max": 30,
        "last_seen_date": "2026-02-01",
        "last_seen_location": "Testville",
        "physical_description": "tall, glasses",
        "clothing_description": "green shirt",
        "contact_agency": "Test PD",
        "contact_info": "testpd@example.invalid",
        "consent_recorded": True,
        "legal_basis": "Court order 123",
    }
    payload.update(overrides)
    return payload


def test_case_create_and_read(client, investigator_headers):
    r = client.post("/api/v1/cases", json=_case_payload(), headers=investigator_headers)
    assert r.status_code == 201, r.text
    case = r.json()
    assert case["case_number"].startswith("MPI-")
    assert case["status"] == "missing"

    r = client.get(f"/api/v1/cases/{case['id']}", headers=investigator_headers)
    assert r.status_code == 200
    assert r.json()["full_name"] == "John Q Testcase"


def test_case_validation(client, investigator_headers):
    # Missing name without name_unknown
    r = client.post("/api/v1/cases", json=_case_payload(full_name=None), headers=investigator_headers)
    assert r.status_code == 422

    # Age range inverted
    r = client.post(
        "/api/v1/cases", json=_case_payload(age_min=50, age_max=20), headers=investigator_headers
    )
    assert r.status_code == 422

    # name_unknown path is valid
    r = client.post(
        "/api/v1/cases",
        json=_case_payload(full_name=None, name_unknown=True),
        headers=investigator_headers,
    )
    assert r.status_code == 201


def test_duplicate_warning_flow(client, investigator_headers):
    first = client.post(
        "/api/v1/cases",
        json=_case_payload(full_name="Dup Person", last_seen_date="2026-03-01"),
        headers=investigator_headers,
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/cases",
        json=_case_payload(full_name="Dup Person", last_seen_date="2026-03-01"),
        headers=investigator_headers,
    )
    assert second.status_code == 200
    body = second.json()
    assert body["duplicate_warning"] is True
    assert body["possible_duplicates"]

    # Acknowledge to proceed
    third = client.post(
        "/api/v1/cases",
        json=_case_payload(
            full_name="Dup Person",
            last_seen_date="2026-03-01",
            acknowledge_duplicate_warning=True,
        ),
        headers=investigator_headers,
    )
    assert third.status_code == 201


def test_search_filters_pagination(client, investigator_headers):
    for i in range(3):
        client.post(
            "/api/v1/cases",
            json=_case_payload(
                full_name=f"Filter Person {i}",
                last_seen_location=f"City-{i}",
                acknowledge_duplicate_warning=True,
            ),
            headers=investigator_headers,
        )
    r = client.get(
        "/api/v1/cases", params={"q": "Filter Person", "page_size": 2}, headers=investigator_headers
    )
    assert r.status_code == 200
    body = r.json()
    assert body["page_size"] == 2
    assert len(body["items"]) == 2
    assert body["total"] >= 3

    r = client.get("/api/v1/cases", params={"status": "missing"}, headers=investigator_headers)
    assert all(i["status"] == "missing" for i in r.json()["items"])

    r = client.get("/api/v1/cases", params={"status": "bogus"}, headers=investigator_headers)
    assert r.status_code == 422


def test_case_update_and_status_history(client, investigator_headers, sample_case):
    cid = sample_case["id"]
    r = client.patch(
        f"/api/v1/cases/{cid}",
        json={"physical_description": "updated description", "status_note": "details refined"},
        headers=investigator_headers,
    )
    assert r.status_code == 200
    assert r.json()["physical_description"] == "updated description"

    # 'located' requires a verification note
    r = client.patch(f"/api/v1/cases/{cid}", json={"status": "located"}, headers=investigator_headers)
    assert r.status_code == 422

    r = client.patch(
        f"/api/v1/cases/{cid}",
        json={
            "status": "located",
            "status_note": "Verified in person by officer Smith, corroborated by family.",
        },
        headers=investigator_headers,
    )
    assert r.status_code == 200
    history = r.json()["status_history"]
    assert any(h["to_status"] == "located" and h["note"] for h in history)


def test_photo_upload_validation(client, investigator_headers, sample_case, make_image):
    cid = sample_case["id"]

    # Valid JPEG
    r = client.post(
        f"/api/v1/cases/{cid}/photos",
        files={"file": ("photo.jpg", make_image(), "image/jpeg")},
        headers=investigator_headers,
    )
    assert r.status_code == 201, r.text
    photo = r.json()
    assert photo["file_size"] > 0

    # Same bytes again -> duplicate conflict
    r = client.post(
        f"/api/v1/cases/{cid}/photos",
        files={"file": ("photo.jpg", make_image(), "image/jpeg")},
        headers=investigator_headers,
    )
    assert r.status_code == 409

    # Wrong extension
    r = client.post(
        f"/api/v1/cases/{cid}/photos",
        files={"file": ("evil.exe", make_image(), "application/octet-stream")},
        headers=investigator_headers,
    )
    assert r.status_code == 422

    # Not an image at all (fake JPEG bytes)
    r = client.post(
        f"/api/v1/cases/{cid}/photos",
        files={"file": ("fake.jpg", b"\xff\xd8\xff" + b"garbage" * 100, "image/jpeg")},
        headers=investigator_headers,
    )
    assert r.status_code == 422

    # Too small image
    r = client.post(
        f"/api/v1/cases/{cid}/photos",
        files={"file": ("tiny.jpg", make_image(size=(8, 8)), "image/jpeg")},
        headers=investigator_headers,
    )
    assert r.status_code == 422


def test_photo_retrieval_requires_auth(client, sample_case, investigator_headers, make_image):
    cid = sample_case["id"]
    r = client.post(
        f"/api/v1/cases/{cid}/photos",
        files={"file": ("p2.png", make_image(fmt="PNG"), "image/png")},
        headers=investigator_headers,
    )
    photo_id = r.json()["id"]

    # Unauthenticated retrieval is refused
    r = client.get(f"/api/v1/cases/{cid}/photos/{photo_id}/file")
    assert r.status_code == 401

    r = client.get(f"/api/v1/cases/{cid}/photos/{photo_id}/file", headers=investigator_headers)
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"


def test_case_archive(client, investigator_headers):
    case = client.post(
        "/api/v1/cases", json=_case_payload(full_name="Archive Me"), headers=investigator_headers
    ).json()
    r = client.delete(f"/api/v1/cases/{case['id']}", headers=investigator_headers)
    assert r.status_code == 200
    r = client.get(f"/api/v1/cases/{case['id']}", headers=investigator_headers)
    assert r.status_code == 404
