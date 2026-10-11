#!/usr/bin/env python3
"""Create or update one SQLArena admin in MongoDB."""
from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from auth import hash_password  # noqa: E402
from mongo_store import get_store  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Create SQLArena admin user")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password")
    args = parser.parse_args()
    password = args.password or getpass.getpass("Admin password: ")
    confirm = args.password or getpass.getpass("Repeat password: ")
    if password != confirm:
        parser.error("passwords do not match")
    try:
        password_hash = hash_password(password)
    except ValueError as exc:
        parser.error(str(exc))
    store = get_store()
    existing = store.find_user_by_email(args.email)
    user = store.save_user({
        "id": existing.get("id") if existing else None,
        "email": args.email,
        "password_hash": password_hash,
        "role": "admin",
        "status": "active",
    })
    print(f"Admin ready: {user['email']} ({store.mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
