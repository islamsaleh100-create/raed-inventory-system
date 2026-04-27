"""
Ledger & Variance Report Service — Epic 6

Provides:
- Stock ledger by branch (paginated transactions)
- Stock ledger by warehouse
- Variance report (daily inventory vs expected stock)
- Low-stock summary
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from app.core.errors import AppError
from app.models import (
    Branch,
    BranchStock,
    DailyInventory,
    DailyInventoryLine,
    InventoryStatus,
    Item,
    StockTransaction,
    TransactionType,
    Warehouse,
    WarehouseStock,
)


# ──────────────────────────────────────────────────────────────────────────
# STOCK LEDGER — BRANCH
# ──────────────────────────────────────────────────────────────────────────

def get_branch_ledger(
    db: Session,
    *,
    branch_id: int,
    item_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    transaction_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    branch = db.query(Branch).filter(Branch.id == branch_id).first()
    if not branch:
        raise AppError(
            status_code=404,
            error_code="ledger.branch_not_found",
            message="Branch not found",
            detail={"branch_id": branch_id},
        )

    q = db.query(StockTransaction).options(
        joinedload(StockTransaction.item)
    ).filter(
        StockTransaction.source_type == "branch",
        StockTransaction.source_id == branch_id,
    )

    # Also include transactions where branch is destination
    q_dest = db.query(StockTransaction).options(
        joinedload(StockTransaction.item)
    ).filter(
        StockTransaction.destination_type == "branch",
        StockTransaction.destination_id == branch_id,
    )

    if item_id:
        q = q.filter(StockTransaction.item_id == item_id)
        q_dest = q_dest.filter(StockTransaction.item_id == item_id)
    if date_from:
        dt_from = datetime.combine(date_from, datetime.min.time())
        q = q.filter(StockTransaction.transaction_date >= dt_from)
        q_dest = q_dest.filter(StockTransaction.transaction_date >= dt_from)
    if date_to:
        dt_to = datetime.combine(date_to, datetime.max.time())
        q = q.filter(StockTransaction.transaction_date <= dt_to)
        q_dest = q_dest.filter(StockTransaction.transaction_date <= dt_to)
    if transaction_type:
        try:
            tx_type = TransactionType(transaction_type)
        except ValueError:
            raise AppError(
                status_code=400,
                error_code="ledger.invalid_transaction_type",
                message=f"Invalid transaction_type: {transaction_type}",
                detail={},
            )
        q = q.filter(StockTransaction.transaction_type == tx_type)
        q_dest = q_dest.filter(StockTransaction.transaction_type == tx_type)

    # Union via Python (SQLite doesn't support UNION on ORM easily)
    source_txs = q.all()
    dest_txs = q_dest.all()
    seen_ids = {t.id for t in source_txs}
    all_txs = source_txs + [t for t in dest_txs if t.id not in seen_ids]
    all_txs.sort(key=lambda t: (t.transaction_date, t.id), reverse=True)

    total = len(all_txs)
    start = (page - 1) * page_size
    page_txs = all_txs[start: start + page_size]

    return {
        "branch_id": branch_id,
        "branch_name": branch.branch_name,
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_tx_to_dict(t) for t in page_txs],
    }


# ──────────────────────────────────────────────────────────────────────────
# STOCK LEDGER — WAREHOUSE
# ──────────────────────────────────────────────────────────────────────────

def get_warehouse_ledger(
    db: Session,
    *,
    warehouse_id: int,
    item_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    transaction_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    wh = db.query(Warehouse).filter(Warehouse.id == warehouse_id).first()
    if not wh:
        raise AppError(
            status_code=404,
            error_code="ledger.warehouse_not_found",
            message="Warehouse not found",
            detail={"warehouse_id": warehouse_id},
        )

    q = db.query(StockTransaction).options(
        joinedload(StockTransaction.item)
    ).filter(
        StockTransaction.source_type == "warehouse",
        StockTransaction.source_id == warehouse_id,
    )

    q_dest = db.query(StockTransaction).options(
        joinedload(StockTransaction.item)
    ).filter(
        StockTransaction.destination_type == "warehouse",
        StockTransaction.destination_id == warehouse_id,
    )

    if item_id:
        q = q.filter(StockTransaction.item_id == item_id)
        q_dest = q_dest.filter(StockTransaction.item_id == item_id)
    if date_from:
        dt_from = datetime.combine(date_from, datetime.min.time())
        q = q.filter(StockTransaction.transaction_date >= dt_from)
        q_dest = q_dest.filter(StockTransaction.transaction_date >= dt_from)
    if date_to:
        dt_to = datetime.combine(date_to, datetime.max.time())
        q = q.filter(StockTransaction.transaction_date <= dt_to)
        q_dest = q_dest.filter(StockTransaction.transaction_date <= dt_to)
    if transaction_type:
        try:
            tx_type = TransactionType(transaction_type)
        except ValueError:
            raise AppError(
                status_code=400,
                error_code="ledger.invalid_transaction_type",
                message=f"Invalid transaction_type: {transaction_type}",
                detail={},
            )
        q = q.filter(StockTransaction.transaction_type == tx_type)
        q_dest = q_dest.filter(StockTransaction.transaction_type == tx_type)

    source_txs = q.all()
    dest_txs = q_dest.all()
    seen_ids = {t.id for t in source_txs}
    all_txs = source_txs + [t for t in dest_txs if t.id not in seen_ids]
    all_txs.sort(key=lambda t: (t.transaction_date, t.id), reverse=True)

    total = len(all_txs)
    start = (page - 1) * page_size
    page_txs = all_txs[start: start + page_size]

    return {
        "warehouse_id": warehouse_id,
        "warehouse_name": wh.warehouse_name,
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_tx_to_dict(t) for t in page_txs],
    }


# ──────────────────────────────────────────────────────────────────────────
# VARIANCE REPORT  (approved inventory lines with variance != 0)
# ──────────────────────────────────────────────────────────────────────────

def get_variance_report(
    db: Session,
    *,
    branch_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    critical_only: bool = False,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """
    Returns inventory lines where variance_qty != 0 from approved inventories.
    critical_only=True filters to lines flagged as 'critical' (abs variance > 25% of expected).
    """
    q = db.query(DailyInventoryLine).join(
        DailyInventory,
        DailyInventoryLine.inventory_id == DailyInventory.id,
    ).options(
        joinedload(DailyInventoryLine.item),
        joinedload(DailyInventoryLine.inventory),
    ).filter(
        DailyInventory.status == InventoryStatus.approved,
        DailyInventoryLine.variance_qty != 0,
    )

    if branch_id:
        q = q.filter(DailyInventory.branch_id == branch_id)
    if date_from:
        q = q.filter(DailyInventory.inventory_date >= date_from)
    if date_to:
        q = q.filter(DailyInventory.inventory_date <= date_to)
    if critical_only:
        q = q.filter(DailyInventoryLine.variance_status == "critical")

    total = q.count()
    lines = q.order_by(
        DailyInventory.inventory_date.desc(),
        DailyInventoryLine.id,
    ).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "inventory_id": line.inventory_id,
                "inventory_date": str(line.inventory.inventory_date),
                "branch_id": line.inventory.branch_id,
                "line_id": line.id,
                "item_id": line.item_id,
                "item_code": line.item.item_code if line.item else None,
                "item_name_ar": line.item.item_name_ar if line.item else None,
                "expected_qty": float(line.book_qty),
                "counted_qty": float(line.counted_qty),
                "variance_qty": float(line.variance_qty),
                "variance_pct": float(line.variance_pct) if line.variance_pct else None,
                "variance_flag": line.variance_status,
                "variance_reason_id": line.variance_reason_id,
                "notes": line.notes,
            }
            for line in lines
        ],
    }


# ──────────────────────────────────────────────────────────────────────────
# LOW-STOCK SUMMARY
# ──────────────────────────────────────────────────────────────────────────

def get_low_stock_summary(
    db: Session,
    *,
    branch_id: Optional[int] = None,
    warehouse_id: Optional[int] = None,
    out_of_stock_only: bool = False,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """Returns branch/warehouse stock lines at or below reorder point."""
    if branch_id:
        q = db.query(BranchStock).options(
            joinedload(BranchStock.item),
            joinedload(BranchStock.branch),
        ).filter(BranchStock.branch_id == branch_id)

        total = q.count()
        rows = q.options(joinedload(BranchStock.item)).all()

        # Filter in Python using item.reorder_point
        if out_of_stock_only:
            rows = [r for r in rows if r.current_qty <= 0]
        else:
            rows = [r for r in rows if r.item and r.current_qty <= r.item.reorder_point]

        total = len(rows)
        page_rows = rows[(page - 1) * page_size: page * page_size]

        return {
            "location_type": "branch",
            "location_id": branch_id,
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "item_id": r.item_id,
                    "item_code": r.item.item_code if r.item else None,
                    "item_name_ar": r.item.item_name_ar if r.item else None,
                    "current_qty": float(r.current_qty),
                    "reorder_point": float(r.item.reorder_point) if r.item else 0,
                    "min_qty": float(r.item.min_qty) if r.item else 0,
                    "out_of_stock": r.current_qty <= 0,
                }
                for r in page_rows
            ],
        }

    elif warehouse_id:
        q = db.query(WarehouseStock).options(
            joinedload(WarehouseStock.item),
        ).filter(WarehouseStock.warehouse_id == warehouse_id)

        rows = q.all()

        if out_of_stock_only:
            rows = [r for r in rows if r.current_qty <= 0]
        else:
            rows = [r for r in rows if r.item and r.current_qty <= r.item.reorder_point]

        total = len(rows)
        page_rows = rows[(page - 1) * page_size: page * page_size]

        return {
            "location_type": "warehouse",
            "location_id": warehouse_id,
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "item_id": r.item_id,
                    "item_code": r.item.item_code if r.item else None,
                    "item_name_ar": r.item.item_name_ar if r.item else None,
                    "current_qty": float(r.current_qty),
                    "reorder_point": float(r.item.reorder_point) if r.item else 0,
                    "min_qty": float(r.item.min_qty) if r.item else 0,
                    "out_of_stock": r.current_qty <= 0,
                }
                for r in page_rows
            ],
        }

    else:
        raise AppError(
            status_code=400,
            error_code="ledger.location_required",
            message="Provide either branch_id or warehouse_id",
            detail={},
        )


# ──────────────────────────────────────────────────────────────────────────
# helpers
# ──────────────────────────────────────────────────────────────────────────

def _tx_to_dict(tx: StockTransaction) -> dict:
    return {
        "id": tx.id,
        "transaction_date": tx.transaction_date,
        "transaction_type": tx.transaction_type.value if tx.transaction_type else None,
        "item_id": tx.item_id,
        "item_code": tx.item.item_code if tx.item else None,
        "item_name_ar": tx.item.item_name_ar if tx.item else None,
        "qty": float(tx.qty),
        "source_type": tx.source_type,
        "source_id": tx.source_id,
        "destination_type": tx.destination_type,
        "destination_id": tx.destination_id,
        "reference_no": tx.reference_no,
        "notes": tx.notes,
        "created_by": tx.created_by,
    }
