from __future__ import annotations

import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models import Branch, BranchBrand, Brand, Warehouse, WarehouseStock

# After seeding official branches, optionally run (from backend/):
#   python finalize_demo_branch_transition.py
# to set supply-chain demo branches inactive and remap legacy demo users.

OFFICIAL_BRANCHES: tuple[tuple[str, str, str, str, tuple[str, ...]], ...] = (
    ("BR-DM-ON-ARKAN", "Onda Arkan", "Dammam", "Arkan", ("Onda",)),
    ("BR-RY-ON-MALQA", "Onda Al Malqa", "Riyadh", "Al Malqa", ("Onda",)),
    ("BR-DM-ON-HASSA", "Onda Hassa", "Dammam", "Hassa", ("Onda",)),
    ("BR-DM-ON-NAJMA", "Onda Najmah", "Dammam", "Najmah", ("Onda",)),
    ("BR-DM-ON-MIDRA", "Onda Al Midra Gym", "Dammam", "Al Midra Gym", ("Onda",)),
    ("BR-DM-ON-HOQAI", "Onda Hoqail", "Dammam", "Hoqail", ("Onda",)),
    ("BR-RY-ON-SEFAR", "Onda Sefarat", "Riyadh", "Sefarat", ("Onda",)),
    ("BR-DM-ON-MUOWA", "Onda Muowasat", "Dammam", "Muowasat", ("Onda",)),
    ("BR-DM-ON-RASTN", "Onda Ras Tanura", "Dammam", "Ras Tanura", ("Onda",)),
    ("BR-DM-ON-DAU", "Onda DAU University", "Dammam", "DAU University", ("Onda",)),
    ("BR-DM-RN-KHOBR", "Ronaldos Al Khobar", "Dammam", "Al Khobar", ("Ronaldos",)),
    ("BR-DM-RN-MAZAR", "Ronaldos Mazaar", "Dammam", "Mazaar", ("Ronaldos",)),
    ("BR-DM-RN-RASTN", "Ronaldos Ras Tanura", "Dammam", "Ras Tanura", ("Ronaldos",)),
    ("BR-DM-RN-ARKAN", "Ronaldos Arkan", "Dammam", "Arkan", ("Ronaldos",)),
    ("BR-RY-RN-TAKHS", "Ronaldos Riyadh Takhasosy", "Riyadh", "Takhasosy", ("Ronaldos",)),
    ("BR-RY-RN-ULAYA", "Ronaldos Al Ulaya", "Riyadh", "Al Ulaya", ("Ronaldos",)),
    ("BR-RY-RN-NADA", "Ronaldos Riyadh Nada", "Riyadh", "Al Nada", ("Ronaldos",)),
    ("BR-DM-RN-ARAMC", "Ronaldos Aramco", "Dammam", "Aramco", ("Ronaldos",)),
    ("BR-DM-RN-AZIZI", "Ronaldos Al Aziziyah", "Dammam", "Al Aziziyah", ("Ronaldos",)),
    ("BR-DM-RN-DAU", "Ronaldos DAU University", "Dammam", "DAU University", ("Ronaldos",)),
    ("BR-DM-SH-KHOBR", "Shawarma Al Khobar", "Dammam", "Al Khobar", ("Shawarma",)),
    ("BR-DM-SH-ARKAN", "Shawarma Arkan", "Dammam", "Arkan", ("Shawarma",)),
    ("BR-RY-SH-OLAYA", "Shawarma Olaya", "Riyadh", "Olaya", ("Shawarma", "Griddle")),
)


OFFICIAL_WAREHOUSES: tuple[tuple[str, str, str], ...] = (
    ("WH-RY-1", "Riyadh Central Warehouse", "Riyadh"),
    ("WH-DM-1", "Dammam Central Warehouse", "Dammam"),
)


def get_seed_warehouse(db) -> Warehouse | None:
    row = db.query(Warehouse).filter(
        Warehouse.warehouse_code == "DEMO-WH-1",
        Warehouse.is_deleted == False,
    ).first()
    if row:
        return row
    return db.query(Warehouse).filter(Warehouse.is_deleted == False).order_by(Warehouse.id.asc()).first()


def ensure_warehouse(db, *, code: str, name: str, location: str) -> tuple[Warehouse, bool]:
    row = db.query(Warehouse).filter(Warehouse.warehouse_code == code).first()
    created = row is None
    if row is None:
        row = Warehouse(
            warehouse_code=code,
            warehouse_name=name,
            location=location,
            active=True,
            is_deleted=False,
        )
        db.add(row)
        db.flush()
        return row, created
    row.warehouse_name = name
    row.location = location
    row.active = True
    row.is_deleted = False
    db.flush()
    return row, created


def ensure_warehouse_stock_copy(db, *, source_warehouse_id: int, target_warehouse_id: int) -> int:
    created = 0
    source_rows = db.query(WarehouseStock).filter(WarehouseStock.warehouse_id == source_warehouse_id).all()
    for src in source_rows:
        existing = db.query(WarehouseStock).filter(
            WarehouseStock.warehouse_id == target_warehouse_id,
            WarehouseStock.item_id == src.item_id,
        ).first()
        if existing:
            continue
        db.add(
            WarehouseStock(
                warehouse_id=target_warehouse_id,
                item_id=src.item_id,
                current_qty=Decimal(str(src.current_qty or 0)),
                reserved_qty=Decimal(str(src.reserved_qty or 0)),
            )
        )
        created += 1
    db.flush()
    return created


def warehouse_for_city(warehouse_by_city: dict[str, Warehouse], city: str) -> Warehouse:
    row = warehouse_by_city.get(city.strip().lower())
    if not row:
        raise RuntimeError(f"No warehouse configured for city '{city}'")
    return row


def get_brand(db, name: str) -> Brand:
    row = db.query(Brand).filter(Brand.name == name).first()
    if not row:
        raise RuntimeError(f"Brand '{name}' not found. Seed brands first.")
    return row


def ensure_branch(db, *, code: str, name: str, city: str, area: str, warehouse_id: int) -> tuple[Branch, bool]:
    row = db.query(Branch).filter(Branch.branch_code == code).first()
    created = row is None
    if row is None:
        row = Branch(
            branch_code=code,
            branch_name=name,
            city=city,
            area=area,
            warehouse_id=warehouse_id,
            active=True,
            is_deleted=False,
        )
        db.add(row)
        db.flush()
        return row, created
    row.branch_name = name
    row.city = city
    row.area = area
    row.warehouse_id = warehouse_id
    row.active = True
    row.is_deleted = False
    db.flush()
    return row, created


def ensure_branch_brand(db, branch_id: int, brand_id: int) -> bool:
    row = db.query(BranchBrand).filter(
        BranchBrand.branch_id == branch_id,
        BranchBrand.brand_id == brand_id,
    ).first()
    if row:
        return False
    db.add(BranchBrand(branch_id=branch_id, brand_id=brand_id))
    db.flush()
    return True


def main() -> int:
    db = SessionLocal()
    try:
        seed_warehouse = get_seed_warehouse(db)
        warehouse_by_city: dict[str, Warehouse] = {}
        warehouses_created = 0
        copied_stock_rows = 0
        for code, name, location in OFFICIAL_WAREHOUSES:
            warehouse, created = ensure_warehouse(db, code=code, name=name, location=location)
            warehouse_by_city[location.strip().lower()] = warehouse
            if created:
                warehouses_created += 1
                if seed_warehouse and seed_warehouse.id != warehouse.id:
                    copied_stock_rows += ensure_warehouse_stock_copy(
                        db,
                        source_warehouse_id=seed_warehouse.id,
                        target_warehouse_id=warehouse.id,
                    )
        created_count = 0
        brand_link_count = 0
        for code, name, city, area, brand_names in OFFICIAL_BRANCHES:
            branch, created = ensure_branch(
                db,
                code=code,
                name=name,
                city=city,
                area=area,
                warehouse_id=warehouse_for_city(warehouse_by_city, city).id,
            )
            if created:
                created_count += 1
            for brand_name in brand_names:
                brand = get_brand(db, brand_name)
                if ensure_branch_brand(db, branch.id, brand.id):
                    brand_link_count += 1
        db.commit()
        total = db.query(Branch).filter(Branch.is_deleted == False).count()
        active_warehouses = db.query(Warehouse).filter(Warehouse.is_deleted == False, Warehouse.active == True).count()
        print(f"official_warehouses={active_warehouses}")
        print(f"warehouses_created={warehouses_created}")
        print(f"warehouse_stock_copied={copied_stock_rows}")
        print(f"official_branches_seeded={len(OFFICIAL_BRANCHES)}")
        print(f"branches_created={created_count}")
        print(f"branch_brand_links_created={brand_link_count}")
        print(f"active_branches_total={total}")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
