"""
Delivery Analytics Service
"""
from decimal import Decimal
from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models import (
    DeliveryBrand, DeliveryBranch, DeliveryBranchAlias,
    DeliveryApp, DeliveryRecord,
)
from app.schemas import (
    DeliveryImportRequest, DeliveryBranchCreate, DeliveryBranchUpdate,
)

AOV_OUTLIER_THRESHOLD = 500

MONTH_NAMES_AR = {
    1: "يناير", 2: "فبراير", 3: "مارس", 4: "أبريل",
    5: "مايو",  6: "يونيو",  7: "يوليو", 8: "أغسطس",
    9: "سبتمبر",10: "أكتوبر",11: "نوفمبر",12: "ديسمبر",
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_or_create_brand(db: Session, name: str) -> DeliveryBrand:
    name = name.strip()
    obj = db.query(DeliveryBrand).filter(
        func.lower(DeliveryBrand.name) == name.lower()
    ).first()
    if not obj:
        obj = DeliveryBrand(name=name)
        db.add(obj)
        db.flush()
    return obj


def _get_or_create_app(db: Session, name: str) -> DeliveryApp:
    name = name.strip()
    obj = db.query(DeliveryApp).filter(
        func.lower(DeliveryApp.name) == name.lower()
    ).first()
    if not obj:
        obj = DeliveryApp(name=name)
        db.add(obj)
        db.flush()
    return obj


def _find_branch(db: Session, brand_id: int, branch_name: str) -> Optional[DeliveryBranch]:
    """بحث ثلاثي: اسم رسمي -> alias -> LIKE"""
    name = branch_name.strip()

    # 1. اسم رسمي
    b = db.query(DeliveryBranch).filter(
        DeliveryBranch.brand_id == brand_id,
        func.lower(DeliveryBranch.name) == name.lower(),
    ).first()
    if b:
        return b

    # 2. alias
    a = db.query(DeliveryBranchAlias).join(DeliveryBranch).filter(
        DeliveryBranch.brand_id == brand_id,
        func.lower(DeliveryBranchAlias.alias) == name.lower(),
    ).first()
    if a:
        return a.branch

    # 3. LIKE جزئي — أول 15 حرف عشان نتجنب الـ false positives
    prefix = name.lower()[:15]
    if len(prefix) >= 3:   # لا نبحث بأقل من 3 أحرف
        b = db.query(DeliveryBranch).filter(
            DeliveryBranch.brand_id == brand_id,
            func.lower(DeliveryBranch.name).contains(prefix),
        ).first()
        if b:
            return b
    return None


def _base_q(db: Session, year=None, month=None, brand_id=None, app_id=None, branch_id=None):
    """query أساسي مع فلاتر مشتركة"""
    q = db.query(DeliveryRecord).filter(DeliveryRecord.is_outlier == False)
    if year:      q = q.filter(DeliveryRecord.year     == int(year))
    if month:     q = q.filter(DeliveryRecord.month    == int(month))
    if brand_id:  q = q.filter(DeliveryRecord.brand_id == int(brand_id))
    if app_id:    q = q.filter(DeliveryRecord.app_id   == int(app_id))
    if branch_id: q = q.filter(DeliveryRecord.branch_id== int(branch_id))
    return q


def _apply_filters(q, year=None, month=None, brand_id=None, app_id=None):
    if year:     q = q.filter(DeliveryRecord.year     == int(year))
    if month:    q = q.filter(DeliveryRecord.month    == int(month))
    if brand_id: q = q.filter(DeliveryRecord.brand_id == int(brand_id))
    if app_id:   q = q.filter(DeliveryRecord.app_id   == int(app_id))
    return q


def _aov(revenue, orders):
    if orders and int(orders) > 0:
        return round(float(revenue) / int(orders), 2)
    return None


# ─── Import ───────────────────────────────────────────────────────────────────

def import_delivery_data(db: Session, data: DeliveryImportRequest, imported_by: int = None):
    batch    = data.batch_name or f"import_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    imported = 0
    skipped  = 0
    unmatched_set: set = set()

    for row in data.rows:
        try:
            brand  = _get_or_create_brand(db, row.brand_name)
            app    = _get_or_create_app(db,   row.app_name)
            branch = _find_branch(db, brand.id, row.branch_name) if row.branch_name else None

            if not branch and row.branch_name:
                unmatched_set.add(row.branch_name.strip())

            # حساب AOV
            orders  = int(row.orders)
            revenue = float(row.revenue)
            aov     = round(revenue / orders, 2) if orders > 0 else None
            is_out  = aov is not None and aov > AOV_OUTLIER_THRESHOLD

            # فحص التكرار
            exists = db.query(DeliveryRecord).filter(
                DeliveryRecord.year           == row.year,
                DeliveryRecord.month          == row.month,
                DeliveryRecord.brand_id       == brand.id,
                DeliveryRecord.app_id         == app.id,
                DeliveryRecord.raw_branch_name == row.branch_name.strip(),
            ).first()
            if exists:
                skipped += 1
                continue

            rec = DeliveryRecord(
                year            = row.year,
                month           = row.month,
                brand_id        = brand.id,
                branch_id       = branch.id if branch else None,
                app_id          = app.id,
                orders          = orders,
                revenue         = Decimal(str(revenue)),
                aov             = Decimal(str(aov)) if aov else None,
                raw_branch_name = row.branch_name.strip() if row.branch_name else None,
                raw_brand_name  = row.brand_name.strip(),
                is_outlier      = is_out,
                import_batch    = batch,
            )
            db.add(rec)
            imported += 1

        except Exception:
            skipped += 1

    db.commit()
    return {
        "imported":  imported,
        "skipped":   skipped,
        "unmatched": len(unmatched_set),
        "batch_id":  batch,
    }


# ─── KPIs ─────────────────────────────────────────────────────────────────────

def get_kpis(db: Session, year=None, month=None, brand_id=None, app_id=None):
    base = db.query(
        func.sum(DeliveryRecord.orders).label("total_orders"),
        func.sum(DeliveryRecord.revenue).label("total_revenue"),
    ).filter(DeliveryRecord.is_outlier == False)
    base = _apply_filters(base, year=year, month=month, brand_id=brand_id, app_id=app_id)
    row  = base.first()

    total_orders  = int(row.total_orders  or 0)
    total_revenue = float(row.total_revenue or 0)
    avg_aov = _aov(total_revenue, total_orders)

    # top app
    ta = _apply_filters(
        db.query(DeliveryApp.id, DeliveryApp.name, func.sum(DeliveryRecord.orders).label("s"))
          .join(DeliveryRecord, DeliveryRecord.app_id == DeliveryApp.id)
          .filter(DeliveryRecord.is_outlier == False),
        year=year, month=month, brand_id=brand_id,
    ).group_by(DeliveryApp.id, DeliveryApp.name).order_by(func.sum(DeliveryRecord.orders).desc()).first()

    # top brand
    tb = _apply_filters(
        db.query(DeliveryBrand.name, func.sum(DeliveryRecord.orders).label("s"))
          .join(DeliveryRecord, DeliveryRecord.brand_id == DeliveryBrand.id)
          .filter(DeliveryRecord.is_outlier == False),
        year=year, month=month,
    ).group_by(DeliveryBrand.name).order_by(func.sum(DeliveryRecord.orders).desc()).first()

    # top branch
    tbr = _apply_filters(
        db.query(DeliveryBranch.name, func.sum(DeliveryRecord.orders).label("s"))
          .join(DeliveryRecord, DeliveryRecord.branch_id == DeliveryBranch.id)
          .filter(DeliveryRecord.is_outlier == False, DeliveryRecord.branch_id != None),
        year=year, month=month, brand_id=brand_id,
    ).group_by(DeliveryBranch.name).order_by(func.sum(DeliveryRecord.orders).desc()).first()

    return {
        "total_orders":   total_orders,
        "total_revenue":  total_revenue,
        "avg_aov":        avg_aov,
        "top_app":        ta.name if ta else None,
        "top_app_orders": int(ta.s)  if ta else None,
        "top_brand":      tb.name if tb else None,
        "top_branch":     tbr.name if tbr else None,
    }


# ─── App Stats ────────────────────────────────────────────────────────────────

def get_app_stats(db: Session, year=None, month=None, brand_id=None):
    q = _apply_filters(
        db.query(
            DeliveryApp.id.label("app_id"),
            DeliveryApp.name.label("app_name"),
            func.sum(DeliveryRecord.orders).label("orders"),
            func.sum(DeliveryRecord.revenue).label("revenue"),
        ).join(DeliveryRecord, DeliveryRecord.app_id == DeliveryApp.id)
         .filter(DeliveryRecord.is_outlier == False),
        year=year, month=month, brand_id=brand_id,
    ).group_by(DeliveryApp.id, DeliveryApp.name)\
     .order_by(func.sum(DeliveryRecord.orders).desc()).all()

    total = sum(int(r.orders or 0) for r in q) or 1
    return [
        {
            "app_id":    r.app_id,
            "app_name":  r.app_name,
            "orders":    int(r.orders or 0),
            "revenue":   float(r.revenue or 0),
            "avg_aov":   _aov(r.revenue, r.orders),
            "share_pct": round(int(r.orders or 0) / total * 100, 1),
        }
        for r in q
    ]


# ─── Brand Stats ──────────────────────────────────────────────────────────────

def get_brand_stats(db: Session, year=None, month=None, app_id=None):
    q = _apply_filters(
        db.query(
            DeliveryBrand.id.label("brand_id"),
            DeliveryBrand.name.label("brand_name"),
            func.sum(DeliveryRecord.orders).label("orders"),
            func.sum(DeliveryRecord.revenue).label("revenue"),
        ).join(DeliveryRecord, DeliveryRecord.brand_id == DeliveryBrand.id)
         .filter(DeliveryRecord.is_outlier == False),
        year=year, month=month, app_id=app_id,
    ).group_by(DeliveryBrand.id, DeliveryBrand.name)\
     .order_by(func.sum(DeliveryRecord.orders).desc()).all()

    total = sum(int(r.orders or 0) for r in q) or 1
    return [
        {
            "brand_id":  r.brand_id,
            "brand_name":r.brand_name,
            "orders":    int(r.orders or 0),
            "revenue":   float(r.revenue or 0),
            "avg_aov":   _aov(r.revenue, r.orders),
            "share_pct": round(int(r.orders or 0) / total * 100, 1),
        }
        for r in q
    ]


# ─── Branch Stats ─────────────────────────────────────────────────────────────

def get_branch_stats(db: Session, year=None, month=None, brand_id=None, app_id=None):
    q = _apply_filters(
        db.query(
            DeliveryBranch.id.label("branch_id"),
            DeliveryBranch.name.label("branch_name"),
            DeliveryBranch.google_maps_url.label("google_maps_url"),
            DeliveryBrand.name.label("brand_name"),
            func.sum(DeliveryRecord.orders).label("orders"),
            func.sum(DeliveryRecord.revenue).label("revenue"),
        ).join(DeliveryRecord, DeliveryRecord.branch_id == DeliveryBranch.id)
         .join(DeliveryBrand,  DeliveryBrand.id == DeliveryBranch.brand_id)
         .filter(DeliveryRecord.is_outlier == False, DeliveryRecord.branch_id != None),
        year=year, month=month, brand_id=brand_id, app_id=app_id,
    ).group_by(
        DeliveryBranch.id, DeliveryBranch.name,
        DeliveryBranch.google_maps_url, DeliveryBrand.name,
    ).order_by(func.sum(DeliveryRecord.orders).desc()).all()

    return [
        {
            "branch_id":      r.branch_id,
            "branch_name":    r.branch_name,
            "brand_name":     r.brand_name,
            "orders":         int(r.orders or 0),
            "revenue":        float(r.revenue or 0),
            "avg_aov":        _aov(r.revenue, r.orders),
            "google_maps_url":r.google_maps_url,
        }
        for r in q
    ]


# ─── Monthly Trend ────────────────────────────────────────────────────────────

def get_monthly_trend(db: Session, year=None, brand_id=None, app_id=None):
    q = _apply_filters(
        db.query(
            DeliveryRecord.year,
            DeliveryRecord.month,
            func.sum(DeliveryRecord.orders).label("orders"),
            func.sum(DeliveryRecord.revenue).label("revenue"),
        ).filter(DeliveryRecord.is_outlier == False),
        year=year, brand_id=brand_id, app_id=app_id,
    ).group_by(DeliveryRecord.year, DeliveryRecord.month)\
     .order_by(DeliveryRecord.year, DeliveryRecord.month).all()

    return [
        {
            "year":    r.year,
            "month":   r.month,
            "orders":  int(r.orders or 0),
            "revenue": float(r.revenue or 0),
        }
        for r in q
    ]


# ─── App × Branch Matrix ──────────────────────────────────────────────────────

def get_app_branch_matrix(db: Session, year=None, month=None, brand_id=None):
    q = _apply_filters(
        db.query(
            DeliveryApp.id.label("app_id"),
            DeliveryApp.name.label("app_name"),
            DeliveryBranch.id.label("branch_id"),
            DeliveryBranch.name.label("branch_name"),
            func.sum(DeliveryRecord.orders).label("orders"),
            func.sum(DeliveryRecord.revenue).label("revenue"),
        ).join(DeliveryRecord, DeliveryRecord.app_id == DeliveryApp.id)
         .join(DeliveryBranch, DeliveryBranch.id == DeliveryRecord.branch_id)
         .filter(DeliveryRecord.is_outlier == False, DeliveryRecord.branch_id != None),
        year=year, month=month, brand_id=brand_id,
    ).group_by(
        DeliveryApp.id, DeliveryApp.name,
        DeliveryBranch.id, DeliveryBranch.name,
    ).order_by(DeliveryApp.name, func.sum(DeliveryRecord.orders).desc()).all()

    # تجميع حسب التطبيق
    apps: dict = {}
    for r in q:
        if r.app_id not in apps:
            apps[r.app_id] = {"app_id": r.app_id, "app_name": r.app_name, "branches": []}
        apps[r.app_id]["branches"].append({
            "branch_id":   r.branch_id,
            "branch_name": r.branch_name,
            "orders":      int(r.orders or 0),
            "revenue":     float(r.revenue or 0),
        })
    return list(apps.values())


# ─── Unmatched ────────────────────────────────────────────────────────────────

def get_unmatched_branches(db: Session):
    rows = db.query(
        DeliveryRecord.raw_branch_name,
        func.count(DeliveryRecord.id).label("cnt"),
    ).filter(DeliveryRecord.branch_id == None)\
     .group_by(DeliveryRecord.raw_branch_name)\
     .order_by(func.count(DeliveryRecord.id).desc()).all()
    return [{"raw_name": r.raw_branch_name, "count": r.cnt} for r in rows]


# ─── Outliers ─────────────────────────────────────────────────────────────────

def get_outliers(db: Session, year=None, month=None):
    q = db.query(DeliveryRecord)\
          .options(joinedload(DeliveryRecord.brand),
                   joinedload(DeliveryRecord.branch),
                   joinedload(DeliveryRecord.app))\
          .filter(DeliveryRecord.is_outlier == True)
    if year:  q = q.filter(DeliveryRecord.year  == int(year))
    if month: q = q.filter(DeliveryRecord.month == int(month))
    return q.order_by(DeliveryRecord.aov.desc()).all()


# ─── Master Data CRUD ─────────────────────────────────────────────────────────

def list_brands(db: Session):
    return db.query(DeliveryBrand).filter(DeliveryBrand.is_active == True)\
             .order_by(DeliveryBrand.name).all()


def list_apps(db: Session):
    return db.query(DeliveryApp).filter(DeliveryApp.is_active == True)\
             .order_by(DeliveryApp.name).all()


def list_branches(db: Session, brand_id=None):
    q = db.query(DeliveryBranch)\
          .options(joinedload(DeliveryBranch.brand), selectinload(DeliveryBranch.aliases))\
          .filter(DeliveryBranch.is_active == True)
    if brand_id:
        q = q.filter(DeliveryBranch.brand_id == int(brand_id))
    return q.order_by(DeliveryBranch.brand_id, DeliveryBranch.name).all()


def create_branch(db: Session, data: DeliveryBranchCreate):
    branch = DeliveryBranch(**data.model_dump())
    db.add(branch)
    db.commit()
    db.refresh(branch)
    return branch


def update_branch(db: Session, branch_id: int, data: DeliveryBranchUpdate):
    branch = db.query(DeliveryBranch).filter(DeliveryBranch.id == branch_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="الفرع غير موجود")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(branch, k, v)
    db.commit()
    db.refresh(branch)
    return branch


def add_alias(db: Session, branch_id: int, alias: str):
    """إضافة اسم بديل لفرع"""
    branch = db.query(DeliveryBranch).filter(DeliveryBranch.id == branch_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="الفرع غير موجود")
    obj = DeliveryBranchAlias(branch_id=branch_id, alias=alias.strip())
    db.add(obj)
    db.commit()
    # أرجع الفرع مع aliases محدثة
    return db.query(DeliveryBranch)\
             .options(joinedload(DeliveryBranch.brand), selectinload(DeliveryBranch.aliases))\
             .filter(DeliveryBranch.id == branch_id).first()


def delete_alias(db: Session, alias_id: int):
    a = db.query(DeliveryBranchAlias).filter(DeliveryBranchAlias.id == alias_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="الاسم البديل غير موجود")
    db.delete(a)
    db.commit()


def get_available_periods(db: Session):
    rows = db.query(DeliveryRecord.year, DeliveryRecord.month)\
             .distinct()\
             .order_by(DeliveryRecord.year, DeliveryRecord.month).all()
    return [
        {"year": r.year, "month": r.month,
         "label": f"{MONTH_NAMES_AR.get(r.month,'')} {r.year}"}
        for r in rows
    ]
