#!/usr/bin/env python3
"""يجهّز بيانات تشغيل عمليات الشفت من ملفَي CSV.

  branch_shift_configs.csv   عدد الشفتات لكل فرع
  brand_count_items.csv      أصناف العد لكل براند

الخصائص المقصودة:
  - **يرفض العمل على الإنتاج.** يتوقف إذا كان ENVIRONMENT ليس local/dev/test.
  - **آمن للتكرار.** إعادة التشغيل لا تُنشئ صفوفًا مكرّرة ولا تعدّل الموجود.
  - **يستثني المطبخين صراحةً** (BR-RYD-05, BR-DMM-03) — ليسا فرعين ولا براند لهما.
  - **يبلّغ ولا يخمّن.** أي فرع أو صنف غير موجود يُطبع ولا يُنشأ.
  - `--dry-run` افتراضيًا. لا يكتب شيئًا إلا مع `--apply`.

الاستخدام:
    python seed_shift_ops_config.py                 # عرض ما سيحدث
    python seed_shift_ops_config.py --apply         # التنفيذ الفعلي
    python seed_shift_ops_config.py --apply --from 2026-09-01
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import re
import sys
from datetime import date
from pathlib import Path

# المطبخان مسجّلان في جدول branches لكنهما ليسا فرعين تشغيليين.
# فتح شفت لأيٍّ منهما يعطي قائمة عدّ فارغة لأنه بلا براند.
EXCLUDED_BRANCH_CODES = {"BR-RYD-05", "BR-DMM-03"}

HERE = Path(__file__).resolve().parent

# السكربت داخل مجلد فرعي، وبايثون يضيف مجلد السكربت لا مجلد العمل إلى sys.path،
# فاستيراد `app` يفشل بـModuleNotFoundError. نضيف جذر الباك إند صراحةً.
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))

# مجلد العمل يحدّد قاعدة البيانات، لا مجلد السكربت:
#   - pydantic-settings يقرأ `.env` **نسبةً إلى مجلد العمل**، فتشغيل السكربت من داخل
#     مجلده يجعل `.env` غير مرئي، فيسقط الإعداد على الافتراضي `sqlite:///./...`.
#   - وهذا المسار النسبي بدوره يُنشئ ملف SQLite **فارغًا** في مجلد العمل.
# النتيجة: السكربت يتصل بقاعدة فارغة بلا أي إنذار. نثبّت مجلد العمل على جذر الباك إند
# قبل أي استيراد لـ`app`، فتصير القاعدة واحدة مهما كان مكان التشغيل.
os.chdir(HERE.parent)


def _mask(url: str) -> str:
    """يخفي كلمة المرور قبل الطباعة."""
    return re.sub(r"://([^:/@]+):[^@]*@", r"://\1:***@", url or "")


def fail(msg: str) -> None:
    print(f"\n✗ {msg}\n", file=sys.stderr)
    sys.exit(1)


def guard_environment():
    """يفحص القيم **الفعّالة** التي سيستخدمها التطبيق، لا متغيّرات النظام.

    النسخة الأولى كانت تقرأ `os.environ` مباشرةً، والتطبيق يقرأ `.env` عبر
    pydantic-settings. المصدران يختلفان في الاتجاهين:
      - `.env` فيه ENVIRONMENT=local والنظام فاضي  ⇒ حارس يمنع تشغيلًا سليمًا.
      - النظام فيه ENVIRONMENT=local و`.env` يشير للإنتاج ⇒ **حارس يسمح بالكتابة على
        الإنتاج**. وهذا هو الاتجاه الخطير: فحص Railway كان يقرأ `os.environ` أيضًا،
        فرابط Railway مكتوب في `.env` كان يمرّ من تحته بلا أي اعتراض.
    `settings` تدمج الاثنين بالأولوية الصحيحة (متغيّر النظام يغلب `.env`)، فهي
    المصدر الوحيد الذي يطابق ما سيتصل به التطبيق فعلًا.
    """
    from app.config import settings  # noqa: E402  — بعد os.chdir، فيُقرأ `.env` الصحيح

    env = (settings.ENVIRONMENT or "").strip().lower()
    if env not in ("local", "dev", "development", "test"):
        fail(
            f"ENVIRONMENT = {env!r} — هذا السكربت لا يعمل إلا على بيئة تطوير.\n"
            "  لا يُشغَّل على الإنتاج. اضبط ENVIRONMENT=local في .env وأعد المحاولة."
        )

    url = (settings.DATABASE_URL or "")
    for marker in ("railway", "rlwy.net", "proxy.rlwy", "amazonaws.com"):
        if marker in url.lower():
            fail(f"DATABASE_URL يشير إلى قاعدة مستضافة ({marker}). متوقف.\n"
                 f"  القيمة الفعّالة: {_mask(url)}")
    return settings


def read_csv(name: str) -> list[dict]:
    path = HERE / name
    if not path.exists():
        fail(f"ملف مفقود: {path}")
    with io.open(path, encoding="utf-8-sig", newline="") as fh:
        return [r for r in csv.DictReader(fh) if any((v or "").strip() for v in r.values())]


def _norm(text: str) -> str:
    """تطبيع للمقارنة: حروف وأرقام فقط، بلا مسافات ولا رموز، حالة موحّدة."""
    import re
    return re.sub(r"[^0-9a-z\u0600-\u06ff]+", "", (text or "").lower())


def _find_brand(db, Brand, name: str):
    """مطابقة البراند بلا حساسية لحالة الأحرف أو المسافات.

    ملفات التجهيز تكتب ONDA بحروف كبيرة، وقاعدة البيانات قد تحمل "Onda".
    المطابقة الحرفية كانت تفشل على 28 صفًا لهذا السبب وحده.
    """
    target = _norm(name)
    for b in db.query(Brand).all():
        if _norm(b.name) == target:
            return b
    return None


def _find_item(db, Item, item_code: str, row: dict):
    """يبحث بالكود إن وُجد، وإلا بالاسم ثم بالمرادفات.

    السبب: ملف تصنيف الأصناف لا يحتوي عمود كود إطلاقًا، فطلب الأكواد من المالك
    كان طلبًا لشيء غير موجود. البحث بالاسم يجعل السكربت يكتشفها بنفسه ويبلّغ عمّا
    لم يجده، بدل أن يتوقف.
    """
    if item_code:
        found = db.query(Item).filter(Item.item_code == item_code).first()
        if found:
            return found, "code"

    candidates = [(row.get("item_name") or "").strip()]
    candidates += [a.strip() for a in (row.get("name_aliases") or "").split("|") if a.strip()]
    wanted = {_norm(c) for c in candidates if c}
    if not wanted:
        return None, None

    # مطابقة تامة بعد التطبيع أولًا، ثم احتواء — الترتيب يمنع أن يبتلع اسم قصير اسمًا أطول
    pool = db.query(Item).filter(Item.is_deleted == False).all()  # noqa: E712
    for exact in (True, False):
        for it in pool:
            for field in (it.item_name_en, it.item_name_ar, it.item_code):
                n = _norm(field)
                if not n:
                    continue
                if exact and n in wanted:
                    return it, "exact"
                if not exact and any(w and (w in n or n in w) and abs(len(w) - len(n)) <= 6 for w in wanted):
                    return it, "fuzzy"
    return None, None


def _count_matching_branches(db, Branch) -> int:
    """عدد صفوف branch_shift_configs.csv التي لها فرع فعلي (بعد استثناء المطبخين)."""
    n = 0
    for row in read_csv("branch_shift_configs.csv"):
        code = (row.get("branch_code") or "").strip()
        if not code or code in EXCLUDED_BRANCH_CODES:
            continue
        if db.query(Branch).filter(Branch.branch_code == code).first():
            n += 1
    return n


def _confirm_production_apply() -> None:
    print("\n⚠️  وضع الإنتاج — للتنفيذ الفعلي اكتب بالضبط: APPLY TO PRODUCTION")
    typed = input("> ").strip()
    if typed != "APPLY TO PRODUCTION":
        fail("التأكيد المكتوب لم يطابق — لم تُكتب أي بيانات.")


def execute_seed(db, Branch, Brand, Item, BranchShiftConfig, BrandShiftCountItem, args, eff_from):
    """منطق التجهيز — يُرجع (created_cfg, created_items, problems)."""
    created_cfg = created_items = 0
    problems: list[str] = []
    mapped: dict[tuple[int, int], str] = {}

    for row in read_csv("branch_shift_configs.csv"):
        code = (row.get("branch_code") or "").strip()
        if not code or code in EXCLUDED_BRANCH_CODES:
            continue

        branch = db.query(Branch).filter(Branch.branch_code == code).first()
        if not branch:
            problems.append(f"فرع غير موجود في قاعدة البيانات: {code} ({row.get('branch_name')})")
            continue

        try:
            shifts = int((row.get("shifts_per_day") or "1").strip())
        except ValueError:
            problems.append(f"{code}: shifts_per_day ليس رقمًا — {row.get('shifts_per_day')!r}")
            continue
        if shifts not in (1, 2):
            problems.append(f"{code}: shifts_per_day = {shifts} — المسموح 1 أو 2 فقط")
            continue

        for n in range(1, shifts + 1):
            exists = (
                db.query(BranchShiftConfig)
                .filter(
                    BranchShiftConfig.branch_id == branch.id,
                    BranchShiftConfig.shift_number == n,
                )
                .first()
            )
            if exists:
                continue
            print(f"  + إعداد شفت: {code} · شفت {n} · من {eff_from}")
            created_cfg += 1
            if args.apply:
                db.add(BranchShiftConfig(
                    branch_id=branch.id,
                    shift_number=n,
                    shift_name_ar=f"الشفت {n}",
                    is_active=True,
                    effective_from=eff_from,
                    effective_to=None,
                ))

    items_csv = HERE / "brand_count_items.csv"
    if items_csv.exists():
        for idx, row in enumerate(read_csv("brand_count_items.csv"), start=1):
            brand_name = (row.get("brand") or "").strip()
            item_code = (row.get("item_code") or "").strip()
            if not brand_name or not (item_code or (row.get("item_name") or "").strip()):
                continue

            brand = _find_brand(db, Brand, brand_name)
            if not brand:
                available = ", ".join(sorted(b.name for b in db.query(Brand).all())) or "(لا توجد براندات)"
                problems.append(
                    f"براند غير موجود: {brand_name!r} — الموجود فعلًا: {available}"
                )
                continue
            item, how = _find_item(db, Item, item_code, row)
            if not item:
                label = item_code or (row.get("item_name") or "").strip()
                problems.append(f"صنف غير موجود: {label!r} (براند {brand_name})")
                continue

            exists = (
                db.query(BrandShiftCountItem)
                .filter(
                    BrandShiftCountItem.brand_id == brand.id,
                    BrandShiftCountItem.item_id == item.id,
                )
                .first()
            )
            if exists:
                continue
            order = int((row.get("display_order") or idx))
            wanted = (row.get("item_name") or item_code or "").strip()
            resolved = f"{item.item_code} · {item.item_name_en or item.item_name_ar}"

            prev = mapped.get((brand.id, item.id))
            if prev:
                problems.append(
                    f"ترسيم مزدوج (براند {brand_name}): {prev!r} و {wanted!r} "
                    f"كلاهما → {resolved}. صحّح الاسم في brand_count_items.csv "
                    f"أو أنشئ الصنف الناقص في القاعدة."
                )
                continue
            mapped[(brand.id, item.id)] = wanted

            mark = {"code": "=", "exact": "=", "fuzzy": "≈"}.get(how, "?")
            print(f"  {mark} صنف عدّ: {brand_name:9} {wanted:22} → {resolved}")
            created_items += 1
            if args.apply:
                db.add(BrandShiftCountItem(
                    brand_id=brand.id, item_id=item.id,
                    display_order=order, is_active=True,
                ))
    else:
        print("  (brand_count_items.csv غير موجود — تخطّي أصناف العد)")

    return created_cfg, created_items, problems


def _print_summary(created_cfg, created_items, problems, args, *, production: bool = False):
    print("\n" + "─" * 62)
    print(f"إعدادات شفتات {'أُنشئت' if args.apply else 'ستُنشأ'}: {created_cfg}")
    print(f"أصناف عدّ    {'أُنشئت' if args.apply else 'ستُنشأ'}: {created_items}")
    print(f"المطبخان المستثنيان: {', '.join(sorted(EXCLUDED_BRANCH_CODES))}")
    print("العلامات: (=) مطابقة تامة · (≈) مطابقة تقريبية — راجع أسطر ≈ بعينك")

    if problems:
        print(f"\n⚠️  {len(problems)} مشكلة — لم يُنشأ لها شيء:")
        for p in problems:
            print(f"   - {p}")

    if not args.apply:
        if production:
            print("\nعرض فقط (وضع الإنتاج). للتنفيذ: --apply + تأكيد APPLY TO PRODUCTION")
        else:
            print("\nعرض فقط. للتنفيذ الفعلي أضف --apply")
    print("─" * 62)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="اكتب فعليًا (الافتراضي عرض فقط)")
    ap.add_argument("--from", dest="effective_from", default=None,
                    help="تاريخ سريان الإعدادات YYYY-MM-DD (الافتراضي: اليوم)")
    ap.add_argument("--production", action="store_true",
                    help="اتصل بـ PROD_DATABASE_URL (لا يقرأ .env). يتطلب --expect-branches")
    ap.add_argument("--expect-branches", type=int, default=None,
                    help="عدد الفروع المتوقع — إلزامي مع --production")
    args = ap.parse_args()

    if args.production and args.expect_branches is None:
        fail("--production يتطلب --expect-branches N")

    eff_from = date.fromisoformat(args.effective_from) if args.effective_from else date.today()

    from app.models import Branch, Brand, Item       # noqa: E402
    from app.models.branch_shift_ops import (        # noqa: E402
        BranchShiftConfig, BrandShiftCountItem,
    )

    if args.production:
        prod_url = (os.environ.get("PROD_DATABASE_URL") or "").strip()
        if not prod_url:
            fail("PROD_DATABASE_URL غير مضبوط.\n"
                 '  $env:PROD_DATABASE_URL = "postgresql://..."')
        if not prod_url.lower().startswith("postgres"):
            fail(f"PROD_DATABASE_URL ليس بوستجرس: {_mask(prod_url)}")

        from sqlalchemy import create_engine, inspect as _sa_inspect  # noqa: E402
        from sqlalchemy.orm import sessionmaker  # noqa: E402

        print(f"وضع الإنتاج — قراءة/كتابة عبر PROD_DATABASE_URL فقط")
        print(f"القاعدة: {_mask(prod_url)}")

        engine = create_engine(prod_url, pool_pre_ping=True)
        if not _sa_inspect(engine).has_table("branches"):
            fail("جدول `branches` غير موجود — تحقق من PROD_DATABASE_URL")

        Session = sessionmaker(bind=engine)
        db = Session()
        try:
            branch_count = _count_matching_branches(db, Branch)
            print(f"فروع مطابقة في CSV: {branch_count} (المتوقع: {args.expect_branches})")
            if branch_count != args.expect_branches:
                fail(
                    f"عدد الفروع {branch_count} ≠ --expect-branches {args.expect_branches} — "
                    "متوقف قبل أي كتابة (حماية من قاعدة خاطئة)."
                )

            preview = argparse.Namespace(apply=False, effective_from=args.effective_from)
            created_cfg, created_items, problems = execute_seed(
                db, Branch, Brand, Item, BranchShiftConfig, BrandShiftCountItem, preview, eff_from,
            )
            _print_summary(created_cfg, created_items, problems, preview, production=True)

            if args.apply:
                _confirm_production_apply()
                db.rollback()
                created_cfg, created_items, problems = execute_seed(
                    db, Branch, Brand, Item, BranchShiftConfig, BrandShiftCountItem, args, eff_from,
                )
                try:
                    db.commit()
                except Exception:
                    db.rollback()
                    raise
                print("\n✓ تم التنفيذ على الإنتاج.")
        finally:
            db.close()
        return

    settings = guard_environment()

    from app.database import SessionLocal, engine     # noqa: E402
    from sqlalchemy import inspect as _sa_inspect     # noqa: E402

    print(f"قاعدة البيانات: {_mask(settings.DATABASE_URL)}")
    print(f"مجلد العمل   : {os.getcwd()}")
    if not _sa_inspect(engine).has_table("branches"):
        fail(
            "جدول `branches` غير موجود في هذه القاعدة — أنت متصل بقاعدة فارغة أو خاطئة.\n"
            "  شغّل `alembic upgrade head` من جذر الباك إند، وتأكد أن `.env` فيه DATABASE_URL الصحيح."
        )

    db = SessionLocal()
    try:
        created_cfg, created_items, problems = execute_seed(
            db, Branch, Brand, Item, BranchShiftConfig, BrandShiftCountItem, args, eff_from,
        )
        if args.apply:
            db.commit()
        _print_summary(created_cfg, created_items, problems, args)
    finally:
        db.close()


if __name__ == "__main__":
    main()
