"""Privacy, notifications, reports and structured-error tests."""
from __future__ import annotations


def test_notifications_flow(client, investigator_headers):
    r = client.get("/api/v1/notifications", headers=investigator_headers)
    assert r.status_code == 200
    assert "items" in r.json()

    r = client.get("/api/v1/notifications/unread-count", headers=investigator_headers)
    assert r.status_code == 200

    r = client.post("/api/v1/notifications/read-all", headers=investigator_headers)
    assert r.status_code == 200


def test_correction_requests(client, investigator_headers, admin_headers):
    r = client.post(
        "/api/v1/privacy/correction-requests",
        json={
            "subject_reference": "MPI-2026-000001",
            "request_type": "correction",
            "description": "A potential match was mistaken; please review and correct the record.",
        },
        headers=investigator_headers,
    )
    assert r.status_code == 201
    req_id = r.json()["id"]

    r = client.get("/api/v1/privacy/correction-requests", headers=admin_headers)
    assert r.status_code == 200
    assert any(i["id"] == req_id for i in r.json())

    r = client.patch(
        f"/api/v1/privacy/correction-requests/{req_id}",
        params={"status": "resolved", "resolution_note": "Rejected match purged per policy."},
        headers=admin_headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "resolved"


def test_retention_run(client, admin_headers):
    r = client.post("/api/v1/privacy/run-retention", headers=admin_headers)
    assert r.status_code == 200
    assert "report" in r.json()


def test_overview_stats(client, investigator_headers):
    r = client.get("/api/v1/stats/overview", headers=investigator_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total_cases"] >= 1
    assert "cases_by_status" in body
    assert body["ai_available"] is False


def test_cases_report_csv_pdf(client, admin_headers):
    r = client.get("/api/v1/reports/cases", params={"format": "csv"}, headers=admin_headers)
    assert r.status_code == 200
    assert "case_number" in r.text

    r = client.get("/api/v1/reports/cases", params={"format": "pdf"}, headers=admin_headers)
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"


def test_activity_summary(client, admin_headers):
    r = client.get("/api/v1/reports/activity-summary", headers=admin_headers)
    assert r.status_code == 200
    assert "actions" in r.json()


def test_structured_error_shape(client):
    r = client.get("/api/v1/cases/definitely-not-a-uuid", headers={"Authorization": "Bearer x.y.z"})
    assert r.status_code == 401
    body = r.json()
    assert set(body["error"].keys()) == {"code", "message", "details"}


def test_pagination_bounds(client, investigator_headers):
    r = client.get("/api/v1/cases", params={"page_size": 1000}, headers=investigator_headers)
    assert r.status_code == 422
    r = client.get("/api/v1/cases", params={"page": 0}, headers=investigator_headers)
    assert r.status_code == 422
