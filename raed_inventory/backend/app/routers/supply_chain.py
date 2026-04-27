from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.database import get_db
from app.models import (
    AreaManagerAssignment,
    AuditLog,
    Brand,
    Branch,
    BranchBrand,
    BranchRequest,
    BranchRequestLine,
    BranchRequestStatus,
    DeliveryOrder,
    DeliveryOrderStatus,
    DeliveryOrderLine,
    DeliveryOrderLineStatus,
    Item,
    ItemBrand,
    KitchenSection,
    KitchenSectionAssignment,
    ProductionOrder,
    ProductionOrderStatus,
    User,
    UserRole,
    Role,
    UserStatus,
    Warehouse,
    WarehouseLine,
    WarehouseLineStatus,
)
from app.schemas import SupplyChainDashboardOut


router = APIRouter(prefix="/api/v1/supply-chain", tags=["Supply Chain"])

DASHBOARD_ROLES = ("admin", "super_admin", "internal_auditor", "warehouse_manager", "warehouse_user", "kitchen_section_manager", "delivery_user", "area_manager")


@router.get("/dashboard", response_model=SupplyChainDashboardOut)
def supply_chain_dashboard(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*DASHBOARD_ROLES)),
):
    pending_approvals = db.query(BranchRequest).filter(BranchRequest.status == BranchRequestStatus.SUBMITTED).count()
    in_production = db.query(ProductionOrder).filter(
        ProductionOrder.status.in_([
            ProductionOrderStatus.PENDING,
            ProductionOrderStatus.IN_PROGRESS,
            ProductionOrderStatus.WAITING_FOR_MATERIALS,
        ])
    ).count()
    warehouse_delays = db.query(WarehouseLine).filter(
        WarehouseLine.status.in_([WarehouseLineStatus.PARTIAL, WarehouseLineStatus.BACKORDER])
    ).count()
    partial_orders = (
        db.query(ProductionOrder).filter(ProductionOrder.status == ProductionOrderStatus.PARTIAL_READY).count()
        + db.query(WarehouseLine).filter(WarehouseLine.status == WarehouseLineStatus.PARTIAL).count()
        + db.query(DeliveryOrderLine).filter(DeliveryOrderLine.status == DeliveryOrderLineStatus.PARTIAL_DELIVERED).count()
    )
    top_rows = (
        db.query(
            BranchRequestLine.item_id.label("item_id"),
            Item.item_name_en.label("item_name"),
            func.sum(BranchRequestLine.qty_requested).label("qty_requested"),
            func.count(BranchRequestLine.id).label("request_count"),
        )
        .join(Item, Item.id == BranchRequestLine.item_id)
        .group_by(BranchRequestLine.item_id, Item.item_name_en)
        .order_by(func.sum(BranchRequestLine.qty_requested).desc())
        .limit(10)
        .all()
    )
    return {
        "pending_approvals": pending_approvals,
        "in_production": in_production,
        "warehouse_delays": warehouse_delays,
        "partial_orders": partial_orders,
        "top_requested_items": [
            {
                "item_id": row.item_id,
                "item_name": row.item_name,
                "qty_requested": str(row.qty_requested),
                "request_count": row.request_count,
            }
            for row in top_rows
        ],
    }


@router.get("/super-admin-overview")
def super_admin_overview(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("super_admin")),
):
    now = datetime.utcnow()
    today = date.today()
    day_start = datetime.combine(today, time.min)

    production_active_statuses = [
        ProductionOrderStatus.PENDING,
        ProductionOrderStatus.IN_PROGRESS,
        ProductionOrderStatus.WAITING_FOR_MATERIALS,
        ProductionOrderStatus.PARTIAL_READY,
    ]
    warehouse_active_statuses = [
        WarehouseLineStatus.PENDING,
        WarehouseLineStatus.AVAILABLE,
        WarehouseLineStatus.PARTIAL,
        WarehouseLineStatus.BACKORDER,
        WarehouseLineStatus.READY_FOR_DISPATCH,
    ]
    delivery_active_statuses = [
        DeliveryOrderStatus.READY,
        DeliveryOrderStatus.OUT_FOR_DELIVERY,
        DeliveryOrderStatus.PARTIAL_DELIVERED,
    ]

    total_requests_today = (
        db.query(BranchRequest)
        .filter(BranchRequest.created_at >= day_start)
        .count()
    )
    pending_approvals = (
        db.query(BranchRequest)
        .filter(BranchRequest.status == BranchRequestStatus.SUBMITTED)
        .count()
    )
    in_production = (
        db.query(ProductionOrder)
        .filter(ProductionOrder.status.in_(production_active_statuses))
        .count()
    )
    warehouse_pending = (
        db.query(WarehouseLine)
        .filter(WarehouseLine.status.in_(warehouse_active_statuses))
        .count()
    )
    out_for_delivery = (
        db.query(DeliveryOrder)
        .filter(DeliveryOrder.status == DeliveryOrderStatus.OUT_FOR_DELIVERY)
        .count()
    )
    delivered_today = (
        db.query(DeliveryOrder)
        .filter(
            DeliveryOrder.status == DeliveryOrderStatus.DELIVERED,
            DeliveryOrder.delivered_at.isnot(None),
            DeliveryOrder.delivered_at >= day_start,
        )
        .count()
    )
    partial_total = (
        db.query(ProductionOrder)
        .filter(ProductionOrder.status == ProductionOrderStatus.PARTIAL_READY)
        .count()
        + db.query(WarehouseLine)
        .filter(WarehouseLine.status == WarehouseLineStatus.PARTIAL)
        .count()
        + db.query(DeliveryOrderLine)
        .filter(DeliveryOrderLine.status == DeliveryOrderLineStatus.PARTIAL_DELIVERED)
        .count()
    )
    active_branches = (
        db.query(Branch)
        .filter(Branch.active == True, Branch.is_deleted == False)
        .count()
    )
    active_users = (
        db.query(User)
        .filter(User.status == UserStatus.active, User.is_deleted == False)
        .count()
    )

    delayed_branch_approvals = (
        db.query(BranchRequest)
        .filter(
            BranchRequest.status == BranchRequestStatus.SUBMITTED,
            BranchRequest.submitted_at.isnot(None),
            BranchRequest.submitted_at <= now - timedelta(hours=8),
        )
        .count()
    )
    delayed_production = (
        db.query(ProductionOrder)
        .filter(
            ProductionOrder.status.in_(production_active_statuses),
            ProductionOrder.created_at <= now - timedelta(hours=24),
        )
        .count()
    )
    delayed_warehouse = (
        db.query(WarehouseLine)
        .filter(
            WarehouseLine.status.in_(
                [
                    WarehouseLineStatus.PENDING,
                    WarehouseLineStatus.BACKORDER,
                    WarehouseLineStatus.READY_FOR_DISPATCH,
                ]
            ),
            WarehouseLine.created_at <= now - timedelta(hours=24),
        )
        .count()
    )
    delayed_delivery = (
        db.query(DeliveryOrder)
        .filter(
            DeliveryOrder.status.in_(
                [
                    DeliveryOrderStatus.READY,
                    DeliveryOrderStatus.OUT_FOR_DELIVERY,
                    DeliveryOrderStatus.PARTIAL_DELIVERED,
                ]
            ),
            DeliveryOrder.created_at <= now - timedelta(hours=24),
        )
        .count()
    )
    delayed_total = (
        delayed_branch_approvals
        + delayed_production
        + delayed_warehouse
        + delayed_delivery
    )

    low_stock_count = (
        db.query(func.count(Item.id))
        .select_from(Item)
        .filter(Item.reorder_point.isnot(None), Item.reorder_point > 0)
        .scalar()
    )

    alerts = []

    def push_alert(key: str, title: str, count: int, severity: str, to: str, description: str):
        if count <= 0:
            return
        alerts.append(
            {
                "key": key,
                "title": title,
                "count": int(count),
                "severity": severity,
                "to": to,
                "description": description,
            }
        )

    push_alert(
        "pending_approvals",
        "طلبات موافقة متأخرة",
        delayed_branch_approvals,
        "critical" if delayed_branch_approvals >= 5 else "warning",
        "/supply-chain/approvals",
        "طلبات منطقة ما زالت معلقة أكثر من 8 ساعات.",
    )
    push_alert(
        "production_delays",
        "أوامر إنتاج متأخرة",
        delayed_production,
        "critical" if delayed_production >= 5 else "warning",
        "/supply-chain/kitchen",
        "أوامر إنتاج نشطة تجاوزت 24 ساعة بدون إغلاق.",
    )
    push_alert(
        "warehouse_delays",
        "اختناقات في المستودع",
        delayed_warehouse,
        "critical" if delayed_warehouse >= 5 else "warning",
        "/supply-chain/warehouse",
        "أسطر مستودع معلقة أو Backorder لأكثر من 24 ساعة.",
    )
    push_alert(
        "delivery_delays",
        "طلبات توصيل متأخرة",
        delayed_delivery,
        "critical" if delayed_delivery >= 5 else "warning",
        "/supply-chain/delivery",
        "طلبات توصيل نشطة بقيت مفتوحة أكثر من 24 ساعة.",
    )
    push_alert(
        "partial_orders",
        "سلاسل جزئية تحتاج متابعة",
        partial_total,
        "warning",
        "/supply-chain/warehouse",
        "يوجد Partial في الإنتاج أو المستودع أو التسليم.",
    )
    push_alert(
        "low_stock_watch",
        "أصناف تحتاج مراقبة المخزون",
        low_stock_count,
        "info",
        "/operations",
        "أصناف لها reorder point وتحتاج متابعة تشغيلية.",
    )

    pipeline = [
        {
            "key": "branch",
            "label": "طلبات الفروع",
            "count": (
                db.query(BranchRequest)
                .filter(BranchRequest.status.in_([BranchRequestStatus.DRAFT, BranchRequestStatus.SUBMITTED]))
                .count()
            ),
            "delayed_count": delayed_branch_approvals,
            "partial_count": 0,
            "to": "/supply-chain/branch-requests",
        },
        {
            "key": "approval",
            "label": "بانتظار الموافقة",
            "count": pending_approvals,
            "delayed_count": delayed_branch_approvals,
            "partial_count": 0,
            "to": "/supply-chain/approvals",
        },
        {
            "key": "production",
            "label": "الإنتاج",
            "count": in_production,
            "delayed_count": delayed_production,
            "partial_count": (
                db.query(ProductionOrder)
                .filter(ProductionOrder.status == ProductionOrderStatus.PARTIAL_READY)
                .count()
            ),
            "to": "/supply-chain/kitchen",
        },
        {
            "key": "warehouse",
            "label": "المستودع",
            "count": warehouse_pending,
            "delayed_count": delayed_warehouse,
            "partial_count": (
                db.query(WarehouseLine)
                .filter(WarehouseLine.status == WarehouseLineStatus.PARTIAL)
                .count()
            ),
            "to": "/supply-chain/warehouse",
        },
        {
            "key": "delivery",
            "label": "التوصيل",
            "count": (
                db.query(DeliveryOrder)
                .filter(DeliveryOrder.status.in_(delivery_active_statuses))
                .count()
            ),
            "delayed_count": delayed_delivery,
            "partial_count": (
                db.query(DeliveryOrder)
                .filter(DeliveryOrder.status == DeliveryOrderStatus.PARTIAL_DELIVERED)
                .count()
            ),
            "to": "/supply-chain/delivery",
        },
        {
            "key": "delivered",
            "label": "تم التسليم اليوم",
            "count": delivered_today,
            "delayed_count": 0,
            "partial_count": 0,
            "to": "/supply-chain/delivery",
        },
    ]

    branch_top_rows = (
        db.query(
            Branch.id.label("id"),
            Branch.branch_name.label("name"),
            Branch.city.label("city"),
            func.count(BranchRequest.id).label("request_count"),
        )
        .join(BranchRequest, BranchRequest.branch_id == Branch.id)
        .group_by(Branch.id, Branch.branch_name, Branch.city)
        .order_by(func.count(BranchRequest.id).desc(), Branch.branch_name.asc())
        .limit(5)
        .all()
    )
    branch_delayed_rows = (
        db.query(
            Branch.id.label("id"),
            Branch.branch_name.label("name"),
            Branch.city.label("city"),
            func.count(BranchRequest.id).label("delayed_count"),
        )
        .join(BranchRequest, BranchRequest.branch_id == Branch.id)
        .filter(
            BranchRequest.status == BranchRequestStatus.SUBMITTED,
            BranchRequest.submitted_at.isnot(None),
            BranchRequest.submitted_at <= now - timedelta(hours=8),
        )
        .group_by(Branch.id, Branch.branch_name, Branch.city)
        .order_by(func.count(BranchRequest.id).desc(), Branch.branch_name.asc())
        .limit(5)
        .all()
    )

    area_rows = (
        db.query(
            User.id.label("id"),
            User.username.label("username"),
            AreaManagerAssignment.city.label("city"),
            Brand.name.label("brand_name"),
            func.count(BranchRequest.id).label("pending_count"),
        )
        .select_from(AreaManagerAssignment)
        .join(User, User.id == AreaManagerAssignment.user_id)
        .join(Brand, Brand.id == AreaManagerAssignment.brand_id)
        .outerjoin(
            BranchRequest,
            (BranchRequest.brand_id == AreaManagerAssignment.brand_id)
            & (BranchRequest.status == BranchRequestStatus.SUBMITTED),
        )
        .outerjoin(Branch, Branch.id == BranchRequest.branch_id)
        .filter(
            AreaManagerAssignment.active == True,
            (Branch.id.is_(None) | (Branch.city == AreaManagerAssignment.city)),
        )
        .group_by(User.id, User.username, AreaManagerAssignment.city, Brand.name)
        .order_by(func.count(BranchRequest.id).desc(), User.username.asc())
        .limit(6)
        .all()
    )

    kitchen_rows = (
        db.query(
            KitchenSection.id.label("id"),
            KitchenSection.name.label("section_name"),
            func.count(ProductionOrder.id).label("active_count"),
            func.sum(
                case(
                    (ProductionOrder.created_at <= now - timedelta(hours=24), 1),
                    else_=0,
                )
            ).label("delayed_count"),
        )
        .outerjoin(
            ProductionOrder,
            (ProductionOrder.kitchen_section_id == KitchenSection.id)
            & (ProductionOrder.status.in_(production_active_statuses)),
        )
        .group_by(KitchenSection.id, KitchenSection.name)
        .order_by(func.count(ProductionOrder.id).desc(), KitchenSection.name.asc())
        .limit(6)
        .all()
    )

    warehouse_rows = (
        db.query(
            Warehouse.id.label("id"),
            Warehouse.warehouse_name.label("warehouse_name"),
            func.count(WarehouseLine.id).label("active_count"),
            func.sum(
                case(
                    (WarehouseLine.status == WarehouseLineStatus.BACKORDER, 1),
                    else_=0,
                )
            ).label("backorder_count"),
        )
        .join(Branch, Branch.warehouse_id == Warehouse.id)
        .outerjoin(
            WarehouseLine,
            (WarehouseLine.branch_id == Branch.id)
            & (WarehouseLine.status.in_(warehouse_active_statuses)),
        )
        .group_by(Warehouse.id, Warehouse.warehouse_name)
        .order_by(func.count(WarehouseLine.id).desc(), Warehouse.warehouse_name.asc())
        .limit(5)
        .all()
    )

    delivery_city_rows = (
        db.query(
            Branch.city.label("city"),
            func.count(DeliveryOrder.id).label("active_count"),
            func.sum(
                case(
                    (DeliveryOrder.status == DeliveryOrderStatus.OUT_FOR_DELIVERY, 1),
                    else_=0,
                )
            ).label("out_count"),
        )
        .join(Branch, Branch.id == DeliveryOrder.branch_id)
        .filter(DeliveryOrder.status.in_(delivery_active_statuses))
        .group_by(Branch.city)
        .order_by(func.count(DeliveryOrder.id).desc(), Branch.city.asc())
        .limit(5)
        .all()
    )

    delivery_branch_rows = (
        db.query(
            Branch.id.label("id"),
            Branch.branch_name.label("name"),
            Branch.city.label("city"),
            func.count(DeliveryOrder.id).label("delivery_count"),
        )
        .join(DeliveryOrder, DeliveryOrder.branch_id == Branch.id)
        .group_by(Branch.id, Branch.branch_name, Branch.city)
        .order_by(func.count(DeliveryOrder.id).desc(), Branch.branch_name.asc())
        .limit(5)
        .all()
    )

    approval_duration_rows = (
        db.query(BranchRequest.submitted_at, BranchRequest.approved_at)
        .filter(
            BranchRequest.approved_at.isnot(None),
            BranchRequest.submitted_at.isnot(None),
        )
        .all()
    )
    delivery_duration_rows = (
        db.query(DeliveryOrder.created_at, DeliveryOrder.delivered_at)
        .filter(
            DeliveryOrder.delivered_at.isnot(None),
            DeliveryOrder.created_at.isnot(None),
        )
        .all()
    )
    avg_approval_hours = (
        sum(
            (approved_at - submitted_at).total_seconds()
            for submitted_at, approved_at in approval_duration_rows
        )
        / len(approval_duration_rows)
        / 3600
        if approval_duration_rows
        else 0.0
    )
    avg_delivery_hours = (
        sum(
            (delivered_at - created_at).total_seconds()
            for created_at, delivered_at in delivery_duration_rows
        )
        / len(delivery_duration_rows)
        / 3600
        if delivery_duration_rows
        else 0.0
    )

    top_item_rows = (
        db.query(
            Item.id.label("id"),
            Item.item_name_en.label("name"),
            func.sum(BranchRequestLine.qty_requested).label("qty_requested"),
            func.count(BranchRequestLine.id).label("request_count"),
        )
        .join(BranchRequestLine, BranchRequestLine.item_id == Item.id)
        .group_by(Item.id, Item.item_name_en)
        .order_by(func.sum(BranchRequestLine.qty_requested).desc(), Item.item_name_en.asc())
        .limit(5)
        .all()
    )

    users_without_branch_or_warehouse = (
        db.query(User)
        .filter(
            User.status == UserStatus.active,
            User.is_deleted == False,
            User.branch_id.is_(None),
            User.warehouse_id.is_(None),
        )
        .count()
    )
    users_without_roles = (
        db.query(User)
        .outerjoin(UserRole, UserRole.user_id == User.id)
        .filter(
            User.status == UserStatus.active,
            User.is_deleted == False,
            UserRole.id.is_(None),
        )
        .count()
    )
    inactive_branch_users = (
        db.query(User)
        .join(Branch, Branch.id == User.branch_id)
        .filter(
            User.status == UserStatus.active,
            User.is_deleted == False,
            Branch.active == False,
        )
        .count()
    )
    branches_without_brand_links = (
        db.query(Branch)
        .outerjoin(BranchBrand, BranchBrand.branch_id == Branch.id)
        .filter(
            Branch.active == True,
            Branch.is_deleted == False,
            BranchBrand.id.is_(None),
        )
        .count()
    )
    items_without_brand_links = (
        db.query(Item)
        .outerjoin(ItemBrand, ItemBrand.item_id == Item.id)
        .filter(
            Item.active == True,
            Item.is_deleted == False,
            ItemBrand.id.is_(None),
        )
        .count()
    )
    kitchen_assignments_without_city = (
        db.query(KitchenSectionAssignment)
        .filter(
            KitchenSectionAssignment.active == True,
            KitchenSectionAssignment.service_city.is_(None),
        )
        .count()
    )
    branch_requestable_hidden_conflicts = (
        db.query(Item)
        .filter(
            Item.active == True,
            Item.is_deleted == False,
            Item.branch_requestable == True,
            Item.visible_in_branch_ui == False,
        )
        .count()
    )

    role_distribution_rows = (
        db.query(
            UserRole.role_id.label("role_id"),
            Role.name.label("role_name"),
            Role.display_name.label("role_display_name"),
            func.count(UserRole.user_id).label("user_count"),
        )
        .join(Role, Role.id == UserRole.role_id)
        .group_by(UserRole.role_id, Role.name, Role.display_name)
        .order_by(func.count(UserRole.user_id).desc(), Role.display_name.asc())
        .all()
    )

    recent_audit_rows = (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(8)
        .all()
    )

    return {
        "generated_at": now.isoformat(),
        "summary": {
            "total_requests_today": total_requests_today,
            "pending_approvals": pending_approvals,
            "in_production": in_production,
            "warehouse_pending": warehouse_pending,
            "out_for_delivery": out_for_delivery,
            "delivered": delivered_today,
            "delayed": delayed_total,
            "partial": partial_total,
            "active_branches": active_branches,
            "active_users": active_users,
        },
        "alerts": alerts,
        "pipeline": pipeline,
        "operations": {
            "branches": {
                "top_requesting": [
                    {
                        "id": row.id,
                        "label": row.name,
                        "city": row.city,
                        "request_count": int(row.request_count or 0),
                    }
                    for row in branch_top_rows
                ],
                "delayed_branches": [
                    {
                        "id": row.id,
                        "label": row.name,
                        "city": row.city,
                        "delayed_count": int(row.delayed_count or 0),
                    }
                    for row in branch_delayed_rows
                ],
            },
            "area_managers": [
                {
                    "id": row.id,
                    "label": row.username,
                    "city": row.city,
                    "brand": row.brand_name,
                    "pending_count": int(row.pending_count or 0),
                }
                for row in area_rows
            ],
            "kitchen": [
                {
                    "id": row.id,
                    "label": row.section_name,
                    "active_count": int(row.active_count or 0),
                    "delayed_count": int(row.delayed_count or 0),
                }
                for row in kitchen_rows
            ],
            "warehouse": [
                {
                    "id": row.id,
                    "label": row.warehouse_name,
                    "active_count": int(row.active_count or 0),
                    "backorder_count": int(row.backorder_count or 0),
                }
                for row in warehouse_rows
            ],
            "delivery": {
                "by_city": [
                    {
                        "label": row.city or "Unknown",
                        "active_count": int(row.active_count or 0),
                        "out_count": int(row.out_count or 0),
                    }
                    for row in delivery_city_rows
                ],
                "top_branches": [
                    {
                        "id": row.id,
                        "label": row.name,
                        "city": row.city,
                        "delivery_count": int(row.delivery_count or 0),
                    }
                    for row in delivery_branch_rows
                ],
            },
        },
        "analytics": {
            "performance": {
                "avg_approval_hours": round(avg_approval_hours or 0, 2),
                "avg_delivery_hours": round(avg_delivery_hours or 0, 2),
                "partial_rate_pct": round(
                    (partial_total / max(total_requests_today, 1)) * 100,
                    1,
                ) if total_requests_today else 0.0,
                "delay_rate_pct": round(
                    (delayed_total / max(total_requests_today, 1)) * 100,
                    1,
                ) if total_requests_today else 0.0,
            },
            "top_items": [
                {
                    "id": row.id,
                    "label": row.name,
                    "qty_requested": float(row.qty_requested or 0),
                    "request_count": int(row.request_count or 0),
                }
                for row in top_item_rows
            ],
        },
        "data_health": {
            "users_without_scope": users_without_branch_or_warehouse,
            "users_without_roles": users_without_roles,
            "inactive_branch_users": inactive_branch_users,
            "branches_without_brand_links": branches_without_brand_links,
            "items_without_brand_links": items_without_brand_links,
            "kitchen_assignments_without_city": kitchen_assignments_without_city,
            "branch_requestable_hidden_conflicts": branch_requestable_hidden_conflicts,
        },
        "governance": {
            "role_distribution": [
                {
                    "role_id": row.role_id,
                    "role_name": str(row.role_name.value if hasattr(row.role_name, "value") else row.role_name),
                    "role_display_name": row.role_display_name,
                    "user_count": int(row.user_count or 0),
                }
                for row in role_distribution_rows
            ],
            "recent_audit": [
                {
                    "id": row.id,
                    "action": row.action,
                    "module": row.module,
                    "entity_type": row.entity_type,
                    "entity_id": row.entity_id,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "user_id": row.user_id,
                }
                for row in recent_audit_rows
            ],
        },
    }
