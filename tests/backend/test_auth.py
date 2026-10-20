"""Authentication tests: login, refresh rotation/reuse, logout, reset, headers."""
from __future__ import annotations


def test_login_success(client, users_ready, passwords):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": users_ready["investigator"], "password": passwords["investigator"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == "investigator"
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["expires_in"] > 0


def test_login_wrong_password(client, users_ready):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": users_ready["investigator"], "password": "definitely-wrong"},
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_login_unknown_user(client):
    r = client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever123"}
    )
    assert r.status_code == 401


def test_login_invalid_email(client):
    r = client.post("/api/v1/auth/login", json={"email": "not-an-email", "password": "x" * 12})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_me_and_bad_token(client, investigator_headers):
    r = client.get("/api/v1/auth/me", headers=investigator_headers)
    assert r.status_code == 200
    assert r.json()["email"] == "investigator@example.com"

    r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer bogus.token.here"})
    assert r.status_code == 401


def test_no_token_rejected(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401


def test_refresh_rotation_and_reuse_detection(client, users_ready, passwords):
    login = client.post(
        "/api/v1/auth/login",
        json={"email": users_ready["rescue_team"], "password": passwords["rescue_team"]},
    ).json()
    old_refresh = login["refresh_token"]

    r1 = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert r1.status_code == 200
    new_refresh = r1.json()["refresh_token"]
    assert new_refresh != old_refresh

    # Reusing the rotated token must revoke the family and fail.
    r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert r2.status_code == 401

    # The whole family is revoked — the new token no longer works either.
    r3 = client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh})
    assert r3.status_code == 401


def test_logout_revokes_refresh(client, users_ready, passwords):
    login = client.post(
        "/api/v1/auth/login",
        json={"email": users_ready["rescue_team"], "password": passwords["rescue_team"]},
    ).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}
    r = client.post("/api/v1/auth/logout", json={"refresh_token": login["refresh_token"]}, headers=headers)
    assert r.status_code == 200
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert r.status_code == 401


def test_change_password(client, users_ready, passwords):
    email = "changepw@example.com"
    from tests.backend.conftest import _ensure_user, _login

    _ensure_user(email, "OldPassword!234", "investigator", "Change PW")
    login = _login(client, email, "OldPassword!234")
    headers = {"Authorization": f"Bearer {login['access_token']}"}

    r = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "wrong-pass-thing", "new_password": "NewPassword!234"},
        headers=headers,
    )
    assert r.status_code == 422

    r = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "OldPassword!234", "new_password": "NewPassword!234"},
        headers=headers,
    )
    assert r.status_code == 200

    # Old refresh token revoked after password change.
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert r.status_code == 401

    # New password works.
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "NewPassword!234"})
    assert r.status_code == 200


def test_password_reset_workflow(client, users_ready):
    r = client.post("/api/v1/auth/request-password-reset", json={"email": users_ready["rescue_team"]})
    assert r.status_code == 200
    body = r.json()
    # Email is not configured in tests -> demo token returned.
    token = body.get("demo_reset_token")
    assert token

    r = client.post(
        "/api/v1/auth/confirm-password-reset",
        json={"token": token, "new_password": "ResetPassword!234"},
    )
    assert r.status_code == 200
    r = client.post(
        "/api/v1/auth/login",
        json={"email": users_ready["rescue_team"], "password": "ResetPassword!234"},
    )
    assert r.status_code == 200


def test_login_rate_limit(client, users_ready, passwords):
    from backend.app.core.config import settings

    old_enabled, old_limit = settings.rate_limit_enabled, settings.login_rate_limit_per_minute
    settings.rate_limit_enabled = True
    settings.login_rate_limit_per_minute = 3
    try:
        codes = []
        for _ in range(5):
            r = client.post(
                "/api/v1/auth/login",
                json={"email": users_ready["investigator"], "password": "bad-password"},
            )
            codes.append(r.status_code)
        assert codes[-1] == 429
        assert 429 in codes
        body = client.post(
            "/api/v1/auth/login",
            json={"email": users_ready["investigator"], "password": "bad-password"},
        ).json()
        assert body["error"]["code"] == "rate_limited"
    finally:
        settings.rate_limit_enabled = old_enabled
        settings.login_rate_limit_per_minute = old_limit


def test_security_headers_present(client):
    r = client.get("/api/health")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert r.headers.get("Referrer-Policy") == "no-referrer"
