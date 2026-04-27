"""
Export Router — /api/v1/export
Epic 12: Download data as CSV or XLSX

Supports:
  GET /export/inventory-compliance?date_from=&date_to=&format=csv|xlsx
  GET /export/variance-report?branch_id=&date_from=&date_to=&format=csv|xlsx
  GET /export/order-summary?date_from=&date_to=&format=csv|xlsx
  GET /export/stock/branches/{branch_id}?format=csv|xlsx
  GET /export/stock/warehouses/{warehouse_id}?format=csv|xlsx
  GET /export/ledger/branches/{branch_id}?format=csv|xlsx
"""
import csv
import io
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from app.core.auth import get_current_active_user, require_roles
from app.database import get_db
from app.models import (
    Branch,
    BranchStock,
    DailyInventory,
    DailyInventoryLine,
    InventoryStatus,
    Item,
    OrderStatus,
    ReplenishmentOrder,
    StockTransaction,
    User,
    Warehouse,
    WarehouseStock,
)
from app.services import ledger_service

router = APIRouter(prefix="/api/v1/export", tags=["Data Export"])

_MGMT = ("branch_manager", "warehouse_manager", "admin", "super_admin")


# ──────────────────────────────────────────────────────────────────────────
# helpers
# ──────────────────────────────────────────────────────────────────────────

def _csv_response(rows: list[dict], filename: str) -> StreamingResponse:
    if not rows:
        rows = [{}]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _xlsx_response(rows: list[dict], filename: str, sheet_name: str = "Sheet1") -> StreamingResponse:
    try:
        import openpyxl
    except ImportError:
        # Fallback to CSV if openpyxl not installed
        return _csv_response(rows, filename.replace(".xlsx", ".csv"))

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name

    if not rows:
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    headers = list(rows[0].keys())
    ws.append(headers)

    # Bold header row
    from openpyxl.styles import Font, PatternFill
    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = header_fill

    for row in rows:
        ws.append([row.get(h) for h in headers])

    # Auto-width columns
    for col in ws.columns:
        max_len = max((len(str(cell.value or "")) for cell in col), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 50)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _respond(rows: list[dict], filename_base: str, fmt: str, sheet_name: str = "Data") -> StreamingResponse:
    if fmt == "xlsx":
        return _xlsx_response(rows, f"{filename_base}.xlsx", sheet_name)
    return _csv_response(rows, f"{filename_base}.csv")


# ──────────────────────────────────────────────────────────────────────────
# INVENTORY COMPLIANCE EXPORT
# ──────────────────────────────────────────────────────────────────────────

@router.get("/inventory-compliance")
def export_inventory_compliance(
    date_from: date,
    date_to: date,
    branch_id: Optional[int] = None,
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_MGMT)),
):
    delta = (date_to - date_from).days
    if delta < 0 or delta > 90:
        from app.core.errors import AppError
        raise AppError(
            status_code=400,
            error_code="export.invalid_date_range",
            message="Date range must be 0–90 days",
            detail={},
        )

    branch_q = db.query(Branch).filter(Branch.active == True)
    if branch_id:
        branch_q = branch_q.filter(Branch.id == branch_id)
    branches = branch_q.all()

    inv_q = db.query(DailyInventory).filter(
        DailyInventory.inventory_date >= date_from,
        DailyInventory.inventory_date <= date_to,
    )
    if branch_id:
        inv_q = inv_q.filter(DailyInventory.branch_id == branch_id)
    inv_map = {(i.branch_id, i.inventory_date): i for i in inv_q.all()}

    dates = [date_from + timedelta(days=d) for d in range(delta + 1)]
    rows = []
    for branch in branches:
        for d in dates:
            inv = inv_map.get((branch.id, d))
            rows.append({
                "branch_id": branch.id,
                "branch_name": branch.branch_name,
                "date": str(d),
                "status": inv.status.value if inv else "missing",
                "inventory_id": inv.id if inv else "",
            })

    return _respond(rows, f"inventory_compliance_{date_from}_{date_to}", format, "Compliance")


# ──────────────────────────────────────────────────────────────────────────
# VARIANCE REPORT EXPORT
# ──────────────────────────────────────────────────────────────────────────

@router.get("/variance-report")
def export_variance_report(
    branch_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    critical_only: bool = False,
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_MGMT)),
):
    data = ledger_service.get_variance_report(
        db,
        branch_id=branch_id,
        date_from=date_from,
        date_to=date_to,
        critical_only=critical_only,
        page=1,
        page_size=10000,
    )
    rows = data["items"]
    return _respond(rows, "variance_report", format, "Variance")


# ──────────────────────────────────────────────────────────────────────────
# ORDER SUMMARY EXPORT
# ──────────────────────────────────────────────────────────────────────────

@router.get("/order-summary")
def export_order_summary(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    branch_id: Optional[int] = None,
    warehouse_id: Optional[int] = None,
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_MGMT)),
):
    q = db.query(ReplenishmentOrder)
    if date_from:
        q = q.filter(ReplenishmentOrder.order_date >= date_from)
    if date_to:
        q = q.filter(ReplenishmentOrder.order_date <= date_to)
    if branch_id:
        q = q.filter(ReplenishmentOrder.branch_id == branch_id)
    if warehouse_id:
        q = q.filter(ReplenishmentOrder.warehouse_id == warehouse_id)

    orders = q.all()
    rows = [
        {
            "order_id": o.id,
            "order_no": o.order_no,
            "branch_id": o.branch_id,
            "warehouse_id": o.warehouse_id,
            "order_type": o.order_type.value if o.order_type else "",
            "status": o.status.value if o.status else "",
            "order_date": str(o.order_date),
            "dispatch_note_no": o.dispatch_note_no or "",
            "created_at": str(o.created_at),
        }
        for o in orders
    ]
    return _respond(rows, "order_summary", format, "Orders")


# ──────────────────────────────────────────────────────────────────────────
# BRANCH STOCK EXPORT
# ──────────────────────────────────────────────────────────────────────────

@router.get("/stock/branches/{branch_id}")
def export_branch_stock(
    branch_id: int,
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_MGMT)),
):
    stocks = db.query(BranchStock).options(
        joinedload(BranchStock.item)
    ).filter(BranchStock.branch_id == branch_id).all()

    rows = [
        {
            "item_id": s.item_id,
            "item_code": s.item.item_code if s.item else "",
            "item_name_ar": s.item.item_name_ar if s.item else "",
            "item_name_en": s.item.item_name_en if s.item else "",
            "current_qty": float(s.current_qty),
            "in_transit_qty": float(s.in_transit_qty),
            "reserved_qty": float(s.reserved_qty),
            "reorder_point": float(s.item.reorder_point) if s.item else 0,
            "min_qty": float(s.item.min_qty) if s.item else 0,
        }
        for s in stocks
    ]
    return _respond(rows, f"branch_{branch_id}_stock", format, "Stock")


# ──────────────────────────────────────────────────────────────────────────
# WAREHOUSE STOCK EXPORT
# ──────────────────────────────────────────────────────────────────────────

@router.get("/stock/warehouses/{warehouse_id}")
def export_warehouse_stock(
    warehouse_id: int,
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_MGMT)),
):
    stocks = db.query(WarehouseStock).options(
        joinedload(WarehouseStock.item)
    ).filter(WarehouseStock.warehouse_id == warehouse_id).all()

    rows = [
        {
            "item_id": s.item_id,
            "item_code": s.item.item_code if s.item else "",
            "item_name_ar": s.item.item_name_ar if s.item else "",
            "item_name_en": s.item.item_name_en if s.item else "",
            "current_qty": float(s.current_qty),
            "reserved_qty": float(s.reserved_qty),
            "reorder_point": float(s.item.reorder_point) if s.item else 0,
        }
        for s in stocks
    ]
    return _respond(rows, f"warehouse_{warehouse_id}_stock", format, "Stock")


# ──────────────────────────────────────────────────────────────────────────
# LEDGER EXPORT
# ──────────────────────────────────────────────────────────────────────────

@router.get("/ledger/branches/{branch_id}")
def export_branch_ledger(
    branch_id: int,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_MGMT)),
):
    data = ledger_service.get_branch_ledger(
        db,
        branch_id=branch_id,
        date_from=date_from,
        date_to=date_to,
        page=1,
        page_size=10000,
    )
    rows = data["items"]
    # Flatten datetime objects
    for row in rows:
        if isinstance(row.get("transaction_date"), datetime):
            row["transaction_date"] = row["transaction_date"].isoformat()
    return _respond(rows, f"branch_{branch_id}_ledger", format, "Ledger")
