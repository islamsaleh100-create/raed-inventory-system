from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models import Branch, User, Warehouse


CITY_WAREHOUSE_CODES: dict[str, str] = {
    "riyadh": "WH-RY-1",
    "dammam": "WH-DM-1",
}

USER_CITY_MAP: dict[str, str] = {
    "warehouse_dammam_manager": "dammam",
    "warehouse_dammam_user": "dammam",
    "delivery_dammam": "dammam",
    "warehouse_riyadh_manager": "riyadh",
    "warehouse_riyadh_user": "riyadh",
    "delivery_riyadh": "riyadh",
    "warehouse_user": "riyadh",
    "delivery_user": "riyadh",
}


def normalize(value: str | None) -> str:
    return (value or "").strip().lower()


def main() -> int:
    db = SessionLocal()
    try:
        warehouse_by_city: dict[str, Warehouse] = {}
        for city, code in CITY_WAREHOUSE_CODES.items():
            wh = db.query(Warehouse).filter(
                Warehouse.warehouse_code == code,
                Warehouse.is_deleted == False,
            ).first()
            if not wh:
                raise RuntimeError(f"Warehouse '{code}' not found for city '{city}'")
            warehouse_by_city[city] = wh

        branch_updates = 0
        for branch in db.query(Branch).filter(Branch.is_deleted == False, Branch.active == True).all():
            city = normalize(branch.city)
            wh = warehouse_by_city.get(city)
            if wh and branch.warehouse_id != wh.id:
                branch.warehouse_id = wh.id
                branch_updates += 1

        user_updates = 0
        for username, city in USER_CITY_MAP.items():
            user = db.query(User).filter(User.username == username, User.is_deleted == False).first()
            wh = warehouse_by_city.get(city)
            if user and wh and user.warehouse_id != wh.id:
                user.warehouse_id = wh.id
                user_updates += 1

        db.commit()
        print(f"branch_updates={branch_updates}")
        print(f"user_updates={user_updates}")
        for username in sorted(USER_CITY_MAP):
            user = db.query(User).filter(User.username == username).first()
            print(f"{username}|warehouse_id={user.warehouse_id if user else None}")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
