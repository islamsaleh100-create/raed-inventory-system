"""Branch request detail: timeline, fulfillment visibility, status summary."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session, joinedload

from app.models import (
    AuditLog,
    BranchRequest,
    BranchRequestLine,
    BranchRequestLineStatus,
    BranchRequestStatus,
    DeliveryOrder,
    DeliveryOrderLine,
    ProductionOrder,
    ProductionOrderStatus,
    SupplyDefaultSource,
    WarehouseLine,
    WarehouseLineSourceType,
)
from app.services import audit_service

AUDIT_ACTION_LABELS: dict[str, str] = {
    "request_created": "تم إنشاء الطلب",
    "request_updated": "تم تحديث الطلب",
    "request_submitted": "تم إرسال الطلب",
    "request_approved": "تم اعتماد الطلب",
    "request_modified_and_approved": "تم تعديل الكميات واعتماد الطلب",
    "request_rejected": "تم رفض الطلب",
    "request_auto_split": "تم تقسيم الطلب (مطبخ / مستودع)",
    "request_split": "تم تقسيم الطلب",
    "production_started": "بدء الإنتاج في المطبخ",
    "production_ready": "الإنتاج جاهز",
    "production_partial_ready": "جاهزية جزئية في المطبخ",
    "production_sent_to_warehouse": "إرسال من المطبخ إلى المستودع",
    "warehouse_receive": "استلام / إقرار المستودع",
    "warehouse_issue": "صرف من المستودع",
    "warehouse_partial_issue": "صرف جزئي من المستودع",
    "warehouse_delay_reason_added": "تسجيل سبب تأخير",
    "delivery_order_created": "إنشاء أمر تسليم",
    "delivery_out_for_delivery": "خرج للتسليم",
    "delivery_delivered": "تم التسليم للفرع",
    "delivery_partial_delivered": "تسليم جزئي للفرع",
}

STATUS_AR: dict[str, str] = {
    BranchRequestStatus.DRAFT.value: "مسودة",
    BranchRequestStatus.SUBMITTED.value: "مرسل — بانتظار مدير المنطقة",
    BranchRequestStatus.AREA_APPROVED.value: "معتمد — بانتظار التقسيم",
    BranchRequestStatus.AREA_REJECTED.value: "مرفوض",
    BranchRequestStatus.SPLIT.value: "تم التقسيم — قيد التنفيذ",
    BranchRequestStatus.IN_EXECUTION.value: "قيد التنفيذ",
    BranchRequestStatus.DELIVERED.value: "تم التسليم",
}


def _dec(value) -> Decimal:
    return Decimal(str(value or 0))


def _line_item_name(line: BranchRequestLine) -> str:
    if line.item_name_ar_snapshot:
        return line.item_name_ar_snapshot
    if line.item and line.item.item_name_ar:
        return line.item.item_name_ar
    if line.item and line.item.item_name_en:
        return line.item.item_name_en
    return f"صنف #{line.item_id}"


def _route_label(line: BranchRequestLine) -> str:
    src = line.resolved_source_type or line.source_type
    src_val = src.value if hasattr(src, "value") else str(src or "")
    src_up = src_val.upper()
    if "KITCHEN" in src_up and "WAREHOUSE" in src_up:
        return "مطبخ / مستودع"
    if src_up in ("KITCHEN",) or src == SupplyDefaultSource.KITCHEN:
        return "مطبخ"
    if src_up in ("WAREHOUSE", "BOTH") or src == SupplyDefaultSource.WAREHOUSE:
        return "مستودع" if src_up != "BOTH" else "مطبخ / مستودع"
    return "مستودع"


def _owner_for_request(status: BranchRequestStatus) -> tuple[str, str]:
    mapping = {
        BranchRequestStatus.DRAFT: ("الفرع", "إرسال الطلب لمدير المنطقة"),
        BranchRequestStatus.SUBMITTED: ("مدير المنطقة", "مراجعة الطلب والموافقة أو الرفض"),
        BranchRequestStatus.AREA_APPROVED: ("النظام", "تقسيم الطلب إلى مطبخ ومستودع"),
        BranchRequestStatus.AREA_REJECTED: ("—", "لا يوجد إجراء — الطلب مرفوض"),
        BranchRequestStatus.SPLIT: ("المطبخ / المستودع", "بدء التنفيذ (إنتاج أو صرف)"),
        BranchRequestStatus.IN_EXECUTION: ("المطبخ / المستودع / التسليم", "إكمال الصرف والتسليم"),
        BranchRequestStatus.DELIVERED: ("—", "لا يوجد إجراء — الطلب مكتمل"),
    }
    return mapping.get(status, ("—", "متابعة حالة الطلب"))


def _audit_events(db: Session, *, entity_type: str, entity_id: int) -> list[dict]:
    entries = audit_service.get_entity_history(db, entity_type=entity_type, entity_id=entity_id)
    events = []
    for entry in entries:
        action = entry.get("action") or ""
        label = AUDIT_ACTION_LABELS.get(action, action.replace("_", " "))
        events.append({
            "key": action,
            "label_ar": label,
            "at": entry.get("created_at"),
            "owner_role_ar": None,
            "detail": None,
            "source": "audit",
        })
    return events


def _request_field_events(row: BranchRequest) -> list[dict]:
    events = []
    if row.created_at:
        events.append({
            "key": "created",
            "label_ar": "تم إنشاء الطلب",
            "at": row.created_at,
            "owner_role_ar": "الفرع",
            "detail": None,
            "source": "request",
        })
    if row.submitted_at:
        events.append({
            "key": "submitted",
            "label_ar": "تم إرسال الطلب",
            "at": row.submitted_at,
            "owner_role_ar": "الفرع",
            "detail": None,
            "source": "request",
        })
    if row.approved_at:
        events.append({
            "key": "approved",
            "label_ar": "تم اعتماد الطلب",
            "at": row.approved_at,
            "owner_role_ar": "مدير المنطقة",
            "detail": row.approval_note,
            "source": "request",
        })
    if row.rejected_at:
        events.append({
            "key": "rejected",
            "label_ar": "تم رفض الطلب",
            "at": row.rejected_at,
            "owner_role_ar": "مدير المنطقة",
            "detail": row.rejection_note,
            "source": "request",
        })
    return events


def _fulfillment_for_line(
    db: Session,
    line: BranchRequestLine,
    warehouse_lines: list[WarehouseLine],
    production_orders: list[ProductionOrder],
    delivery_lines: list[DeliveryOrderLine],
) -> dict:
    requested = _dec(line.qty_approved or line.qty_requested)
    related_wh = [wl for wl in warehouse_lines if wl.source_request_line_id == line.id]
    related_po = [po for po in production_orders if po.source_request_line_id == line.id]

    issued = Decimal("0")
    delivered = Decimal("0")
    remaining = requested
    delay_reason = None

    for wl in related_wh:
        issued += _dec(wl.issued_qty)
        if wl.delay_reason:
            delay_reason = wl.delay_reason
        for dol in delivery_lines:
            if dol.warehouse_line_id == wl.id:
                delivered += _dec(dol.qty_delivered)

    if related_po and not related_wh:
        for po in related_po:
            if po.status == ProductionOrderStatus.SENT_TO_WAREHOUSE:
                issued = max(issued, _dec(po.qty_sent_to_warehouse))
            elif po.status in (ProductionOrderStatus.READY, ProductionOrderStatus.PARTIAL_READY):
                remaining = max(Decimal("0"), requested - _dec(po.qty_ready))

    if related_wh:
        remaining = sum(_dec(wl.pending_qty) for wl in related_wh)
        if remaining == 0 and delivered < requested and issued > delivered:
            remaining = max(Decimal("0"), requested - delivered)
    elif not related_po:
        remaining = requested

    return {
        "request_line_id": line.id,
        "item_id": line.item_id,
        "item_name": _line_item_name(line),
        "requested_qty": requested,
        "issued_qty": issued,
        "delivered_qty": delivered,
        "remaining_qty": remaining,
        "delay_reason": delay_reason,
        "line_status": line.status.value if hasattr(line.status, "value") else str(line.status),
        "route_ar": _route_label(line),
    }


def build_branch_request_detail(db: Session, row: BranchRequest) -> dict:
    branch_name = row.branch.branch_name if row.branch else f"فرع #{row.branch_id}"

    production_orders = (
        db.query(ProductionOrder)
        .filter(ProductionOrder.source_request_id == row.id)
        .all()
    )
    warehouse_lines = (
        db.query(WarehouseLine)
        .options(joinedload(WarehouseLine.item))
        .filter(WarehouseLine.source_request_id == row.id)
        .all()
    )
    delivery_orders = (
        db.query(DeliveryOrder)
        .options(joinedload(DeliveryOrder.lines))
        .filter(DeliveryOrder.source_request_id == row.id)
        .all()
    )
    delivery_line_rows: list[DeliveryOrderLine] = []
    for order in delivery_orders:
        delivery_line_rows.extend(order.lines or [])

    events: list[dict] = []
    events.extend(_request_field_events(row))
    events.extend(_audit_events(db, entity_type="branch_request", entity_id=row.id))

    for po in production_orders:
        events.extend(_audit_events(db, entity_type="production_order", entity_id=po.id))
        if po.status == ProductionOrderStatus.IN_PROGRESS and po.updated_at:
            events.append({
                "key": "production_in_progress",
                "label_ar": "الإنتاج قيد التنفيذ",
                "at": po.updated_at,
                "owner_role_ar": "المطبخ",
                "detail": f"PO-{po.id}",
                "source": "production",
            })

    for wl in warehouse_lines:
        events.extend(_audit_events(db, entity_type="warehouse_line", entity_id=wl.id))
        if wl.delay_reason:
            events.append({
                "key": "delay_reason",
                "label_ar": "سبب تأخير / نقص",
                "at": wl.updated_at or wl.created_at,
                "owner_role_ar": "المستودع",
                "detail": wl.delay_reason,
                "source": "warehouse",
            })
        if wl.status.value in ("PARTIAL", "BACKORDER") and _dec(wl.pending_qty) > 0:
            events.append({
                "key": "partial_backorder",
                "label_ar": "صرف جزئي — متبقي",
                "at": wl.updated_at or wl.created_at,
                "owner_role_ar": "المستودع",
                "detail": f"متبقي {_dec(wl.pending_qty)}",
                "source": "warehouse",
            })

    for order in delivery_orders:
        events.extend(_audit_events(db, entity_type="delivery_order", entity_id=order.id))

    def _sort_key(ev: dict):
        at = ev.get("at")
        if isinstance(at, str):
            try:
                at = datetime.fromisoformat(at.replace("Z", "+00:00"))
            except ValueError:
                at = datetime.min
        return at or datetime.min

    events.sort(key=_sort_key)

    seen = set()
    deduped = []
    for ev in events:
        sig = (ev.get("key"), str(ev.get("at")), ev.get("detail"))
        if sig in seen:
            continue
        seen.add(sig)
        deduped.append(ev)

    fulfillment_lines = [
        _fulfillment_for_line(db, line, warehouse_lines, production_orders, delivery_line_rows)
        for line in row.lines
    ]

    owner, next_action = _owner_for_request(row.status)
    last_updated = row.updated_at or row.created_at

    gaps: list[str] = []
    if row.status in (BranchRequestStatus.SPLIT, BranchRequestStatus.IN_EXECUTION):
        if not production_orders and not warehouse_lines:
            gaps.append("لا توجد سجلات مطبخ أو مستودع بعد التقسيم")
    if row.status == BranchRequestStatus.SUBMITTED and not row.submitted_at:
        gaps.append("تاريخ الإرسال غير مسجل")

    return {
        "request": row,
        "branch_name": branch_name,
        "timeline": deduped,
        "fulfillment_lines": fulfillment_lines,
        "status_summary": {
            "current_status_ar": STATUS_AR.get(row.status.value, row.status.value),
            "current_owner_ar": owner,
            "next_action_ar": next_action,
            "last_updated_at": last_updated,
        },
        "timeline_gaps": gaps,
    }
