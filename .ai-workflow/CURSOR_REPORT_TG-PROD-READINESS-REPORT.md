# CURSOR_REPORT — TG-PROD-READINESS-REPORT

**Task ID:** TG-PROD-READINESS-REPORT  
**Status:** IMPLEMENTED  
**Date:** 2026-08-16  
**Mode:** قراءة الإنتاج فقط — **صفر عمليات كتابة على الإنتاج**

---

## 1. مصدر الرابط

| خطوة | النتيجة |
|---|---|
| `railway status` | مربوط — مشروع `efficient-harmony`، بيئة `production` |
| `railway link -p efficient-harmony -s Postgres -e production` | نجح |
| `railway variables` → `DATABASE_PUBLIC_URL` | وُجد واستُخدم |
| `$env:PROD_DATABASE_URL` | مضبوط في الجلسة فقط — **لم يُكتب في أي ملف** |

---

## 2. مخرجات `check_production_readiness.py` (كاملة)

```
القاعدة: postgresql://postgres:***@switchback.proxy.rlwy.net:50440/railway
الوضع : قراءة فقط (default_transaction_read_only = on)

الإنتاج يحتوي: 25 فرعًا · 142 صنفًا · 4 براند
جداول shift-ops الموجودة: 0/2 ← المايجريشن لم يُطبَّق بعد

──────────────────────────────────────────────────────────────────
الفروع
──────────────────────────────────────────────────────────────────
موجود: 23 · مفقود: 0
   ✓ كل الأكواد موجودة

──────────────────────────────────────────────────────────────────
أصناف العدّ
──────────────────────────────────────────────────────────────────
   ✗ ONDA      TRH 996g               — غير موجود في الإنتاج
   = ONDA      Costa Rica             → SUPF-ONDA-9AB9F720C0 · Coffee Beans Costa Rica
   = ONDA      Colombian 990g         → SUPF-ONDA-A847D41053 · Coffee Beans Colombian
   = ONDA      Guatemala 990g         → SUPF-ONDA-E9A5871DEF · Coffee Beans Guatemala
   = ONDA      12 oz - paper          → SUPF-ONDA-66EC851308 · 12 oz Cups paper
   = ONDA      12 oz - plastic        → SUPF-ONDA-1C2622CF6A · 12 oz cup plastic
   = ONDA      8 oz                   → SUPF-ONDA-A7097EDBFB · 8 oz Cups
   = ONDA      8 oz - lids            → SUPF-ONDA-2C3AE2DA3B · 8 oz Lid
   = ONDA      6 oz                   → SUPF-ONDA-5A5CD0E442 · 6 oz Cups
   = ONDA      6 oz - lids            → SUPF-ONDA-FA4D760435 · 6 oz Lid
   = ONDA      4 oz                   → SUPF-ONDA-72798D5C93 · 4 oz Cups
   = ONDA      4 oz - lids            → SUPF-ONDA-767ED8D93F · 4 oz Lid
   = ONDA      Lemon cake             → SUPF-ONDA-85C22FCBA4 · LEMON CAKE
   ✗ ONDA      Cookies                — غير موجود في الإنتاج
   = ONDA      Brownies               → SUPF-ONDA-C061A06769 · BROWNIE
   ‼ ONDA      Brownies - zaatar      → SUPF-ONDA-C061A06769 · BROWNIE   (نفس صنف 'Brownies')
   ✗ ONDA      Cheese strawberry      — غير موجود في الإنتاج
   ✗ ONDA      Cheese pecan           — غير موجود في الإنتاج
   = ONDA      Tiramisu               → SUPF-ONDA-F2CD63F1D2 · Tiramisu
   = ONDA      Eclair                 → SUPF-ONDA-842D118DFC · ECLAIR CHOCOLATE
   = ONDA      Cheese croissant       → SUPF-ONDA-020DBB8931 · CHEESE CROISSANT
   ✗ ONDA      Zaatar croissant       — غير موجود في الإنتاج
   = ONDA      Turkey croissant       → SUPF-ONDA-FAE93E0BAB · TURKEY CROISSANT
   ✗ RONALDOS  العجين                 — غير موجود في الإنتاج
   ✗ RONALDOS  الدجاج                 — غير موجود في الإنتاج
   ✗ RONALDOS  شرمب                   — غير موجود في الإنتاج
   ✗ SHAWARMA  سيخ دجاج               — غير موجود في الإنتاج
   ✗ SHAWARMA  سيخ لحم                — غير موجود في الإنتاج

══════════════════════════════════════════════════════════════════
فروع مفقودة      : 0
أصناف مفقودة     : 10
مطابقات تقريبية ≈: 0  ← راجعها بعينك، هذه مصدر الأخطاء
ترسيم مزدوج ‼    : 1

كُتب: brand_count_items.resolved.csv
══════════════════════════════════════════════════════════════════
لم تُكتب أي بيانات في قاعدة الإنتاج.
```

---

## 3. الفروع

**الخلاصة:** 23/23 أكواد مطلوبة **موجودة** في الإنتاج. لا فرع مفقود.

| فرع في ملفنا | الحالة |
|---|---|
| BR-DMM-04 … BR-RYD-11 (23 فرعًا) | ✓ كل الأكواد موجودة |

**فروع إضافية في الإنتاج (ليست في ملف shift-ops):**

| الكود | الاسم | ملاحظة |
|---|---|---|
| BR-DMM-03 | KITCHEN / DAM | مطبخ مركزي — **مستثنى عمدًا** في السكربت |
| BR-RYD-05 | KITCHEN / RIYADH | مطبخ مركزي — **مستثنى عمدًا** |

لا حاجة لتصحيح أكواد بديلة — أسماء الفروع الـ23 تطابق الإنتاج بالكود نفسه.

---

## 4. مراجعة أسطر `≈` · `‼` · `✗`

**أسطر `=` (16):** لم تُراجع — مطابقة تامة.

**أسطر `≈` (0):** لا يوجد.

### ‼ ONDA · Brownies - zaatar

| الحكم | **WRONG → SUPF-ONDA-89CC53B235** |
|---|---|
| المرشّحون | `SUPF-ONDA-C061A06769` BROWNIE · `SUPF-ONDA-89CC53B235` BROWNIE Zatar |
| السبب | صنف الزعتر منفصل في الإنتاج باسم `BROWNIE Zatar` |

### ✗ ONDA · TRH 996g — **MISSING** (لا مرشّح TRH/996)

### ✗ ONDA · Cookies — **WRONG → SUPF-ONDA-82FF7926B8** (CHOCOLATE CHIP COOKIE؛ بديل POS: ONDA-PRD-011)

### ✗ ONDA · Cheese strawberry — **WRONG → SUPF-ONDA-53ED2DA6AA** (Cheesecake berry)

### ✗ ONDA · Cheese pecan — **WRONG → SUPF-ONDA-D933CCC32E** (Cheesecake pekan)

### ✗ ONDA · Zaatar croissant — **WRONG → SUPF-ONDA-5EAD74E079** (ZAATER CROISSANT)

### ✗ RONALDOS · العجين — **MISSING**

### ✗ RONALDOS · الدجاج — **MISSING**

### ✗ RONALDOS · شرمب — **MISSING**

### ✗ SHAWARMA · سيخ دجاج — **MISSING**

### ✗ SHAWARMA · سيخ لحم — **MISSING**

---

## 5. سؤال جداول shift-ops

> **هل جداول shift-ops موجودة على الإنتاج؟**

**لا — 0/2.** المايجريشن لم يُطبَّق. التجهيز **محجوب** حتى يقرر المالك تطبيق المايجريشن ثم إنشاء الأصناف الـ6 الناقصة أو تعديل قائمة العدّ.

---

## 6. ملخص

| المقياس | القيمة |
|---|---|
| فروع الإنتاج | 25 |
| أصناف | 142 (كل `item_brands` → Onda فقط) |
| جداول shift-ops | **0/2** |
| فروع shift-ops | **23/23** |
| أصناف عدّ بعد المراجعة | **21/28** مربوطة · **6 MISSING** |

---

## 7. الملفات

- `seed_shift_ops/brand_count_items.resolved.csv` — مكتوب ومُراجع
- هذا التقرير

**صفر عمليات كتابة على الإنتاج.**
