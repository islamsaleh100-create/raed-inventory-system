#!/usr/bin/env python3
"""تقرير جاهزية على قاعدة الإنتاج — **قراءة فقط، بلا أي كتابة**.

يجيب على السؤالين الوحيدين اللذين لا نعرف إجابتهما فعلًا:
  1. هل أكواد الفروع الـ23 موجودة في الإنتاج؟
  2. أي من أصناف العدّ الـ28 موجود في الإنتاج، وبأي كود بالضبط؟

لماذا سكربت منفصل عن `seed_shift_ops_config.py`:
  ذاك السكربت **يكتب**، وحارسه يرفض أي رابط Railway — وهذا حارس صحيح يجب أن يبقى.
  فتحُ ثغرة فيه ليقرأ الإنتاج يفسد الحارس. الفصل يبقي الكاتب ممنوعًا من الإنتاج،
  والقارئ عاجزًا عن الكتابة أصلًا.

ضمانات عدم الكتابة — ثلاث طبقات، لا واحدة:
  - لا يقرأ `.env` إطلاقًا. الرابط يُمرَّر صراحةً، فلا اتصال بالمصادفة.
  - `default_transaction_read_only = on` — **بوستجرس نفسه** يرفض أي كتابة.
  - كل جملة SQL هنا SELECT، ولا commit في الملف كله.

الاستخدام (PowerShell):
    $env:PROD_DATABASE_URL = "postgresql://...:...@...proxy.rlwy.net:PORT/railway"
    python check_production_readiness.py
"""
from __future__ import annotations

import csv
import io
import os
import re
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

HERE = Path(__file__).resolve().parent
EXCLUDED_BRANCH_CODES = {"BR-RYD-05", "BR-DMM-03"}


def fail(msg: str) -> None:
    print(f"\n✗ {msg}\n", file=sys.stderr)
    sys.exit(1)


def _mask(url: str) -> str:
    return re.sub(r"://([^:/@]+):[^@]*@", r"://\1:***@", url or "")


def _norm(text_: str) -> str:
    return re.sub(r"[^0-9a-z؀-ۿ]+", "", (text_ or "").lower())


def read_csv(name: str) -> list[dict]:
    path = HERE / name
    if not path.exists():
        fail(f"ملف مفقود: {path}")
    with io.open(path, encoding="utf-8-sig", newline="") as fh:
        return [r for r in csv.DictReader(fh) if any((v or "").strip() for v in r.values())]


def main() -> None:
    url = (os.environ.get("PROD_DATABASE_URL") or "").strip()
    if not url:
        fail("PROD_DATABASE_URL غير مضبوط.\n"
             '  $env:PROD_DATABASE_URL = "postgresql://..."')
    if not url.lower().startswith("postgres"):
        fail(f"الرابط ليس بوستجرس: {_mask(url)}")

    print(f"القاعدة: {_mask(url)}")
    print("الوضع : قراءة فقط (default_transaction_read_only = on)\n")

    engine = create_engine(url, pool_pre_ping=True)
    with engine.connect() as conn:
        # بوستجرس يرفض أي كتابة بعد هذا السطر، حتى لو أخطأ الكود لاحقًا.
        conn.execute(text("SET default_transaction_read_only = on"))

        branches = {
            r[0]: r[1] for r in
            conn.execute(text("SELECT branch_code, branch_name FROM branches")).all()
        }
        items = conn.execute(text(
            "SELECT item_code, item_name_en, item_name_ar FROM items "
            "WHERE is_deleted = false"
        )).all()

        has_shift_tables = conn.execute(text(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_name IN ('branch_shift_configs','brand_shift_count_items')"
        )).scalar()

        brands = [r[0] for r in conn.execute(text("SELECT name FROM brands")).all()]

    print(f"الإنتاج يحتوي: {len(branches)} فرعًا · {len(items)} صنفًا · {len(brands)} براند")
    print(f"جداول shift-ops الموجودة: {has_shift_tables}/2 "
          f"{'✓ المايجريشن مطبَّق' if has_shift_tables == 2 else '← المايجريشن لم يُطبَّق بعد'}\n")

    # ── الفروع ────────────────────────────────────────────────────────────
    print("─" * 66)
    print("الفروع")
    print("─" * 66)
    missing_branches, found_branches = [], []
    for row in read_csv("branch_shift_configs.csv"):
        code = (row.get("branch_code") or "").strip()
        if not code or code in EXCLUDED_BRANCH_CODES:
            continue
        if code in branches:
            found_branches.append(code)
        else:
            missing_branches.append((code, row.get("branch_name") or ""))

    print(f"موجود: {len(found_branches)} · مفقود: {len(missing_branches)}")
    for code, name in missing_branches:
        print(f"   ✗ {code:12} {name}")
    if not missing_branches:
        print("   ✓ كل الأكواد موجودة")

    # الأكواد الموجودة في الإنتاج ولم نطلبها — قد تكون فروعًا نسيناها
    extra = sorted(set(branches) - set(found_branches) - EXCLUDED_BRANCH_CODES)
    if extra:
        print(f"\nفروع في الإنتاج ليست في ملفنا ({len(extra)}) — راجعها:")
        for code in extra:
            print(f"   ? {code:12} {branches[code]}")

    # ── الأصناف ───────────────────────────────────────────────────────────
    print("\n" + "─" * 66)
    print("أصناف العدّ")
    print("─" * 66)

    pool = [(c, en, ar, _norm(en), _norm(ar), _norm(c)) for c, en, ar in items]

    def find(row: dict):
        cands = [(row.get("item_name") or "").strip()]
        cands += [a.strip() for a in (row.get("name_aliases") or "").split("|") if a.strip()]
        wanted = {_norm(c) for c in cands if c}
        if not wanted:
            return None, None
        for exact in (True, False):
            for code, en, ar, nen, nar, ncode in pool:
                for n in (nen, nar, ncode):
                    if not n:
                        continue
                    if exact and n in wanted:
                        return (code, en or ar), "exact"
                    if not exact and any(
                        w and (w in n or n in w) and abs(len(w) - len(n)) <= 6 for w in wanted
                    ):
                        return (code, en or ar), "fuzzy"
        return None, None

    rows_out, mapped, missing_items, fuzzy_count, dup = [], {}, [], 0, []
    for row in read_csv("brand_count_items.csv"):
        brand = (row.get("brand") or "").strip()
        wanted = (row.get("item_name") or "").strip()
        if not brand or not wanted:
            continue
        hit, how = find(row)
        if not hit:
            missing_items.append((brand, wanted))
            print(f"   ✗ {brand:9} {wanted:22} — غير موجود في الإنتاج")
            rows_out.append({**row, "item_code": ""})
            continue
        code, name = hit
        key = (brand, code)
        if key in mapped:
            dup.append((brand, mapped[key], wanted, code))
            print(f"   ‼ {brand:9} {wanted:22} → {code} · {name}"
                  f"   (نفس صنف {mapped[key]!r})")
            rows_out.append({**row, "item_code": ""})
            continue
        mapped[key] = wanted
        if how == "fuzzy":
            fuzzy_count += 1
        mark = "=" if how == "exact" else "≈"
        print(f"   {mark} {brand:9} {wanted:22} → {code} · {name}")
        rows_out.append({**row, "item_code": code})

    out = HERE / "brand_count_items.resolved.csv"
    with io.open(out, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows_out[0].keys()))
        w.writeheader()
        w.writerows(rows_out)

    # ── الخلاصة ───────────────────────────────────────────────────────────
    print("\n" + "═" * 66)
    print(f"فروع مفقودة      : {len(missing_branches)}")
    print(f"أصناف مفقودة     : {len(missing_items)}")
    print(f"مطابقات تقريبية ≈: {fuzzy_count}  ← راجعها بعينك، هذه مصدر الأخطاء")
    print(f"ترسيم مزدوج ‼    : {len(dup)}")
    print(f"\nكُتب: {out.name}")
    print("  فيه عمود item_code مملوءًا بالأكواد الحقيقية. بعد مراجعة أسطر ≈ يدويًا،")
    print("  سمِّه brand_count_items.csv — عندها تصير المطابقة بالكود، وتختفي فئة الخطأ كلها.")
    print("═" * 66)
    print("لم تُكتب أي بيانات في قاعدة الإنتاج.")


if __name__ == "__main__":
    main()
