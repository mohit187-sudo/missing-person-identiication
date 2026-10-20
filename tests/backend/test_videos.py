"""Video evidence pipeline tests: validation, jobs, status, reports, cancel."""
from __future__ import annotations

import time
import uuid as uuid_mod

import numpy as np
import pytest


def _make_test_video(tmp_path, frames: int = 15, fps: int = 10) -> bytes:
    import cv2

    path = str(tmp_path / "sample.avi")
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    writer = cv2.VideoWriter(path, fourcc, fps, (160, 120))
    if not writer.isOpened():
        pytest.skip("OpenCV video writer unavailable in this environment")
    for i in range(frames):
        frame = np.full((120, 160, 3), (i * 10) % 255, dtype=np.uint8)
        cv2.circle(frame, (80, 60), 30, (200, 180, 160), -1)  # blob "face-ish"
        writer.write(frame)
    writer.release()
    return open(path, "rb").read()


@pytest.fixture()
def video_bytes(tmp_path):
    return _make_test_video(tmp_path)


@pytest.fixture()
def uploaded_video(client, investigator_headers, video_bytes):
    r = client.post(
        "/api/v1/videos",
        files={"file": ("clip.avi", video_bytes, "video/x-msvideo")},
        data={
            "title": "Authorized test clip",
            "lawfully_obtained": "true",
            "authorization_reference": "AUTH-001",
        },
        headers=investigator_headers,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["duration_seconds"] > 0
    assert body["width"] == 160
    return body


def test_video_upload_requires_lawful_confirmation(client, investigator_headers, video_bytes):
    r = client.post(
        "/api/v1/videos",
        files={"file": ("clip.avi", video_bytes, "video/x-msvideo")},
        data={"title": "Test clip", "lawfully_obtained": "false"},
        headers=investigator_headers,
    )
    assert r.status_code == 422


def test_video_upload_and_probe(uploaded_video):
    assert uploaded_video["fps"] > 0


def test_video_upload_rejects_bad_extension(client, investigator_headers):
    r = client.post(
        "/api/v1/videos",
        files={"file": ("evil.exe", b"MZ" + b"\x00" * 2000, "application/octet-stream")},
        data={"title": "Bad", "lawfully_obtained": "true"},
        headers=investigator_headers,
    )
    assert r.status_code == 422


def test_video_upload_rejects_corrupt_file(client, investigator_headers):
    r = client.post(
        "/api/v1/videos",
        files={"file": ("corrupt.mp4", b"\x00" * 4096, "video/mp4")},
        data={"title": "Corrupt", "lawfully_obtained": "true"},
        headers=investigator_headers,
    )
    assert r.status_code == 422
    assert "Corrupt" in r.json()["error"]["message"] or "corrupt" in r.json()["error"]["message"].lower()


def test_process_job_fails_cleanly_without_model(client, investigator_headers, uploaded_video):
    """Without model weights the job FAILS with a clear message — never fake matches."""
    video = uploaded_video

    r = client.post(
        f"/api/v1/videos/{video['id']}/process",
        json={"sampling_interval_seconds": 1.0},
        headers=investigator_headers,
    )
    assert r.status_code == 202
    job_id = r.json()["id"]
    assert r.json()["status"] in ("queued", "running")

    # Wait for the background thread to finish (small video -> fast).
    status = None
    for _ in range(50):
        s = client.get(f"/api/v1/videos/{video['id']}/status", headers=investigator_headers).json()
        status = s["latest"]
        if status["status"] in ("completed", "failed", "cancelled"):
            break
        time.sleep(0.2)

    assert status is not None
    assert status["status"] == "failed"
    assert "AI model unavailable" in status["error_message"]
    assert "download_models.py" in status["error_message"]

    # Report exists and is honest about zero rows.
    report = client.get(f"/api/v1/videos/{video['id']}/report", headers=investigator_headers).json()
    assert report["rows"] == []
    assert "NOT identification" in report["disclaimer"]


def test_video_report_csv_and_pdf(client, investigator_headers, uploaded_video):
    video = uploaded_video
    r = client.get(
        f"/api/v1/videos/{video['id']}/report", params={"format": "csv"}, headers=investigator_headers
    )
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]

    r = client.get(
        f"/api/v1/videos/{video['id']}/report", params={"format": "pdf"}, headers=investigator_headers
    )
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"


def test_cancel_unknown_job(client, investigator_headers):
    r = client.post(f"/api/v1/videos/jobs/{uuid_mod.uuid4()}/cancel", headers=investigator_headers)
    assert r.status_code == 404


def test_videos_require_auth(client):
    assert client.get("/api/v1/videos").status_code == 401
