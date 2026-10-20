"""Shared pytest fixtures — isolated SQLite DB + private storage per test run."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

_TMP = Path(tempfile.mkdtemp(prefix="mpis-test-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["STORAGE_DIR"] = str(_TMP / "storage")
os.environ["JWT_SECRET_KEY"] = "unit-test-secret-key-not-for-production"
os.environ["ENVIRONMENT"] = "test"
os.environ["DEMO_MODE"] = "false"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["AI_BACKEND"] = "opencv_sface"
os.environ["AI_MODEL_PATH"] = str(_TMP / "no-models")

# Import AFTER env vars so settings bind to the test configuration.
from backend.app.core.config import settings  # noqa: E402
from backend.app.core.security import hash_password  # noqa: E402
from backend.app.db.init_db import init_db  # noqa: E402
from backend.app.db.session import SessionLocal  # noqa: E402
from backend.app.models import Role, User  # noqa: E402
from backend.app.security.rate_limit import reset_rate_limits  # noqa: E402

settings.validate_startup()


@pytest.fixture(scope="session")
def app():
    from backend.app.main import create_app

    application = create_app()
    yield application
    from backend.app.tasks import runner

    runner.shutdown()


@pytest.fixture(scope="session")
def client(app):
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        init_db()
        yield c


@pytest.fixture(autouse=True)
def _clean_rate_limits():
    reset_rate_limits()
    yield
    reset_rate_limits()


def _ensure_user(email: str, password: str, role_name: str, full_name: str) -> None:
    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == email).first():
            return
        role = db.query(Role).filter(Role.name == role_name).first()
        db.add(
            User(
                email=email,
                full_name=full_name,
                hashed_password=hash_password(password),
                role_id=role.id,
                agency="Test Agency",
            )
        )
        db.commit()
    finally:
        db.close()


@pytest.fixture(scope="session")
def passwords():
    return {
        "administrator": "AdminPass!2345",
        "investigator": "InvestPass!2345",
        "rescue_team": "RescuePass!2345",
    }


@pytest.fixture(scope="session")
def users_ready(client, passwords):
    _ensure_user("admin@example.com", passwords["administrator"], "administrator", "Test Admin")
    _ensure_user("investigator@example.com", passwords["investigator"], "investigator", "Test Investigator")
    _ensure_user("rescue@example.com", passwords["rescue_team"], "rescue_team", "Test Rescue")
    return {
        "administrator": "admin@example.com",
        "investigator": "investigator@example.com",
        "rescue_team": "rescue@example.com",
    }


def _login(client, email: str, password: str) -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="session")
def tokens(client, users_ready, passwords):
    return {role: _login(client, email, passwords[role]) for role, email in users_ready.items()}


@pytest.fixture(scope="session")
def admin_headers(tokens):
    return {"Authorization": f"Bearer {tokens['administrator']['access_token']}"}


@pytest.fixture(scope="session")
def investigator_headers(tokens):
    return {"Authorization": f"Bearer {tokens['investigator']['access_token']}"}


@pytest.fixture(scope="session")
def rescue_headers(tokens):
    return {"Authorization": f"Bearer {tokens['rescue_team']['access_token']}"}


@pytest.fixture()
def make_image():
    """Factory producing small valid JPEG/PNG images."""
    import io

    from PIL import Image, ImageDraw

    def _make(size=(320, 320), fmt="JPEG", blur=False) -> bytes:
        img = Image.new("RGB", size, (120, 140, 160))
        d = ImageDraw.Draw(img)
        # A simple high-contrast pattern so quality metrics have signal.
        for i in range(0, size[0], 20):
            d.line([(i, 0), (i, size[1])], fill=(255, 255, 255), width=3)
        d.ellipse([size[0] * 0.3, size[1] * 0.2, size[0] * 0.7, size[1] * 0.6], fill=(220, 190, 160))
        if blur:
            from PIL import ImageFilter

            img = img.filter(ImageFilter.GaussianBlur(radius=8))
        buf = io.BytesIO()
        img.save(buf, format=fmt)
        return buf.getvalue()

    return _make


@pytest.fixture()
def sample_case(client, investigator_headers):
    """Create a reusable case; returns the case dict."""
    payload = {
        "full_name": "Fixture Person",
        "age_min": 20,
        "age_max": 30,
        "last_seen_date": "2026-01-15",
        "last_seen_location": "Fixture Street",
        "physical_description": "Fixture description",
        "clothing_description": "Fixture clothes",
        "contact_agency": "Fixture Agency",
        "contact_info": "fixture@example.com",
        "consent_recorded": True,
        "legal_basis": "Test fixture lawful basis",
        "acknowledge_duplicate_warning": True,
    }
    r = client.post("/api/v1/cases", json=payload, headers=investigator_headers)
    assert r.status_code == 201, r.text
    return r.json()
