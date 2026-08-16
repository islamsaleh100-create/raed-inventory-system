#!/usr/bin/env python3
"""يصدّر أصناف الإنتاج إلى CSV ليراجعها المالك بعينه — قراءة فقط.

سبب وجوده: المراجعة المتبقّية سطران في `brand_count_items.resolved.csv`
(`Cookies` و`Cheese strawberry`) اختِيرا من بين مرشّحين. السؤال المجرّد
«كم نوع كوكيز لدى Onda؟» صعب. القائمة أمامك تجعله سؤال اختيار لا استرجاع.

يُنتج ملفين:
  prod_items_all.csv        كل الأصناف — للمراجعة الشاملة إن أردت
  prod_items_review.csv     المرشّحون للسطرين محلّ الخلاف فقط

قراءة فقط: لا يقرأ .env · default_transaction_read_only = on · SELECT بلا commit.

    $env:PROD_DATABASE_URL = "postgresql://..."
    python export_prod_items.py
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

# كلمات السطرين محلّ المراجعة، وما يجاورهما لغويًا حتى لا نُخفي بديلًا وارِدًا
REVIEW_PATTERNS = ["cookie", "كوكي", "cheese", "شيز", "cake", "كيك",
                   "berry", "توت", "strawberry", "فراولة", "pecan", "pekan", "بيكان"]


def main() -> None:
    url = (os.environ.get("PROD_DATABASE_URL") or "").strip()
    if not url or url.startswith("<"):
        print('\n✗ PROD_DATABASE_URL غير مضبوط بقيمة حقيقية.\n'
              '  الصق الرابط كاملًا بلا أقواس مدبَّبة.\n', file=sys.stderr)
        sys.exit(1)

    print(f"القاعدة: {re.sub(r'://([^:/@]+):[^@]*@', '://REDACTED@', url)}")
    print("الوضع : قراءة فقط\n")

    engine = create_engine(url, pool_pre_ping=True)
    with engine.connect() as conn:
        conn.execute(text("SET default_transaction_read_only = on"))
        rows = conn.execute(text("""
            SELECT item_code, item_name_en, item_name_ar, active
            FROM items
            WHERE is_deleted = false
            ORDER BY item_code
        """)).all()

    def write(path: Path, data) -> None:
        with io.open(path, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["item_code", "item_name_en", "item_name_ar", "active"])
            w.writerows(data)

    write(HERE / "prod_items_all.csv", rows)

    def matches(r) -> bool:
        blob = f"{r[1] or ''} {r[2] or ''}".lower()
        return any(p in blob for p in REVIEW_PATTERNS)

    review = [r for r in rows if matches(r)]
    write(HERE / "prod_items_review.csv", review)

    print(f"إجمالي الأصناف        : {len(rows)}")
    print(f"مرشّحو المراجعة       : {len(review)}")
    print(f"\nكُتب: prod_items_all.csv · prod_items_review.csv\n")

    print("─" * 70)
    print("المرشّحون — راجعهم بعينك:")
    print("─" * 70)
    for code, en, ar, active in review:
        flag = "" if active else "  (غير مفعّل)"
        print(f"  {code:26} {(en or ar or '')[:40]}{flag}")
    print("─" * 70)
    print("لم تُكتب أي بيانات في قاعدة الإنتاج.")


if __name__ == "__main__":
    main()
