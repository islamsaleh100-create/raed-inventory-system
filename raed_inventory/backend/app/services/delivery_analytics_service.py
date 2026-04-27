from collections import defaultdict
from decimal import Decimal

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.models import Branch, DeliveryAppMetric, DeliveryBranchProfile


def _safe_float(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _aov(revenue: float, orders: int) -> float:
    if not orders:
        return 0.0
    return round(revenue / orders, 2)


def get_dashboard(db: Session) -> dict:
    inspector = inspect(db.bind)
    delivery_tables_exist = inspector.has_table("delivery_branch_profiles") and inspector.has_table("delivery_app_metrics")
    active_branches_count = db.query(Branch).filter(Branch.active == True, Branch.is_deleted == False).count()

    metrics = []
    branches = []
    if delivery_tables_exist:
        metrics = (
            db.query(DeliveryAppMetric)
            .join(DeliveryBranchProfile, DeliveryAppMetric.branch_profile_id == DeliveryBranchProfile.id)
            .all()
        )
        branches = db.query(DeliveryBranchProfile).filter(DeliveryBranchProfile.is_active == True).all()

    total_revenue = 0.0
    total_orders = 0
    apps = defaultdict(lambda: {"revenue": 0.0, "orders": 0})
    brands = defaultdict(lambda: {"revenue": 0.0, "orders": 0})
    branch_map = defaultdict(lambda: {"revenue": 0.0, "orders": 0, "name": "", "brand": "", "hours": ""})
    trend = defaultdict(lambda: {"revenue": 0.0, "orders": 0})

    for metric in metrics:
        revenue = _safe_float(metric.revenue)
        orders = int(metric.orders_count or 0)
        total_revenue += revenue
        total_orders += orders

        app_bucket = apps[metric.delivery_app]
        app_bucket["revenue"] += revenue
        app_bucket["orders"] += orders

        brand_bucket = brands[metric.branch_profile.brand_name]
        brand_bucket["revenue"] += revenue
        brand_bucket["orders"] += orders

        branch_bucket = branch_map[metric.branch_profile_id]
        branch_bucket["revenue"] += revenue
        branch_bucket["orders"] += orders
        branch_bucket["name"] = metric.branch_profile.branch_name
        branch_bucket["brand"] = metric.branch_profile.brand_name
        if metric.branch_profile.regular_open_time or metric.branch_profile.regular_close_time:
            branch_bucket["hours"] = f"{metric.branch_profile.regular_open_time or '-'} - {metric.branch_profile.regular_close_time or '-'}"

        trend_key = f"{metric.metric_year}-{metric.metric_month:02d}"
        trend_bucket = trend[trend_key]
        trend_bucket["revenue"] += revenue
        trend_bucket["orders"] += orders

    app_comparison = [
        {
            "delivery_app": app_name,
            "total_revenue": round(values["revenue"], 2),
            "total_orders": values["orders"],
            "average_order_value": _aov(values["revenue"], values["orders"]),
        }
        for app_name, values in sorted(apps.items(), key=lambda item: item[1]["revenue"], reverse=True)
    ]

    brand_performance = [
        {
            "brand_name": brand_name,
            "total_revenue": round(values["revenue"], 2),
            "total_orders": values["orders"],
            "average_order_value": _aov(values["revenue"], values["orders"]),
        }
        for brand_name, values in sorted(brands.items(), key=lambda item: item[1]["revenue"], reverse=True)
    ]

    top_branches = [
        {
            "branch_id": branch_id,
            "branch_name": values["name"],
            "brand_name": values["brand"],
            "total_revenue": round(values["revenue"], 2),
            "total_orders": values["orders"],
            "average_order_value": _aov(values["revenue"], values["orders"]),
            "regular_hours": values["hours"] or None,
        }
        for branch_id, values in sorted(branch_map.items(), key=lambda item: item[1]["revenue"], reverse=True)
    ][:10]

    monthly_trend = [
        {
            "label": label,
            "total_revenue": round(values["revenue"], 2),
            "total_orders": values["orders"],
            "average_order_value": _aov(values["revenue"], values["orders"]),
        }
        for label, values in sorted(trend.items())
    ]

    return {
        "totals": {
            "total_revenue": round(total_revenue, 2),
            "total_orders": total_orders,
            "average_order_value": _aov(total_revenue, total_orders),
            "active_branches": len(branches) if delivery_tables_exist else active_branches_count,
            "active_apps": len(apps),
        },
        "app_comparison": app_comparison,
        "brand_performance": brand_performance,
        "top_branches": top_branches,
        "monthly_trend": monthly_trend,
    }


def list_branch_profiles(db: Session) -> list[DeliveryBranchProfile]:
    inspector = inspect(db.bind)
    if inspector.has_table("delivery_branch_profiles"):
        return (
            db.query(DeliveryBranchProfile)
            .order_by(DeliveryBranchProfile.brand_name.asc(), DeliveryBranchProfile.branch_name.asc())
            .all()
        )

    branches = (
        db.query(Branch)
        .filter(Branch.active == True, Branch.is_deleted == False)
        .order_by(Branch.branch_name.asc())
        .all()
    )
    return [
        {
            "id": branch.id,
            "brand_name": "غير محدد بعد",
            "branch_name": branch.branch_name,
            "region": branch.city,
            "city": branch.area,
            "google_maps_url": None,
            "regular_open_time": None,
            "regular_close_time": None,
            "weekend_open_time": None,
            "weekend_close_time": None,
            "hours_notes": "سيتم استكمالها من ملف الدوام واللوكيشن",
            "is_active": branch.active,
        }
        for branch in branches
    ]
