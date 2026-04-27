from __future__ import annotations

import os
import sys
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.security import get_password_hash
from app.database import SessionLocal
from app.models import (
    AreaManagerAssignment,
    Branch,
    Brand,
    Item,
    KitchenSection,
    KitchenSectionAssignment,
    Role,
    RoleName,
    User,
    UserRole,
    UserStatus,
    Warehouse,
)


PASSWORD = "Raed@2025"


@dataclass(frozen=True)
class DemoUserSpec:
    username: str
    full_name: str
    email: str
    roles: tuple[RoleName, ...]
    branch_code: str | None = None
    warehouse_code: str | None = None
    section_names: tuple[str, ...] = ()
    # When set, kitchen section assignments are limited to this city (matches branch.city).
    kitchen_service_city: str | None = None
    area_scope: tuple[tuple[str, tuple[str, ...]], ...] = ()


USERS: tuple[DemoUserSpec, ...] = (
    DemoUserSpec("super.admin", "Super Admin", "super.admin@raed.com", (RoleName.super_admin,)),
    DemoUserSpec("admin", "System Administrator", "admin@raed.com", (RoleName.admin,)),
    # Prefer official branch codes when seeded (seed_official_branches.py).
    DemoUserSpec("branch_onda", "Branch Onda", "branch_onda@raed.com", (RoleName.branch_user, RoleName.branch_manager), branch_code="BR-RY-ON-MALQA"),
    DemoUserSpec("branch_ronaldos", "Branch Ronaldos", "branch_ronaldos@raed.com", (RoleName.branch_user, RoleName.branch_manager), branch_code="BR-RY-RN-ULAYA"),
    DemoUserSpec("branch_shawarma", "Branch Shawarma", "branch_shawarma@raed.com", (RoleName.branch_user, RoleName.branch_manager), branch_code="BR-RY-SH-OLAYA"),
    DemoUserSpec("branch_griddle", "Branch Griddle", "branch_griddle@raed.com", (RoleName.branch_user, RoleName.branch_manager), branch_code="BR-RY-SH-OLAYA"),
    DemoUserSpec("area_dammam_onda", "Area Dammam Onda", "area_dammam_onda@raed.com", (RoleName.area_manager,), area_scope=(("Dammam", ("Onda",)),)),
    DemoUserSpec("area_dammam_restaurants", "Area Dammam Restaurants", "area_dammam_restaurants@raed.com", (RoleName.area_manager,), area_scope=(("Dammam", ("Ronaldos", "Shawarma", "Griddle")),)),
    DemoUserSpec("area_riyadh_all", "Area Riyadh All Brands", "area_riyadh_all@raed.com", (RoleName.area_manager,), area_scope=(("Riyadh", ("Onda", "Ronaldos", "Shawarma", "Griddle")),)),
    DemoUserSpec("kitchen_manager", "Kitchen Manager", "kitchen_manager@raed.com", (RoleName.kitchen_manager, RoleName.kitchen_section_manager), section_names=("Meat & Chicken", "Bakery & Sweets", "Pizza"), kitchen_service_city="Riyadh"),
    DemoUserSpec("meat_manager", "Meat Manager", "meat_manager@raed.com", (RoleName.kitchen_section_manager,), section_names=("Meat & Chicken",), kitchen_service_city="Riyadh"),
    DemoUserSpec("bakery_sweets_manager", "Bakery & Sweets Manager", "bakery_sweets_manager@raed.com", (RoleName.kitchen_section_manager,), section_names=("Bakery & Sweets",), kitchen_service_city="Riyadh"),
    DemoUserSpec("pizza_manager", "Pizza Manager", "pizza_manager@raed.com", (RoleName.kitchen_section_manager,), section_names=("Pizza",), kitchen_service_city="Riyadh"),
    DemoUserSpec("warehouse_user", "Warehouse User", "warehouse_user@raed.com", (RoleName.warehouse_user,), warehouse_code="WH-RY-1"),
    DemoUserSpec("delivery_user", "Delivery User", "delivery_user@raed.com", (RoleName.delivery_user,)),
)


ROLE_META: dict[RoleName, tuple[str, str | None]] = {
    RoleName.super_admin: ("Super Administrator", "Full system access"),
    RoleName.admin: ("System Administrator", "Administrative access"),
    RoleName.branch_user: ("Branch User", "Branch request entry"),
    RoleName.branch_manager: ("Branch Manager", "Branch management and review"),
    RoleName.area_manager: ("Area Manager", "City + brand scoped approval"),
    RoleName.kitchen_manager: ("Kitchen Manager", "Legacy kitchen overview role"),
    RoleName.kitchen_section_manager: ("Kitchen Section Manager", "Kitchen execution scoped by section"),
    RoleName.warehouse_user: ("Warehouse User", "Warehouse execution"),
    RoleName.delivery_user: ("Delivery User", "Delivery execution"),
}


LEGACY_USER_ALIASES: dict[str, str] = {
    "am_riyadh": "area_riyadh_all",
    "am_dammam_cafes": "area_dammam_onda",
    "am_dammam_restaurants": "area_dammam_restaurants",
    "meat.section.mgr": "meat_manager",
    "bakery.section.mgr": "bakery_sweets_manager",
    "pizza.section.mgr": "pizza_manager",
    "wh.user1": "warehouse_user",
    "delivery.user": "delivery_user",
}


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
    existing_role_ids = {ur.role_id for ur in user.user_roles}
    for role_name in roles:
        role = get_or_create_role(db, role_name)
        if role.id not in existing_role_ids:
            db.add(UserRole(user_id=user.id, role_id=role.id))
    db.flush()


def get_or_create_user(db, spec: DemoUserSpec) -> User:
    user = db.query(User).filter(User.username == spec.username).first()
    if not user:
        user = User(
            username=spec.username,
            email=spec.email,
            full_name=spec.full_name,
            hashed_password=get_password_hash(PASSWORD),
            status=UserStatus.active,
            is_deleted=False,
        )
        db.add(user)
        db.flush()
    user.full_name = spec.full_name
    user.email = spec.email
    user.hashed_password = get_password_hash(PASSWORD)
    user.status = UserStatus.active
    user.is_deleted = False
    ensure_user_roles(db, user, spec.roles)
    return user


def get_branch(db, code: str) -> Branch:
    row = db.query(Branch).filter(Branch.branch_code == code, Branch.is_deleted == False).first()
    if not row:
        raise RuntimeError(f"Branch '{code}' not found")
    return row


def get_warehouse(db, code: str) -> Warehouse:
    row = db.query(Warehouse).filter(Warehouse.warehouse_code == code, Warehouse.is_deleted == False).first()
    if not row:
        raise RuntimeError(f"Warehouse '{code}' not found")
    return row


def get_brand(db, name: str) -> Brand:
    row = db.query(Brand).filter(Brand.name == name).first()
    if not row:
        raise RuntimeError(f"Brand '{name}' not found")
    return row


def get_section(db, name: str) -> KitchenSection:
    row = db.query(KitchenSection).filter(KitchenSection.name == name).first()
    if not row:
        raise RuntimeError(f"Kitchen section '{name}' not found")
    return row


def ensure_area_assignment(db, user: User, city: str, brand_name: str) -> None:
    brand = get_brand(db, brand_name)
    row = db.query(AreaManagerAssignment).filter(
        AreaManagerAssignment.user_id == user.id,
        AreaManagerAssignment.city == city,
        AreaManagerAssignment.brand_id == brand.id,
        AreaManagerAssignment.active == True,
    ).first()
    if row:
        return
    db.add(AreaManagerAssignment(user_id=user.id, city=city, brand_id=brand.id, active=True))
    db.flush()


def ensure_section_assignment(db, user: User, section_name: str, service_city: str | None = None) -> None:
    section = get_section(db, section_name)
    row = db.query(KitchenSectionAssignment).filter(
        KitchenSectionAssignment.user_id == user.id,
        KitchenSectionAssignment.kitchen_section_id == section.id,
        KitchenSectionAssignment.active == True,
    ).first()
    city_val = (service_city or "").strip() or None
    if row:
        if city_val and row.service_city != city_val:
            row.service_city = city_val
            db.flush()
        return
    db.add(KitchenSectionAssignment(user_id=user.id, kitchen_section_id=section.id, active=True, service_city=city_val))
    db.flush()


def hide_demo_items(db) -> int:
    rows = db.query(Item).filter(Item.item_code.like("DEMO-%")).all()
    for row in rows:
        row.branch_requestable = False
        row.visible_in_branch_ui = False
        row.active = True
    db.flush()
    return len(rows)


def main() -> int:
    db = SessionLocal()
    try:
        hidden = hide_demo_items(db)
        activated = 0
        for spec in USERS:
            user = get_or_create_user(db, spec)
            user.branch_id = None
            user.warehouse_id = None
            if spec.branch_code:
                user.branch_id = get_branch(db, spec.branch_code).id
            if spec.warehouse_code:
                user.warehouse_id = get_warehouse(db, spec.warehouse_code).id
            for city, brands in spec.area_scope:
                for brand_name in brands:
                    ensure_area_assignment(db, user, city, brand_name)
            for section_name in spec.section_names:
                ensure_section_assignment(db, user, section_name, service_city=spec.kitchen_service_city)
            activated += 1
        alias_pairs = 0
        for legacy_username, canonical_username in LEGACY_USER_ALIASES.items():
            legacy_user = db.query(User).filter(User.username == legacy_username).first()
            canonical_user = db.query(User).filter(User.username == canonical_username).first()
            if legacy_user and canonical_user:
                alias_pairs += 1
        db.commit()
        print(f"activated_users={activated}")
        print(f"hidden_demo_items={hidden}")
        print(f"legacy_alias_pairs={alias_pairs}")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
