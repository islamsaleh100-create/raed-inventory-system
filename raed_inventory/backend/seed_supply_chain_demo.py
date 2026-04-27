"""
Supply Chain V1 — Demo-Ready Seed Script (2026-04-24)

Seeds a complete, deterministic demo environment so a non-technical tester
can run the full flow from the UI:

    Branch creates request -> Area Manager approves (auto-split) ->
    Kitchen Section produces -> Warehouse fulfills -> Delivery completes

Idempotent — safe to run multiple times.

Run from backend/ directory:
    python seed_supply_chain_demo.py

Demo accounts created/ensured (all use password Raed@2025):
    super.admin              — super_admin
    am_riyadh                — area_manager   (Riyadh × all 4 brands)
    am_dammam_cafes          — area_manager   (Dammam × Onda only)
    am_dammam_restaurants    — area_manager   (Dammam × Ronaldos/Shawarma/Griddle)
    branch.mgr1              — branch_manager (existing — re-used)
    branch.user1             — branch_user    (existing — re-used)
    meat.section.mgr         — kitchen_section_manager (Meat & Chicken)
    bakery.section.mgr       — kitchen_section_manager (Bakery & Sweets)
    pizza.section.mgr        — kitchen_section_manager (Pizza)
    wh.mgr1                  — warehouse_manager (existing — re-used)
    wh.user1                 — warehouse_user (existing — re-used)
    delivery.user            — delivery_user

Note: kitchen_manager role is intentionally NOT created. Per Model C of the
Supply Chain spec, there is no separate "kitchen manager" — each section has
its own manager (kitchen_section_manager). Approval is the area_manager's job.
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from decimal import Decimal
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine, Base
from app.core.security import get_password_hash
from app.startup_schema import ensure_local_schema_compatibility
from app.models import (
    AreaManagerAssignment,
    Branch,
    BranchBrand,
    BranchStock,
    Brand,
    Item,
    ItemBrand,
    ItemCategory,
    KitchenSection,
    KitchenSectionAssignment,
    Role,
    RoleName,
    SupplyDefaultSource,
    SupplySourceType,
    UnitOfMeasure,
    User,
    UserRole,
    UserStatus,
    Warehouse,
    WarehouseStock,
)


PASSWORD = "Raed@2025"

ROLE_DEFS = {
    RoleName.super_admin: ("Super Administrator", "Full system access"),
    RoleName.admin: ("System Administrator", "Administrative access"),
    RoleName.branch_user: ("Branch User", "Branch request entry"),
    RoleName.branch_manager: ("Branch Manager", "Branch management and review"),
    RoleName.warehouse_user: ("Warehouse User", "Warehouse execution"),
    RoleName.warehouse_manager: ("Warehouse Manager", "Warehouse oversight"),
    RoleName.area_manager: ("Area Manager", "City + brand scoped approval"),
    RoleName.kitchen_section_manager: ("Kitchen Section Manager", "Kitchen execution scoped by section"),
    RoleName.delivery_user: ("Delivery User", "Delivery execution"),
}


# ─────────────────────────────────────────────
# Seed data
# ─────────────────────────────────────────────

# code, name (for Brand.name field — we only have name)
BRANDS = [
    "Onda",
    "Ronaldos",
    "Shawarma",
    "Griddle",
]

# Kitchen sections — name only (KitchenSection has a `name` field)
KITCHEN_SECTIONS = [
    "Meat & Chicken",
    "Bakery & Sweets",
    "Pizza",
]

# (username, email, full_name, role_name)
DEMO_USERS = [
    ("super.admin",           "super.admin@raed.com",           "Super Admin",                     RoleName.super_admin),
    ("admin",                 "admin@raed.com",                 "System Administrator",            RoleName.admin),
    ("am_riyadh",             "am_riyadh@raed.com",             "Area Manager Riyadh",              RoleName.area_manager),
    ("am_dammam_cafes",       "am_dammam_cafes@raed.com",       "Area Manager Dammam Cafes",       RoleName.area_manager),
    ("am_dammam_restaurants", "am_dammam_restaurants@raed.com", "Area Manager Dammam Restaurants", RoleName.area_manager),
    ("branch.mgr1",           "branch.mgr1@raed.com",           "Branch Manager Demo",             RoleName.branch_manager),
    ("branch.user1",          "branch.user1@raed.com",          "Branch User Demo",                RoleName.branch_user),
    ("meat.section.mgr",      "meat.mgr@raed.com",              "Meat Section Manager",            RoleName.kitchen_section_manager),
    ("bakery.section.mgr",    "bakery.mgr@raed.com",            "Bakery Section Manager",          RoleName.kitchen_section_manager),
    ("pizza.section.mgr",     "pizza.mgr@raed.com",             "Pizza Section Manager",           RoleName.kitchen_section_manager),
    ("wh.mgr1",               "wh.mgr1@raed.com",               "Warehouse Manager Demo",          RoleName.warehouse_manager),
    ("wh.user1",              "wh.user1@raed.com",              "Warehouse User Demo",             RoleName.warehouse_user),
    ("delivery.user",         "delivery@raed.com",              "Delivery User",                   RoleName.delivery_user),
]

# Area Manager assignments: (username, city, [brand_names])
AM_ASSIGNMENTS = [
    ("am_riyadh",             "Riyadh", BRANDS),                              # all 4 brands
    ("am_dammam_cafes",       "Dammam", ["Onda"]),                            # cafes only
    ("am_dammam_restaurants", "Dammam", ["Ronaldos", "Shawarma", "Griddle"]), # restaurants
]

# Kitchen section manager assignments: (username, section_name)
KS_ASSIGNMENTS = [
    ("meat.section.mgr",   "Meat & Chicken"),
    ("bakery.section.mgr", "Bakery & Sweets"),
    ("pizza.section.mgr",  "Pizza"),
]

# Branches we'll ENSURE EXIST (idempotent). (code, name, city, area, brands)
DEMO_BRANCHES = [
    ("BR-RY-ONDA-1",  "Onda Riyadh - Olaya",      "Riyadh", "Olaya",  ["Onda"]),
    ("BR-RY-RON-1",   "Ronaldos Riyadh - Malaz",  "Riyadh", "Malaz",  ["Ronaldos"]),
    ("BR-RY-SHA-1",   "Shawarma Riyadh - Hittin", "Riyadh", "Hittin", ["Shawarma"]),
    ("BR-RY-GRI-1",   "Griddle Riyadh - Salmania","Riyadh", "Salmania",["Griddle"]),
    ("BR-DM-ONDA-1",  "Onda Dammam - Corniche",   "Dammam", "Corniche",["Onda"]),
    ("BR-DM-RON-1",   "Ronaldos Dammam - Faisal", "Dammam", "Faisal", ["Ronaldos"]),
    ("BR-DM-SHA-1",   "Shawarma Dammam - Khaleej","Dammam", "Khaleej",["Shawarma"]),
    ("BR-DM-GRI-1",   "Griddle Dammam - Rakah",   "Dammam", "Rakah",  ["Griddle"]),
]

# Used by finalize_demo_branch_transition.py — keep in sync with DEMO_BRANCHES above.
DEMO_BRANCH_CODES: frozenset[str] = frozenset(row[0] for row in DEMO_BRANCHES)

# Items per brand:
#  - one WAREHOUSE item   (FINISHED, branch_requestable, source=WAREHOUSE)
#  - one KITCHEN item     (FINISHED, branch_requestable, source=KITCHEN, kitchen_section)
#  - one BOTH item        (default_source for split decision)
#
# Format: (item_code, name_ar, name_en, source_type, default_source, kitchen_section, brand)
DEMO_ITEMS = [
    # Onda — cafes
    ("DEMO-ONDA-CUP",   "كوب أوندا 16oz",    "Onda Cup 16oz",     SupplySourceType.WAREHOUSE, SupplyDefaultSource.WAREHOUSE, None,                "Onda"),
    ("DEMO-ONDA-CAKE",  "كيك شوكولاتة",       "Chocolate Cake",    SupplySourceType.KITCHEN,   SupplyDefaultSource.KITCHEN,   "Bakery & Sweets",   "Onda"),
    ("DEMO-ONDA-CROIS", "كرواسون زبدة",       "Butter Croissant",  SupplySourceType.BOTH,      SupplyDefaultSource.KITCHEN,   "Bakery & Sweets",   "Onda"),
    # Ronaldos — pizza
    ("DEMO-RON-BOX",    "صندوق بيتزا",        "Pizza Box",         SupplySourceType.WAREHOUSE, SupplyDefaultSource.WAREHOUSE, None,                "Ronaldos"),
    ("DEMO-RON-DOUGH",  "عجين بيتزا",         "Pizza Dough Ball",  SupplySourceType.KITCHEN,   SupplyDefaultSource.KITCHEN,   "Pizza",             "Ronaldos"),
    ("DEMO-RON-SAUCE",  "صوص بيتزا",          "Pizza Sauce",       SupplySourceType.BOTH,      SupplyDefaultSource.WAREHOUSE, "Pizza",             "Ronaldos"),
    # Shawarma — shawarma
    ("DEMO-SHA-WRAP",   "خبز شاورما",          "Shawarma Wrap",     SupplySourceType.WAREHOUSE, SupplyDefaultSource.WAREHOUSE, None,                "Shawarma"),
    ("DEMO-SHA-MEAT",   "شاورما لحم متبلة",     "Marinated Shawarma",SupplySourceType.KITCHEN,   SupplyDefaultSource.KITCHEN,   "Meat & Chicken",    "Shawarma"),
    ("DEMO-SHA-PICK",   "مخلل شاورما",         "Shawarma Pickles",  SupplySourceType.BOTH,      SupplyDefaultSource.WAREHOUSE, None,                "Shawarma"),
    # Griddle — grill
    ("DEMO-GRI-PLATE",  "صحن جريل ورقي",      "Griddle Paper Plate", SupplySourceType.WAREHOUSE, SupplyDefaultSource.WAREHOUSE, None,              "Griddle"),
    ("DEMO-GRI-CHK",    "دجاج جريل متبل",      "Marinated Griddle Chicken", SupplySourceType.KITCHEN, SupplyDefaultSource.KITCHEN, "Meat & Chicken", "Griddle"),
    ("DEMO-GRI-SAUCE",  "صوص جريل",            "Griddle Sauce",     SupplySourceType.BOTH,      SupplyDefaultSource.WAREHOUSE, None,                "Griddle"),
]


# ─────────────────────────────────────────────
# Helpers — get or create
# ─────────────────────────────────────────────

def goc_role(db: Session, role_name: RoleName) -> Role | None:
    row = db.query(Role).filter(Role.name == role_name).first()
    if row:
        return row
    display_name, description = ROLE_DEFS.get(role_name, (role_name.value.replace("_", " ").title(), None))
    row = Role(name=role_name, display_name=display_name, description=description)
    db.add(row)
    db.flush()
    return row


def ensure_user_role(db: Session, user: User, role_name: RoleName) -> None:
    role = goc_role(db, role_name)
    existing = db.query(UserRole).filter(
        UserRole.user_id == user.id,
        UserRole.role_id == role.id,
    ).first()
    if not existing:
        db.add(UserRole(user_id=user.id, role_id=role.id))
        db.flush()


def goc_brand(db: Session, name: str) -> Brand:
    row = db.query(Brand).filter(Brand.name == name).first()
    if row:
        return row
    row = Brand(name=name, active=True)
    db.add(row)
    db.flush()
    return row


def goc_kitchen_section(db: Session, name: str) -> KitchenSection:
    row = db.query(KitchenSection).filter(KitchenSection.name == name).first()
    if row:
        return row
    row = KitchenSection(name=name, active=True)
    db.add(row)
    db.flush()
    return row


def goc_user(db: Session, username: str, email: str, full_name: str, role_name: RoleName) -> tuple[User, bool]:
    """Return (user, created_bool)."""
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        existing.email = email or existing.email
        existing.full_name = full_name or existing.full_name
        existing.hashed_password = get_password_hash(PASSWORD)
        existing.status = UserStatus.active
        existing.is_deleted = False
        ensure_user_role(db, existing, role_name)
        db.flush()
        return existing, False
    role = goc_role(db, role_name)
    if not role:
        raise RuntimeError(f"Role '{role_name.value}' missing — run roles seed first")
    user = User(
        username=username,
        email=email,
        full_name=full_name,
        hashed_password=get_password_hash(PASSWORD),
        status=UserStatus.active,
        is_deleted=False,
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    db.flush()
    return user, True


def goc_category(db: Session, code: str = "DEMO", name_ar: str = "تصنيف ديمو", name_en: str = "Demo Category") -> ItemCategory:
    row = db.query(ItemCategory).filter(ItemCategory.code == code).first()
    if row:
        return row
    row = ItemCategory(code=code, name_ar=name_ar, name_en=name_en, active=True)
    db.add(row)
    db.flush()
    return row


def goc_unit(db: Session, code: str = "PCS", name_ar: str = "قطعة", name_en: str = "Piece") -> UnitOfMeasure:
    row = db.query(UnitOfMeasure).filter(UnitOfMeasure.code == code).first()
    if row:
        return row
    row = UnitOfMeasure(code=code, name_ar=name_ar, name_en=name_en, active=True)
    db.add(row)
    db.flush()
    return row


def goc_branch(db: Session, code: str, name: str, city: str, area: str, warehouse_id: int) -> Branch:
    row = db.query(Branch).filter(Branch.branch_code == code).first()
    if row:
        return row
    row = Branch(
        branch_code=code, branch_name=name, city=city, area=area,
        warehouse_id=warehouse_id, active=True, is_deleted=False,
    )
    db.add(row)
    db.flush()
    return row


def goc_branch_brand(db: Session, branch_id: int, brand_id: int) -> BranchBrand:
    row = db.query(BranchBrand).filter(
        BranchBrand.branch_id == branch_id,
        BranchBrand.brand_id == brand_id,
    ).first()
    if row:
        return row
    row = BranchBrand(branch_id=branch_id, brand_id=brand_id)
    db.add(row)
    db.flush()
    return row


def goc_am_assignment(db: Session, user_id: int, city: str, brand_id: int) -> AreaManagerAssignment:
    row = db.query(AreaManagerAssignment).filter(
        AreaManagerAssignment.user_id == user_id,
        AreaManagerAssignment.city == city,
        AreaManagerAssignment.brand_id == brand_id,
        AreaManagerAssignment.active == True,
    ).first()
    if row:
        return row
    row = AreaManagerAssignment(user_id=user_id, city=city, brand_id=brand_id, active=True)
    db.add(row)
    db.flush()
    return row


def goc_ks_assignment(db: Session, user_id: int, ks_id: int) -> KitchenSectionAssignment:
    row = db.query(KitchenSectionAssignment).filter(
        KitchenSectionAssignment.user_id == user_id,
        KitchenSectionAssignment.kitchen_section_id == ks_id,
        KitchenSectionAssignment.active == True,
    ).first()
    if row:
        return row
    row = KitchenSectionAssignment(user_id=user_id, kitchen_section_id=ks_id, active=True, service_city=None)
    db.add(row)
    db.flush()
    return row


def goc_item_brand(db: Session, item_id: int, brand_id: int) -> ItemBrand:
    row = db.query(ItemBrand).filter(
        ItemBrand.item_id == item_id,
        ItemBrand.brand_id == brand_id,
    ).first()
    if row:
        return row
    row = ItemBrand(item_id=item_id, brand_id=brand_id)
    db.add(row)
    db.flush()
    return row


def goc_item(
    db: Session,
    *,
    code: str,
    name_ar: str,
    name_en: str,
    source_type: SupplySourceType,
    default_source: SupplyDefaultSource,
    kitchen_section_id: int | None,
    category_id: int,
    unit_id: int,
) -> tuple[Item, bool]:
    existing = db.query(Item).filter(Item.item_code == code).first()
    if existing:
        if code.startswith("DEMO-"):
            existing.branch_requestable = False
            existing.visible_in_branch_ui = False
            existing.active = True
            db.flush()
        return existing, False
    is_demo_ui_hidden = code.startswith("DEMO-")
    item = Item(
        item_code=code,
        item_name_ar=name_ar,
        item_name_en=name_en,
        category_id=category_id,
        unit_id=unit_id,
        source_type=source_type,
        default_source=default_source,
        kitchen_section_id=kitchen_section_id,
        active=True,
        branch_requestable=not is_demo_ui_hidden,
        visible_in_branch_ui=not is_demo_ui_hidden,
        is_deleted=False,
        min_qty=Decimal("0"),
        max_qty=Decimal("0"),
        reorder_point=Decimal("0"),
        safety_stock=Decimal("0"),
    )
    db.add(item)
    db.flush()
    return item, True


def goc_warehouse_stock(db: Session, warehouse_id: int, item_id: int, qty: Decimal) -> WarehouseStock:
    row = db.query(WarehouseStock).filter(
        WarehouseStock.warehouse_id == warehouse_id,
        WarehouseStock.item_id == item_id,
    ).first()
    if row:
        return row
    row = WarehouseStock(warehouse_id=warehouse_id, item_id=item_id, current_qty=qty)
    db.add(row)
    db.flush()
    return row


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main() -> int:
    db = SessionLocal()
    summary: dict[str, int] = {}
    try:
        ensure_local_schema_compatibility()
        Base.metadata.create_all(bind=engine)

        # 1. Brands
        brand_by_name: dict[str, Brand] = {}
        n_new = 0
        for name in BRANDS:
            existed = db.query(Brand).filter(Brand.name == name).first() is not None
            brand_by_name[name] = goc_brand(db, name)
            if not existed:
                n_new += 1
        print(f"[1/9] brands: {len(BRANDS)} ensured ({n_new} created)")
        summary["brands_created"] = n_new

        # 2. Kitchen sections
        ks_by_name: dict[str, KitchenSection] = {}
        n_new = 0
        for name in KITCHEN_SECTIONS:
            existed = db.query(KitchenSection).filter(KitchenSection.name == name).first() is not None
            ks_by_name[name] = goc_kitchen_section(db, name)
            if not existed:
                n_new += 1
        print(f"[2/9] kitchen sections: {len(KITCHEN_SECTIONS)} ensured ({n_new} created)")
        summary["kitchen_sections_created"] = n_new

        # 3. Demo users
        n_new = 0
        for username, email, full_name, role_name in DEMO_USERS:
            _, created = goc_user(db, username, email, full_name, role_name)
            if created:
                n_new += 1
        print(f"[3/9] demo users: {len(DEMO_USERS)} ensured ({n_new} created)")
        summary["users_created"] = n_new

        # 4. Branches — need a warehouse first; reuse the first active one
        wh = db.query(Warehouse).filter(Warehouse.active == True, Warehouse.is_deleted == False).first()
        if not wh:
            print("  ! No active warehouse found — creating DEMO-WH-1")
            wh = Warehouse(
                warehouse_code="DEMO-WH-1",
                warehouse_name="Demo Central Warehouse",
                location="Riyadh",
                active=True,
                is_deleted=False,
            )
            db.add(wh)
            db.flush()

        n_new = 0
        branch_by_code: dict[str, Branch] = {}
        for code, name, city, area, brand_names in DEMO_BRANCHES:
            existed = db.query(Branch).filter(Branch.branch_code == code).first() is not None
            br = goc_branch(db, code, name, city, area, wh.id)
            branch_by_code[code] = br
            if not existed:
                n_new += 1
        print(f"[4/9] branches: {len(DEMO_BRANCHES)} ensured ({n_new} created)")
        summary["branches_created"] = n_new

        # 4.1 Bind reused demo accounts to deterministic branch / warehouse data.
        # Prefer an official Ronaldos Riyadh branch when seeded so re-runs stay compatible
        # after finalize_demo_branch_transition.py deactivates BR-RY-RON-1.
        official_ron_riyadh = db.query(Branch).filter(
            Branch.branch_code == "BR-RY-RN-ULAYA",
            Branch.is_deleted == False,  # noqa: E712
        ).first()
        demo_branch = official_ron_riyadh or branch_by_code.get("BR-RY-RON-1") or next(iter(branch_by_code.values()))
        for username, role_name in (
            ("super.admin", RoleName.super_admin),
            ("am_riyadh", RoleName.area_manager),
            ("am_dammam_cafes", RoleName.area_manager),
            ("am_dammam_restaurants", RoleName.area_manager),
            ("delivery.user", RoleName.delivery_user),
            ("meat.section.mgr", RoleName.kitchen_section_manager),
            ("bakery.section.mgr", RoleName.kitchen_section_manager),
            ("pizza.section.mgr", RoleName.kitchen_section_manager),
        ):
            user = db.query(User).filter(User.username == username).first()
            if user:
                user.status = UserStatus.active
                user.is_deleted = False
                user.hashed_password = get_password_hash(PASSWORD)
                ensure_user_role(db, user, role_name)
        for username, role_name in (("branch.user1", RoleName.branch_user), ("branch.mgr1", RoleName.branch_manager)):
            user = db.query(User).filter(User.username == username).first()
            if user:
                user.branch_id = demo_branch.id
                user.warehouse_id = None
                user.status = UserStatus.active
                user.is_deleted = False
                user.hashed_password = get_password_hash(PASSWORD)
                ensure_user_role(db, user, role_name)
        for username, role_name in (("wh.user1", RoleName.warehouse_user), ("wh.mgr1", RoleName.warehouse_manager)):
            user = db.query(User).filter(User.username == username).first()
            if user:
                user.branch_id = None
                user.warehouse_id = wh.id
                user.status = UserStatus.active
                user.is_deleted = False
                user.hashed_password = get_password_hash(PASSWORD)
                ensure_user_role(db, user, role_name)

        # 5. branch_brands mappings
        n_new = 0
        for code, _name, _city, _area, brand_names in DEMO_BRANCHES:
            br = branch_by_code[code]
            for bname in brand_names:
                if bname not in brand_by_name:
                    print(f"  ! brand '{bname}' missing — skipping for {code}")
                    continue
                brand = brand_by_name[bname]
                existed = db.query(BranchBrand).filter(
                    BranchBrand.branch_id == br.id,
                    BranchBrand.brand_id == brand.id,
                ).first() is not None
                goc_branch_brand(db, br.id, brand.id)
                if not existed:
                    n_new += 1
        print(f"[5/9] branch_brands mappings: {n_new} new")
        summary["branch_brands_created"] = n_new

        # 6. Area manager assignments
        n_new = 0
        for username, city, brand_names in AM_ASSIGNMENTS:
            user = db.query(User).filter(User.username == username).first()
            if not user:
                print(f"  ! User '{username}' missing — skipping assignment")
                continue
            for bname in brand_names:
                brand = brand_by_name.get(bname)
                if not brand:
                    continue
                existed = db.query(AreaManagerAssignment).filter(
                    AreaManagerAssignment.user_id == user.id,
                    AreaManagerAssignment.city == city,
                    AreaManagerAssignment.brand_id == brand.id,
                    AreaManagerAssignment.active == True,
                ).first() is not None
                goc_am_assignment(db, user.id, city, brand.id)
                if not existed:
                    n_new += 1
        print(f"[6/9] area_manager_assignments: {n_new} new")
        summary["am_assignments_created"] = n_new

        # 7. Kitchen section assignments
        n_new = 0
        for username, ks_name in KS_ASSIGNMENTS:
            user = db.query(User).filter(User.username == username).first()
            ks = ks_by_name.get(ks_name)
            if not user or not ks:
                continue
            existed = db.query(KitchenSectionAssignment).filter(
                KitchenSectionAssignment.user_id == user.id,
                KitchenSectionAssignment.kitchen_section_id == ks.id,
                KitchenSectionAssignment.active == True,
            ).first() is not None
            goc_ks_assignment(db, user.id, ks.id)
            if not existed:
                n_new += 1
        print(f"[7/9] kitchen_section_assignments: {n_new} new")
        summary["ks_assignments_created"] = n_new

        # 8. Items + item_brands
        cat = db.query(ItemCategory).filter(ItemCategory.active == True).first() or goc_category(db)
        unit = db.query(UnitOfMeasure).filter(UnitOfMeasure.active == True).first() or goc_unit(db)
        if not cat or not unit:
            print("  ! Missing default item_category or unit — cannot seed items")
            db.rollback()
            return 1

        n_items = 0
        n_item_brands = 0
        for code, name_ar, name_en, source_type, default_source, ks_name, brand_name in DEMO_ITEMS:
            ks_id = ks_by_name[ks_name].id if ks_name else None
            # Defensive: source_type may have been written as a string in the
            # DEMO_ITEMS table; coerce in case.
            if isinstance(source_type, str):
                source_type = SupplySourceType[source_type.split(".")[-1]] if "." in source_type else SupplySourceType(source_type)
            item, created = goc_item(
                db,
                code=code, name_ar=name_ar, name_en=name_en,
                source_type=source_type, default_source=default_source,
                kitchen_section_id=ks_id,
                category_id=cat.id, unit_id=unit.id,
            )
            if created:
                n_items += 1
            brand = brand_by_name.get(brand_name)
            if brand:
                existed = db.query(ItemBrand).filter(
                    ItemBrand.item_id == item.id,
                    ItemBrand.brand_id == brand.id,
                ).first() is not None
                goc_item_brand(db, item.id, brand.id)
                if not existed:
                    n_item_brands += 1
        print(f"[8/9] items: {n_items} new, item_brands: {n_item_brands} new")
        summary["items_created"] = n_items
        summary["item_brands_created"] = n_item_brands

        # 9. Warehouse stock — seed enough qty for warehouse-source items
        n_stock = 0
        for code, *_rest in DEMO_ITEMS:
            item = db.query(Item).filter(Item.item_code == code).first()
            if not item:
                continue
            # Seed 500 units for every demo item to make the demo painless.
            existed = db.query(WarehouseStock).filter(
                WarehouseStock.warehouse_id == wh.id,
                WarehouseStock.item_id == item.id,
            ).first() is not None
            goc_warehouse_stock(db, wh.id, item.id, Decimal("500"))
            if not existed:
                n_stock += 1
        print(f"[9/9] warehouse_stock seeded: {n_stock} new rows in {wh.warehouse_name}")
        summary["warehouse_stock_created"] = n_stock

        db.commit()

        print("")
        print("================================================")
        print("  Supply Chain V1 demo seed COMPLETE")
        print("================================================")
        print("")
        print("  Demo accounts (password = Raed@2025):")
        print("    super.admin              (super_admin)")
        print("    am_riyadh                (area_manager — Riyadh × all brands)")
        print("    am_dammam_cafes          (area_manager — Dammam × Onda)")
        print("    am_dammam_restaurants    (area_manager — Dammam × Ronaldos/Shawarma/Griddle)")
        print("    branch.mgr1              (branch_manager — re-used)")
        print("    branch.user1             (branch_user — re-used)")
        print("    meat.section.mgr         (kitchen_section_manager — Meat & Chicken)")
        print("    bakery.section.mgr       (kitchen_section_manager — Bakery & Sweets)")
        print("    pizza.section.mgr        (kitchen_section_manager — Pizza)")
        print("    wh.mgr1                  (warehouse_manager — re-used)")
        print("    wh.user1                 (warehouse_user — re-used)")
        print("    delivery.user            (delivery_user)")
        print("")
        print("  Summary:", summary)
        return 0

    except Exception as exc:
        db.rollback()
        print(f"  ERROR: {exc}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
