"""
Set KitchenSectionAssignment.service_city from matrix-style usernames (kitchen_dammam_* / kitchen_riyadh_*).

Idempotent. Run after Alembic adds service_city column.

    python backfill_kitchen_assignment_service_city.py

Does not touch assignments for users that do not match the naming pattern (legacy global scope preserved).
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models import KitchenSectionAssignment, User


def infer_city(username: str) -> str | None:
    m = re.match(r"^kitchen_(dammam|riyadh)_", username, re.I)
    if not m:
        return None
    return m.group(1).capitalize()


def main() -> int:
    db = SessionLocal()
    updated = 0
    try:
        users = db.query(User).filter(User.username.like("kitchen_%"), User.is_deleted == False).all()  # noqa: E712
        for user in users:
            city = infer_city(user.username)
            if not city:
                continue
            rows = (
                db.query(KitchenSectionAssignment)
                .filter(
                    KitchenSectionAssignment.user_id == user.id,
                    KitchenSectionAssignment.active == True,  # noqa: E712
                )
                .all()
            )
            for row in rows:
                if row.service_city != city:
                    row.service_city = city
                    updated += 1
        db.commit()
        print(f"kitchen_assignment_service_city_updates={updated}")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
