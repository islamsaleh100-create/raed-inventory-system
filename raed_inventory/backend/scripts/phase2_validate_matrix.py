"""One-off Phase 2 matrix validation — prints JSON-ish summary for report."""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func

from app.database import SessionLocal
from app.models import (
    AreaManagerAssignment,
    Branch,
    Brand,
    KitchenSection,
    KitchenSectionAssignment,
    Role,
    User,
    Warehouse,
)
from seed_phase2_official_users import (
    ADMIN_USERS,
    CANONICAL_AREA_MANAGERS,
    DELIVERY_USERS,
    FUTURE_KITCHEN_MANAGERS,
    KITCHEN_SECTION_USERS,
    LEGACY_AREA_MANAGERS,
    OFFICIAL_BRANCH_USERS,
    WAREHOUSE_USERS,
)


def main() -> None:
    db = SessionLocal()
    try:
        required_roles = [
            "super_admin",
            "admin",
            "area_manager",
            "branch_user",
            "kitchen_section_manager",
            "warehouse_manager",
            "warehouse_user",
            "delivery_user",
        ]
        role_map = {r.name.value: r.display_name for r in db.query(Role).all()}
        out = {
            "roles": {r: r in role_map for r in required_roles},
            "role_mappings": {
                "SUPER_ADMIN": "super_admin",
                "ADMIN": "admin",
                "AREA_MANAGER": "area_manager",
                "BRANCH_USER": "branch_user (+ branch_manager for official branch users)",
                "KITCHEN_SECTION_MANAGER": "kitchen_section_manager",
                "WAREHOUSE_MANAGER": "warehouse_manager",
                "WAREHOUSE_USER": "warehouse_user",
                "DELIVERY_USER": "delivery_user",
            },
            "kitchen_manager_future_role": "ABSENT",
            "users_verified": [],
            "failed_users": [],
            "legacy_area_managers": {},
            "area_assignments": {},
            "branch_mappings": [],
            "kitchen_sections": {},
            "kitchen_users": [],
            "warehouse_users": [],
            "delivery_users": [],
            "future_kitchen_managers": [],
            "duplicate_usernames": [],
        }

        if "kitchen_manager_future" in role_map:
            out["kitchen_manager_future_role"] = "PRESENT (unexpected)"

        all_official = (
            list(ADMIN_USERS)
            + list(CANONICAL_AREA_MANAGERS)
            + list(OFFICIAL_BRANCH_USERS)
            + list(KITCHEN_SECTION_USERS)
            + list(WAREHOUSE_USERS)
            + list(DELIVERY_USERS)
        )

        for username in all_official:
            user = db.query(User).filter(User.username == username, User.is_deleted == False).first()
            if not user:
                out["failed_users"].append({"username": username, "reason": "not_found"})
                continue
            status = getattr(user.status, "value", user.status)
            roles = [ur.role.name.value for ur in user.user_roles]
            out["users_verified"].append(
                {
                    "username": username,
                    "active": status == "active",
                    "roles": roles,
                    "branch_id": user.branch_id,
                    "warehouse_id": user.warehouse_id,
                }
            )

        for legacy in LEGACY_AREA_MANAGERS:
            user = db.query(User).filter(User.username == legacy).first()
            if not user:
                out["legacy_area_managers"][legacy] = "not_found"
            else:
                status = getattr(user.status, "value", user.status)
                active_assignments = (
                    db.query(AreaManagerAssignment)
                    .filter(
                        AreaManagerAssignment.user_id == user.id,
                        AreaManagerAssignment.active == True,
                    )
                    .count()
                )
                out["legacy_area_managers"][legacy] = {
                    "status": status,
                    "active_assignments": active_assignments,
                }

        for am_username, scopes in CANONICAL_AREA_MANAGERS.items():
            user = db.query(User).filter(User.username == am_username).first()
            if not user:
                continue
            rows = []
            for a in (
                db.query(AreaManagerAssignment)
                .filter(
                    AreaManagerAssignment.user_id == user.id,
                    AreaManagerAssignment.active == True,
                )
                .all()
            ):
                brand = db.query(Brand).filter(Brand.id == a.brand_id).first()
                rows.append({"city": a.city, "brand": brand.name if brand else None, "brand_id": a.brand_id})
            out["area_assignments"][am_username] = rows

        for username, branch_code in OFFICIAL_BRANCH_USERS.items():
            user = db.query(User).filter(User.username == username).first()
            branch = db.query(Branch).filter(Branch.branch_code == branch_code).first()
            issue = None
            if not user:
                issue = "user_missing"
            elif not branch:
                issue = "branch_code_missing"
            elif user.branch_id != branch.id:
                issue = f"branch_id_mismatch user={user.branch_id} expected={branch.id}"
            elif not branch.active:
                issue = "branch_inactive"
            out["branch_mappings"].append(
                {
                    "username": username,
                    "branch_code": branch_code,
                    "branch_name": branch.branch_name if branch else None,
                    "city": branch.city if branch else None,
                    "active": branch.active if branch else None,
                    "issue": issue,
                }
            )

        for section_name in ("Meat & Chicken", "Bakery & Sweets", "Pizza"):
            out["kitchen_sections"][section_name] = (
                db.query(KitchenSection).filter(KitchenSection.name == section_name).count()
            )

        kitchen_as_branch = (
            db.query(Branch)
            .filter(Branch.branch_name.ilike("%kitchen%"), Branch.is_deleted == False)
            .count()
        )
        out["kitchens_not_branches"] = kitchen_as_branch == 0

        for username, (city, section_name) in KITCHEN_SECTION_USERS.items():
            user = db.query(User).filter(User.username == username).first()
            assignment = None
            if user:
                assignment = (
                    db.query(KitchenSectionAssignment)
                    .filter(
                        KitchenSectionAssignment.user_id == user.id,
                        KitchenSectionAssignment.active == True,
                    )
                    .first()
                )
            section = db.query(KitchenSection).filter(KitchenSection.name == section_name).first()
            out["kitchen_users"].append(
                {
                    "username": username,
                    "section": section_name,
                    "service_city": assignment.service_city if assignment else None,
                    "section_id": section.id if section else None,
                }
            )

        for username, (wh_code, _) in WAREHOUSE_USERS.items():
            user = db.query(User).filter(User.username == username).first()
            wh = db.query(Warehouse).filter(Warehouse.warehouse_code == wh_code).first()
            out["warehouse_users"].append(
                {
                    "username": username,
                    "warehouse_code": wh_code,
                    "warehouse_id": user.warehouse_id if user else None,
                    "expected_wh_id": wh.id if wh else None,
                    "city": wh.location if wh else None,
                    "match": user and wh and user.warehouse_id == wh.id,
                }
            )

        for username, wh_code in DELIVERY_USERS.items():
            user = db.query(User).filter(User.username == username).first()
            wh = db.query(Warehouse).filter(Warehouse.warehouse_code == wh_code).first()
            out["delivery_users"].append(
                {
                    "username": username,
                    "warehouse_code": wh_code,
                    "warehouse_id": user.warehouse_id if user else None,
                    "has_scope": bool(user and user.warehouse_id),
                }
            )

        for username in FUTURE_KITCHEN_MANAGERS:
            user = db.query(User).filter(User.username == username).first()
            status = getattr(user.status, "value", user.status) if user else None
            out["future_kitchen_managers"].append({"username": username, "status": status})

        dups = (
            db.query(User.username, func.count(User.id))
            .filter(User.is_deleted == False)
            .group_by(User.username)
            .having(func.count(User.id) > 1)
            .all()
        )
        out["duplicate_usernames"] = [{"username": u, "count": c} for u, c in dups]

        out_path = os.environ.get("PHASE2_MATRIX_OUT")
        payload = json.dumps(out, indent=2, ensure_ascii=False)
        if out_path:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(payload)
        print(payload)
    finally:
        db.close()


if __name__ == "__main__":
    main()
