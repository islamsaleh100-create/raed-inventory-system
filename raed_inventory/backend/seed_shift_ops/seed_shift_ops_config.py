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
import sys
from datetime import date
from pathlib import Path

# المطبخان مسجّلان في جدول branches لكنهما ليسا فرعين تشغيليين.
# فتح شفت لأيٍّ منهما يعطي قائمة عدّ فارغة لأنه بلا براند.
EXCLUDED_BRANCH_CODES = {"BR-RYD-05", "BR-DMM-03"}

HERE = Path(__file__).resolve().parent


def fail(msg: str) -> None:
    print(f"\n✗ {msg}\n", file=sys.stderr)
    sys.exit(1)


def guard_environment() -> None:
    env = (os.environ.get("ENVIRONMENT") or "").strip().lower()
    if env not in ("local", "dev", "development", "test"):
        fail(
            f"ENVIRONMENT = {env!r} — هذا السكربت لا يعمل إلا على بيئة تطوير.\n"
            "  لا يُشغَّل على الإنتاج. اضبط ENVIRONMENT=local وأعد المحاولة."
        )
    url = (os.environ.get("DATABASE_URL") or "")
    for marker in ("railway", "rlwy.net", "proxy.rlwy"):
        if marker in url.lower():
            fail("DATABASE_URL يشير إلى Railway. متوقف.")


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


def _find_item(db, Item, item_code: str, row: dict):
    """يبحث بالكود إن وُجد، وإلا بالاسم ثم بالمرادفات.

    السبب: ملف تصنيف الأصناف لا يحتوي عمود كود إطلاقًا، فطلب الأكواد من المالك
    كان طلبًا لشيء غير موجود. البحث بالاسم يجعل السكربت يكتشفها بنفسه ويبلّغ عمّا
    لم يجده، بدل أن يتوقف.
    """
    if item_code:
        found = db.query(Item).filter(Item.item_code == item_code).first()
        if found:
            return found

    candidates = [(row.get("item_name") or "").strip()]
    candidates += [a.strip() for a in (row.get("name_aliases") or "").split("|") if a.strip()]
    wanted = {_norm(c) for c in candidates if c}
    if not wanted:
        return None

    # مطابقة تامة بعد التطبيع أولًا، ثم احتواء — الترتيب يمنع أن يبتلع اسم قصير اسمًا أطول
    pool = db.query(Item).filter(Item.is_deleted == False).all()  # noqa: E712
    for exact in (True, False):
        for it in pool:
            for field in (it.item_name_en, it.item_name_ar, it.item_code):
                n = _norm(field)
                if not n:
                    continue
                if exact and n in wanted:
                    return it
                if not exact and any(w and (w in n or n in w) and abs(len(w) - len(n)) <= 6 for w in wanted):
                    return it
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="اكتب فعليًا (الافتراضي عرض فقط)")
    ap.add_argument("--from", dest="effective_from", default=None,
                    help="تاريخ سريان الإعدادات YYYY-MM-DD (الافتراضي: اليوم)")
    args = ap.parse_args()

    guard_environment()

    from app.database import SessionLocal            # noqa: E402
    from app.models import Branch, Brand, Item       # noqa: E402
    from app.models.branch_shift_ops import (        # noqa: E402
        BranchShiftConfig, BrandShiftCountItem,
    )

    eff_from = date.fromisoformat(args.effective_from) if args.effective_from else date.today()
    db = SessionLocal()
    created_cfg = created_items = 0
    problems: list[str] = []

    try:
        # ── 1. إعدادات الشفتات ────────────────────────────────────────────
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
                    continue  # موجود — لا نلمسه، تجنّبًا لتداخل الفترات
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

        # ── 2. أصناف العد لكل براند ───────────────────────────────────────
        items_csv = HERE / "brand_count_items.csv"
        if items_csv.exists():
            for idx, row in enumerate(read_csv("brand_count_items.csv"), start=1):
                brand_name = (row.get("brand") or "").strip()
                item_code = (row.get("item_code") or "").strip()
                if not brand_name or not (item_code or (row.get("item_name") or "").strip()):
                    continue

                brand = db.query(Brand).filter(Brand.name == brand_name).first()
                if not brand:
                    problems.append(f"براند غير موجود: {brand_name!r}")
                    continue
                item = _find_item(db, Item, item_code, row)
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
                print(f"  + صنف عدّ: {brand_name} · {item_code} · ترتيب {order}")
                created_items += 1
                if args.apply:
                    db.add(BrandShiftCountItem(
                        brand_id=brand.id, item_id=item.id,
                        display_order=order, is_active=True,
                    ))
        else:
            print("  (brand_count_items.csv غير موجود — تخطّي أصناف العد)")

        if args.apply:
            db.commit()
    finally:
        db.close()

    print("\n" + "─" * 62)
    print(f"إعدادات شفتات {'أُنشئت' if args.apply else 'ستُنشأ'}: {created_cfg}")
    print(f"أصناف عدّ    {'أُنشئت' if args.apply else 'ستُنشأ'}: {created_items}")
    print(f"المطبخان المستثنيان: {', '.join(sorted(EXCLUDED_BRANCH_CODES))}")

    if problems:
        print(f"\n⚠️  {len(problems)} مشكلة — لم يُنشأ لها شيء:")
        for p in problems:
            print(f"   - {p}")

    if not args.apply:
        print("\nعرض فقط. للتنفيذ الفعلي أضف --apply")
    print("─" * 62)


if __name__ == "__main__":
    main()
