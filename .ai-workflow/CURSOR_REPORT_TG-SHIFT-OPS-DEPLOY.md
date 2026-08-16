# CURSOR_REPORT — TG-SHIFT-OPS-DEPLOY

**Task ID:** TG-SHIFT-OPS-DEPLOY  
**Status:** IMPLEMENTED (المرحلتان ٠ · ١ فقط)  
**Date:** 2026-08-16  
**Executor:** Cursor  
**Production writes in this gate:** **صفر**

---

## نطاق التنفيذ

| مرحلة | من نفّذ | الحالة |
|---|---|---|
| ٠ · فحوصات ما قبل النشر | Cursor | ✅ |
| ١ · تجهيزات الكود | Cursor | ✅ |
| ٢–٥ · دمج / مايجريشن / seed / دخان | **Islam** | ⏸ لم تُنفَّذ |

---

## ٠.١ · `branch_brands` على الإنتاج (قراءة فقط)

```sql
SELECT b.branch_code, b.branch_name, count(bb.brand_id) AS brands
FROM branches b LEFT JOIN branch_brands bb ON bb.branch_id = b.id
GROUP BY b.branch_code, b.branch_name ORDER BY brands, b.branch_code;
```

| branch_code | brands | branch_name |
|---|---:|---|
| BR-DMM-03 | **0** | KITCHEN / DAM |
| BR-RYD-05 | **0** | KITCHEN / RIYADH |
| BR-DMM-04 | 1 | Onda 1 - ARKAN |
| BR-DMM-05 | 1 | Onda 16 - Namjah |
| BR-DMM-06 | 1 | Onda 18 - Al Midra Gym |
| BR-DMM-07 | 1 | Onda 2 - HOQAIL |
| BR-DMM-08 | 1 | Onda 5 - MUOWASAT |
| BR-DMM-09 | 1 | ONDA DAU University |
| BR-DMM-10 | 1 | Pizza 10 - Mazaar |
| BR-DMM-11 | 1 | Pizza 3 - Arkan |
| BR-DMM-12 | 1 | Pizza 7 - Aramco |
| BR-DMM-13 | 1 | Ronaldos DAU University |
| BR-DMM-14 | 1 | SHAWERMA - 4 - ARKAN |
| BR-HSA-01 | 1 | Onda 14 - HASSA |
| BR-KHB-02 | 1 | Pizza 1 - AlKHOBAR |
| BR-KHB-03 | 1 | Pizza 9 - Al Azizia |
| BR-KHB-04 | 1 | SHAWERMA - 1 - Khobar |
| BR-RTN-01 | 1 | Onda 9 - Ras Tanura |
| BR-RTN-02 | 1 | Pizza 15 - Ras Tanura |
| BR-RYD-06 | 1 | Onda 13 - Al Malqa |
| BR-RYD-07 | 1 | Onda 4 - SEFARAT |
| BR-RYD-08 | 1 | Pizza 4 - Riyadh Takhasosy |
| BR-RYD-09 | 1 | Pizza 5 - ALULYA |
| BR-RYD-10 | 1 | Pizza 6 - Riyadh Nada |
| BR-RYD-11 | 1 | SHAWERMA - OLAYA |

**فروع `brands = 0`:** `BR-DMM-03` · `BR-RYD-05` — مطابخ مركزية، **مستثناة عمدًا** في seed (`EXCLUDED_BRANCH_CODES`).

**الـ23 فرع shift-ops:** كلها `brands = 1` — `branch_brands` **ليست** فارغة لRonaldos/Shawarma/Onda. إضافة `brand_shift_count_items` لاحقًا **ستظهر** في الجرد (بعد seed).

---

## ٠.٢ · الحزمة الكاملة

```powershell
python -m pytest tests/ -q --deselect tests/test_epic10_13_unittest.py
```

**الملخّص الأخير (حرفيًا):**
```
= 117 failed, 423 passed, 221 skipped, 22 deselected, 10 warnings in 1404.82s (0:23:24) =
```

| فحص | النتيجة |
|---|---|
| `FAILED tests/test_shift_ops_*` | **صفر** — كل shift-ops خضراء |
| shift-ops في نفس التشغيل | api 4 · gaps **22** · isolation 2 · sequencing 7 · validation 5 = **40 passed** |
| مقارنة بعدد الفشل | **117 failed** — نفس العدد السابق (399→423 passed بسبب +24 اختبار/بيئة؛ ليس فشل shift-ops جديد) |

**لا فشل جديد مُنسوب لـ shift-ops.**

---

## ٠.٣ · بناء الواجهة

```
npm run build → ✓ built in 51.92s
dist/index.html                     0.70 kB │ gzip:   0.46 kB
dist/assets/index-C766ou6y.css     47.95 kB │ gzip:   8.39 kB
dist/assets/index-XaEU1Aa7.js   1,780.51 kB │ gzip: 503.10 kB
```

---

## ٠.٤ · المايجريشن ذهابًا وإيابًا (محلي — PostgreSQL)

```
alembic upgrade head          ✅
alembic downgrade -1          ✅  (a9b8c7d6e5f4 → c1d2e3f4a5b6)
alembic upgrade head          ✅  (c1d2e3f4a5b6 → a9b8c7d6e5f4)
```

**Context impl: PostgresqlImpl** — قاعدة محلية Postgres (ليست SQLite).  
`EXCLUDE USING gist` **يُنشأ فعلًا** على Postgres محليًا وعلى الإنتاج عند تطبيق المرحلة ٣.

---

## ١.١ · `--production` في `seed_shift_ops_config.py`

| شرط | الحالة |
|---|---|
| بدون `--production` → السلوك القديم (رفض Railway) | ✅ |
| `--production` بدون `--expect-branches` → يتوقف | ✅ |
| `--expect-branches` مخالف → يتوقف قبل كتابة | ✅ (اختُبر: 0 ≠ 99) |
| `--production` بدون `--apply` → عرض فقط | ✅ |
| تأكيد `APPLY TO PRODUCTION` عند `--apply` | ✅ مُنفَّذ |
| الرابط من `PROD_DATABASE_URL` فقط | ✅ |
| **لم يُشغَّل على الإنتاج** | ✅ |

---

## ١.٢ · حقول التقرير

في `build_shift_report` أُضيف فقط:
- `count_lines_total`
- `count_lines_filled`

**صفر تعديل** على حقول قائمة.

في `ShiftOpsReportPage.jsx`: عمود `filled/total` — `0/0` يظهر **رمادي + شارة «بلا أصناف»**.

---

## ١.٣ · الاختبار الجديد

```
python -m pytest tests/test_shift_ops_*.py -q
→ 40 passed in 28.48s
```

`test_branch_without_count_items_empty_count_submits` — فرع بلا `brand_shift_count_items`:
- جرد بصفر أسطر → `submit_count` ينجح → `submit_cash` ينجح → `submitted`
- التقرير: `count_lines_total == 0` · `count_lines_filled == 0`

---

## الملفات المُعدَّلة (هذا الجيت)

1. `raed_inventory/backend/seed_shift_ops/seed_shift_ops_config.py`
2. `raed_inventory/backend/app/services/shift_ops_service.py`
3. `raed_inventory/frontend/src/pages/shift_ops/ShiftOpsReportPage.jsx`
4. `raed_inventory/backend/tests/test_shift_ops_gaps.py`
5. `.ai-workflow/CURSOR_REPORT_TG-SHIFT-OPS-DEPLOY.md`

---

## فحوصات الأمان

| فحص | نتيجة |
|---|---|
| كتابة على الإنتاج | **صفر** |
| `git commit` / `push` / `merge` | **لم يُنفَّذ** |
| رابط DB في ملفات | **لم يُكتب** |

---

## الخطوات التالية (Islam — المراحل ٢–٥)

1. `git checkout main && git merge --ff-only feature/shift-ops && git push`
2. تأكيد ظهور مسارات `/shift-ops` في `/openapi.json` الإنتاج
3. `alembic upgrade head` على الإنتاج → **2/2** جداول
4. استبدال `brand_count_items.resolved.csv` → `brand_count_items.csv` (بعد مراجعة Cookies + Cheese strawberry)
5. `seed_shift_ops_config.py --production --expect-branches 23 --apply`
6. دخان: Onda **22/22** + Ronaldos **0/0** مميَّز
