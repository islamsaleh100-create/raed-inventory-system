"""
seed_delivery.py
================
سكريبت يحمّل البيانات الأساسية (Brands, Apps, Branches, Aliases)
ويستورد بيانات التطبيقات من ملفي Excel:
  1. Read Location -New Update.xlsx  → بيانات الفروع (اللوكيشن، الساعات)
  2. تحليل تطبيقات التوصيل 2026.xlsx → بيانات الطلبات

الاستخدام:
    python seed_delivery.py

ملاحظة: شغّل السكريبت من مجلد backend مع تفعيل الـ virtual environment
"""

import sys
import os
import zipfile
import xml.etree.ElementTree as ET
from decimal import Decimal
from datetime import datetime

# أضف مجلد backend للمسار
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models import (
    DeliveryBrand, DeliveryBranch, DeliveryBranchAlias,
    DeliveryApp, DeliveryRecord,
)

# ─── ثوابت ────────────────────────────────────────────────────────────────────

LOCATION_FILE = os.path.join(
    os.path.dirname(__file__),
    "../../uploads/Read Location -New Update.xlsx",
)
ANALYTICS_FILE = os.path.join(
    os.path.dirname(__file__),
    "../../uploads/تحليل تطبيقات التوصيل 2026.xlsx",
)

AOV_OUTLIER_THRESHOLD = 500

# البراندات الأساسية
BRANDS = [
    {"name": "ONDA",       "name_ar": "أوندا"},
    {"name": "Ronaldos",   "name_ar": "رونالدوس"},
    {"name": "Shawarma",   "name_ar": "شاورما"},
    {"name": "Griddle",    "name_ar": "جريدل"},
]

# التطبيقات الأساسية
APPS = [
    {"name": "HungerStation", "name_ar": "هنقرستيشن"},
    {"name": "Keeta",          "name_ar": "كيتا"},
    {"name": "Ninja",          "name_ar": "نينجا"},
]


# ─── Excel Parser ─────────────────────────────────────────────────────────────

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def _read_xlsx(path: str) -> list[list]:
    """قراءة xlsx وإرجاع قائمة من الصفوف (كل صف قائمة من القيم)"""
    rows = []
    with zipfile.ZipFile(path) as z:
        # اقرأ shared strings
        shared_strings = []
        if "xl/sharedStrings.xml" in z.namelist():
            tree = ET.parse(z.open("xl/sharedStrings.xml"))
            for si in tree.getroot().findall(f".//{NS}si"):
                texts = [t.text or "" for t in si.findall(f".//{NS}t")]
                shared_strings.append("".join(texts))

        # اقرأ الـ sheet الأول
        sheet_names = [n for n in z.namelist() if n.startswith("xl/worksheets/sheet")]
        sheet_names.sort()
        sheet_path = sheet_names[0]
        tree = ET.parse(z.open(sheet_path))
        root = tree.getroot()

        for row_el in root.findall(f".//{NS}row"):
            row = []
            for c in row_el.findall(f"{NS}c"):
                t = c.get("t", "")
                v_el = c.find(f"{NS}v")
                val = ""
                if v_el is not None and v_el.text is not None:
                    if t == "s":
                        val = shared_strings[int(v_el.text)]
                    else:
                        val = v_el.text
                row.append(val.strip() if isinstance(val, str) else val)
            rows.append(row)
    return rows


def _safe_str(v) -> str:
    return str(v).strip() if v not in (None, "") else ""


def _safe_int(v) -> int:
    try:
        return int(float(str(v).replace(",", "")))
    except Exception:
        return 0


def _safe_decimal(v) -> Decimal:
    try:
        return Decimal(str(v).replace(",", ""))
    except Exception:
        return Decimal("0")


# ─── Seed Functions ───────────────────────────────────────────────────────────

def seed_brands(db) -> dict[str, DeliveryBrand]:
    brand_map = {}
    for b in BRANDS:
        obj = db.query(DeliveryBrand).filter(DeliveryBrand.name == b["name"]).first()
        if not obj:
            obj = DeliveryBrand(name=b["name"], name_ar=b["name_ar"])
            db.add(obj)
            db.flush()
            print(f"  ✓ Brand: {b['name']}")
        brand_map[b["name"].upper()] = obj
    db.commit()
    return brand_map


def seed_apps(db) -> dict[str, DeliveryApp]:
    app_map = {}
    for a in APPS:
        obj = db.query(DeliveryApp).filter(DeliveryApp.name == a["name"]).first()
        if not obj:
            obj = DeliveryApp(name=a["name"], name_ar=a["name_ar"])
            db.add(obj)
            db.flush()
            print(f"  ✓ App: {a['name']}")
        app_map[a["name"].upper()] = obj
    db.commit()
    return app_map


def seed_branches_from_location(db, brand_map: dict) -> dict[str, DeliveryBranch]:
    """
    يقرأ ملف Location ويحمّل الفروع.
    يفترض أن الملف يحتوي على: Brand, Branch Name, Region/City,
    Regular Hours, Weekend Hours, Notes, Google Maps URL
    """
    branch_map = {}

    if not os.path.exists(LOCATION_FILE):
        print(f"  ⚠️  ملف اللوكيشن غير موجود: {LOCATION_FILE}")
        print("     تأكد من وضع الملف في المسار الصحيح أو عدّل LOCATION_FILE في السكريبت")
        return branch_map

    rows = _read_xlsx(LOCATION_FILE)
    if not rows:
        print("  ⚠️  ملف اللوكيشن فارغ")
        return branch_map

    # تجاهل الصف الأول (headers)
    headers = [str(h).strip().lower() for h in rows[0]]
    print(f"  Headers (location): {headers[:8]}")

    # حاول نتعرف على الأعمدة
    def col(name_variants):
        for v in name_variants:
            for i, h in enumerate(headers):
                if v in h:
                    return i
        return -1

    idx_brand   = col(["brand"])
    idx_name    = col(["branch", "store", "name", "فرع", "اسم"])
    idx_region  = col(["region", "city", "area", "منطقة", "مدينة"])
    idx_reg_hrs = col(["regular", "weekday", "عادي"])
    idx_wknd    = col(["weekend", "جمعة", "عطلة"])
    idx_notes   = col(["notes", "ملاحظات"])
    idx_maps    = col(["map", "google", "خريطة", "رابط"])

    print(f"  Columns detected → brand:{idx_brand} name:{idx_name} region:{idx_region} maps:{idx_maps}")

    for row in rows[1:]:
        if not row or not any(row):
            continue

        def get(i):
            return _safe_str(row[i]) if 0 <= i < len(row) else ""

        brand_raw = get(idx_brand) if idx_brand >= 0 else "ONDA"
        name      = get(idx_name)  if idx_name  >= 0 else ""
        if not name:
            continue

        # ابحث عن البراند
        brand_key = brand_raw.upper()
        brand_obj = None
        for k, v in brand_map.items():
            if k in brand_key or brand_key in k:
                brand_obj = v
                break
        if not brand_obj:
            # default للأول
            brand_obj = list(brand_map.values())[0]

        existing = db.query(DeliveryBranch).filter(
            DeliveryBranch.brand_id == brand_obj.id,
            DeliveryBranch.name == name,
        ).first()

        if not existing:
            existing = DeliveryBranch(
                brand_id=brand_obj.id,
                name=name,
                region=get(idx_region),
                regular_hours=get(idx_reg_hrs),
                weekend_hours=get(idx_wknd),
                hours_notes=get(idx_notes),
                google_maps_url=get(idx_maps),
            )
            db.add(existing)
            db.flush()
            print(f"  ✓ Branch: {name} ({brand_obj.name})")
        else:
            # تحديث روابط الخريطة إن كانت فارغة
            if not existing.google_maps_url and get(idx_maps):
                existing.google_maps_url = get(idx_maps)

        branch_map[name.upper()] = existing

    db.commit()
    return branch_map


def _find_branch(name: str, branch_map: dict) -> DeliveryBranch | None:
    """بحث ثلاثي: اسم مطابق → اسم جزئي → None"""
    key = name.strip().upper()
    if key in branch_map:
        return branch_map[key]
    # جزئي
    for k, v in branch_map.items():
        if key in k or k in key:
            return v
    return None


def seed_delivery_records(
    db,
    brand_map: dict,
    app_map: dict,
    branch_map: dict,
):
    """يقرأ ملف التطبيقات ويستورد السجلات"""
    if not os.path.exists(ANALYTICS_FILE):
        print(f"  ⚠️  ملف التطبيقات غير موجود: {ANALYTICS_FILE}")
        return

    rows = _read_xlsx(ANALYTICS_FILE)
    if not rows:
        print("  ⚠️  ملف التطبيقات فارغ")
        return

    headers = [str(h).strip().lower() for h in rows[0]]
    print(f"  Headers (analytics): {headers[:10]}")

    def col(name_variants):
        for v in name_variants:
            for i, h in enumerate(headers):
                if v in h:
                    return i
        return -1

    idx_year    = col(["year", "سنة"])
    idx_month   = col(["month", "شهر"])
    idx_brand   = col(["brand", "براند"])
    idx_branch  = col(["branch", "store", "فرع"])
    idx_app     = col(["app", "platform", "تطبيق"])
    idx_orders  = col(["order", "طلب", "count"])
    idx_revenue = col(["revenue", "sales", "إيراد", "مبيعات"])
    idx_aov     = col(["aov", "average order"])

    print(f"  Columns → year:{idx_year} month:{idx_month} brand:{idx_brand} branch:{idx_branch} app:{idx_app} orders:{idx_orders} revenue:{idx_revenue}")

    batch_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    imported = 0
    skipped  = 0
    unmatched_branches = set()

    for i, row in enumerate(rows[1:], start=2):
        if not row or not any(row):
            continue

        def get(idx):
            return _safe_str(row[idx]) if 0 <= idx < len(row) else ""

        year  = _safe_int(get(idx_year))  if idx_year  >= 0 else 0
        month = _safe_int(get(idx_month)) if idx_month >= 0 else 0
        if year == 0 or month == 0:
            skipped += 1
            continue

        raw_brand  = get(idx_brand)  if idx_brand  >= 0 else ""
        raw_branch = get(idx_branch) if idx_branch >= 0 else ""
        raw_app    = get(idx_app)    if idx_app    >= 0 else ""

        orders  = _safe_int(get(idx_orders))     if idx_orders  >= 0 else 0
        revenue = _safe_decimal(get(idx_revenue)) if idx_revenue >= 0 else Decimal("0")

        # حساب AOV
        if idx_aov >= 0 and get(idx_aov):
            aov = _safe_decimal(get(idx_aov))
        elif orders > 0 and revenue > 0:
            aov = round(revenue / orders, 2)
        else:
            aov = None

        is_outlier = bool(aov and aov > AOV_OUTLIER_THRESHOLD)

        # ابحث عن Brand
        brand_obj = None
        for k, v in brand_map.items():
            if k in raw_brand.upper() or raw_brand.upper() in k:
                brand_obj = v
                break
        if not brand_obj:
            brand_obj = list(brand_map.values())[0]

        # ابحث عن App
        app_obj = None
        for k, v in app_map.items():
            if k in raw_app.upper() or raw_app.upper() in k:
                app_obj = v
                break
        if not app_obj:
            print(f"  ⚠️  صف {i}: تطبيق غير معروف '{raw_app}' — تخطي")
            skipped += 1
            continue

        # ابحث عن Branch
        branch_obj = _find_branch(raw_branch, branch_map)
        if not branch_obj and raw_branch:
            unmatched_branches.add(raw_branch)

        # تحقق من التكرار
        existing = db.query(DeliveryRecord).filter(
            DeliveryRecord.year == year,
            DeliveryRecord.month == month,
            DeliveryRecord.brand_id == brand_obj.id,
            DeliveryRecord.app_id == app_obj.id,
            DeliveryRecord.raw_branch_name == raw_branch,
        ).first()

        if existing:
            skipped += 1
            continue

        rec = DeliveryRecord(
            year=year,
            month=month,
            brand_id=brand_obj.id,
            branch_id=branch_obj.id if branch_obj else None,
            app_id=app_obj.id,
            orders=orders,
            revenue=revenue,
            aov=aov,
            raw_branch_name=raw_branch,
            raw_brand_name=raw_brand,
            is_outlier=is_outlier,
            import_batch=batch_id,
        )
        db.add(rec)
        imported += 1

        if imported % 50 == 0:
            db.commit()
            print(f"  ... {imported} سجل محفوظ")

    db.commit()
    print(f"\n  ✅ تم استيراد {imported} سجل، تخطي {skipped}")

    if unmatched_branches:
        print(f"\n  ⚠️  فروع غير مربوطة ({len(unmatched_branches)}):")
        for b in sorted(unmatched_branches):
            print(f"     - {b}")


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n🚀 بدء تهيئة بيانات Delivery Analytics...\n")

    db = SessionLocal()
    try:
        print("📦 Brands...")
        brand_map = seed_brands(db)

        print("\n📱 Apps...")
        app_map = seed_apps(db)

        print("\n🏪 Branches (from Location file)...")
        branch_map = seed_branches_from_location(db, brand_map)

        print(f"\n     عدد الفروع المحمّلة: {len(branch_map)}")

        print("\n📊 Delivery Records (from Analytics file)...")
        seed_delivery_records(db, brand_map, app_map, branch_map)

        print("\n✅ اكتملت عملية التهيئة بنجاح!\n")

    except Exception as e:
        db.rollback()
        print(f"\n❌ خطأ: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()
