"""
Seed script for Quality Visit & Training Assessment module
Sources the REAL ONDA templates from the business docs:
  - stores visit checklist.xlsx       - ONDA Internal Visit Checklist (6 sections)
  - تقييم البارستا.xlsx              - Barista Assessment (8 sections, 23 items)
  - تقيم مدراء الافرع.xlsx           - Branch Manager Assessment (7 sections, 17 items)

Re-runnable: upserts by natural keys (name_ar for sections/templates, text_ar for items).
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# K2: force UTF-8 on stdout/stderr so emoji prints never crash on Windows
# (cp1252 console can't encode ✅/🔵/🎉 etc.). Python 3.7+ supports reconfigure.
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# K2: additional fallback — wrap print() so even if reconfigure fails, emoji
# characters are replaced rather than raising UnicodeEncodeError. This
# protects against the migration 0012 and main.py startup auto-seed paths.
_original_print = print
def _safe_print(*args, **kwargs):
    try:
        _original_print(*args, **kwargs)
    except UnicodeEncodeError:
        try:
            safe_args = [
                (str(a).encode("ascii", "replace").decode("ascii") if isinstance(a, str) else a)
                for a in args
            ]
            _original_print(*safe_args, **kwargs)
        except Exception:
            pass  # give up silently — seed still proceeds

# Override the module-level print (affects calls inside this file only)
print = _safe_print  # noqa: A001

from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app.models import (
    Base,
    Role, RoleName,
    QualityVisitSection, QualityVisitItem,
    TrainingTemplate, TrainingTemplateSection, TrainingTemplateItem,
    TrainingRoleType,
)


def create_tables():
    """
    Safety-net table creation.
    On PostgreSQL: tables must already exist via `alembic upgrade head`.
    This function is a no-op on PostgreSQL and only creates tables on SQLite.
    """
    url = str(engine.url)
    if not url.startswith("sqlite"):
        print("i  PostgreSQL detected -- skipping create_all (use `alembic upgrade head` first)")
        return
    Base.metadata.create_all(bind=engine)
    print("OK Tables created / verified (SQLite)")


# ─── Quality Visit Checklist (ONDA Internal Visit Checklist) ─────────────────
# Each item: (text_ar, text_en, response_type, numeric_unit, benchmark_ar)
# response_type: "yes_no" | "numeric" | "text"

QUALITY_SECTIONS = [
    {
        "name_ar": "الجودة",
        "name_en": "Quality",
        "order": 1,
        "weight": 25.0,
        "items": [
            ("جميع ملصقات التواريخ صحيحة ومحدثة",
             "All date stamps are correct and updated",
             "yes_no", None, None),
            ("جميع المعدات معايرة",
             "All equipments are calibrated",
             "yes_no", None, None),
            ("جميع درجات الحرارة مطابقة للمعايير",
             "All temperatures are up to standards",
             "yes_no", None, None),
            ("جميع الهدر محسوب ومسجل بشكل صحيح",
             "All wastage checked and logged properly",
             "yes_no", None, None),
            ("قراءة TDS لمياه التحضير",
             "TDS reading of brew water",
             "numeric", "ppm", "النطاق المقبول: 75 - 250 ppm"),
        ],
    },
    {
        "name_ar": "نظافة الموظفين",
        "name_en": "Staff Hygiene",
        "order": 2,
        "weight": 15.0,
        "items": [
            ("جميع الموظفين يرتدون زي نظيف",
             "All staff are using clean uniforms",
             "yes_no", None, None),
            ("جميع الموظفين حلقوا وقصوا الأظافر",
             "All employees are shaved and nails trimmed",
             "yes_no", None, None),
            ("جميع الموظفين يرتدون قفازات وكمامات",
             "All employees using gloves and face masks",
             "yes_no", None, None),
            ("جميع الموظفين يلتزمون بسياسة المجوهرات",
             "All employees follow the jewellery policy",
             "yes_no", None, None),
            ("جميع الموظفين لديهم بطاقة بلدية سارية",
             "All employees have a valid Baladia card",
             "yes_no", None, None),
        ],
    },
    {
        "name_ar": "الخدمة",
        "name_en": "Service",
        "order": 3,
        "weight": 15.0,
        "items": [
            ("مظهر الموظفين مرتب ومهذّب",
             "All employees are neat and trimmed",
             "yes_no", None, None),
            ("جميع الإضافات مملوءة ومرتبة",
             "All condiments are refilled and stacked",
             "yes_no", None, None),
            ("ثلاجة العرض منظمة ومرتبة",
             "Display chiller is organized and stacked",
             "yes_no", None, None),
            ("البيع التلقائي / البيع الإيحائي مطبّق",
             "Suggestive / upselling is followed",
             "yes_no", None, None),
            ("وقت الخدمة حسب الهدف",
             "Service time is according to target",
             "yes_no", None, None),
            ("جميع التطبيقات مفعّلة ومراقبة",
             "All applications turned on and checked",
             "yes_no", None, None),
        ],
    },
    {
        "name_ar": "النظافة العامة",
        "name_en": "Cleanliness",
        "order": 4,
        "weight": 20.0,
        "items": [
            ("البار منظم ونظيف",
             "The bar is organized and clean",
             "yes_no", None, None),
            ("منطقة الصالة الداخلية منظمة ونظيفة",
             "Dine-in area is organized and clean",
             "yes_no", None, None),
            ("مسار السيارة (Drive-through) نظيف",
             "Drive through lane is clean",
             "yes_no", None, None),
            ("النوافذ والأبواب نظيفة",
             "Windows and doors are clean",
             "yes_no", None, None),
            ("غرفة المخزون منظمة ونظيفة",
             "Stock room is organized and clean",
             "yes_no", None, None),
            ("المنطقة الخارجية للجلوس منظمة ونظيفة",
             "Outdoor dining is organized and clean",
             "yes_no", None, None),
            ("قائمة الفحص مُعتَمدة ومُنفّذة",
             "Checklist is validated and worked on",
             "yes_no", None, None),
            ("دورات المياه نظيفة ومُمَوَّنة",
             "Rest room is clean and refilled",
             "yes_no", None, None),
        ],
    },
    {
        "name_ar": "الأهداف اليومية",
        "name_en": "Daily Targets",
        "order": 5,
        "weight": 20.0,
        "items": [
            ("متوسط الفاتورة الشهري",
             "Monthly average check",
             "numeric", "SAR", "يسجل الرقم الفعلي لنهاية الشهر حتى اليوم"),
            ("متوسط المبيعات اليومي",
             "Daily average sales",
             "numeric", "SAR", "مبيعات اليوم الإجمالية"),
            ("متوسط عدد الضيوف اليومي",
             "Average daily guest count",
             "numeric", "count", "عدد ضيوف اليوم"),
            ("عدد الضيوف الشهري",
             "Monthly guest count",
             "numeric", "count", "التراكمي من أول الشهر"),
            ("المستهدف مقابل الفعلي (%)",
             "Target vs actual (%)",
             "numeric", "%", "نسبة تحقيق الهدف الشهري"),
        ],
    },
    {
        "name_ar": "الاحتياجات والملاحظات",
        "name_en": "Needs & Notes",
        "order": 6,
        "weight": 5.0,
        "items": [
            ("احتياجات الفرع",
             "Store needs",
             "text", None, "أدوات، مواد، أو طلبات تحتاج متابعة من الإدارة"),
        ],
    },
]


def seed_quality_sections(db: Session):
    print("🔵 Seeding Quality Visit checklist (ONDA real)...")
    for sec_data in QUALITY_SECTIONS:
        section = db.query(QualityVisitSection).filter(
            QualityVisitSection.name_ar == sec_data["name_ar"]
        ).first()
        if section:
            section.name_en = sec_data["name_en"]
            section.order   = sec_data["order"]
            section.weight  = sec_data["weight"]
            section.is_active = True
            print(f"  🔄 Section updated: {sec_data['name_ar']}")
        else:
            section = QualityVisitSection(
                name_ar=sec_data["name_ar"],
                name_en=sec_data["name_en"],
                order=sec_data["order"],
                weight=sec_data["weight"],
                is_active=True,
            )
            db.add(section)
            db.flush()
            print(f"  ✅ Section created: {sec_data['name_ar']}")

        for i, (text_ar, text_en, rtype, unit, bench_ar) in enumerate(sec_data["items"], start=1):
            item = db.query(QualityVisitItem).filter(
                QualityVisitItem.section_id == section.id,
                QualityVisitItem.text_ar == text_ar,
            ).first()
            if item:
                item.text_en       = text_en
                item.response_type = rtype
                item.numeric_unit  = unit
                item.benchmark_ar  = bench_ar
                item.order         = i
                item.is_active     = True
            else:
                db.add(QualityVisitItem(
                    section_id=section.id,
                    text_ar=text_ar,
                    text_en=text_en,
                    response_type=rtype,
                    numeric_unit=unit,
                    benchmark_ar=bench_ar,
                    order=i,
                    is_active=True,
                ))
    db.commit()
    print("✅ Quality checklist seeded / refreshed")


# ─── Training Templates ────────────────────────────────────────────────────────
# item: (text_ar, text_en, benchmark_ar, benchmark_en)
# benchmark_ar/en optional — from the business description

BARISTA_TEMPLATE = {
    "role_type": TrainingRoleType.branch_employee,
    "name_ar": "نموذج تقييم الباريستا",
    "name_en": "Barista Assessment Form",
    "version": "v1.0",
    "sections": [
        {
            "name_ar": "المهارات الفنية والتحضير",
            "name_en": "Technical & Preparation Skills",
            "order": 1,
            "weight": 20.0,
            "items": [
                ("اتباع المعايير في تحضير المشروبات بدقة",
                 "Follows beverage preparation standards precisely",
                 "وصفة مطابقة للمعيار، جرعات دقيقة، وقت extraction سليم",
                 "Recipe matches spec, doses accurate, correct extraction time"),
                ("التعامل مع المكائن والمعدات (برمجة المكائن والمطاحن بدقة)",
                 "Handles machines & equipment (programs espresso machine & grinder accurately)",
                 "ضبط الطحن والضغط وفق المعيار، استجابة للتغيرات",
                 "Grinder/pressure tuned to spec, adapts to variables"),
                ("المعرفة التامة بالمنتجات (القائمة، أنواع القهوة، الأصول)",
                 "Complete product knowledge (menu, coffee types, origins)",
                 "يشرح 5 أنواع قهوة على الأقل ويربطها بالقائمة",
                 "Explains ≥5 coffee types and links them to the menu"),
            ],
        },
        {
            "name_ar": "الخدمة والتفاعل مع العملاء",
            "name_en": "Service & Customer Interaction",
            "order": 2,
            "weight": 15.0,
            "items": [
                ("التعامل الاحترافي مع العملاء (اللباقة، الترحيب، تقديم الفاتورة، المساعدة في اختيار الطلب)",
                 "Professional customer handling (courtesy, greeting, bill presentation, order assistance)",
                 "ترحيب خلال 30 ثانية، تقديم اقتراحات مناسبة، لغة محترمة",
                 "Greets within 30s, offers relevant suggestions, respectful language"),
                ("الاستجابة السريعة لطلبات العملاء وتنفيذها بدقة حسب رغبة العميل",
                 "Responds quickly and executes orders accurately per customer preference",
                 "تأكيد الطلب بصوت واضح، تنفيذ حسب الطلب بدون تعديل",
                 "Confirms order audibly, executes as requested without deviation"),
                ("التعامل مع شكاوى العملاء (القدرة على حل الشكاوى بشكل فعال ولطيف)",
                 "Handles customer complaints (resolves effectively and politely)",
                 "استماع، اعتذار، حل فوري أو تصعيد للمدير",
                 "Listens, apologizes, resolves immediately or escalates to manager"),
            ],
        },
        {
            "name_ar": "الالتزام والانضباط",
            "name_en": "Commitment & Discipline",
            "order": 3,
            "weight": 15.0,
            "items": [
                ("الالتزام بمواعيد العمل",
                 "Adheres to work schedule",
                 "لا تأخير أو غياب غير مبرر خلال الفترة",
                 "No unexcused tardiness/absence in period"),
                ("اتباع قواعد السلامة والصحة (ارتداء القفازات، الكمام، غطاء الشعر)",
                 "Follows safety & hygiene rules (gloves, mask, hair cover)",
                 "التزام 100% في كل الورديات",
                 "100% compliance in all shifts"),
                ("الالتزام بالسياسات الداخلية (عدم استخدام السماعات/الهاتف/تناول الطعام داخل منطقة التحضير)",
                 "Follows internal policies (no headphones/phone/eating in prep area)",
                 "لا مخالفات موثقة",
                 "No documented violations"),
                ("الالتزام بالجداول العملية (التنظيف، الجرد، الطلبات)",
                 "Adheres to operational schedules (cleaning, inventory, ordering)",
                 "قوائم الفحص مكتملة، مهام موقعة",
                 "Checklists complete, tasks signed off"),
            ],
        },
        {
            "name_ar": "السرعة والدقة في تنفيذ الطلبات",
            "name_en": "Speed & Accuracy",
            "order": 4,
            "weight": 15.0,
            "items": [
                ("السرعة في التحضير مع الحفاظ على الجودة خاصة في أوقات الذروة",
                 "Preparation speed while maintaining quality — especially at peak",
                 "متوسط وقت التحضير ضمن الهدف ±10%",
                 "Avg prep time within ±10% of target"),
                ("الدقة في تنفيذ الطلب مع مراعاة الطلبات الخاصة (extra hot، سكر، زيادة فوم)",
                 "Order accuracy including customizations (extra hot, sugar, more foam)",
                 "معدل إعادة التحضير < 2%",
                 "Rework rate < 2%"),
            ],
        },
        {
            "name_ar": "التنظيم والنظافة داخل البار",
            "name_en": "Bar Organization & Cleanliness",
            "order": 5,
            "weight": 10.0,
            "items": [
                ("العمل بروح الفريق",
                 "Teamwork",
                 "يساعد الزملاء، يشارك الأدوات، لا خلافات أمام العملاء",
                 "Helps colleagues, shares tools, no friction in front of guests"),
                ("الحفاظ على نظافة وترتيب البار ومنطقة العمل (أثناء وبعد الوردية)",
                 "Keeps bar and work area clean and organized (during and after shift)",
                 "محطة نظيفة بين كل 3 طلبات، closing كامل",
                 "Station clean every 3 orders, full closing complete"),
                ("التأكد من توفر جميع المنتجات المحضّرة مسبقاً (قهوة اليوم، سبانيش، إلخ)",
                 "Ensures all pre-prepped products are available (drip coffee, Spanish, etc.)",
                 "لا نفاد خلال الوردية",
                 "No stock-out during shift"),
            ],
        },
        {
            "name_ar": "التعلم المستمر والتطوير",
            "name_en": "Continuous Learning & Development",
            "order": 6,
            "weight": 10.0,
            "items": [
                ("تطوير المهارات الخاصة بالقهوة (التذوق، الآرت، التبخير)",
                 "Develops coffee-specific skills (cupping, latte art, steaming)",
                 "يتقن على الأقل رسمتين في الـ art",
                 "Masters at least 2 latte-art patterns"),
                ("ابتكار أو اقتراح أفكار جديدة (مشاركة أفكار بنّاءة، العمل بطريقة مبتكرة)",
                 "Innovates or proposes new ideas (constructive input, creative work)",
                 "اقتراح واحد موثق خلال الفترة",
                 "At least 1 documented proposal in period"),
            ],
        },
        {
            "name_ar": "المظهر العام والنظافة الشخصية",
            "name_en": "Appearance & Personal Hygiene",
            "order": 7,
            "weight": 5.0,
            "items": [
                ("الالتزام بالزي الرسمي",
                 "Wears the official uniform",
                 "زي نظيف ومكوي، شارة الاسم",
                 "Uniform clean and pressed, name badge worn"),
                ("النظافة الشخصية",
                 "Personal hygiene",
                 "أظافر مقصوصة، شعر مرتب، لا روائح قوية",
                 "Nails trimmed, hair neat, no strong odors"),
            ],
        },
        {
            "name_ar": "الكاشير",
            "name_en": "Cashier",
            "order": 8,
            "weight": 10.0,
            "items": [
                ("تقفيل الحسابات بدقة",
                 "Closes register accurately",
                 "صندوق متطابق، لا فروقات غير مبررة",
                 "Till matches, no unexplained variances"),
                ("إدخال الطلبات بطريقة صحيحة ومباشرة (مع مراعاة الدفع واسم العميل إن وُجد خصم)",
                 "Enters orders correctly and directly (payment method, customer name if discount)",
                 "أقل من 5 تعديلات فاتورة لكل 100 طلب",
                 "Fewer than 5 bill corrections per 100 orders"),
            ],
        },
    ],
}


BRANCH_MANAGER_TEMPLATE = {
    "role_type": TrainingRoleType.branch_manager,
    "name_ar": "نموذج تقييم مدير الفرع",
    "name_en": "Branch Manager Assessment Form",
    "version": "v1.0",
    "sections": [
        {
            "name_ar": "إدارة العمليات اليومية",
            "name_en": "Daily Operations Management",
            "order": 1,
            "weight": 18.0,
            "items": [
                ("تنظيم جدول الموظفين (توزيع حسب الكفاءة، استلام المفاتيح، عهدة المفاتيح)",
                 "Staff scheduling (skill-based allocation, key handover, key custody)",
                 "تغطية 100% لكل الورديات، سجل عهدة مفاتيح محدّث",
                 "100% shift coverage, up-to-date key custody log"),
                ("التأكد من توفير المواد والأدوات بشكل دائم والمتابعة مع مسؤول المشتريات",
                 "Ensures continuous supply of materials and coordinates with procurement",
                 "لا نفاد لأي منتج تشغيلي خلال الفترة",
                 "No stock-out of any operational item"),
                ("مراقبة النظافة العامة والصيانة (الجلسات الداخلية والخارجية، البار، دورات المياه)",
                 "Oversees cleanliness and maintenance (indoor/outdoor seating, bar, restrooms)",
                 "قوائم فحص يومية موقعة، لا ملاحظات متكررة",
                 "Daily checklists signed, no recurring findings"),
            ],
        },
        {
            "name_ar": "قيادة الفريق وتطوير المهارات",
            "name_en": "Team Leadership & Development",
            "order": 2,
            "weight": 15.0,
            "items": [
                ("التحفيز المستمر وتعزيز روح المبادرة (تحديات يومية بين الشفتات/الموظفين)",
                 "Continuous motivation (daily challenges between shifts/staff)",
                 "نشاط/تحدي موثق على الأقل أسبوعياً",
                 "At least one documented activity/challenge weekly"),
                ("تطوير المهارات (تدريب وتوجيه الموظفين)",
                 "Skills development (training & coaching)",
                 "خطة تدريب شهرية موثقة لكل موظف",
                 "Monthly documented training plan per employee"),
                ("حل المشاكل بين الموظفين وبناء بيئة عمل إيجابية",
                 "Resolves staff conflicts and builds positive work environment",
                 "حل النزاعات خلال 24 ساعة بدون تصعيد",
                 "Conflicts resolved within 24h without escalation"),
            ],
        },
        {
            "name_ar": "إدارة الجودة",
            "name_en": "Quality Management",
            "order": 3,
            "weight": 18.0,
            "items": [
                ("التأكد من تحضير المنتجات حسب المعايير (في جميع الشفتات)",
                 "Ensures product preparation per standards (across all shifts)",
                 "فحص عشوائي كل ساعتين كحد أقصى، توثيق الملاحظات",
                 "Random check max every 2 hours, findings documented"),
                ("مراقبة استلام وتخزين المنتجات حسب المعايير",
                 "Monitors receiving and storage per standards",
                 "FIFO مطبق، تواريخ واضحة، لا انتهاء صلاحية",
                 "FIFO applied, dates visible, no expired items"),
                ("متابعة تواريخ المنتجات بشكل منتظم (قهوة، سيروبات، حليب)",
                 "Regularly tracks product dates (coffee, syrups, milk)",
                 "جدول انتهاء صلاحية محدّث أسبوعياً",
                 "Expiry tracker updated weekly"),
                ("مراقبة جودة أداء الموظفين مع العملاء (التواصل، الزي، التقديم، النظافة)",
                 "Monitors staff customer-facing quality (communication, uniform, service, hygiene)",
                 "تقرير مراقبة أسبوعي لكل موظف",
                 "Weekly observation report per employee"),
            ],
        },
        {
            "name_ar": "خدمة العملاء",
            "name_en": "Customer Service",
            "order": 4,
            "weight": 12.0,
            "items": [
                ("التعامل مع شكاوى واستفسارات العملاء وحلها بطريقة مرضية",
                 "Handles customer complaints/inquiries with satisfying resolution",
                 "100% من الشكاوى مُغلقة خلال 24 ساعة",
                 "100% of complaints closed within 24h"),
                ("تعزيز العلاقة مع العملاء وتحسين التجربة",
                 "Strengthens customer relationships and improves experience",
                 "قاعدة عملاء منتظمين معروفة بالاسم",
                 "Regular customer base known by name"),
                ("أخذ آراء العملاء (التواصل حول تجربتهم وتدوين الملاحظات)",
                 "Collects customer feedback (talks to guests, logs notes)",
                 "على الأقل 10 ملاحظات موثقة شهرياً",
                 "At least 10 documented feedback items monthly"),
            ],
        },
        {
            "name_ar": "الإدارة المالية وضبط التكاليف",
            "name_en": "Financial Management & Cost Control",
            "order": 5,
            "weight": 15.0,
            "items": [
                ("مراقبة المخزون (التحكم بالاستهلاك وطلب المنتجات حسب الحاجة)",
                 "Inventory control (usage control and needs-based ordering)",
                 "نسبة الهدر < 2% من المبيعات",
                 "Waste rate < 2% of sales"),
                ("تسجيل ومراقبة المبيعات اليومية (متوسط الفاتورة، الهدف)",
                 "Records and monitors daily sales (avg check, target)",
                 "تحقيق ≥95% من هدف المبيعات الشهري",
                 "≥95% of monthly sales target achieved"),
            ],
        },
        {
            "name_ar": "التقارير والتواصل الإداري",
            "name_en": "Reporting & Administrative Communication",
            "order": 6,
            "weight": 10.0,
            "items": [
                ("رفع تقارير دورية وأسبوعية (المبيعات، أداء الموظفين، العمليات اليومية، المشاكل والملاحظات)",
                 "Submits periodic/weekly reports (sales, staff performance, operations, issues)",
                 "تقرير أسبوعي مُسلَّم قبل يوم الأحد صباحاً",
                 "Weekly report delivered before Sunday morning"),
                ("رفع تقرير احتياجات البلدية (تجديد الكروت الصحية، رخصة المحل والدفاع المدني، طفايات الحريق، ستارة الهواء، صاعق الحشرات)",
                 "Reports municipality/civil-defense needs (health card renewals, licenses, extinguishers, air curtain, insect killer)",
                 "تقرير شهري موثق، لا وثائق منتهية",
                 "Monthly documented report, no expired documents"),
                ("التواصل الفعّال مع الموظفين والإدارة العليا",
                 "Effective communication with staff and upper management",
                 "استجابة ≤4 ساعات للتواصل الإداري",
                 "≤4h response to management communication"),
            ],
        },
        {
            "name_ar": "البلدية والاشتراطات الرقابية",
            "name_en": "Municipality & Regulatory Compliance",
            "order": 7,
            "weight": 12.0,
            "items": [
                ("مراقبة الكروت الصحية، رخص الدفاع المدني، السجل التجاري، طفايات الحريق، التخزين، تواريخ الانتهاء، أغطية الحاويات والمجاري، الماسك/الكمام/غطاء الشعر/الأظافر",
                 "Monitors health cards, civil-defense permits, trade registry, extinguishers, storage, expiry dates, bin/drain covers, masks/hair-cover/nails",
                 "كل الوثائق سارية، زيارات التفتيش بلا مخالفات",
                 "All documents valid, inspections with zero violations"),
            ],
        },
    ],
}


def seed_training_templates(db: Session):
    print("🔵 Seeding Training Templates (real)...")
    for tmpl_data in [BARISTA_TEMPLATE, BRANCH_MANAGER_TEMPLATE]:
        tmpl = db.query(TrainingTemplate).filter(
            TrainingTemplate.name_ar == tmpl_data["name_ar"],
        ).first()
        if tmpl:
            tmpl.name_en   = tmpl_data["name_en"]
            tmpl.role_type = tmpl_data["role_type"]
            tmpl.version   = tmpl_data["version"]
            tmpl.is_active = True
            print(f"  🔄 Template updated: {tmpl_data['name_ar']}")
        else:
            tmpl = TrainingTemplate(
                role_type=tmpl_data["role_type"],
                name_ar=tmpl_data["name_ar"],
                name_en=tmpl_data["name_en"],
                version=tmpl_data["version"],
                is_active=True,
            )
            db.add(tmpl)
            db.flush()
            print(f"  ✅ Template created: {tmpl_data['name_ar']}")

        for sec_data in tmpl_data["sections"]:
            section = db.query(TrainingTemplateSection).filter(
                TrainingTemplateSection.template_id == tmpl.id,
                TrainingTemplateSection.name_ar == sec_data["name_ar"],
            ).first()
            if section:
                section.name_en = sec_data["name_en"]
                section.order   = sec_data["order"]
                section.weight  = sec_data["weight"]
            else:
                section = TrainingTemplateSection(
                    template_id=tmpl.id,
                    name_ar=sec_data["name_ar"],
                    name_en=sec_data["name_en"],
                    order=sec_data["order"],
                    weight=sec_data["weight"],
                )
                db.add(section)
                db.flush()

            for i, (text_ar, text_en, bench_ar, bench_en) in enumerate(sec_data["items"], start=1):
                item = db.query(TrainingTemplateItem).filter(
                    TrainingTemplateItem.section_id == section.id,
                    TrainingTemplateItem.text_ar == text_ar,
                ).first()
                if item:
                    item.text_en      = text_en
                    item.benchmark_ar = bench_ar
                    item.benchmark_en = bench_en
                    item.order        = i
                    item.is_active    = True
                else:
                    db.add(TrainingTemplateItem(
                        section_id=section.id,
                        text_ar=text_ar,
                        text_en=text_en,
                        benchmark_ar=bench_ar,
                        benchmark_en=bench_en,
                        order=i,
                        is_active=True,
                    ))

    db.commit()
    print("✅ Training templates seeded / refreshed")


NEW_ROLES = [
    (RoleName.quality_visitor, "مفتش جودة", "يقوم بزيارات الجودة الميدانية وتسجيل نتائجها"),
    (RoleName.quality_manager, "مدير الجودة", "يراجع ويعتمد زيارات الجودة ويتابع الإجراءات"),
    (RoleName.trainer, "مدرب", "يجري تقييمات التدريب"),
    (RoleName.area_manager, "مدير المنطقة", "يُقيّم موظفي الفروع ومدراء الفروع التابعين له"),
    (RoleName.sales_manager, "مدير المبيعات والتوصيل", "يحلل بيانات تطبيقات التوصيل والمبيعات ويدير استيراد الفواتير وربط الفروع"),
]


def seed_new_roles(db: Session):
    print("🔵 Seeding new roles (quality_visitor, quality_manager, trainer, area_manager, sales_manager)...")
    for role_name, display, desc in NEW_ROLES:
        existing = db.query(Role).filter(Role.name == role_name).first()
        if existing:
            print(f"  ⏩ Role already exists: {role_name.value}")
            continue
        db.add(Role(name=role_name, display_name=display, description=desc))
        print(f"  ✅ Role created: {role_name.value}")
    db.commit()
    print("✅ New roles seeded")


def main():
    print("=" * 55)
    print("  Quality & Training Module — Seed Data (real ONDA)")
    print("=" * 55)
    create_tables()
    db = SessionLocal()
    try:
        seed_new_roles(db)
        seed_quality_sections(db)
        seed_training_templates(db)
        print("\n🎉 All quality & training seed data loaded successfully!")
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error during seeding: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
