"""
Delivery Analytics Router
/api/v1/delivery — تحليل بيانات تطبيقات التوصيل
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user, require_roles
from app.database import get_db
from app.schemas import (
    DeliveryBrandOut,
    DeliveryBranchOut,
    DeliveryBranchCreate,
    DeliveryBranchUpdate,
    DeliveryAppOut,
    DeliveryImportRequest,
    DeliveryImportResult,
    DeliveryRecordOut,
    DeliveryAliasCreate,
    DeliveryKPI,
    DeliveryAppStat,
    DeliveryBrandStat,
    DeliveryBranchStat,
    DeliveryMonthlyTrend,
    DeliveryAppBranchMatrix,
    DeliveryUnmatchedBranch,
)
from app.services import delivery_service

router = APIRouter(prefix="/api/v1/delivery", tags=["Delivery Analytics"])

# ─── RBAC ─────────────────────────────────────────────────────────────────────
# Unified Delivery-section policy (2026-04-23):
#   sales_manager     : full access (read + write) — primary owner
#   operations_manager: read-only (dashboards/KPIs/stats) — supervisory view
#   area_manager      : read-only — regional oversight (reviewer role)
#   super_admin       : always bypasses via require_roles() short-circuit
#   admin             : explicit read/write access via role tuples below
# NOTE: aggregate endpoints (no branch_id) expose regional-to-global data;
# per-branch endpoints MUST call can_access_branch() to restrict area_manager
# to their own region. TODO: scope aggregates by region in a follow-up.
_DELIVERY_READ_ROLES = ("sales_manager", "operations_manager", "area_manager", "admin")
_DELIVERY_WRITE_ROLES = ("sales_manager", "admin")


# ─── Master Data: Brands ──────────────────────────────────────────────────────

@router.get("/brands", response_model=list[DeliveryBrandOut])
def list_brands(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*_DELIVERY_READ_ROLES)),
):
    return delivery_service.list_brands(db)


@router.post("/brands", response_model=DeliveryBrandOut, status_code=201)
def create_brand(
    data: dict,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*_DELIVERY_WRITE_ROLES)),
):
    from app.models import DeliveryBrand
    from sqlalchemy import func
    name = (data.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    existing = db.query(DeliveryBrand).filter(
        func.lower(DeliveryBrand.name) == name.lower()
    ).first()
    if existing:
        return existing
    brand = DeliveryBrand(name=name, name_ar=data.get("name_ar"), is_active=True)
    db.add(brand)
    db.commit()
    db.refresh(brand)
    return brand


# ─── Master Data: Apps ────────────────────────────────────────────────────────

@router.get("/apps", response_model=list[DeliveryAppOut])
def list_apps(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*_DELIVERY_READ_ROLES)),
):
    return delivery_service.list_apps(db)


# ─── Master Data: Branches ────────────────────────────────────────────────────

@router.get("/branches", response_model=list[DeliveryBranchOut])
def list_branches(
    brand_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*_DELIVERY_READ_ROLES)),
):
    return delivery_service.list_branches(db, brand_id=brand_id)


@router.post("/branches", response_model=DeliveryBranchOut, status_code=201)
def create_branch(
    data: DeliveryBranchCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*_DELIVERY_WRITE_ROLES)),
):
    return delivery_service.create_branch(db, data)


@router.put("/branches/{branch_id}", response_model=DeliveryBranchOut)
def update_branch(
    branch_id: int,
    data: DeliveryBranchUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*_DELIVERY_WRITE_ROLES)),
):
    return delivery_service.update_branch(db, branch_id, data)


@router.post("/branches/{branch_id}/aliases", response_model=DeliveryBranchOut, status_code=201)
def add_alias(
    branch_id: int,
    data: DeliveryAliasCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*_DELIVERY_WRITE_ROLES)),
):
    return delivery_service.add_alias(db, branch_id, data.alias)


@router.delete("/branches/{branch_id}/aliases/{alias_id}", status_code=204)
def delete_alias(
    branch_id: int,
    alias_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*_DELIVERY_WRITE_ROLES)),
):
    delivery_service.delete_alias(db, alias_id)


# ─── Available Periods ────────────────────────────────────────────────────────

@router.get("/periods")
def get_periods(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*_DELIVERY_READ_ROLES)),
):
    """قائمة السنوات والأشهر المتاحة في البيانات"""
    return delivery_service.get_available_periods(db)


# ─── Import ───────────────────────────────────────────────────────────────────

@router.post("/import", response_model=DeliveryImportResult, status_code=201)
def import_data(
    data: DeliveryImportRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*_DELIVERY_WRITE_ROLES)),
):
    """
    استيراد بيانات التوصيل.
    يُرسل JSON بالبيانات المستخرجة من Excel في الفرونت اند.
    """
    return delivery_service.import_delivery_data(db, data, imported_by=current_user.id)


# ─── Analytics ────────────────────────────────────────────────────────────────

@router.get("/kpis", response_model=DeliveryKPI)
def get_kpis(
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    brand_id: Optional[int] = Query(None),
    app_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*_DELIVERY_READ_ROLES)),
):
    """KPIs الرئيسية: إجمالي الطلبات، الإيراد، متوسط AOV، أعلى تطبيق/براند/فرع"""
    return delivery_service.get_kpis(db, year=year, month=month, brand_id=brand_id, app_id=app_id)


@router.get("/stats/apps", response_model=list[DeliveryAppStat])
def get_app_stats(
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    brand_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*_DELIVERY_READ_ROLES)),
):
    """إحصائيات كل تطبيق مع نسبة الحصة السوقية"""
    return delivery_service.get_app_stats(db, year=year, month=month, brand_id=brand_id)


@router.get("/stats/brands", response_model=list[DeliveryBrandStat])
def get_brand_stats(
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    app_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*_DELIVERY_READ_ROLES)),
):
    """إحصائيات كل براند"""
    return delivery_service.get_brand_stats(db, year=year, month=month, app_id=app_id)


@router.get("/stats/branches", response_model=list[DeliveryBranchStat])
def get_branch_stats(
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    brand_id: Optional[int] = Query(None),
    app_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*_DELIVERY_READ_ROLES)),
):
    """إحصائيات كل فرع مع رابط الخريطة"""
    return delivery_service.get_branch_stats(
        db, year=year, month=month, brand_id=brand_id, app_id=app_id
    )


@router.get("/stats/trend", response_model=list[DeliveryMonthlyTrend])
def get_monthly_trend(
    year: Optional[int] = Query(None),
    brand_id: Optional[int] = Query(None),
    app_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*_DELIVERY_READ_ROLES)),
):
    """اتجاه شهري للطلبات والإيراد"""
    return delivery_service.get_monthly_trend(db, year=year, brand_id=brand_id, app_id=app_id)


@router.get("/stats/matrix", response_model=list[DeliveryAppBranchMatrix])
def get_app_branch_matrix(
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    brand_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*_DELIVERY_READ_ROLES)),
):
    """مصفوفة: لكل تطبيق → قائمة الفروع مع الطلبات والإيراد"""
    return delivery_service.get_app_branch_matrix(
        db, year=year, month=month, brand_id=brand_id
    )


@router.get("/unmatched", response_model=list[DeliveryUnmatchedBranch])
def get_unmatched(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*_DELIVERY_READ_ROLES)),
):
    """الفروع غير المربوطة — تحتاج إضافة alias أو فرع جديد"""
    return delivery_service.get_unmatched_branches(db)


@router.get("/outliers", response_model=list[DeliveryRecordOut])
def get_outliers(
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*_DELIVERY_READ_ROLES)),
):
    """سجلات AOV شاذة (> 500 ريال)"""
    return delivery_service.get_outliers(db, year=year, month=month)
