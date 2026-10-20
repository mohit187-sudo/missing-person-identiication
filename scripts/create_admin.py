"""Create the first administrator account securely.

Usage:
    python scripts/create_admin.py --email admin@example.com --password 'STRONG-PASS'
    python scripts/create_admin.py            # interactive prompts (hidden input)
"""
from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.core.config import settings  # noqa: E402
from backend.app.db.init_db import create_admin, init_db  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Create the first administrator account.")
    parser.add_argument("--email", default=None)
    parser.add_argument("--password", default=None, help="Min 10 characters.")
    parser.add_argument("--full-name", default="Administrator")
    args = parser.parse_args()

    settings.validate_startup()
    init_db()

    email = args.email or input("Administrator email: ").strip()
    password = args.password or getpass.getpass("Password (min 10 chars): ")
    if len(password) < 10:
        print("Password must be at least 10 characters.", file=sys.stderr)
        return 1

    user = create_admin(email=email, password=password, full_name=args.full_name)
    print(f"Administrator ready: {user.email} ({user.role_name})")
    print("Sign in at the frontend /api/v1/auth/login endpoint.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
