"""Seed synthetic DEMO data (clearly labelled, isolated from real cases).

Every record created here sets is_demo=True and every generated image carries a
"SYNTHETIC DEMO DATA" label. Demo matches are never presented as real
identifications. Requires no external services or credentials.

Usage:
    python scripts/seed_demo.py
"""
from __future__ import annotations

import io
import random
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw  # noqa: E402

from backend.app.core.config import settings  # noqa: E402
from backend.app.core.security import hash_password  # noqa: E402
from backend.app.db.init_db import init_db  # noqa: E402
from backend.app.db.session import SessionLocal  # noqa: E402
from backend.app.models import (  # noqa: E402
    CaseStatusHistory,
    MissingPersonCase,
    PersonPhoto,
    Role,
    User,
    utcnow,
)
from backend.app.services.storage import validate_and_save_photo  # noqa: E402

DEMO_PROFILES = [
    ("Demo Person Alpha", 22, 26, "Last seen near Central Station demo area", "blue jacket, jeans"),
    ("Demo Person Beta", 40, 45, "Demo park district", "grey coat, black shoes"),
    ("Demo Person Gamma", 15, 17, "Demo school neighborhood", "red hoodie, backpack"),
    (None, 30, 35, "Unknown location (demo)", "olive jacket"),
]


def synthetic_portrait(seed: int, label: str) -> bytes:
    """Generate a clearly synthetic portrait-like image (NOT a real person)."""
    rng = random.Random(seed)
    img = Image.new("RGB", (480, 640), (rng.randint(40, 220), rng.randint(40, 220), rng.randint(40, 220)))
    d = ImageDraw.Draw(img)
    # Simple abstract "portrait" shapes — obviously synthetic.
    d.ellipse([140, 120, 340, 380], fill=(255, 224, 196))
    d.rectangle([170, 420, 310, 640], fill=(rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255)))
    d.ellipse([190, 210, 230, 250], fill=(60, 60, 60))
    d.ellipse([250, 210, 290, 250], fill=(60, 60, 60))
    d.arc([200, 260, 280, 320], 20, 160, fill=(120, 60, 60), width=6)
    d.rectangle([0, 600, 480, 640], fill=(200, 30, 30))
    d.text((12, 8), "SYNTHETIC DEMO DATA — NOT A REAL PERSON", fill=(255, 255, 255))
    d.text((12, 608), label, fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def main() -> int:
    random.seed(42)
    settings.validate_startup()
    init_db()
    db = SessionLocal()
    try:
        # Demo users (passwords are local-demo only).
        role_inv = db.query(Role).filter(Role.name == "investigator").first()
        role_rescue = db.query(Role).filter(Role.name == "rescue_team").first()
        demo_users = []
        for email, name, role in [
            ("investigator.demo@example.com", "Demo Investigator", role_inv),
            ("rescue.demo@example.com", "Demo Rescue Team", role_rescue),
        ]:
            u = db.query(User).filter(User.email == email).first()
            if not u:
                u = User(
                    email=email,
                    full_name=name,
                    hashed_password=hash_password("DemoPass!234"),
                    role_id=role.id,
                    agency="Demo Agency (synthetic)",
                )
                db.add(u)
                db.commit()
            demo_users.append(u)

        for i, (name, age_min, age_max, loc, clothing) in enumerate(DEMO_PROFILES):
            case_number = f"DEMO-2026-{i+1:04d}"
            case = db.query(MissingPersonCase).filter(MissingPersonCase.case_number == case_number).first()
            if case:
                print(f"[skip] {case_number}")
                continue
            case = MissingPersonCase(
                case_number=case_number,
                full_name=name,
                name_unknown=name is None,
                age_min=age_min,
                age_max=age_max,
                last_seen_date=date.today() - timedelta(days=3 + i),
                last_seen_location=loc + " (SYNTHETIC DEMO)",
                physical_description="Synthetic demo record. Physical details are fabricated for testing.",
                clothing_description=clothing + " (demo)",
                contact_agency="Demo Agency (synthetic)",
                contact_info="demo@example.invalid",
                status="missing",
                consent_recorded=True,
                legal_basis="Synthetic demo data — no real person involved.",
                authorization_reference="DEMO-SEED",
                is_demo=True,
                created_by=demo_users[0].id,
                owned_by=demo_users[0].id,
            )
            db.add(case)
            db.flush()
            db.add(
                CaseStatusHistory(
                    case_id=case.id,
                    from_status=None,
                    to_status="missing",
                    note="Seeded synthetic demo case.",
                    changed_by=demo_users[0].id,
                    created_at=utcnow(),
                )
            )
            img_bytes = synthetic_portrait(seed=100 + i, label=f"DEMO {case_number}")
            rel, sha, size, meta = validate_and_save_photo(img_bytes, f"demo_{case_number}.jpg")
            db.add(
                PersonPhoto(
                    case_id=case.id,
                    file_path=rel,
                    original_filename=f"demo_{case_number}.jpg",
                    content_type="image/jpeg",
                    file_size=size,
                    sha256=sha,
                    is_primary=True,
                    width=meta["width"],
                    height=meta["height"],
                    uploaded_by=demo_users[0].id,
                )
            )
            db.commit()
            print(f"[ ok ] seeded {case_number} ({name or 'name unknown'})")

        print(
            "\nDemo data ready. Demo accounts (local demo only):\n"
            "  investigator.demo@example.com / DemoPass!234\n"
            "  rescue.demo@example.com / DemoPass!234\n"
            "All demo records are flagged is_demo=true and labelled in the UI."
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
