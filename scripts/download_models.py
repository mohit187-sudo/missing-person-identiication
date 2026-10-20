"""Download documented OpenCV Zoo face-model weights (Apache-2.0).

Fetches the official YuNet detector and SFace recognizer ONNX files from the
opencv/opencv_zoo GitHub repository into backend/models/. No paid API and no
credentials are required.

Usage:
    python scripts/download_models.py
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "backend" / "models"

# Official opencv/opencv_zoo raw model files (Apache License 2.0).
# Ref: https://github.com/opencv/opencv_zoo/tree/main/models
BASE = "https://raw.githubusercontent.com/opencv/opencv_zoo/main/models"
FILES = {
    "face_detection_yunet_2023mar.onnx": f"{BASE}/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "face_recognition_sface_2021dec.onnx": f"{BASE}/face_recognition_sface/face_recognition_sface_2021dec.onnx",
}

MIN_SIZES = {
    "face_detection_yunet_2023mar.onnx": 50_000,        # ~230 KB expected
    "face_recognition_sface_2021dec.onnx": 5_000_000,   # ~37 MB expected
}


def download(name: str, url: str) -> bool:
    dest = DEST / name
    if dest.exists() and dest.stat().st_size >= MIN_SIZES.get(name, 1000):
        print(f"[skip] {name} already present ({dest.stat().st_size:,} bytes)")
        return True
    print(f"[get ] {name} <- {url}")
    try:
        with urllib.request.urlopen(url, timeout=120) as resp:
            data = resp.read()
    except Exception as exc:
        print(f"[fail] {name}: {exc}", file=sys.stderr)
        return False
    if len(data) < MIN_SIZES.get(name, 1000):
        print(f"[fail] {name}: downloaded file suspiciously small ({len(data)} bytes)", file=sys.stderr)
        return False
    DEST.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    print(f"[ ok ] {name} ({len(data):,} bytes)")
    return True


def main() -> int:
    print(f"Model destination: {DEST}")
    ok = all(download(name, url) for name, url in FILES.items())
    if ok:
        print("\nAll model weights installed.")
        print("License: OpenCV Zoo models are Apache-2.0 (opencv/opencv_zoo).")
        print("Restart the backend, then check GET /api/health/ready -> ai_model.ok=true")
        return 0
    print(
        "\nSome downloads failed. If GitHub is unreachable, download the two "
        ".onnx files manually from https://github.com/opencv/opencv_zoo and "
        "place them in backend/models/.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
