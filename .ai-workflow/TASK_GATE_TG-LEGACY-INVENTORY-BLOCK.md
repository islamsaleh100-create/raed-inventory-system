# TASK_GATE_TG-LEGACY-INVENTORY-BLOCK

## Task ID
TG-LEGACY-INVENTORY-BLOCK

## Status
APPROVED

## Cursor Permission
EXECUTE

## Owner
Islam. Executor: Cursor. Reviewer: Claude. Commit/Deploy: Islam.

## الحجم
سطر واحد + اختباران. أصغر جيت في المشروع، وشرط إطلاق.

---

# المشكلة

`raed_inventory/backend/app/routers/inventory.py:28`

```python
_APPROVAL_ROLES = ("branch_manager", "admin", "super_admin")
```

واعتماد أي جرد في الموديول القديم ينادي تلقائيًا
`replenishment_service.generate_replenishment_order()` (`inventory_service.py:210`)،
و`ReplenishmentOrder.warehouse_id` إجباري.

**ما تغيّر (قرار المالك 2026-08-15):** الفروع ستعمل بدور **`branch_manager`** حصرًا — لن تُنشأ
حسابات `branch_user` إطلاقًا. أي أن الدور الوحيد على مستوى الفرع أصبح هو نفسه الدور الذي يملك
صلاحية اعتماد الجرد القديم.

**ما فعله جيت الواجهة:** ضيّق مسارات `/inventory` في `App.jsx` والقوائم إلى `admin`/`super_admin`.
هذا **إخفاء للشاشة، وليس منعًا للـAPI**. الـendpoint ما زال قابلًا للنداء مباشرة بتوكن مدير فرع.

**شرط الإطلاق كان "إخفاء/منع".** نُفِّذ الإخفاء فقط. هذا الجيت ينفّذ المنع.

---

# المطلوب

## ١ · إزالة `branch_manager` من صلاحية الاعتماد

```diff
- _APPROVAL_ROLES = ("branch_manager", "admin", "super_admin")
+ # branch_manager أُزيل 2026-08-15: أصبح دور الفرع التشغيلي الوحيد، وموديول الجرد القديم
+ # يولّد أمر تجديد للمستودع تلقائيًا عند الاعتماد. الفروع تستخدم /shift-ops بدلًا منه.
+ _APPROVAL_ROLES = ("admin", "super_admin")
```

**هذا هو التغيير الوحيد المسموح في هذا الملف.** لا تلمس `_BRANCH_ROLES` ولا أي دالة ولا أي
endpoint آخر.

> **لماذا `_BRANCH_ROLES` تُترك كما هي:** هي تحكم الإنشاء والترحيل، وهي لا تولّد أمر تجديد.
> الخطر محصور في الاعتماد وحده. توسيع النطاق هنا انحراف.

## ٢ · اختباران

في `tests/` (ملف جديد `test_legacy_inventory_block.py`):

- `branch_manager` ينادي `POST /api/v1/inventory/{id}/approve` ⇒ **403**
- `admin` ينادي نفس الـendpoint ⇒ **لا يُرفض بـ403** (لا يُشترط 200 — المهم ألا تكون الصلاحية
  قد انكسرت للإدارة)

---

# الملفات المسموح بها

1. `raed_inventory/backend/app/routers/inventory.py` — سطر `_APPROVAL_ROLES` فقط
2. `raed_inventory/backend/tests/test_legacy_inventory_block.py` — جديد
3. `.ai-workflow/CURSOR_REPORT_TG-LEGACY-INVENTORY-BLOCK.md` — جديد

**ممنوع:** أي ملف آخر · `services/inventory_service.py` · أي شيء في `shift_ops` ·
`git commit` · `git push` · migration.

# معايير القبول

- [ ] `git diff app/routers/inventory.py` ⇒ سطر `_APPROVAL_ROLES` + التعليق فقط. **لا شيء غيره.**
- [ ] `grep -n "_BRANCH_ROLES" app/routers/inventory.py` ⇒ **غير معدّلة**.
- [ ] الاختباران يمرّان.
- [ ] `python -m pytest tests/test_shift_ops_*.py -q` ⇒ **39 passed**، لم ينكسر شيء.
- [ ] أي اختبار قائم كان يعتمد على `branch_manager` في الاعتماد ⇒ **قف واكتبه في التقرير**،
      لا تعدّله. قد يكون كاشفًا لاستخدام تشغيلي فعلي لم ننتبه له.

# ملاحظة للمالك

هذا التغيير يمنع مدير الفرع من اعتماد الجرد القديم. **إذا كان أي مدير فرع يستخدم هذه الشاشة
فعليًا اليوم لغرض حقيقي**، سيتوقف عن العمل. الاعتقاد الحالي أن لا أحد يستخدمها — الفرع المنشور
عمره ٣ شهور والموديول لم يُشغَّل تشغيليًا. **أكّد ذلك قبل النشر، لا قبل الـcommit.**
