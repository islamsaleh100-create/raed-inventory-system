"""
Phase 2 — Official user & scope matrix seed (local/dev only).

Idempotent. Ensures official usernames, assignments, and legacy area-manager migration.

Password: env PHASE2_DEMO_PASSWORD (default Raed@Demo2026) — local/dev only.

Prerequisites (run once):
  python seed_supply_chain_demo.py   # brands, sections, base roles
  python seed_official_branches.py
  python backfill_official_kitchens.py

Usage (from backend/):
  python seed_phase2_official_users.py
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.security import get_password_hash
from app.database import SessionLocal
from app.models import (
    AreaManagerAssignment,
    Branch,
    Brand,
    KitchenSection,
    KitchenSectionAssignment,
    Role,
    RoleName,
    User,
    UserRole,
    UserStatus,
    Warehouse,
)

DEMO_PASSWORD = os.environ.get("PHASE2_DEMO_PASSWORD", "Raed@Demo2026")

# Legacy area managers → deactivate after copying assignments to canonical targets.
LEGACY_AREA_MANAGERS: tuple[str, ...] = (
    "am_riyadh",
    "am_dammam",
    "am_dammam_cafes",
)

CANONICAL_AREA_MANAGERS: dict[str, list[tuple[str, str]]] = {
    "area_dammam_onda": [("Dammam", "Onda")],
    "area_dammam_restaurants": [
        ("Dammam", "Ronaldos"),
        ("Dammam", "Shawarma"),
        ("Dammam", "Griddle"),
    ],
    "area_riyadh_all": [
        ("Riyadh", "Onda"),
        ("Riyadh", "Ronaldos"),
        ("Riyadh", "Shawarma"),
        ("Riyadh", "Griddle"),
    ],
}

OFFICIAL_BRANCH_USERS: dict[str, str] = {
    "branch_onda_1_arkan": "BR-DM-ON-ARKAN",
    "branch_onda_13_al_malqa": "BR-RY-ON-MALQA",
    "branch_onda_14_hassa": "BR-DM-ON-HASSA",
    "branch_onda_16_najmah": "BR-DM-ON-NAJMA",
    "branch_onda_18_al_midra_gym": "BR-DM-ON-MIDRA",
    "branch_onda_2_hoqail": "BR-DM-ON-HOQAI",
    "branch_onda_4_sefarat": "BR-RY-ON-SEFAR",
    "branch_onda_5_muowasat": "BR-DM-ON-MUOWA",
    "branch_onda_9_ras_tanura": "BR-DM-ON-RASTN",
    "branch_onda_dau_university": "BR-DM-ON-DAU",
    "branch_pizza_1_al_khobar": "BR-DM-RN-KHOBR",
    "branch_pizza_10_mazaar": "BR-DM-RN-MAZAR",
    "branch_pizza_15_ras_tanura": "BR-DM-RN-RASTN",
    "branch_pizza_3_arkan": "BR-DM-RN-ARKAN",
    "branch_pizza_4_riyadh_takhasosy": "BR-RY-RN-TAKHS",
    "branch_pizza_5_al_ulaya": "BR-RY-RN-ULAYA",
    "branch_pizza_6_riyadh_nada": "BR-RY-RN-NADA",
    "branch_pizza_7_aramco": "BR-DM-RN-ARAMC",
    "branch_pizza_9_al_azizia": "BR-DM-RN-AZIZI",
    "branch_ronaldos_dau_university": "BR-DM-RN-DAU",
    "branch_shawarma_1_khobar": "BR-DM-SH-KHOBR",
    "branch_shawarma_4_arkan": "BR-DM-SH-ARKAN",
    "branch_shawarma_olaya": "BR-RY-SH-OLAYA",
}

KITCHEN_SECTION_USERS: dict[str, tuple[str, str]] = {
    "kitchen_dammam_meat_and_chicken_mgr": ("Dammam", "Meat & Chicken"),
    "kitchen_dammam_bakery_and_sweets_mgr": ("Dammam", "Bakery & Sweets"),
    "kitchen_dammam_pizza_mgr": ("Dammam", "Pizza"),
    "kitchen_riyadh_meat_and_chicken_mgr": ("Riyadh", "Meat & Chicken"),
    "kitchen_riyadh_bakery_and_sweets_mgr": ("Riyadh", "Bakery & Sweets"),
    "kitchen_riyadh_pizza_mgr": ("Riyadh", "Pizza"),
}

FUTURE_KITCHEN_MANAGERS: tuple[str, ...] = (
    "kitchen_dammam_manager_future",
    "kitchen_riyadh_manager_future",
)

WAREHOUSE_USERS: dict[str, tuple[str, RoleName]] = {
    "warehouse_dammam_manager": ("WH-DM-1", RoleName.warehouse_manager),
    "warehouse_dammam_user": ("WH-DM-1", RoleName.warehouse_user),
    "warehouse_riyadh_manager": ("WH-RY-1", RoleName.warehouse_manager),
    "warehouse_riyadh_user": ("WH-RY-1", RoleName.warehouse_user),
}

DELIVERY_USERS: dict[str, str] = {
    "delivery_dammam": "WH-DM-1",
    "delivery_riyadh": "WH-RY-1",
}

ADMIN_USERS: dict[str, RoleName] = {
    "super.admin": RoleName.super_admin,
    "admin": RoleName.admin,
}

ROLE_META: dict[RoleName, tuple[str, str | None]] = {
    RoleName.super_admin: ("Super Administrator", "Full system access"),
    RoleName.admin: ("System Administrator", "Administrative access"),
    RoleName.branch_user: ("Branch User", "Branch request entry"),
    RoleName.branch_manager: ("Branch Manager", "Branch management and review"),
    RoleName.area_manager: ("Area Manager", "City + brand scoped approval"),
    RoleName.kitchen_section_manager: ("Kitchen Section Manager", "Kitchen execution scoped by section"),
    RoleName.warehouse_manager: ("Warehouse Manager", "Warehouse oversight"),
    RoleName.warehouse_user: ("Warehouse User", "Warehouse execution"),
    RoleName.delivery_user: ("Delivery User", "Delivery execution"),
}


@dataclass
class MigrationRecord:
    legacy_username: str
    assignments_copied: int
    deactivated: bool


def get_or_create_role(db, role_name: RoleName) -> Role:
    row = db.query(Role).filter(Role.name == role_name).first()
    if row:
        return row
    display_name, description = ROLE_META.get(role_name, (role_name.value.replace("_", " ").title(), None))
    row = Role(name=role_name, display_name=display_name, description=description)
    db.add(row)
    db.flush()
    return row


def ensure_user_roles(db, user: User, roles: tuple[RoleName, ...]) -> None:
    existing = {ur.role_id for ur in user.user_roles}
    for role_name in roles:
        role = get_or_create_role(db, role_name)
        if role.id not in existing:
            db.add(UserRole(user_id=user.id, role_id=role.id))


def upsert_user(
    db,
    username: str,
    *,
    full_name: str,
    email: str,
    roles: tuple[RoleName, ...],
    active: bool = True,
) -> User:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        user = User(
            username=username,
            email=email,
            full_name=full_name,
            hashed_password=get_password_hash(DEMO_PASSWORD),
            status=UserStatus.active if active else UserStatus.inactive,
            is_deleted=False,
        )
        db.add(user)
        db.flush()
    user.email = email
    user.full_name = full_name
    user.hashed_password = get_password_hash(DEMO_PASSWORD)
    user.status = UserStatus.active if active else UserStatus.inactive
    user.is_deleted = False
    ensure_user_roles(db, user, roles)
    return user


def get_branch(db, code: str) -> Branch:
    row = db.query(Branch).filter(Branch.branch_code == code, Branch.is_deleted == False).first()  # noqa: E712
    if not row:
        raise RuntimeError(f"Branch '{code}' not found — run seed_official_branches.py first")
    return row


def get_warehouse(db, code: str) -> Warehouse:
    row = db.query(Warehouse).filter(Warehouse.warehouse_code == code, Warehouse.is_deleted == False).first()  # noqa: E712
    if not row:
        raise RuntimeError(f"Warehouse '{code}' not found — run seed_official_branches.py first")
    return row


def get_brand(db, name: str) -> Brand:
    row = db.query(Brand).filter(Brand.name == name).first()
    if not row:
        raise RuntimeError(f"Brand '{name}' not found — run seed_supply_chain_demo.py first")
    return row


def get_section(db, name: str) -> KitchenSection:
    row = db.query(KitchenSection).filter(KitchenSection.name == name).first()
    if not row:
        raise RuntimeError(f"Kitchen section '{name}' not found")
    return row


def ensure_area_assignment(db, user: User, city: str, brand_name: str) -> bool:
    brand = get_brand(db, brand_name)
    row = db.query(AreaManagerAssignment).filter(
        AreaManagerAssignment.user_id == user.id,
        AreaManagerAssignment.city == city,
        AreaManagerAssignment.brand_id == brand.id,
        AreaManagerAssignment.active == True,  # noqa: E712
    ).first()
    if row:
        return False
    db.add(AreaManagerAssignment(user_id=user.id, city=city, brand_id=brand.id, active=True))
    return True


def ensure_section_assignment(db, user: User, section_name: str, service_city: str) -> bool:
    section = get_section(db, section_name)
    row = db.query(KitchenSectionAssignment).filter(
        KitchenSectionAssignment.user_id == user.id,
        KitchenSectionAssignment.kitchen_section_id == section.id,
        KitchenSectionAssignment.active == True,  # noqa: E712
    ).first()
    if row:
        if row.service_city != service_city:
            row.service_city = service_city
        return False
    db.add(
        KitchenSectionAssignment(
            user_id=user.id,
            kitchen_section_id=section.id,
            active=True,
            service_city=service_city,
        )
    )
    return True


def canonical_username_for_assignment(city: str, brand_name: str) -> str:
    if city == "Riyadh":
        return "area_riyadh_all"
    if city == "Dammam" and brand_name == "Onda":
        return "area_dammam_onda"
    if city == "Dammam":
        return "area_dammam_restaurants"
    return "area_riyadh_all"


def migrate_legacy_area_managers(db) -> list[MigrationRecord]:
    records: list[MigrationRecord] = []
    for legacy_username in LEGACY_AREA_MANAGERS:
        legacy = db.query(User).filter(User.username == legacy_username).first()
        if not legacy:
            records.append(MigrationRecord(legacy_username, 0, False))
            continue

        copied = 0
        assignments = db.query(AreaManagerAssignment).filter(
            AreaManagerAssignment.user_id == legacy.id,
            AreaManagerAssignment.active == True,  # noqa: E712
        ).all()
        for assignment in assignments:
            brand = db.query(Brand).filter(Brand.id == assignment.brand_id).first()
            if not brand:
                continue
            canonical_name = canonical_username_for_assignment(assignment.city, brand.name)
            canonical = upsert_user(
                db,
                canonical_name,
                full_name=canonical_name.replace("_", " ").title(),
                email=f"{canonical_name}@raed.local",
                roles=(RoleName.area_manager,),
                active=True,
            )
            if ensure_area_assignment(db, canonical, assignment.city, brand.name):
                copied += 1
            assignment.active = False
            assignment.ended_at = datetime.utcnow()

        legacy.status = UserStatus.inactive
        legacy.is_deleted = False
        records.append(MigrationRecord(legacy_username, copied, True))
    return records


def seed_official_users(db) -> dict[str, int]:
    stats = {
        "admins": 0,
        "area_managers": 0,
        "branch_users": 0,
        "kitchen_users": 0,
        "warehouse_users": 0,
        "delivery_users": 0,
        "future_inactive": 0,
    }

    for username, role in ADMIN_USERS.items():
        upsert_user(
            db,
            username,
            full_name=username.replace(".", " ").title(),
            email=f"{username}@raed.local",
            roles=(role,),
        )
        stats["admins"] += 1

    for username, scopes in CANONICAL_AREA_MANAGERS.items():
        user = upsert_user(
            db,
            username,
            full_name=username.replace("_", " ").title(),
            email=f"{username}@raed.local",
            roles=(RoleName.area_manager,),
        )
        user.branch_id = None
        user.warehouse_id = None
        for city, brand_name in scopes:
            ensure_area_assignment(db, user, city, brand_name)
        stats["area_managers"] += 1

    for username, branch_code in OFFICIAL_BRANCH_USERS.items():
        branch = get_branch(db, branch_code)
        user = upsert_user(
            db,
            username,
            full_name=username.replace("_", " ").title(),
            email=f"{username}@raed.local",
            roles=(RoleName.branch_user, RoleName.branch_manager),
        )
        user.branch_id = branch.id
        user.warehouse_id = None
        stats["branch_users"] += 1

    for username, (city, section_name) in KITCHEN_SECTION_USERS.items():
        user = upsert_user(
            db,
            username,
            full_name=username.replace("_", " ").title(),
            email=f"{username}@raed.local",
            roles=(RoleName.kitchen_section_manager,),
        )
        user.branch_id = None
        user.warehouse_id = None
        ensure_section_assignment(db, user, section_name, city)
        stats["kitchen_users"] += 1

    for username, (wh_code, role) in WAREHOUSE_USERS.items():
        wh = get_warehouse(db, wh_code)
        user = upsert_user(
            db,
            username,
            full_name=username.replace("_", " ").title(),
            email=f"{username}@raed.local",
            roles=(role,),
        )
        user.branch_id = None
        user.warehouse_id = wh.id
        stats["warehouse_users"] += 1

    for username, wh_code in DELIVERY_USERS.items():
        wh = get_warehouse(db, wh_code)
        user = upsert_user(
            db,
            username,
            full_name=username.replace("_", " ").title(),
            email=f"{username}@raed.local",
            roles=(RoleName.delivery_user,),
        )
        user.branch_id = None
        user.warehouse_id = wh.id
        stats["delivery_users"] += 1

    for username in FUTURE_KITCHEN_MANAGERS:
        upsert_user(
            db,
            username,
            full_name=username.replace("_", " ").title(),
            email=f"{username}@raed.local",
            roles=(RoleName.kitchen_section_manager,),
            active=False,
        )
        stats["future_inactive"] += 1

    return stats


def main() -> int:
    db = SessionLocal()
    try:
        stats = seed_official_users(db)
        migrations = migrate_legacy_area_managers(db)
        db.commit()
        print("phase2_official_users=ok")
        for key, value in stats.items():
            print(f"  {key}={value}")
        print("legacy_area_manager_migration:")
        for rec in migrations:
            print(f"  {rec.legacy_username}: copied={rec.assignments_copied} deactivated={rec.deactivated}")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
