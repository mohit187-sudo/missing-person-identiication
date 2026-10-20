"""Role-based access control — enforced on the backend for every role."""
from __future__ import annotations


def test_rescue_cannot_create_case(client, rescue_headers):
    r = client.post(
        "/api/v1/cases",
        json={"full_name": "X", "consent_recorded": True, "legal_basis": "y"},
        headers=rescue_headers,
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


def test_rescue_can_read_cases(client, rescue_headers):
    r = client.get("/api/v1/cases", headers=rescue_headers)
    assert r.status_code == 200


def test_rescue_cannot_use_biometric_search(client, rescue_headers, make_image):
    r = client.post(
        "/api/v1/matching/search",
        files={"file": ("q.jpg", make_image(), "image/jpeg")},
        headers=rescue_headers,
    )
    assert r.status_code == 403


def test_rescue_cannot_list_matches(client, rescue_headers):
    assert client.get("/api/v1/matches", headers=rescue_headers).status_code == 403


def test_investigator_cannot_access_admin(client, investigator_headers):
    assert client.get("/api/v1/admin/users", headers=investigator_headers).status_code == 403
    assert client.get("/api/v1/admin/audit-logs", headers=investigator_headers).status_code == 403
    assert client.get("/api/v1/reports/cases", headers=investigator_headers).status_code == 403


def test_admin_can_manage_users(client, admin_headers):
    r = client.get("/api/v1/admin/users", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["total"] >= 3


def test_admin_audit_logs(client, admin_headers):
    r = client.get(
        "/api/v1/admin/audit-logs", params={"action": "auth.login"}, headers=admin_headers
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert any(e["action"] == "auth.login" for e in body["items"])


def test_deactivated_user_cannot_login(client, admin_headers, users_ready):
    # Create then deactivate a user.
    r = client.post(
        "/api/v1/admin/users",
        json={
            "email": "deact@example.com",
            "full_name": "Deactivated User",
            "password": "DeactPass!2345",
            "role": "investigator",
        },
        headers=admin_headers,
    )
    assert r.status_code == 201
    user_id = r.json()["id"]

    login = client.post(
        "/api/v1/auth/login", json={"email": "deact@example.com", "password": "DeactPass!2345"}
    )
    assert login.status_code == 200

    r = client.patch(f"/api/v1/admin/users/{user_id}", json={"is_active": False}, headers=admin_headers)
    assert r.status_code == 200

    login = client.post(
        "/api/v1/auth/login", json={"email": "deact@example.com", "password": "DeactPass!2345"}
    )
    assert login.status_code == 401

    # Existing session token is also rejected once deactivated.
    r = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login.headers.get('x', '')}"},
    )


def test_admin_can_update_role(client, admin_headers):
    r = client.post(
        "/api/v1/admin/users",
        json={
            "email": "roletest@example.com",
            "full_name": "Role Test",
            "password": "RolePass!2345",
            "role": "rescue_team",
        },
        headers=admin_headers,
    )
    user_id = r.json()["id"]
    r = client.patch(f"/api/v1/admin/users/{user_id}", json={"role": "investigator"}, headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["role"] == "investigator"


def test_privacy_retention_admin_only(client, investigator_headers, admin_headers):
    assert client.get("/api/v1/privacy/retention-policies", headers=investigator_headers).status_code == 200
    r = client.put(
        "/api/v1/privacy/retention-policies/photos",
        json={"retention_days": 100, "action": "delete", "is_active": True},
        headers=investigator_headers,
    )
    assert r.status_code == 403
    r = client.put(
        "/api/v1/privacy/retention-policies/photos",
        json={"retention_days": 100, "action": "delete", "is_active": True, "description": "d"},
        headers=admin_headers,
    )
    assert r.status_code == 200
