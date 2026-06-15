#!/usr/bin/env python3
"""
LAN Trial opening stock validation (read-only).

Usage (from backend/):
  python validate_lan_opening_stock.py [--write-report]

Exit codes:
  0 = GO or GO WITH WARNINGS
  1 = NO-GO
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import joinedload

from app.database import SessionLocal
from app.models import (
    Branch,
    BranchBrand,
    Item,
    ItemBrand,
    ItemType,
    SupplyDefaultSource,
    SupplySourceType,
    Warehouse,
    WarehouseStock,
)

DEFAULT_TRIAL_BRANCH_NAMES = (
    "Onda 1 - ARKAN",
    "Onda Arkan",
    "Pizza 1 - AlKHOBAR",
    "Ronaldos Al Khobar",
    "SHAWERMA - 1 - Khobar",
    "Shawarma Al Khobar",
)

DEFAULT_TRIAL_BRANCH_CODES = (
    "BR-DM-ON-ARKAN",
    "BR-DM-RN-KHOBR",
    "BR-DM-SH-KHOBR",
)

DEFAULT_WAREHOUSE_NAMES = (
    "Dammam Warehouse",
    "Dammam Central Warehouse",
)

DEFAULT_WAREHOUSE_CODES = ("WH-DM-1",)


def _dec(value) -> Decimal:
    return Decimal(str(value or 0))


def _resolve_branches(db) -> list[Branch]:
    rows = db.query(Branch).filter(Branch.is_deleted == False, Branch.active == True).all()
    selected: list[Branch] = []
    for code in DEFAULT_TRIAL_BRANCH_CODES:
        hit = next((b for b in rows if b.branch_code == code), None)
        if hit and hit not in selected:
            selected.append(hit)
    if len(selected) < 3:
        for name in DEFAULT_TRIAL_BRANCH_NAMES:
            hit = next((b for b in rows if b.branch_name == name), None)
            if hit and hit not in selected:
                selected.append(hit)
    return selected


def _resolve_warehouse(db) -> Warehouse | None:
    for code in DEFAULT_WAREHOUSE_CODES:
        row = db.query(Warehouse).filter(Warehouse.warehouse_code == code, Warehouse.is_deleted == False).first()
        if row:
            return row
    for name in DEFAULT_WAREHOUSE_NAMES:
        row = db.query(Warehouse).filter(Warehouse.warehouse_name == name, Warehouse.is_deleted == False).first()
        if row:
            return row
    return db.query(Warehouse).filter(Warehouse.is_deleted == False, Warehouse.location.ilike("%Dammam%")).first()


def _requestable_items_for_branch(db, branch: Branch) -> list[Item]:
    brand_ids = [
        bb.brand_id for bb in db.query(BranchBrand).filter(BranchBrand.branch_id == branch.id).all()
    ]
    if not brand_ids:
        return []
    items = (
        db.query(Item)
        .join(ItemBrand, ItemBrand.item_id == Item.id)
        .filter(
            ItemBrand.brand_id.in_(brand_ids),
            Item.active == True,
            Item.branch_requestable == True,
            Item.visible_in_branch_ui == True,
            Item.source_type != SupplySourceType.NOT_REQUESTABLE,
            Item.item_type != ItemType.raw_material,
            Item.is_deleted == False,
        )
        .distinct()
        .all()
    )
    warehouse_items = [
        item for item in items
        if item.default_source == SupplyDefaultSource.WAREHOUSE
        or item.source_type in (SupplySourceType.WAREHOUSE, SupplySourceType.BOTH)
    ]
    return warehouse_items


def validate(db) -> dict:
    branches = _resolve_branches(db)
    warehouse = _resolve_warehouse(db)

    result = {
        "branches": [{"id": b.id, "code": b.branch_code, "name": b.branch_name} for b in branches],
        "warehouse": None,
        "zero_stock": [],
        "below_reorder": [],
        "missing_stock_rows": [],
        "warnings": [],
        "errors": [],
    }

    if not branches:
        result["errors"].append("No trial branches found (expected BR-DM-ON-ARKAN, BR-DM-RN-KHOBR, BR-DM-SH-KHOBR)")
    if not warehouse:
        result["errors"].append("No Dammam trial warehouse found (expected WH-DM-1 / Dammam Central Warehouse)")
    else:
        result["warehouse"] = {
            "id": warehouse.id,
            "code": warehouse.warehouse_code,
            "name": warehouse.warehouse_name,
        }

    if not warehouse:
        result["verdict"] = "NO-GO"
        return result

    seen_item_ids: set[int] = set()
    for branch in branches:
        for item in _requestable_items_for_branch(db, branch):
            if item.id in seen_item_ids:
                continue
            seen_item_ids.add(item.id)
            stock = (
                db.query(WarehouseStock)
                .filter(
                    WarehouseStock.warehouse_id == warehouse.id,
                    WarehouseStock.item_id == item.id,
                )
                .first()
            )
            if not stock:
                result["missing_stock_rows"].append({
                    "item_id": item.id,
                    "item_code": item.item_code,
                    "item_name": item.item_name_ar or item.item_name_en,
                })
                continue
            qty = _dec(stock.current_qty)
            if qty <= 0:
                result["zero_stock"].append({
                    "item_id": item.id,
                    "item_code": item.item_code,
                    "item_name": item.item_name_ar or item.item_name_en,
                    "current_qty": str(qty),
                })
            reorder = _dec(getattr(item, "reorder_point", 0))
            if reorder > 0 and qty < reorder:
                result["below_reorder"].append({
                    "item_id": item.id,
                    "item_code": item.item_code,
                    "item_name": item.item_name_ar or item.item_name_en,
                    "current_qty": str(qty),
                    "reorder_point": str(reorder),
                })

    if result["errors"]:
        result["verdict"] = "NO-GO"
    elif result["zero_stock"] or result["missing_stock_rows"]:
        result["verdict"] = "NO-GO"
    elif result["below_reorder"]:
        result["verdict"] = "GO WITH WARNINGS"
        result["warnings"].append(f"{len(result['below_reorder'])} items below reorder point")
    else:
        result["verdict"] = "GO"

    return result


def write_report(result: dict, path: str) -> None:
    lines = [
        "# LAN Opening Stock Validation Report",
        "",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        f"## Verdict: **{result['verdict']}**",
        "",
        "## Trial Branches Detected",
        "",
    ]
    for b in result.get("branches", []):
        lines.append(f"- `{b['code']}` — {b['name']} (id={b['id']})")
    wh = result.get("warehouse")
    lines.extend([
        "",
        "## Trial Warehouse",
        "",
        f"- `{wh['code']}` — {wh['name']} (id={wh['id']})" if wh else "- **Not found**",
        "",
        f"## Zero Stock Items ({len(result.get('zero_stock', []))})",
        "",
    ])
    for row in result.get("zero_stock", [])[:50]:
        lines.append(f"- {row['item_code']} — {row['item_name']} (qty={row['current_qty']})")
    if len(result.get("zero_stock", [])) > 50:
        lines.append(f"- … and {len(result['zero_stock']) - 50} more")

    lines.extend(["", f"## Missing Stock Rows ({len(result.get('missing_stock_rows', []))})", ""])
    for row in result.get("missing_stock_rows", [])[:50]:
        lines.append(f"- {row['item_code']} — {row['item_name']}")

    lines.extend(["", f"## Below Reorder Point ({len(result.get('below_reorder', []))})", ""])
    for row in result.get("below_reorder", [])[:30]:
        lines.append(
            f"- {row['item_code']} — {row['item_name']} (qty={row['current_qty']}, reorder={row['reorder_point']})"
        )

    if result.get("errors"):
        lines.extend(["", "## Errors", ""])
        for err in result["errors"]:
            lines.append(f"- {err}")

    if result.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        for w in result["warnings"]:
            lines.append(f"- {w}")

    lines.extend([
        "",
        "## Name Mapping Notes",
        "",
        "- Spec names may differ from official seed names.",
        "- `Onda 1 - ARKAN` → `Onda Arkan` (`BR-DM-ON-ARKAN`)",
        "- `Pizza 1 - AlKHOBAR` → official user maps to `Ronaldos Al Khobar` (`BR-DM-RN-KHOBR`)",
        "- `SHAWERMA - 1 - Khobar` → `Shawarma Al Khobar` (`BR-DM-SH-KHOBR`)",
        "- `Dammam Warehouse` → `Dammam Central Warehouse` (`WH-DM-1`)",
        "",
        "*Validation only — no stock modified.*",
    ])

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate LAN trial opening stock")
    parser.add_argument("--write-report", action="store_true", help="Write LAN_OPENING_STOCK_VALIDATION_REPORT.md")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        result = validate(db)
    finally:
        db.close()

    print(f"Verdict: {result['verdict']}")
    print(f"Branches: {len(result.get('branches', []))}")
    print(f"Zero stock: {len(result.get('zero_stock', []))}")
    print(f"Missing rows: {len(result.get('missing_stock_rows', []))}")
    print(f"Below reorder: {len(result.get('below_reorder', []))}")

    if args.write_report:
        report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "LAN_OPENING_STOCK_VALIDATION_REPORT.md")
        write_report(result, os.path.normpath(report_path))
        print(f"Report written: {report_path}")

    if result["verdict"] == "NO-GO":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
