#!/usr/bin/env python3
"""
Seed LAN trial opening warehouse stock from review CSV (read-only on workflows/RBAC/items).

Usage (from backend/):
  python seed_lan_opening_stock.py \\
    --input ../LAN_OPENING_STOCK_MISSING_ITEMS_REVIEW.csv \\
    --warehouse WH-DM-1 \\
    --i-understand-this-is-lan-trial-stock

Safety:
  - Requires DATABASE_URL database name to contain ``lan_trial``
  - Requires ``--i-understand-this-is-lan-trial-stock``
  - Creates missing WarehouseStock rows only, or updates when current_qty is NULL/missing/zero
  - Never reduces existing stock unless ``--force`` is passed
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models import Item, Warehouse, WarehouseStock

BACKEND = Path(__file__).resolve().parent
REPO_ROOT = BACKEND.parent.parent


def _database_name() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise SystemExit("DATABASE_URL is not set")
    parsed = urlparse(url.replace("+psycopg2", ""))
    return (parsed.path or "").lstrip("/").lower()


def _dec(value) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    return Decimal(str(value))


def _resolve_input(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_file():
        return candidate.resolve()
    for base in (REPO_ROOT, BACKEND):
        alt = (base / path).resolve()
        if alt.is_file():
            return alt
    raise SystemExit(f"Input CSV not found: {path}")


def load_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise SystemExit(f"No rows in {path}")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed LAN trial opening warehouse stock")
    parser.add_argument("--input", required=True, help="Review CSV path")
    parser.add_argument("--warehouse", default="WH-DM-1", help="Target warehouse code")
    parser.add_argument(
        "--i-understand-this-is-lan-trial-stock",
        action="store_true",
        help="Required safety acknowledgement",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite non-zero existing stock with final_opening_qty",
    )
    args = parser.parse_args()

    if not args.i_understand_this_is_lan_trial_stock:
        raise SystemExit("Refusing to run without --i-understand-this-is-lan-trial-stock")

    db_name = _database_name()
    if "lan_trial" not in db_name:
        raise SystemExit(
            f"Refusing to run: DATABASE_URL database '{db_name}' does not contain 'lan_trial'"
        )

    csv_path = _resolve_input(args.input)
    rows = load_csv(csv_path)

    db = SessionLocal()
    warehouse_id: int | None = None
    summary = {
        "database": db_name,
        "warehouse_code": args.warehouse,
        "input": str(csv_path),
        "created": [],
        "updated": [],
        "skipped": [],
        "errors": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        warehouse = (
            db.query(Warehouse)
            .filter(Warehouse.warehouse_code == args.warehouse, Warehouse.is_deleted == False)
            .first()
        )
        if not warehouse:
            raise SystemExit(f"Warehouse not found: {args.warehouse}")

        for row in rows:
            wh_code = (row.get("warehouse_code") or "").strip()
            if wh_code and wh_code != args.warehouse:
                summary["skipped"].append(
                    {"item_id": row.get("item_id"), "reason": f"warehouse_code mismatch ({wh_code})"}
                )
                continue

            item_id_raw = row.get("item_id")
            try:
                item_id = int(item_id_raw)
            except (TypeError, ValueError):
                summary["errors"].append({"row": row, "reason": "invalid item_id"})
                continue

            qty_raw = row.get("final_opening_qty") or row.get("recommended_opening_qty")
            try:
                qty = _dec(qty_raw)
            except InvalidOperation:
                summary["errors"].append({"item_id": item_id, "reason": f"invalid qty: {qty_raw}"})
                continue
            if qty <= 0:
                summary["skipped"].append({"item_id": item_id, "reason": "non-positive final_opening_qty"})
                continue

            item = db.query(Item).filter(Item.id == item_id, Item.is_deleted == False).first()
            if not item:
                summary["errors"].append({"item_id": item_id, "reason": "item not found"})
                continue

            stock = (
                db.query(WarehouseStock)
                .filter(WarehouseStock.warehouse_id == warehouse.id, WarehouseStock.item_id == item_id)
                .first()
            )

            if stock is None:
                stock = WarehouseStock(
                    warehouse_id=warehouse.id,
                    item_id=item_id,
                    current_qty=qty,
                    reserved_qty=Decimal("0"),
                )
                db.add(stock)
                summary["created"].append(
                    {"item_id": item_id, "item_code": item.item_code, "qty": str(qty)}
                )
                continue

            current = _dec(stock.current_qty)
            if current > 0 and not args.force:
                summary["skipped"].append(
                    {
                        "item_id": item_id,
                        "item_code": item.item_code,
                        "reason": f"existing non-zero stock ({current})",
                    }
                )
                continue

            stock.current_qty = qty
            summary["updated"].append(
                {"item_id": item_id, "item_code": item.item_code, "from_qty": str(current), "to_qty": str(qty)}
            )

        db.commit()
        warehouse_id = warehouse.id
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print("LAN trial opening stock seed complete")
    print(f"  database: {summary['database']}")
    print(f"  warehouse: {summary['warehouse_code']} (id={warehouse_id})")
    print(f"  created: {len(summary['created'])}")
    print(f"  updated: {len(summary['updated'])}")
    print(f"  skipped: {len(summary['skipped'])}")
    print(f"  errors: {len(summary['errors'])}")
    for entry in summary["created"]:
        print(f"    + {entry['item_code']} -> {entry['qty']}")
    for entry in summary["updated"]:
        print(f"    ~ {entry['item_code']} {entry['from_qty']} -> {entry['to_qty']}")
    for entry in summary["skipped"]:
        print(f"    skip item_id={entry.get('item_id')} ({entry.get('reason')})")
    for entry in summary["errors"]:
        print(f"    ERR {entry}")

    return 1 if summary["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
