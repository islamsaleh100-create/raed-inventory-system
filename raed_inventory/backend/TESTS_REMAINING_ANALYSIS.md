# تحليل الاختبارات الفاشلة المتبقية (post-Cursor)

**تاريخ المراجعة:** 2026-04-17  
**الوضع:** 180 passed / 15 failed / 0 errors (92.3% pass rate)

هذا الملف يحلّل الـ 15 اختبار المتبقي (≈13 فشل + 2 نتائج مؤقّتة) ويصنّفها.
تم إصلاح الـ sweeping API path drift سابقًا بواسطة Cursor، فما تبقى يقع في 5 فئات.

---

## الفئة 1 — Master payloads drift (≈ 3-4 اختبارات)

**الملف:** `test_epic2_master_data_unittest.py`

**النمط:** الاختبارات تمرّر payloads قديمة لا تحتوي حقولًا أصبحت إلزامية في
schemas (مثل `min_stock`/`max_stock` في الأصناف، أو `city` في الفروع).

**خطوات التحقّق لـ Cursor:**

1. شغّل:
   ```bash
   cd raed_inventory/backend
   pytest tests/test_epic2_master_data_unittest.py --tb=short -v 2>&1 | head -80
   ```
2. لكل فشل، قارن الـ schema في `app/schemas/master.py` مع الـ payload في الاختبار.
3. الإصلاح: أضف الحقول الناقصة للـ payloads في الاختبار — لا تُغيّر الـ schema.

**التقدير:** 30-45 دقيقة.

---

## الفئة 2 — Warehouse approval order (≈ 2-3 اختبارات)

**الملف:** `test_epic4_9_unittest.py` (scenarios: warehouse_review → approve)

**النمط:** الاختبار يستدعي `/approve` مباشرة بعد `/warehouse-review` لكن
`orders_service.approve` الحالي يشترط حالة = `warehouse_reviewed`. قد يكون
الـ state-machine تغيّر.

**خطوات التحقّق لـ Cursor:**

1. افتح `app/services/orders_service.py` واقرأ `approve_order`.
2. افتح نفس ملف الاختبار، ابحث عن `/approve`.
3. إذا كان الـ test يتخطّى حالة `warehouse_review` → أضفها قبل الـ approve call.

**التقدير:** 30 دقيقة.

---

## الفئة 3 — Duplicate daily inventory per day (≈ 1-2 اختبار)

**الملف:** `test_epic3_inventory_workflow_unittest.py`

**النمط:** الاختبار يحاول إنشاء جرد ثاني لنفس (branch_id, inventory_date)
ويتوقّع 200 أو 201 لكن الـ API يرجع 409 Conflict بسبب unique constraint.

**خطوات التحقّق لـ Cursor:**

1. راجع `DailyInventory` model → يجب أن يكون هناك `UniqueConstraint(branch_id,
   inventory_date)` — إذا موجود، السلوك الصحيح هو 409.
2. حدِّث توقّع الاختبار:
   ```python
   self.assertEqual(resp.status_code, 409)
   self.assertEqual(resp.json()["error_code"], "inventory_already_exists")
   ```

**التقدير:** 15 دقيقة.

---

## الفئة 4 — Import audit trail (≈ 2 اختبار)

**الملفات:** `test_epic10_13_unittest.py`, `test_security_and_workflow_fixes_unittest.py`

**النمط:** توقّع سطور audit_log معيّنة بعد import_data — ربما `entity_type`
تغيّر الـ naming.

**خطوات التحقّق لـ Cursor:**

1. شغّل الاختبار مع `-v` وانظر للـ assertion الفاشل — غالبًا نص `entity_type`.
2. اقرأ `app/services/audit_service.py` لمعرفة الـ entity_type الفعلي.
3. حدِّث الاختبار ليطابق الـ naming الحالي.

**التقدير:** 20 دقيقة.

---

## الفئة 5 — Low stock counts (≈ 1-2 اختبار)

**الملف:** `test_epic14_15_unittest.py`

**النمط:** الاختبار يتوقّع عددًا محدّدًا من الأصناف تحت الحد الأدنى، لكن الـ
seed data تغيّرت أو صيغة الحساب (min_stock vs target) تغيّرت.

**خطوات التحقّق لـ Cursor:**

1. اقرأ `app/services/dashboard_service.py` → `get_low_stock_items`.
2. افتح الاختبار وعدِّل الـ fixture ليضع أصنافًا واضحة تحت الحد الأدنى.
3. تحقّق من الـ assertion الرقمي أنه يعكس البيانات الجديدة بدقّة.

**التقدير:** 30 دقيقة.

---

## إجراء عامّ لـ Cursor

> **أمر تشغيل مقترح:**
>
> ```bash
> cd raed_inventory/backend
> pytest --tb=short -q --lf 2>&1 | tee /tmp/remaining_failures.log
> grep -E "^FAILED|^ERROR" /tmp/remaining_failures.log
> ```
>
> ثم لكل فشل:
> 1. حدِّد الفئة من الجدول أعلاه.
> 2. طبّق الإصلاح المقترح.
> 3. أعد التشغيل لـ ملف واحد للتحقّق قبل الانتقال.

**الهدف النهائي:** 195 passed / 0 failed (أو مع skip واضح إذا كانت السيناريو
خارج الـ scope).

**التقدير الكلّي:** 2-3 ساعات عمل مركّز.

---

## ما لم يتغيّر

- الـ conftest.py نفسه يعمل — لا تلمسه.
- الـ fixtures الأساسية (`client`, `admin_token`, `branch_manager_token`) سليمة.
- الـ migrations على head (f6a7b8c9d0e1) — لا تحتاج migration جديدة.

*تاريخ التحديث: 2026-04-17*
