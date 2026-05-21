#!/usr/bin/env python3
"""Create or update the admin user in Supabase Auth."""

import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / "api" / ".env")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@market.in")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Market@123")


def main() -> int:
    if not SUPABASE_URL or not SERVICE_KEY:
        print("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in api/.env", file=sys.stderr)
        return 1

    headers = {
        "Authorization": f"Bearer {SERVICE_KEY}",
        "apikey": SERVICE_KEY,
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=30) as client:
        list_resp = client.get(
            f"{SUPABASE_URL}/auth/v1/admin/users",
            headers=headers,
            params={"email": ADMIN_EMAIL},
        )
        list_resp.raise_for_status()
        users = list_resp.json().get("users", [])

        if users:
            user_id = users[0]["id"]
            resp = client.put(
                f"{SUPABASE_URL}/auth/v1/admin/users/{user_id}",
                headers=headers,
                json={
                    "email": ADMIN_EMAIL,
                    "password": ADMIN_PASSWORD,
                    "email_confirm": True,
                    "user_metadata": {"role": "admin"},
                },
            )
            action = "updated"
        else:
            resp = client.post(
                f"{SUPABASE_URL}/auth/v1/admin/users",
                headers=headers,
                json={
                    "email": ADMIN_EMAIL,
                    "password": ADMIN_PASSWORD,
                    "email_confirm": True,
                    "user_metadata": {"role": "admin"},
                },
            )
            action = "created"

        if resp.status_code >= 400:
            print(f"Failed: {resp.status_code} {resp.text}", file=sys.stderr)
            return 1

        print(f"Admin user {action}: {ADMIN_EMAIL}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
