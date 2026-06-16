from datetime import datetime
from decimal import Decimal
from html import escape
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, joinedload

from app.core.auth import get_user_roles, require_roles
from app.core.errors import AppError
from app.core.locking import lock_row
from app.database import get_db
from app.models import (
    Branch,
    BranchBrand,
    BranchRequestLine,
    BranchRequestLineStatus,
    KitchenMaterialRequest,
    KitchenMaterialRequestStatus,
    KitchenSectionAssignment,
    Item,
    ProductionOrder,
    ProductionOrderStatus,
    ReplenishmentOrder,
    ReplenishmentOrderLine,
    SupplyDefaultSource,
    TransactionType,
    User,
    WarehouseLine,
    WarehouseLineSourceType,
    WarehouseLineStatus,
    WarehouseStock,
)
from app.schemas import (
    KitchenMaterialRequestOut,
    KitchenMaterialDecisionPayload,
    KitchenMaterialRejectPayload,
    ProductionMaterialRequestCreate,
    ProductionOrderOut,
    ProductionQtyPayload,
)
from app.services import audit_service, stock_ledger_service
from app.services import supply_chain_idempotency_service
from app.services.supply_chain_serializers import production_order_out


router = APIRouter(prefix="/api/v1/production-orders", tags=["Production Orders"])

PRODUCTION_ROLES = ("kitchen_section_manager", "internal_auditor", "admin", "super_admin")
MATERIAL_APPROVE_ROLES = ("warehouse_manager", "admin", "super_admin")
MATERIAL_ISSUE_ROLES = ("warehouse_user", "warehouse_manager", "admin", "super_admin")


def _roles(user: User) -> list[str]:
    return get_user_roles(user)


def _broad_access(user: User) -> bool:
    return any(r in _roles(user) for r in ("admin", "super_admin", "internal_auditor"))


def _norm_city(value: str | None) -> str | None:
    if value is None:
        return None
    v = str(value).strip().lower()
    return v or None


def _kitchen_scopes(db: Session, user: User) -> list[tuple[int, str | None]]:
    """(kitchen_section_id, service_city or None). None city = all cities for that section."""
    now = datetime.utcnow()
    rows = (
        db.query(KitchenSectionAssignment.kitchen_section_id, KitchenSectionAssignment.service_city)
        .filter(
            KitchenSectionAssignment.user_id == user.id,
            KitchenSectionAssignment.active == True,
            (KitchenSectionAssignment.ended_at.is_(None)) | (KitchenSectionAssignment.ended_at > now),
        )
        .all()
    )
    return [(int(r[0]), r[1]) for r in rows]


def _get_order(db: Session, order_id: int) -> ProductionOrder:
    row = db.query(ProductionOrder).options(
        joinedload(ProductionOrder.item),
        joinedload(ProductionOrder.kitchen_section),
        joinedload(ProductionOrder.destination_branch),
    ).filter(ProductionOrder.id == order_id).first()
    if not row:
        raise AppError(
            status_code=404,
            error_code="production_orders.not_found",
            message="Production order not found",
            detail={"production_order_id": order_id},
        )
    return row


def _serialize_production_order(db: Session, order_or_id: ProductionOrder | int) -> ProductionOrderOut:
    row = _get_order(db, order_or_id) if isinstance(order_or_id, int) else order_or_id
    return production_order_out(row)


def _require_section_access(db: Session, user: User, row: ProductionOrder) -> None:
    if _broad_access(user):
        return
    if "kitchen_section_manager" not in _roles(user):
        raise AppError(
            status_code=403,
            error_code="production_orders.section_access_denied",
            message="Access denied for this kitchen section",
            detail={"kitchen_section_id": row.kitchen_section_id},
        )
    branch = row.destination_branch
    dest_city = _norm_city(branch.city) if branch else None
    now = datetime.utcnow()
    assignments = (
        db.query(KitchenSectionAssignment)
        .filter(
            KitchenSectionAssignment.user_id == user.id,
            KitchenSectionAssignment.kitchen_section_id == row.kitchen_section_id,
            KitchenSectionAssignment.active == True,
            (KitchenSectionAssignment.ended_at.is_(None)) | (KitchenSectionAssignment.ended_at > now),
        )
        .all()
    )
    for asg in assignments:
        if asg.service_city is None or _norm_city(asg.service_city) == dest_city:
            return
    raise AppError(
        status_code=403,
        error_code="production_orders.section_access_denied",
        message="Access denied for this kitchen section",
        detail={"kitchen_section_id": row.kitchen_section_id},
    )


def _audit(db: Session, request: Request, user: User, action: str, row: ProductionOrder, values: dict | None = None) -> None:
    audit_service.log(
        db,
        user_id=user.id,
        action=action,
        module="production_orders",
        entity_type="production_order",
        entity_id=row.id,
        new_values=values,
        ip_address=request.client.host if request.client else None,
    )


def _daily_kitchen_lines_query(db: Session, current_user: User, source_order_id: int | None = None):
    q = (
        db.query(ReplenishmentOrderLine, ReplenishmentOrder, Branch)
        .join(ReplenishmentOrder, ReplenishmentOrder.id == ReplenishmentOrderLine.order_id)
        .join(Branch, Branch.id == ReplenishmentOrder.branch_id)
        .join(Item, Item.id == ReplenishmentOrderLine.item_id)
        .options(joinedload(ReplenishmentOrderLine.item))
        .filter(
            Item.default_source == SupplyDefaultSource.KITCHEN,
            ReplenishmentOrderLine.wh_approved_qty > 0,
        )
    )
    if source_order_id is not None:
        q = q.filter(ReplenishmentOrder.id == source_order_id)

    if not _broad_access(current_user):
        scopes = _kitchen_scopes(db, current_user)
        if not scopes:
            return q.filter(ReplenishmentOrderLine.id == -1)
        conds = []
        for sid, svc_city in scopes:
            if svc_city:
                conds.append(
                    and_(
                        Item.kitchen_section_id == sid,
                        func.lower(func.trim(Branch.city)) == _norm_city(svc_city),
                    )
                )
            else:
                conds.append(Item.kitchen_section_id == sid)
        q = q.filter(or_(*conds))
    return q


def _daily_status(lines: list[ReplenishmentOrderLine], order_status: str) -> str:
    statuses = {str(line.line_status or "") for line in lines}
    if statuses and statuses.issubset({"kitchen_sent_to_warehouse"}):
        return "kitchen_sent_to_warehouse"
    if statuses and statuses.issubset({"kitchen_ready", "kitchen_sent_to_warehouse"}):
        return "kitchen_ready"
    if "kitchen_in_progress" in statuses:
        return "kitchen_in_progress"
    if "kitchen_received" in statuses:
        return "kitchen_received"
    return order_status


def _daily_line_item_dict(item: Item | None) -> dict | None:
    if not item:
        return None
    return {
        "id": item.id,
        "item_code": item.item_code,
        "item_name_ar": item.item_name_ar,
        "item_name_en": item.item_name_en,
        "category_id": item.category_id,
        "unit_id": item.unit_id,
        "item_type": item.item_type.value if hasattr(item.item_type, "value") else str(item.item_type),
        "storage_type": item.storage_type.value if hasattr(item.storage_type, "value") else str(item.storage_type),
        "purchase_unit_id": item.purchase_unit_id,
        "supply_unit_id": item.supply_unit_id,
        "conversion_ratio": item.conversion_ratio,
        "branch_requestable": item.branch_requestable,
        "visible_in_branch_ui": item.visible_in_branch_ui,
        "active": item.active,
        "min_qty": item.min_qty,
        "max_qty": item.max_qty,
        "reorder_point": item.reorder_point,
        "safety_stock": item.safety_stock,
        "lead_time_days": item.lead_time_days,
        "shelf_life_days": item.shelf_life_days,
        "average_consumption_mode": item.average_consumption_mode.value if hasattr(item.average_consumption_mode, "value") else str(item.average_consumption_mode),
        "critical_item": item.critical_item,
        "source_type": item.source_type.value if hasattr(item.source_type, "value") else str(item.source_type),
        "default_source": item.default_source.value if hasattr(item.default_source, "value") else str(item.default_source),
        "kitchen_section_id": item.kitchen_section_id,
    }


def _get_material_request(db: Session, material_request_id: int) -> KitchenMaterialRequest:
    row = db.query(KitchenMaterialRequest).options(
        joinedload(KitchenMaterialRequest.production_order).joinedload(ProductionOrder.destination_branch),
        joinedload(KitchenMaterialRequest.item),
        joinedload(KitchenMaterialRequest.kitchen_section),
    ).filter(KitchenMaterialRequest.id == material_request_id).first()
    if not row:
        raise AppError(
            status_code=404,
            error_code="kitchen_material_requests.not_found",
            message="Kitchen material request not found",
            detail={"kitchen_material_request_id": material_request_id},
        )
    return row


def _require_material_warehouse_access(user: User, row: KitchenMaterialRequest) -> None:
    if _broad_access(user):
        return
    if user.warehouse_id is None:
        raise AppError(
            status_code=403,
            error_code="kitchen_material_requests.access_denied",
            message="Warehouse assignment is required",
            detail={"kitchen_material_request_id": row.id},
        )
    branch = row.production_order.destination_branch if row.production_order else None
    if branch and branch.warehouse_id == user.warehouse_id:
        return
    raise AppError(
        status_code=403,
        error_code="kitchen_material_requests.access_denied",
        message="Access denied for this kitchen material request",
        detail={"kitchen_material_request_id": row.id},
    )


@router.get("", response_model=list[ProductionOrderOut])
def list_production_orders(
    status: Optional[ProductionOrderStatus] = None,
    kitchen_section_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*PRODUCTION_ROLES)),
):
    q = db.query(ProductionOrder).options(
        joinedload(ProductionOrder.item),
        joinedload(ProductionOrder.destination_branch).joinedload(Branch.warehouse),
    )
    if not _broad_access(current_user):
        q = q.join(Branch, Branch.id == ProductionOrder.destination_branch_id)
        scopes = _kitchen_scopes(db, current_user)
        if not scopes:
            q = q.filter(ProductionOrder.id == -1)
        else:
            conds = []
            for sid, svc_city in scopes:
                if svc_city:
                    conds.append(
                        and_(
                            ProductionOrder.kitchen_section_id == sid,
                            func.lower(func.trim(Branch.city)) == _norm_city(svc_city),
                        )
                    )
                else:
                    conds.append(ProductionOrder.kitchen_section_id == sid)
            q = q.filter(or_(*conds))
    if status:
        q = q.filter(ProductionOrder.status == status)
    if kitchen_section_id:
        q = q.filter(ProductionOrder.kitchen_section_id == kitchen_section_id)
    rows = q.order_by(ProductionOrder.created_at.desc()).all()
    return [production_order_out(row) for row in rows]


@router.get("/daily-kitchen-lines")
def list_daily_order_kitchen_lines(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*PRODUCTION_ROLES)),
):
    """
    Surface KITCHEN-routed lines from the legacy daily order flow on the
    kitchen section page. Daily replenishment orders are not ProductionOrder
    rows, so these rows are read-only operational visibility.
    """
    q = _daily_kitchen_lines_query(db, current_user)
    result = []
    for line, order, branch in q.order_by(ReplenishmentOrder.created_at.desc(), ReplenishmentOrderLine.id.asc()).all():
        item = line.item
        result.append({
            "id": f"daily-{line.id}",
            "legacy_daily": True,
            "source_order_id": order.id,
            "source_order_no": order.order_no,
            "source_line_id": line.id,
            "destination_branch_id": order.branch_id,
            "destination_branch": {
                "id": branch.id,
                "branch_name": branch.branch_name,
                "branch_name_ar": branch.branch_name,
            },
            "brand_id": None,
            "kitchen_section_id": item.kitchen_section_id if item else None,
            "item_id": line.item_id,
            "qty_requested": line.wh_approved_qty,
            "qty_ready": line.picked_qty,
            "qty_sent_to_warehouse": line.dispatched_qty,
            "status": order.status.value if hasattr(order.status, "value") else str(order.status),
            "priority": None,
            "notes": f"Daily order {order.order_no}",
            "created_at": order.created_at,
            "updated_at": order.updated_at or order.created_at,
            "item": _daily_line_item_dict(item),
        })
    return result


@router.get("/daily-kitchen-orders")
def list_daily_kitchen_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*PRODUCTION_ROLES)),
):
    grouped: dict[int, dict] = {}
    for line, order, branch in _daily_kitchen_lines_query(db, current_user).order_by(
        ReplenishmentOrder.created_at.desc(),
        ReplenishmentOrderLine.id.asc(),
    ).all():
        row = grouped.setdefault(order.id, {
            "id": order.id,
            "order_no": order.order_no,
            "branch_id": order.branch_id,
            "branch_name": branch.branch_name,
            "status": order.status.value if hasattr(order.status, "value") else str(order.status),
            "created_at": order.created_at,
            "updated_at": order.updated_at or order.created_at,
            "lines": [],
        })
        row["lines"].append({
            "id": line.id,
            "item_id": line.item_id,
            "item": _daily_line_item_dict(line.item),
            "qty_requested": line.wh_approved_qty,
            "qty_ready": line.picked_qty,
            "qty_sent_to_warehouse": line.dispatched_qty,
            "line_status": line.line_status,
            "notes": line.notes,
        })

    for row in grouped.values():
        row["items_count"] = len(row["lines"])
        row["qty_requested_total"] = sum(Decimal(str(line["qty_requested"] or 0)) for line in row["lines"])
        row["qty_ready_total"] = sum(Decimal(str(line["qty_ready"] or 0)) for line in row["lines"])
        row["qty_sent_total"] = sum(Decimal(str(line["qty_sent_to_warehouse"] or 0)) for line in row["lines"])
        row["kitchen_status"] = _daily_status(
            [
                type("Line", (), {"line_status": line["line_status"]})()
                for line in row["lines"]
            ],
            row["status"],
        )
    return list(grouped.values())


def _load_daily_kitchen_order_rows(db: Session, current_user: User, source_order_id: int):
    rows = _daily_kitchen_lines_query(db, current_user, source_order_id).order_by(ReplenishmentOrderLine.id.asc()).all()
    if not rows:
        raise AppError(
            status_code=404,
            error_code="production_orders.daily_kitchen_order_not_found",
            message="Daily kitchen order not found for this section",
            detail={"source_order_id": source_order_id},
        )
    return rows


@router.post("/daily-kitchen-orders/{source_order_id}/receive")
def receive_daily_kitchen_order(
    source_order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*PRODUCTION_ROLES)),
):
    rows = _load_daily_kitchen_order_rows(db, current_user, source_order_id)
    for line, _, _ in rows:
        if line.line_status != "kitchen_sent_to_warehouse":
            line.line_status = "kitchen_received"
    db.commit()
    return {"source_order_id": source_order_id, "status": "kitchen_received"}


@router.post("/daily-kitchen-orders/{source_order_id}/start")
def start_daily_kitchen_order(
    source_order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*PRODUCTION_ROLES)),
):
    rows = _load_daily_kitchen_order_rows(db, current_user, source_order_id)
    for line, _, _ in rows:
        if line.line_status != "kitchen_sent_to_warehouse":
            line.line_status = "kitchen_in_progress"
    db.commit()
    return {"source_order_id": source_order_id, "status": "kitchen_in_progress"}


@router.post("/daily-kitchen-orders/{source_order_id}/mark-ready")
def mark_daily_kitchen_order_ready(
    source_order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*PRODUCTION_ROLES)),
):
    rows = _load_daily_kitchen_order_rows(db, current_user, source_order_id)
    for line, _, _ in rows:
        if line.line_status != "kitchen_sent_to_warehouse":
            line.picked_qty = line.wh_approved_qty
            line.line_status = "kitchen_ready"
    db.commit()
    return {"source_order_id": source_order_id, "status": "kitchen_ready"}


@router.post("/daily-kitchen-orders/{source_order_id}/send-to-warehouse")
def send_daily_kitchen_order_to_warehouse(
    source_order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*PRODUCTION_ROLES)),
):
    rows = _load_daily_kitchen_order_rows(db, current_user, source_order_id)
    _, order, branch = rows[0]
    brand = db.query(BranchBrand).filter(BranchBrand.branch_id == order.branch_id).order_by(BranchBrand.id).first()
    if not brand:
        raise AppError(
            status_code=400,
            error_code="production_orders.branch_brand_missing",
            message="Branch has no brand mapping",
            detail={"branch_id": order.branch_id},
        )

    created = 0
    for line, _, _ in rows:
        if Decimal(str(line.picked_qty or 0)) <= 0:
            line.picked_qty = line.wh_approved_qty
        line.dispatched_qty = line.picked_qty
        line.line_status = "kitchen_sent_to_warehouse"
        marker = f"daily_order:{order.order_no}:line:{line.id}"
        exists = db.query(WarehouseLine).filter(
            WarehouseLine.source_type == WarehouseLineSourceType.KITCHEN_OUTPUT,
            WarehouseLine.branch_id == order.branch_id,
            WarehouseLine.item_id == line.item_id,
            WarehouseLine.delay_reason == marker,
        ).first()
        if not exists:
            db.add(WarehouseLine(
                source_request_id=None,
                source_request_line_id=None,
                source_type=WarehouseLineSourceType.KITCHEN_OUTPUT,
                branch_id=order.branch_id,
                brand_id=brand.brand_id,
                kitchen_section_id=line.item.kitchen_section_id if line.item else None,
                item_id=line.item_id,
                requested_qty=line.dispatched_qty,
                issued_qty=Decimal("0"),
                pending_qty=line.dispatched_qty,
                status=WarehouseLineStatus.PENDING,
                delay_reason=marker,
            ))
            created += 1
    db.commit()
    return {"source_order_id": source_order_id, "status": "kitchen_sent_to_warehouse", "warehouse_lines_created": created}


@router.get("/daily-kitchen-orders/{source_order_id}/pdf", response_class=HTMLResponse)
def daily_kitchen_order_pdf(
    source_order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*PRODUCTION_ROLES)),
):
    rows = _load_daily_kitchen_order_rows(db, current_user, source_order_id)
    _, order, branch = rows[0]
    line_html = []
    for line, _, _ in rows:
        item_name = line.item.item_name_en if line.item else str(line.item_id)
        line_html.append(
            f"<tr><td>{escape(item_name)}</td><td>{escape(line.item.item_code if line.item else '')}</td>"
            f"<td>{escape(str(line.wh_approved_qty))}</td><td>{escape(str(line.picked_qty or 0))}</td></tr>"
        )
    return HTMLResponse(f"""
    <!doctype html>
    <html lang="ar" dir="rtl">
    <head>
      <meta charset="utf-8">
      <title>{escape(order.order_no)} Kitchen Order</title>
      <style>
        body {{ font-family: Arial, sans-serif; margin: 24px; color: #111827; }}
        h1 {{ margin: 0 0 8px; font-size: 24px; }}
        .meta {{ margin: 4px 0; color: #374151; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 18px; }}
        th, td {{ border: 1px solid #d1d5db; padding: 8px; text-align: right; }}
        th {{ background: #f3f4f6; }}
        button {{ margin-bottom: 16px; padding: 8px 14px; }}
        @media print {{ button {{ display: none; }} }}
      </style>
    </head>
    <body>
      <button onclick="window.print()">طباعة / حفظ PDF</button>
      <h1>طلبية مطبخ</h1>
      <div class="meta"><strong>رقم الطلبية:</strong> {escape(order.order_no)}</div>
      <div class="meta"><strong>الفرع:</strong> {escape(branch.branch_name)}</div>
      <div class="meta"><strong>التاريخ:</strong> {escape(str(order.order_date))}</div>
      <table>
        <thead><tr><th>الصنف</th><th>الكود</th><th>المطلوب</th><th>الجاهز</th></tr></thead>
        <tbody>{''.join(line_html)}</tbody>
      </table>
    </body>
    </html>
    """)


@router.get("/{order_id}", response_model=ProductionOrderOut)
def get_production_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*PRODUCTION_ROLES)),
):
    row = _get_order(db, order_id)
    _require_section_access(db, current_user, row)
    return _serialize_production_order(db, row)


@router.post("/{order_id}/start", response_model=ProductionOrderOut)
def start_production_order(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*PRODUCTION_ROLES)),
):
    idempotency_record, replayed = supply_chain_idempotency_service.begin(
        db,
        client_request_id=request.headers.get("X-Idempotency-Key"),
        operation_name="production_orders.start",
        current_user=current_user,
    )
    row = _get_order(db, order_id)
    _require_section_access(db, current_user, row)
    if replayed or row.status == ProductionOrderStatus.IN_PROGRESS:
        return _serialize_production_order(db, row)
    if row.status != ProductionOrderStatus.PENDING:
        raise AppError(status_code=400, error_code="production_orders.invalid_status", message="Only pending orders can start")
    row.status = ProductionOrderStatus.IN_PROGRESS
    row.updated_at = datetime.utcnow()
    if row.source_request_line:
        row.source_request_line.status = BranchRequestLineStatus.IN_PRODUCTION
    _audit(db, request, current_user, "production_started", row, {"status": row.status.value})
    db.commit()
    supply_chain_idempotency_service.complete(db, record=idempotency_record, response_reference_type="production_order", response_reference_id=row.id)
    return _serialize_production_order(db, row.id)


@router.post("/{order_id}/mark-partial-ready", response_model=ProductionOrderOut)
def mark_partial_ready(
    order_id: int,
    payload: ProductionQtyPayload,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*PRODUCTION_ROLES)),
):
    row = _get_order(db, order_id)
    _require_section_access(db, current_user, row)
    if row.status != ProductionOrderStatus.IN_PROGRESS:
        raise AppError(
            status_code=400,
            error_code="production_orders.invalid_status",
            message="Partial ready is only allowed from IN_PROGRESS",
            detail={"status": row.status.value},
        )
    if payload.qty_ready >= row.qty_requested:
        raise AppError(
            status_code=400,
            error_code="production_orders.partial_qty_invalid",
            message="Partial ready quantity must be less than requested quantity",
            detail={"qty_requested": str(row.qty_requested), "qty_ready": str(payload.qty_ready)},
        )
    row.qty_ready = payload.qty_ready
    row.status = ProductionOrderStatus.PARTIAL_READY
    row.notes = payload.notes or row.notes
    row.updated_at = datetime.utcnow()
    _audit(db, request, current_user, "production_partial_ready", row, {"qty_ready": str(row.qty_ready)})
    db.commit()
    return _serialize_production_order(db, row.id)


@router.post("/{order_id}/mark-ready", response_model=ProductionOrderOut)
def mark_ready(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*PRODUCTION_ROLES)),
):
    idempotency_record, replayed = supply_chain_idempotency_service.begin(
        db,
        client_request_id=request.headers.get("X-Idempotency-Key"),
        operation_name="production_orders.mark_ready",
        current_user=current_user,
    )
    row = _get_order(db, order_id)
    _require_section_access(db, current_user, row)
    if replayed or row.status == ProductionOrderStatus.READY:
        return _serialize_production_order(db, row)
    if row.status not in (ProductionOrderStatus.IN_PROGRESS, ProductionOrderStatus.PARTIAL_READY):
        raise AppError(
            status_code=400,
            error_code="production_orders.invalid_status",
            message="Ready is only allowed from IN_PROGRESS or PARTIAL_READY",
            detail={"status": row.status.value},
        )
    row.qty_ready = row.qty_requested
    row.status = ProductionOrderStatus.READY
    row.updated_at = datetime.utcnow()
    _audit(db, request, current_user, "production_ready", row, {"qty_ready": str(row.qty_ready)})
    db.commit()
    supply_chain_idempotency_service.complete(db, record=idempotency_record, response_reference_type="production_order", response_reference_id=row.id)
    return _serialize_production_order(db, row.id)


@router.post("/{order_id}/send-to-warehouse", response_model=ProductionOrderOut)
def send_to_warehouse(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*PRODUCTION_ROLES)),
):
    idempotency_record, replayed = supply_chain_idempotency_service.begin(
        db,
        client_request_id=request.headers.get("X-Idempotency-Key"),
        operation_name="production_orders.send_to_warehouse",
        current_user=current_user,
    )
    row = _get_order(db, order_id)
    _require_section_access(db, current_user, row)
    if replayed:
        return _serialize_production_order(db, row)
    if row.status not in (ProductionOrderStatus.READY, ProductionOrderStatus.PARTIAL_READY, ProductionOrderStatus.SENT_TO_WAREHOUSE):
        raise AppError(
            status_code=400,
            error_code="production_orders.not_ready",
            message="Only ready or partial-ready production can be sent to warehouse",
        )
    ready_qty = Decimal(str(row.qty_ready))
    if ready_qty <= 0:
        raise AppError(status_code=400, error_code="production_orders.no_ready_qty", message="No ready quantity to send")
    sent_qty = Decimal(str(row.qty_sent_to_warehouse or 0))
    qty_to_send = ready_qty - sent_qty
    if qty_to_send < 0:
        raise AppError(
            status_code=400,
            error_code="production_orders.sent_qty_exceeds_ready",
            message="Sent quantity cannot exceed ready quantity",
            detail={"qty_ready": str(row.qty_ready), "qty_sent_to_warehouse": str(row.qty_sent_to_warehouse)},
        )
    wh = db.query(WarehouseLine).filter(
        WarehouseLine.source_request_line_id == row.source_request_line_id,
        WarehouseLine.source_type == WarehouseLineSourceType.KITCHEN_OUTPUT,
    ).first()
    if qty_to_send > 0 and not wh:
        wh = WarehouseLine(
            source_request_id=row.source_request_id,
            source_request_line_id=row.source_request_line_id,
            source_type=WarehouseLineSourceType.KITCHEN_OUTPUT,
            branch_id=row.destination_branch_id,
            brand_id=row.brand_id,
            kitchen_section_id=row.kitchen_section_id,
            item_id=row.item_id,
            requested_qty=qty_to_send,
            issued_qty=Decimal("0"),
            pending_qty=qty_to_send,
            status=WarehouseLineStatus.AVAILABLE,
        )
        db.add(wh)
    elif qty_to_send > 0:
        wh.requested_qty = Decimal(str(wh.requested_qty or 0)) + qty_to_send
        wh.pending_qty = Decimal(str(wh.pending_qty or 0)) + qty_to_send
        wh.status = WarehouseLineStatus.AVAILABLE if wh.pending_qty > 0 else WarehouseLineStatus.READY_FOR_DISPATCH
        wh.updated_at = datetime.utcnow()
    warehouse_id = row.destination_branch.warehouse_id if row.destination_branch else None
    if not warehouse_id:
        raise AppError(
            status_code=400,
            error_code="production_orders.destination_warehouse_missing",
            message="Destination branch has no warehouse",
            detail={"branch_id": row.destination_branch_id},
        )
    if qty_to_send > 0:
        stock = db.query(WarehouseStock).filter(
            WarehouseStock.warehouse_id == warehouse_id,
            WarehouseStock.item_id == row.item_id,
        ).first()
        if not stock:
            stock = WarehouseStock(
                warehouse_id=warehouse_id,
                item_id=row.item_id,
                current_qty=Decimal("0"),
                reserved_qty=Decimal("0"),
            )
            db.add(stock)
        stock.current_qty = Decimal(str(stock.current_qty or 0)) + qty_to_send
        stock.last_updated = datetime.utcnow()
        row.qty_sent_to_warehouse = sent_qty + qty_to_send
        stock_ledger_service.post_transaction(
            db,
            transaction_type=TransactionType.adjustment_in,
            item_id=row.item_id,
            qty=qty_to_send,
            source_type="kitchen_output",
            source_id=row.kitchen_section_id,
            destination_type="warehouse",
            destination_id=warehouse_id,
            reference_no=f"PO-{row.id}-{row.qty_sent_to_warehouse}",
            notes="Supply Chain V1 kitchen output received into warehouse",
            created_by=current_user.id,
        )
    if Decimal(str(row.qty_sent_to_warehouse or 0)) >= Decimal(str(row.qty_requested)):
        row.status = ProductionOrderStatus.SENT_TO_WAREHOUSE
    elif row.status == ProductionOrderStatus.READY:
        row.status = ProductionOrderStatus.PARTIAL_READY
    row.updated_at = datetime.utcnow()
    if row.source_request_line:
        row.source_request_line.status = (
            BranchRequestLineStatus.READY_IN_WAREHOUSE
            if Decimal(str(row.qty_sent_to_warehouse or 0)) >= Decimal(str(row.qty_requested))
            else BranchRequestLineStatus.PARTIAL_WAREHOUSE
        )
    _audit(
        db,
        request,
        current_user,
        "production_sent_to_warehouse",
        row,
        {"qty_ready": str(row.qty_ready), "qty_sent_to_warehouse": str(row.qty_sent_to_warehouse), "qty_sent_now": str(qty_to_send)},
    )
    db.commit()
    supply_chain_idempotency_service.complete(db, record=idempotency_record, response_reference_type="production_order", response_reference_id=row.id)
    return _serialize_production_order(db, row.id)


@router.post("/{order_id}/request-materials", response_model=KitchenMaterialRequestOut, status_code=201)
def request_materials(
    order_id: int,
    payload: ProductionMaterialRequestCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*PRODUCTION_ROLES)),
):
    row = _get_order(db, order_id)
    _require_section_access(db, current_user, row)
    if row.status not in (ProductionOrderStatus.PENDING, ProductionOrderStatus.IN_PROGRESS):
        raise AppError(
            status_code=400,
            error_code="production_orders.invalid_status",
            message="Material requests are only allowed from PENDING or IN_PROGRESS",
            detail={"status": row.status.value},
        )
    material = KitchenMaterialRequest(
        production_order_id=row.id,
        kitchen_section_id=row.kitchen_section_id,
        item_id=payload.item_id,
        qty=payload.qty,
        status=KitchenMaterialRequestStatus.PENDING,
        notes=payload.notes,
    )
    row.status = ProductionOrderStatus.WAITING_FOR_MATERIALS
    row.updated_at = datetime.utcnow()
    db.add(material)
    _audit(db, request, current_user, "kitchen_material_requested", row, {"item_id": payload.item_id, "qty": str(payload.qty)})
    db.commit()
    db.refresh(material)
    return material


@router.post("/material-requests/{material_request_id}/approve", response_model=KitchenMaterialRequestOut)
def approve_material_request(
    material_request_id: int,
    payload: KitchenMaterialDecisionPayload,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*MATERIAL_APPROVE_ROLES)),
):
    row = _get_material_request(db, material_request_id)
    _require_material_warehouse_access(current_user, row)
    if row.status == KitchenMaterialRequestStatus.APPROVED:
        return row
    if row.status != KitchenMaterialRequestStatus.PENDING:
        raise AppError(
            status_code=400,
            error_code="kitchen_material_requests.invalid_status",
            message="Only pending requests can be approved",
            detail={"status": row.status.value},
        )
    row.status = KitchenMaterialRequestStatus.APPROVED
    if payload.notes:
        row.notes = payload.notes
    _audit(
        db,
        request,
        current_user,
        "kitchen_material_approved",
        row.production_order,
        {"material_request_id": row.id, "status": row.status.value},
    )
    db.commit()
    db.refresh(row)
    return row


@router.post("/material-requests/{material_request_id}/issue", response_model=KitchenMaterialRequestOut)
def issue_material_request(
    material_request_id: int,
    payload: KitchenMaterialDecisionPayload,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*MATERIAL_ISSUE_ROLES)),
):
    row = _get_material_request(db, material_request_id)
    _require_material_warehouse_access(current_user, row)
    if row.status == KitchenMaterialRequestStatus.ISSUED:
        return row
    if row.status not in (KitchenMaterialRequestStatus.PENDING, KitchenMaterialRequestStatus.APPROVED):
        raise AppError(
            status_code=400,
            error_code="kitchen_material_requests.invalid_status",
            message="Only pending or approved requests can be issued",
            detail={"status": row.status.value},
        )
    branch = row.production_order.destination_branch if row.production_order else None
    warehouse_id = branch.warehouse_id if branch else None
    if not warehouse_id:
        raise AppError(
            status_code=400,
            error_code="kitchen_material_requests.destination_warehouse_missing",
            message="Production destination branch has no warehouse",
            detail={"kitchen_material_request_id": row.id},
        )
    stock = lock_row(
        db.query(WarehouseStock).filter(
            WarehouseStock.warehouse_id == warehouse_id,
            WarehouseStock.item_id == row.item_id,
        )
    ).first()
    available_qty = Decimal(str(stock.current_qty or 0)) if stock else Decimal("0")
    if available_qty < Decimal(str(row.qty)):
        raise AppError(
            status_code=400,
            error_code="kitchen_material_requests.insufficient_stock",
            message="Insufficient warehouse stock for kitchen material issue",
            detail={"item_id": row.item_id, "required_qty": str(row.qty), "available_qty": str(available_qty)},
        )
    stock.current_qty = available_qty - Decimal(str(row.qty))
    stock.last_updated = datetime.utcnow()
    wh_line = WarehouseLine(
        source_request_id=row.production_order.source_request_id,
        source_request_line_id=None,
        source_type=WarehouseLineSourceType.KITCHEN_MATERIAL_REQUEST,
        branch_id=row.production_order.destination_branch_id,
        brand_id=row.production_order.brand_id,
        kitchen_section_id=row.kitchen_section_id,
        item_id=row.item_id,
        requested_qty=row.qty,
        issued_qty=row.qty,
        pending_qty=Decimal("0"),
        status=WarehouseLineStatus.DELIVERED,
        delay_reason=None,
    )
    db.add(wh_line)
    stock_ledger_service.post_transaction(
        db,
        transaction_type=TransactionType.warehouse_issue,
        item_id=row.item_id,
        qty=-Decimal(str(row.qty)),
        source_type="warehouse",
        source_id=warehouse_id,
        destination_type="kitchen_material_request",
        destination_id=row.id,
        reference_no=f"KMR-{row.id}",
        notes="Kitchen material issued from warehouse",
        created_by=current_user.id,
    )
    row.status = KitchenMaterialRequestStatus.ISSUED
    if payload.notes:
        row.notes = payload.notes
    row.production_order.status = ProductionOrderStatus.IN_PROGRESS
    row.production_order.updated_at = datetime.utcnow()
    _audit(
        db,
        request,
        current_user,
        "kitchen_material_issued",
        row.production_order,
        {"material_request_id": row.id, "qty": str(row.qty), "warehouse_id": warehouse_id},
    )
    db.commit()
    db.refresh(row)
    return row


@router.post("/material-requests/{material_request_id}/reject", response_model=KitchenMaterialRequestOut)
def reject_material_request(
    material_request_id: int,
    payload: KitchenMaterialRejectPayload,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*MATERIAL_APPROVE_ROLES)),
):
    row = _get_material_request(db, material_request_id)
    _require_material_warehouse_access(current_user, row)
    if row.status == KitchenMaterialRequestStatus.REJECTED:
        return row
    if row.status not in (KitchenMaterialRequestStatus.PENDING, KitchenMaterialRequestStatus.APPROVED):
        raise AppError(
            status_code=400,
            error_code="kitchen_material_requests.invalid_status",
            message="Only pending or approved requests can be rejected",
            detail={"status": row.status.value},
        )
    row.status = KitchenMaterialRequestStatus.REJECTED
    row.notes = payload.reason
    row.production_order.status = ProductionOrderStatus.IN_PROGRESS
    row.production_order.updated_at = datetime.utcnow()
    _audit(
        db,
        request,
        current_user,
        "kitchen_material_rejected",
        row.production_order,
        {"material_request_id": row.id, "reason": payload.reason},
    )
    db.commit()
    db.refresh(row)
    return row
