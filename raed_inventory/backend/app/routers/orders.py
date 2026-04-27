"""
Replenishment Orders Router
Handles full order lifecycle: create -> review -> approve -> pick -> dispatch -> receive -> close
"""
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session, joinedload, selectinload
from typing import Optional
from datetime import date, datetime
from decimal import Decimal
from app.database import get_db
from app.core.auth import (
    require_roles,
    get_current_active_user,
    can_access_branch,
    can_access_warehouse,
)
from app.core.errors import AppError
from app.models import (
    ReplenishmentOrder, ReplenishmentOrderLine,
    OrderStatus, OrderType, User
)
from app.schemas import (
    BranchReviewRequest,
    CancelOrderRequest,
    DispatchOrderRequest,
    ExceptionalOrderCreate,
    InterBranchApproveRequest,
    InterBranchOrderCreate,
    InterBranchOrderOut,
    InterBranchRejectRequest,
    OrderActionResponse,
    OrderListResponse,
    OrderSummaryOut,
    PickListOut,
    ReceivingConfirmCreate,
    RejectOrderRequest,
    WarehouseReviewRequest,
)
from app.services import replenishment_service, orders_service, inter_branch_service

router = APIRouter(prefix="/api/v1/orders", tags=["Replenishment Orders"])


def _ensure_order_read_access(current_user: User, order: ReplenishmentOrder, db: Session):
    user_roles = [ur.role.name.value for ur in current_user.user_roles]
    if any(role in user_roles for role in ["super_admin", "admin", "operations_manager"]):
        return
    if any(role in user_roles for role in ["branch_user", "branch_manager"]) and can_access_branch(current_user, order.branch_id, db):
        return
    if any(role in user_roles for role in ["warehouse_user", "warehouse_manager"]) and can_access_warehouse(current_user, order.warehouse_id):
        return
    raise AppError(
        status_code=403,
        error_code="orders.read_access_denied",
        message="Access denied for this order",
        detail={"order_id": order.id},
    )


def _ensure_order_branch_access(current_user: User, order: ReplenishmentOrder, db: Session):
    if not can_access_branch(current_user, order.branch_id, db):
        raise AppError(
            status_code=403,
            error_code="orders.branch_access_denied",
            message="Access denied for this branch order",
            detail={"order_id": order.id, "branch_id": order.branch_id},
        )


def _ensure_order_warehouse_access(current_user: User, order: ReplenishmentOrder):
    if not can_access_warehouse(current_user, order.warehouse_id):
        raise AppError(
            status_code=403,
            error_code="orders.warehouse_access_denied",
            message="Access denied for this warehouse order",
            detail={"order_id": order.id, "warehouse_id": order.warehouse_id},
        )


def _order_to_dict(order: ReplenishmentOrder) -> dict:
    return {
        "id": order.id,
        "order_no": order.order_no,
        "branch_id": order.branch_id,
        "warehouse_id": order.warehouse_id,
        "order_type": order.order_type,
        "status": order.status,
        "order_date": str(order.order_date),
        "notes": order.notes,
        "dispatch_note_no": order.dispatch_note_no,
        "created_at": order.created_at,
        "lines": [_line_to_dict(l) for l in order.lines],
    }


def _line_to_dict(line: ReplenishmentOrderLine) -> dict:
    item = line.item
    return {
        "id": line.id,
        "item_id": line.item_id,
        "item_code": item.item_code if item else None,
        "item_name_ar": item.item_name_ar if item else None,
        "item_name_en": item.item_name_en if item else None,
        "unit": item.unit.name_ar if item and item.unit else None,
        "suggested_qty": float(line.suggested_qty),
        "branch_requested_qty": float(line.branch_requested_qty),
        "wh_approved_qty": float(line.wh_approved_qty),
        "picked_qty": float(line.picked_qty),
        "dispatched_qty": float(line.dispatched_qty),
        "received_qty": float(line.received_qty),
        "damaged_qty": float(line.damaged_qty),
        "missing_qty": float(line.missing_qty),
        "shortage_flag": line.shortage_flag,
        "shortage_reason": line.shortage_reason,
        "rejection_reason": line.rejection_reason,
        "line_status": line.line_status,
        "notes": line.notes,
    }


@router.get("/", response_model=OrderListResponse)
def list_orders(
    branch_id: Optional[int] = None,
    warehouse_id: Optional[int] = None,
    status: Optional[str] = None,
    order_type: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    q = db.query(ReplenishmentOrder).options(
        selectinload(ReplenishmentOrder.lines).selectinload(ReplenishmentOrderLine.item)
    )

    # Role-based filtering
    user_roles = [ur.role.name.value for ur in current_user.user_roles]
    if "branch_user" in user_roles or "branch_manager" in user_roles:
        q = q.filter(ReplenishmentOrder.branch_id == current_user.branch_id)
    elif "warehouse_user" in user_roles or "warehouse_manager" in user_roles:
        q = q.filter(ReplenishmentOrder.warehouse_id == current_user.warehouse_id)

    if branch_id:
        q = q.filter(ReplenishmentOrder.branch_id == branch_id)
    if warehouse_id:
        q = q.filter(ReplenishmentOrder.warehouse_id == warehouse_id)
    if status:
        q = q.filter(ReplenishmentOrder.status == status)
    if order_type:
        q = q.filter(ReplenishmentOrder.order_type == order_type)
    if date_from:
        q = q.filter(ReplenishmentOrder.order_date >= date_from)
    if date_to:
        q = q.filter(ReplenishmentOrder.order_date <= date_to)

    total = q.count()
    orders = q.order_by(ReplenishmentOrder.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_order_to_dict(o) for o in orders]
    }


@router.get("/{order_id}", response_model=OrderSummaryOut)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    order = db.query(ReplenishmentOrder).options(
        selectinload(ReplenishmentOrder.lines).selectinload(ReplenishmentOrderLine.item)
    ).filter(ReplenishmentOrder.id == order_id).first()
    if not order:
        raise AppError(
            status_code=404,
            error_code="orders.not_found",
            message="Order not found",
            detail={"order_id": order_id},
        )
    _ensure_order_read_access(current_user, order, db)
    return _order_to_dict(order)


@router.post("/exceptional", status_code=201)
def create_exceptional_order(
    payload: ExceptionalOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("branch_user", "branch_manager", "admin", "super_admin"))
):
    if not can_access_branch(current_user, payload.branch_id, db):
        raise AppError(
            status_code=403,
            error_code="orders.branch_access_denied",
            message="Access denied for this branch",
            detail={"branch_id": payload.branch_id},
        )
    items = [
        {"item_id": i.item_id, "branch_requested_qty": i.resolved_qty, "notes": i.notes}
        for i in payload.items
    ]
    return replenishment_service.create_exceptional_order(
        db, payload.branch_id, items, payload.notes, current_user
    )


@router.post("/daily", status_code=201)
def create_daily_order(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("branch_manager", "admin", "super_admin")),
):
    """Branch manager creates a daily manual order."""
    branch_id = payload.get("branch_id") or current_user.branch_id
    if branch_id is None:
        raise AppError(
            status_code=400,
            error_code="orders.branch_id_required",
            message="branch_id is required",
            detail={},
        )
    if not can_access_branch(current_user, branch_id, db):
        raise AppError(
            status_code=403,
            error_code="orders.branch_access_denied",
            message="Access denied for this branch",
            detail={"branch_id": branch_id},
        )
    items = payload.get("items") or []
    return replenishment_service.create_daily_order(
        db=db,
        branch_id=branch_id,
        items=items,
        notes=payload.get("notes"),
        user=current_user,
    )


@router.post("/{order_id}/area-review")
def area_manager_review(
    order_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("area_manager", "admin", "super_admin")),
):
    """Area manager reviews the daily order."""
    order = (
        db.query(ReplenishmentOrder)
        .options(joinedload(ReplenishmentOrder.lines))
        .filter(ReplenishmentOrder.id == order_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="الطلبية غير موجودة")
    if order.status not in (OrderStatus.branch_reviewed, OrderStatus.system_generated):
        raise HTTPException(status_code=400, detail="الطلبية ليست في حالة مناسبة للمراجعة")

    line_notes = payload.get("line_notes") or {}
    for line in order.lines:
        if str(line.id) in line_notes:
            line.notes = line_notes[str(line.id)]
        elif line.id in line_notes:
            line.notes = line_notes[line.id]

    order.status = OrderStatus.area_manager_review
    if payload.get("notes") is not None:
        order.notes = payload.get("notes")
    db.commit()
    return {"message": "تمت مراجعة الطلبية", "order_id": order_id}


@router.post("/{order_id}/branch-review", response_model=OrderActionResponse)
def branch_review_order(
    order_id: int,
    payload: BranchReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("branch_user", "branch_manager", "admin", "super_admin"))
):
    """Branch reviews and optionally adjusts quantities"""
    return orders_service.branch_review_order(
        db,
        order_id=order_id,
        payload=payload.model_dump(),
        current_user=current_user,
    )


@router.post("/{order_id}/submit-to-warehouse", response_model=OrderActionResponse)
def submit_to_warehouse(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    # H13: area_manager also allowed — typical flow is area-review → submit-to-warehouse
    current_user: User = Depends(require_roles("branch_manager", "area_manager", "admin", "super_admin"))
):
    """Branch manager / area manager submits approved order to warehouse"""
    return orders_service.submit_to_warehouse(
        db,
        order_id=order_id,
        current_user=current_user,
        client_request_id=request.headers.get("X-Client-Request-Id"),
    )


@router.post("/{order_id}/warehouse-review", response_model=OrderActionResponse)
def warehouse_review_order(
    order_id: int,
    payload: WarehouseReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("warehouse_user", "warehouse_manager", "admin", "super_admin"))
):
    """Warehouse reviews and adjusts approved quantities"""
    return orders_service.warehouse_review_order(
        db,
        order_id=order_id,
        payload=payload.model_dump(),
        current_user=current_user,
    )


@router.post("/{order_id}/approve", response_model=OrderActionResponse)
def warehouse_approve_order(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("warehouse_manager", "admin", "super_admin"))
):
    """Warehouse manager approves the order"""
    return orders_service.warehouse_approve_order(
        db,
        order_id=order_id,
        current_user=current_user,
        client_request_id=request.headers.get("X-Client-Request-Id"),
    )


@router.post("/{order_id}/reject", response_model=OrderActionResponse)
def warehouse_reject_order(
    order_id: int,
    payload: RejectOrderRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("warehouse_manager", "admin", "super_admin"))
):
    return orders_service.warehouse_reject_order(
        db,
        order_id=order_id,
        payload=payload.model_dump(),
        current_user=current_user,
        client_request_id=request.headers.get("X-Client-Request-Id"),
    )


@router.post("/{order_id}/start-picking", response_model=OrderActionResponse)
def start_picking(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("warehouse_user", "warehouse_manager", "admin", "super_admin"))
):
    return orders_service.start_picking(
        db,
        order_id=order_id,
        current_user=current_user,
        client_request_id=request.headers.get("X-Client-Request-Id"),
    )


@router.post("/{order_id}/dispatch", response_model=OrderActionResponse)
def dispatch_order(
    order_id: int,
    payload: DispatchOrderRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("warehouse_user", "warehouse_manager", "admin", "super_admin"))
):
    """
    Dispatch items from warehouse to branch.
    Updates warehouse stock and branch in_transit_qty.
    """
    return orders_service.dispatch_order(
        db,
        order_id=order_id,
        payload=payload.model_dump(),
        current_user=current_user,
        client_request_id=request.headers.get("X-Client-Request-Id"),
    )


@router.post("/{order_id}/receive", response_model=OrderActionResponse)
def receive_order(
    order_id: int,
    payload: ReceivingConfirmCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("branch_user", "branch_manager", "admin", "super_admin"))
):
    """
    Branch confirms receipt of dispatched items.
    Updates branch stock and closes the order.
    """
    return orders_service.receive_order(
        db,
        order_id=order_id,
        payload=payload.model_dump(),
        current_user=current_user,
        client_request_id=request.headers.get("X-Client-Request-Id"),
    )


@router.post("/{order_id}/cancel", response_model=OrderActionResponse)
def cancel_order(
    order_id: int,
    payload: CancelOrderRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Cancel an order. Branch can cancel before warehouse approval; warehouse/admin can cancel up to picking."""
    return orders_service.cancel_order(
        db,
        order_id=order_id,
        reason=payload.reason,
        current_user=current_user,
        client_request_id=request.headers.get("X-Idempotency-Key"),
    )


# ──────────────────────────────────────────────────────────────────────────
# Close order — final lifecycle step (received/dispatched → closed)
# ──────────────────────────────────────────────────────────────────────────
@router.post("/{order_id}/close", response_model=OrderActionResponse)
def close_order(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "warehouse_manager",
            "operations_manager",
            "admin",
            "super_admin",
        )
    ),
):
    """Mark a received/dispatched order as closed (end of lifecycle, no more changes)."""
    return orders_service.close_order(
        db,
        order_id=order_id,
        current_user=current_user,
        client_request_id=request.headers.get("X-Idempotency-Key"),
    )


# ──────────────────────────────────────────────────────────────────────────
# Order timeline — status/action history
# ──────────────────────────────────────────────────────────────────────────
@router.get("/{order_id}/timeline")
def get_order_timeline(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Return the list of status transitions for an order (audit/history view)."""
    return orders_service.get_order_timeline(
        db,
        order_id=order_id,
        current_user=current_user,
    )


# ──────────────────────────────────────────────────────────────────────────
# Auto-replenishment — manual trigger (admin only)
# ──────────────────────────────────────────────────────────────────────────
@router.post("/auto-replenishment/run", status_code=200)
def trigger_auto_replenishment(
    db: Session = Depends(get_db),
    days_of_cover: int = Query(3, ge=1, le=14),
    current_user: User = Depends(
        require_roles("super_admin", "admin", "operations_manager")
    ),
):
    """
    تشغيل دورة الـ auto-replenishment يدوياً لجميع الفروع النشطة.
    الـ scheduler يعمل تلقائياً كل يوم لو REPLENISHMENT_SCHEDULER_ENABLED=true،
    هذا الـ endpoint للتشغيل الطارئ أو الاختبار.
    """
    from app.services.scheduler_service import run_auto_replenishment_once

    result = run_auto_replenishment_once(db, days_of_cover=days_of_cover)
    return result


# ──────────────────────────────────────────────────────────────────────────
# Inter-branch transfer workflow (OrderType.inter_branch)
#   1. branch_manager → POST /orders/inter-branch               (create request)
#   2. area_manager   → GET  /orders/inter-branch/pending       (list requests)
#   3. area_manager   → POST /orders/{id}/inter-branch-approve  (move stock)
#   4. area_manager   → POST /orders/{id}/inter-branch-reject   (reject)
# ──────────────────────────────────────────────────────────────────────────

@router.post("/inter-branch", status_code=201, response_model=InterBranchOrderOut)
def create_inter_branch_order(
    payload: InterBranchOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("branch_manager", "area_manager", "operations_manager", "admin", "super_admin")
    ),
):
    """مدير الفرع يُنشئ طلب تحويل مخزون إلى فرع آخر (بانتظار موافقة مدير المنطقة)."""
    return inter_branch_service.create_inter_branch_order(
        db,
        source_branch_id=payload.source_branch_id,
        destination_branch_id=payload.destination_branch_id,
        items=[{"item_id": l.item_id, "qty": l.qty} for l in payload.items],
        reason=payload.reason,
        reference_no=payload.reference_no,
        notes=payload.notes,
        current_user=current_user,
    )


@router.get("/inter-branch/pending")
def list_pending_inter_branch_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("area_manager", "operations_manager", "admin", "super_admin")
    ),
):
    """قائمة طلبات التحويل المنتظرة موافقة مدير المنطقة (مقيّدة بمنطقته)."""
    return inter_branch_service.list_pending_inter_branch(db, current_user=current_user)


@router.post("/{order_id}/inter-branch-approve")
def approve_inter_branch_order(
    order_id: int,
    payload: InterBranchApproveRequest = Body(default=InterBranchApproveRequest()),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("area_manager", "operations_manager", "admin", "super_admin")
    ),
):
    """مدير المنطقة يوافق على طلب التحويل — المخزون ينتقل فعليًا."""
    return inter_branch_service.approve_inter_branch_order(
        db,
        order_id=order_id,
        notes=payload.notes,
        current_user=current_user,
    )


@router.post("/{order_id}/inter-branch-reject")
def reject_inter_branch_order(
    order_id: int,
    payload: InterBranchRejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("area_manager", "operations_manager", "admin", "super_admin")
    ),
):
    """مدير المنطقة يرفض طلب التحويل مع ذكر السبب."""
    return inter_branch_service.reject_inter_branch_order(
        db,
        order_id=order_id,
        reason=payload.reason,
        current_user=current_user,
    )
