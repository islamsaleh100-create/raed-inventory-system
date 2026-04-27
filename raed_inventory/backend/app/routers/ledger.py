"""
Ledger Router — /api/v1/ledger
Epic 6: stock ledger by branch/warehouse, variance report, low-stock summary
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import (
    get_current_active_user,
    require_roles,
    can_access_branch,
    can_access_warehouse,
    get_user_roles,
)
from app.database import get_db
from app.models import User
from app.services import ledger_service

router = APIRouter(prefix="/api/v1/ledger", tags=["Ledger & Reports"])

_READONLY_ROLES = ("branch_user", "branch_manager", "warehouse_user", "warehouse_manager", "admin", "super_admin", "operations_manager", "area_manager")


def _assert_branch_access(user: User, branch_id: int, db: Session) -> None:
    # Pass `db` so area_manager region check can query the branches table.
    if not can_access_branch(user, branch_id, db):
        raise HTTPException(status_code=403, detail="ليس لديك صلاحية على هذا الفرع")


def _assert_warehouse_access(user: User, warehouse_id: int) -> None:
    if not can_access_warehouse(user, warehouse_id):
        raise HTTPException(status_code=403, detail="ليس لديك صلاحية على هذا المستودع")


@router.get("/branches/{branch_id}")
def get_branch_ledger(
    branch_id: int,
    item_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    transaction_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_READONLY_ROLES)),
):
    """
    Paginated stock transaction log for a branch.
    — تحقق صلاحية الوصول في الـ router قبل تمرير الطلب للـ service (منع IDOR).
    """
    _assert_branch_access(current_user, branch_id, db)
    return ledger_service.get_branch_ledger(
        db,
        branch_id=branch_id,
        item_id=item_id,
        date_from=date_from,
        date_to=date_to,
        transaction_type=transaction_type,
        page=page,
        page_size=page_size,
    )


@router.get("/warehouses/{warehouse_id}")
def get_warehouse_ledger(
    warehouse_id: int,
    item_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    transaction_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_READONLY_ROLES)),
):
    """Paginated stock transaction log for a warehouse — تحقق الصلاحية قبل الاستعلام."""
    _assert_warehouse_access(current_user, warehouse_id)
    return ledger_service.get_warehouse_ledger(
        db,
        warehouse_id=warehouse_id,
        item_id=item_id,
        date_from=date_from,
        date_to=date_to,
        transaction_type=transaction_type,
        page=page,
        page_size=page_size,
    )


@router.get("/variance-report")
def get_variance_report(
    branch_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    critical_only: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_READONLY_ROLES)),
):
    """
    Returns approved inventory lines where variance_qty != 0.
    مستخدمو الفروع يُقيَّدون تلقائياً بفرعهم (حتى لو لم يمرروا branch_id).
    """
    user_roles = get_user_roles(current_user)
    # مدير/مستخدم الفرع: فرض فلترة على فرعه فقط
    if any(r in user_roles for r in ("branch_user", "branch_manager")) and not any(
        r in user_roles for r in ("super_admin", "admin", "operations_manager")
    ):
        if branch_id is None:
            branch_id = current_user.branch_id
        elif branch_id != current_user.branch_id:
            raise HTTPException(status_code=403, detail="ليس لديك صلاحية على هذا الفرع")

    if branch_id is not None:
        _assert_branch_access(current_user, branch_id, db)

    return ledger_service.get_variance_report(
        db,
        branch_id=branch_id,
        date_from=date_from,
        date_to=date_to,
        critical_only=critical_only,
        page=page,
        page_size=page_size,
    )


@router.get("/low-stock")
def get_low_stock_summary(
    branch_id: Optional[int] = None,
    warehouse_id: Optional[int] = None,
    out_of_stock_only: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_READONLY_ROLES)),
):
    """
    Returns stock lines at or below reorder point.
    Provide either branch_id or warehouse_id.
    """
    if branch_id is not None:
        _assert_branch_access(current_user, branch_id, db)
    if warehouse_id is not None:
        _assert_warehouse_access(current_user, warehouse_id)

    return ledger_service.get_low_stock_summary(
        db,
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        out_of_stock_only=out_of_stock_only,
        page=page,
        page_size=page_size,
    )
