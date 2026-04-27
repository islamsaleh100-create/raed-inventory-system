"""
Data Import Router — /api/v1/import
Epic 15: Upload CSV or XLSX files to bulk-create / update items and stock.

Endpoints:
  POST /import/items              — create/update items from CSV or XLSX
  POST /import/branch-stock       — set branch stock quantities from CSV or XLSX
  POST /import/warehouse-stock    — set warehouse stock quantities from CSV or XLSX
  GET  /import/templates/{name}   — download a template CSV for each import type

Expected columns per template:
  items:           item_code, item_name_ar, item_name_en, category_code, unit_code,
                   min_qty, max_qty, reorder_point, active (optional)
  branch-stock:    branch_code, item_code, qty
  warehouse-stock: warehouse_code, item_code, qty
"""
import csv
import io
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.database import get_db
from app.models import (
    Branch, BranchStock, Item, ItemCategory, UnitOfMeasure, User, Warehouse, WarehouseStock,
)
from app.services import audit_service

router = APIRouter(prefix="/api/v1/import", tags=["Data Import"])

_ADMIN = ("admin", "super_admin")


# ──────────────────────────────────────────────────────────────────────────────
# TEMPLATES
# ──────────────────────────────────────────────────────────────────────────────

_TEMPLATES: dict[str, list[str]] = {
    "items": [
        "item_code", "item_name_ar", "item_name_en",
        "category_code", "unit_code",
        "min_qty", "max_qty", "reorder_point", "active",
    ],
    "branch-stock": ["branch_code", "item_code", "qty"],
    "warehouse-stock": ["warehouse_code", "item_code", "qty"],
}


@router.get("/templates/{name}")
def download_template(
    name: str,
    current_user: User = Depends(require_roles(*_ADMIN)),
):
    """Download a blank CSV template for the given import type."""
    if name not in _TEMPLATES:
        raise HTTPException(status_code=404, detail=f"Unknown template '{name}'. Available: {list(_TEMPLATES)}")

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(_TEMPLATES[name])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{name}-template.csv"'},
    )


# ──────────────────────────────────────────────────────────────────────────────
# helpers
# ──────────────────────────────────────────────────────────────────────────────

def _read_upload(file: UploadFile) -> list[dict]:
    """
    Parse an uploaded CSV or XLSX file into a list of row dicts.
    Returns rows with lowercased, stripped header keys.
    """
    from app.config import settings

    fname = (file.filename or "").lower()
    # امتدادات مسموحة فقط
    allowed_ext = (".xlsx", ".xls", ".csv", ".tsv", ".txt")
    if not any(fname.endswith(ext) for ext in allowed_ext):
        raise HTTPException(
            status_code=400,
            detail=f"امتداد الملف غير مدعوم. المسموح: {', '.join(allowed_ext)}",
        )

    # فحص حجم الملف — منع DoS
    max_size_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if file.size is not None and file.size > max_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"الملف أكبر من الحد المسموح ({settings.MAX_UPLOAD_SIZE_MB} MB)",
        )

    raw = file.file.read(max_size_bytes + 1)
    if len(raw) > max_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"الملف أكبر من الحد المسموح ({settings.MAX_UPLOAD_SIZE_MB} MB)",
        )

    if fname.endswith(".xlsx") or fname.endswith(".xls"):
        try:
            import openpyxl
        except ImportError:
            raise HTTPException(status_code=400, detail="openpyxl not installed; upload CSV instead")
        try:
            wb = openpyxl.load_workbook(io.BytesIO(raw), data_only=True, read_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"ملف Excel تالف أو غير صالح: {type(e).__name__}")
        if not rows:
            return []
        headers = [str(h).strip().lower() if h is not None else "" for h in rows[0]]
        return [
            {headers[i]: (str(cell).strip() if cell is not None else "") for i, cell in enumerate(row)}
            for row in rows[1:]
            if any(cell is not None for cell in row)
        ]

    # Default: treat as CSV
    try:
        text = raw.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        return [
            {k.strip().lower(): v.strip() for k, v in row.items()}
            for row in reader
        ]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"ملف CSV غير صالح: {type(e).__name__}")


def _ok(created: int, updated: int, errors: list[dict]) -> dict:
    return {"created": created, "updated": updated, "errors": errors, "total_errors": len(errors)}


def _decimal(val, default: Decimal = Decimal("0")) -> Decimal:
    """Parse a string/number to Decimal, falling back to default on failure."""
    if val is None or str(val).strip() == "":
        return default
    try:
        return Decimal(str(val).strip())
    except (InvalidOperation, ValueError):
        return default


# ──────────────────────────────────────────────────────────────────────────────
# ITEMS IMPORT
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/items")
def import_items(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_ADMIN)),
):
    """
    Create or update items from a CSV / XLSX file.

    Required columns: item_code, item_name_ar, item_name_en, category_code, unit_code
    Optional: min_qty, max_qty, reorder_point, active
    """
    rows = _read_upload(file)
    if not rows:
        raise HTTPException(status_code=400, detail="File is empty or could not be parsed")

    created = updated = 0
    errors: list[dict] = []

    # Pre-load lookup maps
    cats = {c.code: c for c in db.query(ItemCategory).all()}
    units = {u.code: u for u in db.query(UnitOfMeasure).all()}

    for idx, row in enumerate(rows, start=2):   # row 1 = header
        item_code = row.get("item_code", "").strip()
        if not item_code:
            errors.append({"row": idx, "error": "item_code is required"})
            continue

        item_name_ar = row.get("item_name_ar", "").strip()
        item_name_en = row.get("item_name_en", "").strip()
        if not item_name_ar:
            errors.append({"row": idx, "item_code": item_code, "error": "item_name_ar is required"})
            continue

        cat_code = row.get("category_code", "").strip()
        unit_code = row.get("unit_code", "").strip()

        category = cats.get(cat_code)
        if cat_code and not category:
            errors.append({"row": idx, "item_code": item_code, "error": f"category_code '{cat_code}' not found"})
            continue

        unit = units.get(unit_code)
        if unit_code and not unit:
            errors.append({"row": idx, "item_code": item_code, "error": f"unit_code '{unit_code}' not found"})
            continue

        existing = db.query(Item).filter(Item.item_code == item_code).first()

        if existing:
            existing.item_name_ar = item_name_ar
            existing.item_name_en = item_name_en or existing.item_name_en
            if category:
                existing.category_id = category.id
            if unit:
                existing.unit_id = unit.id
            existing.min_qty = _decimal(row.get("min_qty"), Decimal(str(existing.min_qty or 0)))
            existing.max_qty = _decimal(row.get("max_qty"), Decimal(str(existing.max_qty or 0)))
            existing.reorder_point = _decimal(row.get("reorder_point"), Decimal(str(existing.reorder_point or 0)))
            active_val = row.get("active", "").lower()
            if active_val in ("true", "1", "yes"):
                existing.active = True
            elif active_val in ("false", "0", "no"):
                existing.active = False
            updated += 1
        else:
            if not category:
                errors.append({"row": idx, "item_code": item_code, "error": "category_code required for new items"})
                continue
            if not unit:
                errors.append({"row": idx, "item_code": item_code, "error": "unit_code required for new items"})
                continue

            item = Item(
                item_code=item_code,
                item_name_ar=item_name_ar,
                item_name_en=item_name_en,
                category_id=category.id,
                unit_id=unit.id,
                min_qty=_decimal(row.get("min_qty"), Decimal("0")),
                max_qty=_decimal(row.get("max_qty"), Decimal("0")),
                reorder_point=_decimal(row.get("reorder_point"), Decimal("0")),
                active=True,
            )
            db.add(item)
            created += 1

    db.commit()
    audit_service.log(
        db,
        user_id=current_user.id,
        action="import",
        module="master",
        entity_type="item",
        new_values={"created": created, "updated": updated, "errors": len(errors)},
    )
    db.commit()
    return _ok(created, updated, errors)


# ──────────────────────────────────────────────────────────────────────────────
# BRANCH STOCK IMPORT
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/branch-stock")
def import_branch_stock(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_ADMIN)),
):
    """
    Set branch stock quantities from CSV / XLSX.
    Required columns: branch_code, item_code, qty
    """
    rows = _read_upload(file)
    if not rows:
        raise HTTPException(status_code=400, detail="File is empty or could not be parsed")

    created = updated = 0
    errors: list[dict] = []

    branches = {b.branch_code: b for b in db.query(Branch).filter(Branch.is_deleted == False).all()}
    items = {i.item_code: i for i in db.query(Item).filter(Item.is_deleted == False).all()}

    for idx, row in enumerate(rows, start=2):
        branch_code = row.get("branch_code", "").strip()
        item_code = row.get("item_code", "").strip()
        qty_str = row.get("qty", "0").strip()

        if not branch_code or not item_code:
            errors.append({"row": idx, "error": "branch_code and item_code are required"})
            continue

        branch = branches.get(branch_code)
        if not branch:
            errors.append({"row": idx, "branch_code": branch_code, "error": "Branch not found"})
            continue

        item = items.get(item_code)
        if not item:
            errors.append({"row": idx, "item_code": item_code, "error": "Item not found"})
            continue

        try:
            qty = float(qty_str)
        except ValueError:
            errors.append({"row": idx, "item_code": item_code, "error": f"Invalid qty: {qty_str!r}"})
            continue

        stock = db.query(BranchStock).filter(
            BranchStock.branch_id == branch.id,
            BranchStock.item_id == item.id,
        ).first()

        if stock:
            stock.current_qty = qty
            updated += 1
        else:
            db.add(BranchStock(branch_id=branch.id, item_id=item.id, current_qty=qty))
            created += 1

    db.commit()
    audit_service.log(
        db,
        user_id=current_user.id,
        action="import",
        module="stock",
        entity_type="branch_stock",
        new_values={"created": created, "updated": updated, "errors": len(errors)},
    )
    db.commit()
    return _ok(created, updated, errors)


# ──────────────────────────────────────────────────────────────────────────────
# WAREHOUSE STOCK IMPORT
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/warehouse-stock")
def import_warehouse_stock(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_ADMIN)),
):
    """
    Set warehouse stock quantities from CSV / XLSX.
    Required columns: warehouse_code, item_code, qty
    """
    rows = _read_upload(file)
    if not rows:
        raise HTTPException(status_code=400, detail="File is empty or could not be parsed")

    created = updated = 0
    errors: list[dict] = []

    warehouses = {w.warehouse_code: w for w in db.query(Warehouse).filter(Warehouse.is_deleted == False).all()}
    items = {i.item_code: i for i in db.query(Item).filter(Item.is_deleted == False).all()}

    for idx, row in enumerate(rows, start=2):
        warehouse_code = row.get("warehouse_code", "").strip()
        item_code = row.get("item_code", "").strip()
        qty_str = row.get("qty", "0").strip()

        if not warehouse_code or not item_code:
            errors.append({"row": idx, "error": "warehouse_code and item_code are required"})
            continue

        warehouse = warehouses.get(warehouse_code)
        if not warehouse:
            errors.append({"row": idx, "warehouse_code": warehouse_code, "error": "Warehouse not found"})
            continue

        item = items.get(item_code)
        if not item:
            errors.append({"row": idx, "item_code": item_code, "error": "Item not found"})
            continue

        try:
            qty = float(qty_str)
        except ValueError:
            errors.append({"row": idx, "item_code": item_code, "error": f"Invalid qty: {qty_str!r}"})
            continue

        stock = db.query(WarehouseStock).filter(
            WarehouseStock.warehouse_id == warehouse.id,
            WarehouseStock.item_id == item.id,
        ).first()

        if stock:
            stock.current_qty = qty
            updated += 1
        else:
            db.add(WarehouseStock(warehouse_id=warehouse.id, item_id=item.id, current_qty=qty))
            created += 1

    db.commit()
    audit_service.log(
        db,
        user_id=current_user.id,
        action="import",
        module="stock",
        entity_type="warehouse_stock",
        new_values={"created": created, "updated": updated, "errors": len(errors)},
    )
    db.commit()
    return _ok(created, updated, errors)
