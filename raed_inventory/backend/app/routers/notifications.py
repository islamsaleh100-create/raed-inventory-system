"""
Notifications Router — /api/v1/notifications

يقدّم جرس الإشعارات لكل دور، كل دور يرى فقط الحالات التي تخصّه.
كل إشعار يحمل i18n key ليترجمه الـ frontend، ورابط وجهة (target_url)
لفتح الكيان المعني مباشرة.

Endpoints:
    GET /summary      — counts per section (لملء الـ badge)
    GET /list         — recent items grouped by section (لعرض القائمة)
"""
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Set

from app.core.area_manager_scope import get_area_manager_branch_ids

from fastapi import APIRouter, Depends, Query
from sqlalchemy import inspect, func
from sqlalchemy.orm import Session, load_only

from app.core.auth import get_current_active_user, get_user_roles
from app.database import get_db
from app.models import (
    AssessmentStatus,
    Branch,
    DailyInventory,
    InventoryStatus,
    OrderStatus,
    OrderType,
    QualityResponseStatus,
    QualityVisit,
    QualityVisitResponse,
    QualityVisitStatus,
    ReplenishmentOrder,
    TrainingAssessment,
    User,
)

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _area_branch_ids(user: User, db: Session) -> List[int]:
    """Branch ids in scope for area_manager notifications (city + brand assignments)."""
    return get_area_manager_branch_ids(user, db)


def _has_destination_branch_id(db: Session) -> bool:
    bind = db.get_bind()
    if bind is None:
        return True
    cache_key = "_notifications_has_destination_branch_id"
    cached = getattr(bind, cache_key, None)
    if cached is not None:
        return cached
    try:
        names = {str(col.get("name")) for col in inspect(bind).get_columns("replenishment_orders")}
        value = "destination_branch_id" in names
    except Exception:
        value = True
    setattr(bind, cache_key, value)
    return value


def _orders_query(db: Session):
    return db.query(ReplenishmentOrder).options(
        load_only(
            ReplenishmentOrder.id,
            ReplenishmentOrder.order_no,
            ReplenishmentOrder.branch_id,
            ReplenishmentOrder.warehouse_id,
            ReplenishmentOrder.order_type,
            ReplenishmentOrder.status,
            ReplenishmentOrder.updated_at,
        )
    )


def _orders_count(query) -> int:
    return int(query.with_entities(func.count(ReplenishmentOrder.id)).order_by(None).scalar() or 0)


def _inventories_query(db: Session):
    return db.query(DailyInventory).options(
        load_only(
            DailyInventory.id,
            DailyInventory.branch_id,
            DailyInventory.inventory_date,
            DailyInventory.status,
            DailyInventory.submitted_at,
        )
    )


def _count_with(query, column) -> int:
    return int(query.with_entities(func.count(column)).order_by(None).scalar() or 0)


def _order_item(o: ReplenishmentOrder) -> Dict[str, Any]:
    return {
        "id": o.id,
        "order_no": o.order_no,
        "status": o.status.value if o.status else None,
        "order_type": o.order_type.value if o.order_type else None,
        "branch_id": o.branch_id,
        "destination_branch_id": None,
        "warehouse_id": o.warehouse_id,
        "updated_at": o.updated_at.isoformat() if o.updated_at else None,
        "target_url": f"/orders/{o.id}",
    }


def _inventory_item(inv: DailyInventory) -> Dict[str, Any]:
    return {
        "id": inv.id,
        "branch_id": inv.branch_id,
        "inventory_date": str(inv.inventory_date),
        "status": inv.status.value if inv.status else None,
        "updated_at": inv.submitted_at.isoformat() if inv.submitted_at else None,
        "target_url": f"/inventory/{inv.id}",
    }


def _quality_item(v: QualityVisit) -> Dict[str, Any]:
    return {
        "id": v.id,
        "branch_id": v.branch_id,
        "visit_date": str(v.visit_date),
        "status": v.status.value if v.status else None,
        "updated_at": v.updated_at.isoformat() if v.updated_at else None,
        "target_url": f"/quality/{v.id}",
    }


def _training_item(a: TrainingAssessment) -> Dict[str, Any]:
    return {
        "id": a.id,
        "branch_id": a.branch_id,
        "trainee_id": a.trainee_id,
        "status": a.status.value if a.status else None,
        "assessment_date": str(a.assessment_date),
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
        "target_url": f"/training/{a.id}",
    }


# ──────────────────────────────────────────────────────────────────────────────
# Section builders
# كل section builder يرجّع dict بالشكل:
# { "key": "<i18n_key>", "count": N, "items": [...], "target_url": "..." }
# key هو مفتاح الترجمة في frontend (notifications.<key>).
# ──────────────────────────────────────────────────────────────────────────────

_RECENT_LIMIT = 20


def _section_orders_to_receive(db: Session, branch_id: int) -> Dict[str, Any]:
    """للفرع: طلبيات تم صرفها من المستودع وفي انتظار استلام الفرع."""
    q = _orders_query(db).filter(
        ReplenishmentOrder.branch_id == branch_id,
        ReplenishmentOrder.status == OrderStatus.dispatched,
    ).order_by(ReplenishmentOrder.updated_at.desc())
    rows = q.limit(_RECENT_LIMIT).all()
    total = _orders_count(q)
    return {
        "key": "orders_to_receive",
        "count": total,
        "items": [_order_item(o) for o in rows],
        "target_url": "/receiving",
    }


def _section_rejected_orders_for_branch(db: Session, branch_id: int) -> Dict[str, Any]:
    """للفرع: طلبيات مرفوضة خلال آخر 7 أيام."""
    cutoff = datetime.utcnow() - timedelta(days=7)
    q = _orders_query(db).filter(
        ReplenishmentOrder.branch_id == branch_id,
        ReplenishmentOrder.status == OrderStatus.rejected,
        ReplenishmentOrder.updated_at >= cutoff,
    ).order_by(ReplenishmentOrder.updated_at.desc())
    rows = q.limit(_RECENT_LIMIT).all()
    total = _orders_count(q)
    return {
        "key": "rejected_orders",
        "count": total,
        "items": [_order_item(o) for o in rows],
        "target_url": "/orders?status=rejected",
    }


def _section_inter_branch_inbound(db: Session, branch_id: int) -> Dict[str, Any]:
    """للفرع الوجهة: تحويلات واردة معلّقة بانتظار موافقة مدير المنطقة."""
    if not _has_destination_branch_id(db):
        return {"key": "inter_branch_inbound_pending", "count": 0, "items": [], "target_url": "/orders?type=inter_branch"}
    q = _orders_query(db).filter(
        ReplenishmentOrder.destination_branch_id == branch_id,
        ReplenishmentOrder.order_type == OrderType.inter_branch,
        ReplenishmentOrder.status == OrderStatus.area_manager_review,
    ).order_by(ReplenishmentOrder.updated_at.desc())
    rows = q.limit(_RECENT_LIMIT).all()
    total = _orders_count(q)
    return {
        "key": "inter_branch_inbound_pending",
        "count": total,
        "items": [_order_item(o) for o in rows],
        "target_url": "/orders?type=inter_branch",
    }


def _section_daily_inventory_pending(db: Session, branch_id: int) -> Dict[str, Any]:
    """لمدير الفرع: جرد يومي تم تقديمه وينتظر الموافقة."""
    q = _inventories_query(db).filter(
        DailyInventory.branch_id == branch_id,
        DailyInventory.status.in_([
            InventoryStatus.submitted,
            InventoryStatus.pending_approval,
        ]),
    ).order_by(DailyInventory.submitted_at.desc())
    rows = q.limit(_RECENT_LIMIT).all()
    total = _count_with(q, DailyInventory.id)
    return {
        "key": "daily_inventory_pending",
        "count": total,
        "items": [_inventory_item(inv) for inv in rows],
        "target_url": "/inventory",
    }


def _section_missing_inventory_today(db: Session, branch_id: int) -> Dict[str, Any]:
    """لمدير الفرع: جرد اليوم لم يبدأ بعد."""
    today = date.today()
    exists = db.query(DailyInventory.id).filter(
        DailyInventory.branch_id == branch_id,
        DailyInventory.inventory_date == today,
    ).first()
    count = 0 if exists else 1
    return {
        "key": "missing_inventory_today",
        "count": count,
        "items": [{"branch_id": branch_id, "inventory_date": str(today), "target_url": "/inventory"}] if count else [],
        "target_url": "/inventory",
    }


# المستودع
def _section_pending_warehouse_review(db: Session, warehouse_id: Optional[int]) -> Dict[str, Any]:
    q = _orders_query(db).filter(
        ReplenishmentOrder.status == OrderStatus.submitted_to_warehouse,
    )
    if warehouse_id:
        q = q.filter(ReplenishmentOrder.warehouse_id == warehouse_id)
    q = q.order_by(ReplenishmentOrder.updated_at.desc())
    rows = q.limit(_RECENT_LIMIT).all()
    total = _orders_count(q)
    return {
        "key": "pending_warehouse_review",
        "count": total,
        "items": [_order_item(o) for o in rows],
        "target_url": "/warehouse/orders",
    }


def _section_approved_for_picking(db: Session, warehouse_id: Optional[int]) -> Dict[str, Any]:
    q = _orders_query(db).filter(
        ReplenishmentOrder.status == OrderStatus.approved,
    )
    if warehouse_id:
        q = q.filter(ReplenishmentOrder.warehouse_id == warehouse_id)
    q = q.order_by(ReplenishmentOrder.updated_at.desc())
    rows = q.limit(_RECENT_LIMIT).all()
    total = _orders_count(q)
    return {
        "key": "approved_for_picking",
        "count": total,
        "items": [_order_item(o) for o in rows],
        "target_url": "/warehouse/picking",
    }


def _section_in_picking(db: Session, warehouse_id: Optional[int]) -> Dict[str, Any]:
    q = _orders_query(db).filter(
        ReplenishmentOrder.status == OrderStatus.picking,
    )
    if warehouse_id:
        q = q.filter(ReplenishmentOrder.warehouse_id == warehouse_id)
    q = q.order_by(ReplenishmentOrder.updated_at.desc())
    rows = q.limit(_RECENT_LIMIT).all()
    total = _orders_count(q)
    return {
        "key": "in_picking",
        "count": total,
        "items": [_order_item(o) for o in rows],
        "target_url": "/warehouse/picking",
    }


# مدير المنطقة
def _section_inter_branch_pending_approval(db: Session, branch_ids: List[int]) -> Dict[str, Any]:
    if not branch_ids:
        return {"key": "inter_branch_pending_approval", "count": 0, "items": [], "target_url": "/operations/inter-branch-approvals"}
    q = _orders_query(db).filter(
        ReplenishmentOrder.order_type == OrderType.inter_branch,
        ReplenishmentOrder.status == OrderStatus.area_manager_review,
        ReplenishmentOrder.branch_id.in_(branch_ids),
    ).order_by(ReplenishmentOrder.updated_at.desc())
    rows = q.limit(_RECENT_LIMIT).all()
    total = _orders_count(q)
    return {
        "key": "inter_branch_pending_approval",
        "count": total,
        "items": [_order_item(o) for o in rows],
        "target_url": "/operations/inter-branch-approvals",
    }


def _section_daily_order_area_review(db: Session, branch_ids: List[int]) -> Dict[str, Any]:
    if not branch_ids:
        return {"key": "daily_order_area_review", "count": 0, "items": [], "target_url": "/orders"}
    q = _orders_query(db).filter(
        ReplenishmentOrder.order_type == OrderType.daily_order,
        ReplenishmentOrder.status == OrderStatus.area_manager_review,
        ReplenishmentOrder.branch_id.in_(branch_ids),
    ).order_by(ReplenishmentOrder.updated_at.desc())
    rows = q.limit(_RECENT_LIMIT).all()
    total = _orders_count(q)
    return {
        "key": "daily_order_area_review",
        "count": total,
        "items": [_order_item(o) for o in rows],
        "target_url": "/orders",
    }


# العمليات / الأدمن (كل ما سبق بدون فلتر منطقة)
def _section_all_pending_warehouse(db: Session) -> Dict[str, Any]:
    return _section_pending_warehouse_review(db, warehouse_id=None)


def _section_all_area_manager_review(db: Session) -> Dict[str, Any]:
    q = _orders_query(db).filter(
        ReplenishmentOrder.status == OrderStatus.area_manager_review,
    ).order_by(ReplenishmentOrder.updated_at.desc())
    rows = q.limit(_RECENT_LIMIT).all()
    total = _orders_count(q)
    return {
        "key": "all_area_manager_review",
        "count": total,
        "items": [_order_item(o) for o in rows],
        "target_url": "/orders",
    }


def _section_all_pending_inventories(db: Session) -> Dict[str, Any]:
    q = _inventories_query(db).filter(
        DailyInventory.status.in_([
            InventoryStatus.submitted,
            InventoryStatus.pending_approval,
        ]),
    ).order_by(DailyInventory.submitted_at.desc())
    rows = q.limit(_RECENT_LIMIT).all()
    total = _count_with(q, DailyInventory.id)
    return {
        "key": "all_pending_inventories",
        "count": total,
        "items": [_inventory_item(inv) for inv in rows],
        "target_url": "/reports/inventory",
    }


# الجودة
def _section_pending_quality_visits(db: Session, visitor_id: Optional[int] = None, manager: bool = False) -> Dict[str, Any]:
    """
    - visitor: زياراته في draft (تحت يده)
    - manager: زيارات في submitted تنتظر مراجعته
    """
    if manager:
        q = db.query(QualityVisit).filter(
            QualityVisit.is_deleted == False,
            QualityVisit.status == QualityVisitStatus.submitted,
        ).order_by(QualityVisit.updated_at.desc())
        key = "pending_quality_reviews"
    else:
        q = db.query(QualityVisit).filter(
            QualityVisit.is_deleted == False,
            QualityVisit.visitor_id == visitor_id,
            QualityVisit.status == QualityVisitStatus.draft,
        ).order_by(QualityVisit.updated_at.desc())
        key = "my_draft_quality_visits"
    rows = q.limit(_RECENT_LIMIT).all()
    total = _count_with(q, QualityVisit.id)
    return {
        "key": key,
        "count": total,
        "items": [_quality_item(v) for v in rows],
        "target_url": "/quality",
    }


# التدريب / التقييم
def _section_pending_training_assessments(db: Session, branch_ids: Optional[List[int]] = None) -> Dict[str, Any]:
    q = db.query(TrainingAssessment).filter(
        TrainingAssessment.status == AssessmentStatus.submitted,
    )
    if branch_ids is not None:
        if not branch_ids:
            return {"key": "pending_training_assessments", "count": 0, "items": [], "target_url": "/training"}
        q = q.filter(TrainingAssessment.branch_id.in_(branch_ids))
    q = q.order_by(TrainingAssessment.updated_at.desc())
    rows = q.limit(_RECENT_LIMIT).all()
    total = _count_with(q, TrainingAssessment.id)
    return {
        "key": "pending_training_assessments",
        "count": total,
        "items": [_training_item(a) for a in rows],
        "target_url": "/training",
    }


def _section_needs_reeval_training(db: Session, branch_ids: Optional[List[int]] = None) -> Dict[str, Any]:
    q = db.query(TrainingAssessment).filter(
        TrainingAssessment.status == AssessmentStatus.needs_reeval,
    )
    if branch_ids is not None:
        if not branch_ids:
            return {"key": "training_needs_reeval", "count": 0, "items": [], "target_url": "/training"}
        q = q.filter(TrainingAssessment.branch_id.in_(branch_ids))
    q = q.order_by(TrainingAssessment.updated_at.desc())
    rows = q.limit(_RECENT_LIMIT).all()
    total = _count_with(q, TrainingAssessment.id)
    return {
        "key": "training_needs_reeval",
        "count": total,
        "items": [_training_item(a) for a in rows],
        "target_url": "/training",
    }


# إجراءات تصحيحية متأخرة أو على وشك الاستحقاق (خلال 3 أيام)
def _section_overdue_quality_actions(db: Session, branch_ids: Optional[List[int]] = None) -> Dict[str, Any]:
    """إجراءات تصحيحية على بنود No غير محلولة، تاريخ استحقاق ≤ اليوم + 3"""
    threshold = date.today() + timedelta(days=3)
    q = (
        db.query(QualityVisitResponse)
        .join(QualityVisit, QualityVisit.id == QualityVisitResponse.visit_id)
        .filter(
            QualityVisit.is_deleted == False,  # noqa: E712
            QualityVisitResponse.status == QualityResponseStatus.no,
            QualityVisitResponse.is_resolved == False,  # noqa: E712
            QualityVisitResponse.due_date != None,  # noqa: E711
            QualityVisitResponse.due_date <= threshold,
        )
    )
    if branch_ids is not None:
        if not branch_ids:
            return {"key": "overdue_quality_actions", "count": 0, "items": [], "target_url": "/quality"}
        q = q.filter(QualityVisit.branch_id.in_(branch_ids))

    q = q.order_by(QualityVisitResponse.due_date.asc())
    rows = q.limit(_RECENT_LIMIT).all()
    total = _count_with(q, QualityVisitResponse.id)
    items = [
        {
            "id": r.id,
            "visit_id": r.visit_id,
            "due_date": str(r.due_date) if r.due_date else None,
            "action_owner": r.action_owner,
            "corrective_action": (r.corrective_action or "")[:120],
            "target_url": f"/quality/{r.visit_id}",
        }
        for r in rows
    ]
    return {
        "key": "overdue_quality_actions",
        "count": total,
        "items": items,
        "target_url": "/quality",
    }


# تقييمات تدريب مردودة للمقيّم لتصحيحها — ظهرت بعد إضافة rejection_reason
def _section_rejected_training_drafts(db: Session, trainer_id: Optional[int] = None,
                                       branch_ids: Optional[List[int]] = None) -> Dict[str, Any]:
    """Assessments في draft ولها rejection_reason — المعتمِد ردّها والمقيّم يحتاج يصلّحها"""
    q = db.query(TrainingAssessment).filter(
        TrainingAssessment.status == AssessmentStatus.draft,
        TrainingAssessment.rejection_reason != None,  # noqa: E711
    )
    if trainer_id is not None:
        q = q.filter(TrainingAssessment.trainer_id == trainer_id)
    if branch_ids is not None:
        if not branch_ids:
            return {"key": "rejected_training_drafts", "count": 0, "items": [], "target_url": "/training"}
        q = q.filter(TrainingAssessment.branch_id.in_(branch_ids))

    q = q.order_by(TrainingAssessment.updated_at.desc())
    rows = q.limit(_RECENT_LIMIT).all()
    total = _count_with(q, TrainingAssessment.id)
    return {
        "key": "rejected_training_drafts",
        "count": total,
        "items": [_training_item(a) for a in rows],
        "target_url": "/training",
    }


# تذكير: موعد إعادة التقييم اقترب (خلال 7 أيام) لتقييم في needs_reeval
def _section_training_reeval_due_soon(db: Session, branch_ids: Optional[List[int]] = None) -> Dict[str, Any]:
    threshold = date.today() + timedelta(days=7)
    q = db.query(TrainingAssessment).filter(
        TrainingAssessment.status == AssessmentStatus.needs_reeval,
        TrainingAssessment.re_eval_date != None,  # noqa: E711
        TrainingAssessment.re_eval_date <= threshold,
    )
    if branch_ids is not None:
        if not branch_ids:
            return {"key": "training_reeval_due_soon", "count": 0, "items": [], "target_url": "/training"}
        q = q.filter(TrainingAssessment.branch_id.in_(branch_ids))

    q = q.order_by(TrainingAssessment.re_eval_date.asc())
    rows = q.limit(_RECENT_LIMIT).all()
    total = _count_with(q, TrainingAssessment.id)
    return {
        "key": "training_reeval_due_soon",
        "count": total,
        "items": [_training_item(a) for a in rows],
        "target_url": "/training",
    }


# ──────────────────────────────────────────────────────────────────────────────
# Dispatcher — based on role, collect relevant sections.
# ──────────────────────────────────────────────────────────────────────────────

def _build_sections(user: User, db: Session) -> List[Dict[str, Any]]:
    roles = get_user_roles(user)
    is_super = "super_admin" in roles
    is_admin = "admin" in roles
    # admin gets the same global oversight sections as operations_manager,
    # but this is an explicit product decision rather than a generic bypass.
    is_ops   = is_super or is_admin or "operations_manager" in roles
    sections: List[Dict[str, Any]] = []

    # Branch
    if ({"branch_user", "branch_manager"} & set(roles)) and user.branch_id:
        sections.append(_section_orders_to_receive(db, user.branch_id))
        sections.append(_section_rejected_orders_for_branch(db, user.branch_id))
        sections.append(_section_inter_branch_inbound(db, user.branch_id))
        if "branch_manager" in roles:
            sections.append(_section_daily_inventory_pending(db, user.branch_id))
            sections.append(_section_missing_inventory_today(db, user.branch_id))
            # إجراءات جودة متأخرة على فرع المدير
            sections.append(_section_overdue_quality_actions(db, branch_ids=[user.branch_id]))

    # Warehouse
    if {"warehouse_user", "warehouse_manager"} & set(roles):
        wh_id = user.warehouse_id
        sections.append(_section_pending_warehouse_review(db, wh_id))
        sections.append(_section_approved_for_picking(db, wh_id))
        sections.append(_section_in_picking(db, wh_id))

    # Area manager — scoped to same region
    if "area_manager" in roles:
        branch_ids = _area_branch_ids(user, db)
        sections.append(_section_inter_branch_pending_approval(db, branch_ids))
        sections.append(_section_daily_order_area_review(db, branch_ids))
        sections.append(_section_pending_training_assessments(db, branch_ids))
        sections.append(_section_needs_reeval_training(db, branch_ids))
        # تقييمات ردّها المعتمِد للمقيّم (area_manager) — محتاجة تصحيح
        sections.append(_section_rejected_training_drafts(db, trainer_id=user.id))
        # اقترب موعد إعادة التقييم — تحرّك الآن
        sections.append(_section_training_reeval_due_soon(db, branch_ids))
        # إجراءات تصحيحية متأخرة على فروع منطقته
        sections.append(_section_overdue_quality_actions(db, branch_ids=branch_ids))

    # Operations / Admin / Super-admin — global view
    if is_ops:
        sections.append(_section_all_pending_warehouse(db))
        sections.append(_section_all_area_manager_review(db))
        sections.append(_section_all_pending_inventories(db))

    # Quality
    if "quality_visitor" in roles:
        sections.append(_section_pending_quality_visits(db, visitor_id=user.id, manager=False))
    if ("quality_manager" in roles) or is_ops:
        sections.append(_section_pending_quality_visits(db, manager=True))
        # نظرة عامة على الإجراءات المتأخرة (كل الفروع)
        sections.append(_section_overdue_quality_actions(db, branch_ids=None))

    # Training / Assessment — approvers
    if ("quality_manager" in roles) or ("trainer" in roles) or is_ops:
        sections.append(_section_pending_training_assessments(
            db, branch_ids=None if is_ops or "quality_manager" in roles
            else [user.branch_id] if user.branch_id else []
        ))

    # De-duplicate by key (admin might collect some keys twice through role overlap)
    seen: Set[str] = set()
    unique: List[Dict[str, Any]] = []
    for s in sections:
        if s["key"] in seen:
            continue
        seen.add(s["key"])
        unique.append(s)
    return unique


def _safe_section(builder, *args, **kwargs) -> Dict[str, Any]:
    section = builder(*args, **kwargs)
    if not isinstance(section, dict):
        raise ValueError(f"Notification section builder {getattr(builder, '__name__', builder)} did not return dict")
    section.setdefault("key", getattr(builder, "__name__", "unknown_section"))
    section.setdefault("count", 0)
    section.setdefault("items", [])
    section.setdefault("target_url", None)
    return section


# ──────────────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/summary")
def notifications_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    يرجّع عدد كل تصنيف (للـ badge) مع عدد مختصر من العناصر للعرض في الجرس.
    كل section يشتمل على i18n key بدل النص لعدم تكرار المنطق في الـ backend.
    """
    sections = _build_sections(current_user, db)
    total = sum(s["count"] for s in sections)
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "total": total,
        "sections": [
            {
                "key": s["key"],
                "count": s["count"],
                "target_url": s.get("target_url"),
                # للبيل نعيد حتى 5 عناصر فقط — لو المستخدم فتح الدروب داون.
                "items": s["items"][:5],
            }
            for s in sections
        ],
    }


@router.get("/list")
def notifications_list(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    يرجّع نسخة أوسع من نفس الأقسام — لاستخدامها في صفحة الإشعارات التفصيلية.
    """
    sections = _build_sections(current_user, db)
    total = sum(s["count"] for s in sections)
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "total": total,
        "sections": [
            {
                "key": s["key"],
                "count": s["count"],
                "target_url": s.get("target_url"),
                "items": s["items"][:limit],
            }
            for s in sections
        ],
    }
