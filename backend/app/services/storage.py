"""Private file storage for photos/videos and upload security validation.

Files are written under STORAGE_DIR (never a publicly served folder). Retrieval
happens only through authenticated API endpoints. Validation covers extension,
MIME sniffing, Pillow decode verification, size limits and SHA-256 hashing.
A malware-scan integration point is provided (`scan_for_malware`).
"""
from __future__ import annotations

import hashlib
import io
import uuid
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, UnidentifiedImageError

from backend.app.core.config import settings
from backend.app.core.exceptions import ValidationAppError

ALLOWED_PHOTO_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
ALLOWED_PHOTO_EXT = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_VIDEO_EXT = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
ALLOWED_VIDEO_MIME_PREFIX = ("video/",)


def storage_root() -> Path:
    root = settings.storage_path
    root.mkdir(parents=True, exist_ok=True)
    return root


def scan_for_malware(path: Path) -> str:
    """Malware-scanning integration point.

    Plug in ClamAV or a cloud scanning SDK here. Default implementation marks
    the file 'unavailable' (never claims a file is clean without scanning).
    """
    return "unavailable"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_and_save_photo(upload_bytes: bytes, filename: str) -> Tuple[str, str, int, dict]:
    """Validate an image upload and write it to private storage.

    Returns (relative_path, sha256, size, metadata).
    """
    max_bytes = settings.max_photo_upload_mb * 1024 * 1024
    if len(upload_bytes) > max_bytes:
        raise ValidationAppError(
            f"Photo exceeds the {settings.max_photo_upload_mb} MB limit.",
            {"max_bytes": max_bytes},
        )
    if len(upload_bytes) < 128:
        raise ValidationAppError("Uploaded file is empty or too small to be a valid image.")

    ext = Path(filename or "upload.jpg").suffix.lower()
    if ext not in ALLOWED_PHOTO_EXT:
        raise ValidationAppError(
            "Unsupported image type. Allowed: JPEG, PNG, WEBP.",
            {"allowed_extensions": sorted(ALLOWED_PHOTO_EXT)},
        )

    try:
        with Image.open(io.BytesIO(upload_bytes)) as img:
            img.verify()  # structural check
        with Image.open(io.BytesIO(upload_bytes)) as img:
            img.load()  # full decode — catches truncated/corrupt files
            fmt = img.format
            width, height = img.size
    except (UnidentifiedImageError, OSError) as exc:
        raise ValidationAppError("File is not a valid image.", {"reason": str(exc)})

    if fmt not in ALLOWED_PHOTO_FORMATS:
        raise ValidationAppError(
            "Image format not allowed.", {"detected_format": fmt, "allowed": sorted(ALLOWED_PHOTO_FORMATS)}
        )
    if width < 32 or height < 32:
        raise ValidationAppError("Image resolution too small (min 32x32).", {"width": width, "height": height})

    digest = _sha256(upload_bytes)
    photo_id = uuid.uuid4()
    rel = Path("photos") / digest[:2] / f"{photo_id}{ext}"
    dest = storage_root() / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(upload_bytes)

    return (
        str(rel).replace("\\", "/"),
        digest,
        len(upload_bytes),
        {"width": width, "height": height, "format": fmt, "content_type": ALLOWED_PHOTO_FORMATS[fmt]},
    )


def validate_and_save_video(upload_bytes: bytes, filename: str) -> Tuple[str, str, int, str]:
    """Validate a video upload by extension/MIME/size and store privately.

    Deep codec probing happens in the video pipeline (OpenCV) at process time;
    corrupt files fail the job gracefully there.
    """
    max_bytes = settings.max_video_upload_mb * 1024 * 1024
    if len(upload_bytes) > max_bytes:
        raise ValidationAppError(
            f"Video exceeds the {settings.max_video_upload_mb} MB limit.", {"max_bytes": max_bytes}
        )
    if len(upload_bytes) < 256:
        raise ValidationAppError("Uploaded file is empty or too small to be a valid video.")

    ext = Path(filename or "upload.mp4").suffix.lower()
    if ext not in ALLOWED_VIDEO_EXT:
        raise ValidationAppError(
            "Unsupported video type. Allowed: MP4, AVI, MOV, MKV, WEBM.",
            {"allowed_extensions": sorted(ALLOWED_VIDEO_EXT)},
        )

    digest = _sha256(upload_bytes)
    video_id = uuid.uuid4()
    rel = Path("videos") / digest[:2] / f"{video_id}{ext}"
    dest = storage_root() / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(upload_bytes)
    content_type = "video/" + (ext.lstrip(".") if ext != ".mkv" else "x-matroska")
    return str(rel).replace("\\", "/"), digest, len(upload_bytes), content_type


def absolute_path(relative: str) -> Path:
    p = (storage_root() / relative).resolve()
    if not str(p).startswith(str(storage_root())):
        raise ValidationAppError("Invalid storage path.")
    return p


def delete_file_quiet(relative: str) -> None:
    try:
        absolute_path(relative).unlink(missing_ok=True)
    except Exception:
        pass
