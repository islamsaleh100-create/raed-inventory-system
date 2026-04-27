"""
Brand-aware legacy quality checklist seeding.

This keeps the old /quality visit module usable for non-Onda branches until the
new evaluation flows fully replace it.
"""
from __future__ import annotations

from app.models import QualityVisitItem, QualityVisitSection


CHECKLISTS = {
    "ronaldos": [
        (
            "التشغيل والاستعداد",
            "Operations & Readiness",
            [
                ("جاهزية الفرن قبل التشغيل", "Oven readiness before operation"),
                ("توفر العجين والصوص والجبن والإضافات", "Availability of dough, sauce, cheese and toppings"),
                ("الالتزام بخطة التحضير اليومية", "Daily prep plan compliance"),
                ("سرعة تجهيز الطلب", "Order preparation speed"),
                ("تنظيم محطة البيتزا", "Pizza station organization"),
            ],
        ),
        (
            "جودة المنتج",
            "Product Quality",
            [
                ("جودة العجين", "Dough quality"),
                ("كمية الصوص والجبن حسب الوصفة", "Sauce and cheese quantity according to recipe"),
                ("توزيع الإضافات", "Toppings distribution"),
                ("مستوى الخبز واللون", "Baking level and color"),
                ("دقة التقطيع", "Pizza cutting accuracy"),
            ],
        ),
        (
            "النظافة وسلامة الغذاء",
            "Hygiene & Food Safety",
            [
                ("نظافة الفرن وطاولة العمل", "Oven and worktable cleanliness"),
                ("فصل الخام عن الجاهز", "Separation of raw and ready items"),
                ("الالتزام بدرجات الحرارة", "Temperature control"),
                ("الالتزام بالقفازات وغطاء الرأس", "Gloves and head cover compliance"),
                ("الالتزام بتواريخ الصلاحية وFIFO", "Expiry and FIFO compliance"),
            ],
        ),
        (
            "خدمة العملاء والكاشير",
            "Customer Service & Cashier",
            [
                ("سرعة استقبال الطلب", "Order receiving speed"),
                ("التعامل مع العميل", "Customer handling"),
                ("معالجة الشكاوى", "Complaint handling"),
                ("دقة الفاتورة", "Invoice accuracy"),
                ("الالتزام بالعروض والبيع الإضافي", "Offer compliance and upselling"),
            ],
        ),
    ],
    "shawarma": [
        (
            "التشغيل والاستعداد",
            "Operations & Readiness",
            [
                ("جاهزية السيخ قبل وقت الذروة", "Skewer readiness before peak time"),
                ("جاهزية الخبز والصوص والخضار", "Bread, sauces and vegetables readiness"),
                ("توفر الدجاج أو اللحم", "Chicken or meat availability"),
                ("جاهزية المعدات", "Equipment readiness"),
                ("سرعة التحضير", "Preparation speed"),
            ],
        ),
        (
            "جودة المنتج",
            "Product Quality",
            [
                ("طعم الشاورما", "Shawarma taste"),
                ("مستوى الطهي", "Cooking level"),
                ("جودة التقطيع", "Cutting quality"),
                ("كمية الصوص والخضار", "Sauce and vegetable quantity"),
                ("تناسق المنتج خلال اليوم", "Product consistency during the day"),
            ],
        ),
        (
            "سلامة الغذاء والنظافة",
            "Food Safety & Cleanliness",
            [
                ("حرارة السيخ", "Skewer temperature"),
                ("تخزين الدجاج أو اللحم", "Chicken or meat storage"),
                ("فصل الخام عن الجاهز", "Raw and ready separation"),
                ("تعقيم الأدوات والسكاكين", "Knife and tools sanitation"),
                ("الالتزام بـ FIFO", "FIFO compliance"),
            ],
        ),
        (
            "خدمة العملاء والانضباط",
            "Customer Service & Discipline",
            [
                ("سرعة استقبال الطلب", "Order receiving speed"),
                ("زمن تقديم الخدمة", "Service time compliance"),
                ("دقة التسليم", "Order delivery accuracy"),
                ("انضباط الفريق", "Staff discipline"),
                ("متابعة المدير وقت الذروة", "Manager peak-time follow-up"),
            ],
        ),
    ],
    "griddle": [
        (
            "التشغيل والاستعداد",
            "Operations & Readiness",
            [
                ("جاهزية الجريل قبل التشغيل", "Grill readiness before operation"),
                ("توفر اللحم أو الدجاج والخبز والصوص", "Availability of meat or chicken, bread and sauces"),
                ("جاهزية خط الإنتاج", "Production line organization"),
                ("سرعة التحضير", "Order preparation speed"),
                ("جاهزية الـ mise en place", "Mise en place readiness"),
            ],
        ),
        (
            "جودة المنتج",
            "Product Quality",
            [
                ("مستوى استواء اللحم", "Meat cooking level"),
                ("طعم التتبيلة", "Marinade taste"),
                ("مظهر الساندوتش أو البرجر", "Burger or sandwich appearance"),
                ("حرارة المنتج عند التسليم", "Product temperature at handover"),
                ("ثبات الجودة", "Quality consistency"),
            ],
        ),
        (
            "سلامة الغذاء والنظافة",
            "Food Safety & Cleanliness",
            [
                ("فصل الخام عن الجاهز", "Raw and ready separation"),
                ("درجات حرارة التخزين", "Storage temperature"),
                ("التعامل الآمن مع اللحوم", "Safe meat handling"),
                ("نظافة الأدوات والطاولات", "Tools and tables cleanliness"),
                ("الالتزام بـ FIFO", "FIFO compliance"),
            ],
        ),
        (
            "خدمة العملاء والانضباط",
            "Customer Service & Discipline",
            [
                ("سرعة الخدمة", "Service speed"),
                ("دقة الطلب", "Order accuracy"),
                ("التعامل مع الشكاوى", "Complaint handling"),
                ("توزيع المهام", "Task distribution"),
                ("الالتزام بالسياسات", "Policy compliance"),
            ],
        ),
    ],
    "onda": [
        (
            "النظافة والترتيب",
            "Cleanliness & Organization",
            [
                ("نظافة منطقة تحضير القهوة", "Coffee prep area cleanliness"),
                ("نظافة الأجهزة والمعدات", "Equipment cleanliness"),
                ("نظافة الأرضيات والجدران", "Floor and wall cleanliness"),
                ("نظافة دورات المياه", "Restroom cleanliness"),
            ],
        ),
        (
            "جودة التشغيل",
            "Operations Quality",
            [
                ("جاهزية البار قبل التشغيل", "Bar readiness before operation"),
                ("توفر المواد الأساسية", "Availability of core ingredients"),
                ("سرعة تقديم الطلب", "Order service speed"),
                ("عرض المنتجات بطريقة مناسبة", "Proper product display"),
            ],
        ),
    ],
}


def _seed_brand(db, brand_key: str, sections: list[tuple[str, str, list[tuple[str, str]]]]) -> int:
    created = 0
    existing = (
        db.query(QualityVisitSection)
        .filter(QualityVisitSection.brand_key == brand_key)
        .limit(1)
        .first()
    )
    if existing:
        return 0

    for section_order, (name_ar, name_en, items) in enumerate(sections, start=1):
        section = QualityVisitSection(
            brand_key=brand_key,
            name_ar=name_ar,
            name_en=name_en,
            order=section_order,
            weight=25.0,
            is_active=True,
        )
        db.add(section)
        db.flush()
        for item_order, (text_ar, text_en) in enumerate(items, start=1):
            db.add(
                QualityVisitItem(
                    section_id=section.id,
                    text_ar=text_ar,
                    text_en=text_en,
                    response_type="yes_no",
                    order=item_order,
                    is_active=True,
                )
            )
            created += 1
    return created


def ensure_quality_checklists_seeded(db) -> dict[str, int]:
    created = {}
    has_global = (
        db.query(QualityVisitSection)
        .filter(QualityVisitSection.brand_key.is_(None))
        .limit(1)
        .first()
        is not None
    )
    for brand_key, sections in CHECKLISTS.items():
        if brand_key == "onda" and has_global:
            # Keep legacy Onda/global checklist as-is to avoid replacing the
            # richer existing store-visit template already in use.
            created[brand_key] = 0
            continue
        created[brand_key] = _seed_brand(db, brand_key, sections)
    if any(created.values()):
        db.commit()
    return created
