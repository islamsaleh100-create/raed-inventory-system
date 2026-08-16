# TASK_GATE_TG-SHIFT-OPS-BACKEND.md

## Task ID
TG-SHIFT-OPS-BACKEND

## Origin
قرار المالك 2026-08-14: بناء **عمليات شفت الفرع** (جرد + كاش) داخل نظام رائد على السيرفر،
معزولة تمامًا عن المستودع والمطبخ، مع تقرير لحساب المراجعة.

## Owner
Islam. Executor: Cursor. Reviewer: Claude. Commit/Deploy: Islam.

## Status
APPROVED

## Cursor Permission
EXECUTE

## Scope of THIS gate
**الباك إند فقط.** الواجهة الأمامية في gate منفصل (`TG-SHIFT-OPS-FRONTEND`) بعد اعتماد ده.

---

## ⚠️ قبل البدء — شرط إيقاف

شجرة العمل فيها **٢١٩ ملف معدّل غير محفوظ**. لو Cursor اشتغل فوقها، مراجعة `git diff` مستحيل
تفصل شغله عن شغل المالك.

**Cursor: لو `git status --porcelain | wc -l` أكبر من ١٠، توقّف واكتب `Status: BLOCKED` وقل للمالك
يعمل commit أو stash الأول. متبدأش.**

---

## القرارات المعتمدة (لا تُناقش، نفّذها كما هي)

| القرار | القيمة |
|---|---|
| الدورة | **الشفت** — لا اليوم. فرع ممكن يكون له شفت أو شفتين. |
| الاعتماد | **مفيش**. `draft → submitted` وخلاص. مفيش approve/reject. |
| إعادة الفتح | **موجودة** بصلاحية مدير فقط، بسبب إلزامي، ومسجّلة. التفاصيل في قسم مستقل أدناه. |
| الربط بالمستودع/المطبخ | **صفر**. لا أوامر تجديد، لا حركة مخزون، لا طلبات فرع. |
| الموديول القديم | **يفضل زي ما هو تمامًا**. ممنوع لمسه. |
| تقرير المراجعة | قراءة فقط لـ `internal_auditor` + `admin` + `super_admin` |

### لماذا العزل مطلوب — السبب التقني
`services/inventory_service.py:210` ينادي `replenishment_service.generate_replenishment_order()`
تلقائيًا عند الاعتماد، و`ReplenishmentOrder.warehouse_id` إجباري. الموديول الجديد **يجب ألا يكرر
هذا السلوك بأي شكل**.

---

## قيود صارمة — أي خرق = `DO_NOT_COMMIT`

**ممنوع على الكود الجديد أن يستورد أو ينادي أيًا مما يلي:**

```
replenishment_service      stock_ledger_service       stock_adjustment_service
ledger_service             branch_request_split_service
branch_request_detail_service                          delivery_service
inventory_service          orders_service             procurement (أي شيء منه)
```

**ممنوع تعديل أي ملف قائم** باستثناء التسجيل في `main.py` (سطر `include_router` واحد) و
`models/__init__.py` (إضافة كلاسات جديدة **فقط** — لا تعديل ولا حذف لأي كلاس قائم).

**ممنوع نهائيًا:** تعديل `routers/inventory.py` أو `services/inventory_service.py` أو أي جدول قائم
أو أي migration قائم. الجداول الجديدة **جديدة بالكامل**، لا تعديل على `daily_inventory` أو
`inventory_lines` أو `replenishment_orders`.

---

## الملفات المسموح بها

**جديدة:**
1. `raed_inventory/backend/app/models/branch_shift_ops.py`
2. `raed_inventory/backend/app/services/shift_ops_service.py`
3. `raed_inventory/backend/app/services/shift_ops_validation.py`
4. `raed_inventory/backend/app/routers/shift_ops.py`
5. `raed_inventory/backend/alembic/versions/<rev>_branch_shift_operations.py`
6. `raed_inventory/backend/tests/test_shift_ops_validation.py`
7. `raed_inventory/backend/tests/test_shift_ops_api.py`
8. `raed_inventory/backend/tests/test_shift_ops_isolation.py`
9. `.ai-workflow/CURSOR_REPORT_TG-SHIFT-OPS-BACKEND.md`

**تعديل محدود:**
10. `raed_inventory/backend/app/models/__init__.py` — استيراد/تصدير الكلاسات الجديدة فقط
11. `raed_inventory/backend/app/main.py` — سطر `app.include_router(shift_ops.router)` فقط
12. `raed_inventory/backend/app/schemas/__init__.py` — سكيمات جديدة فقط، لا تعديل على قائم

أي ملف خارج القائمة = توقّف واكتب `BLOCKED`.

---

## الجداول الجديدة

### `branch_shift_configs`
`id` · `branch_id` FK→branches · `shift_number` (1..n) · `shift_name_ar` · `is_active`
· قيد فريد `(branch_id, shift_number)`

### `branch_shifts`
`id` · `branch_id` FK · `shift_date` (Date) · `shift_number` · `status` enum(`draft`,`submitted`)
· `opened_by` FK→users · `opened_at` · `submitted_by` · `submitted_at` · `notes`
· `reopened_by` FK→users nullable · `reopened_at` nullable · `reopen_reason` String(300) nullable
· `reopen_count` Integer default 0
· **قيد فريد `(branch_id, shift_date, shift_number)`** — يمنع تكرار نفس الشفت.

### `brand_shift_count_items` — قائمة العد **على مستوى البراند**
`id` · `brand_id` FK→brands · `item_id` FK→items · `display_order` · `is_active`
· قيد فريد `(brand_id, item_id)`

> **لماذا البراند وليس الفرع:** قائمة أوندا واحدة تخدم ١٠ فروع، ورونالدوز واحدة تخدم ١٠.
> لو كانت على مستوى الفرع لاحتجت ٢٣ قائمة، وإضافة صنف واحد لأوندا تعني ١٠ صفوف بدل صف واحد.
> هذا يطابق `Brand_Items` في جوجل شيت.

### `branch_shift_count_exclusions` — استثناء اختياري لفرع
`id` · `branch_id` FK · `item_id` FK→items · `reason` · قيد فريد `(branch_id, item_id)`

قائمة العد الفعلية لفرع = أصناف براند الفرع النشطة **ناقص** استثناءات الفرع.
الجدول ده غالبًا هيفضل فاضي — موجود عشان فرع مالوش صنف معيّن ما يتقفلش عليه الشفت.

> قراءة `items` و `brands` للاسم والوحدة **مسموحة** — قراءة فقط. الممنوع هو الكتابة أو توليد أوامر.

### `branch_shift_counts`
`id` · `shift_id` FK→branch_shifts **UNIQUE** · `status` enum(`draft`,`submitted`)
· `general_notes` · `created_by` · `updated_by` · `submitted_by` · `created_at` · `updated_at`
· `submitted_at`

### `branch_shift_count_lines`
`id` · `count_id` FK · `item_id` FK→items · `opening_balance` Numeric(12,2)
· `received_qty` · `returned_qty` · `damaged_qty` · `closing_balance` · `consumption_qty`
· `item_notes` · `row_status` enum(`incomplete`,`valid`,`invalid`)
· قيد فريد `(count_id, item_id)`

### `branch_shift_cash`
`id` · `shift_id` FK→branch_shifts **UNIQUE** · `status` enum(`draft`,`submitted`)
· `total_sale` · `bill_count` Integer · `mada_sales` · `cash_sales` · `app_sales` · `refund_bill`
· `exchange_amount` · `expiry_amount` · `cash_expense` · `cash_float_carried_forward`
· `cash_deposited` · `expense_type` enum(`invoices`,`advance`,`handed_to_person`,`operational`,`other`)
· `expense_details` · `shift_notes` · `cash_variance` · `cash_variance_reason`
· `created_by` · `updated_by` · `submitted_by` · `created_at` · `updated_at` · `submitted_at`

كل الحقول المالية `Numeric(12,2)`، غير سالبة. **ممنوع Float.**

**Migration:** نادِ `op.get_bind()` **داخل** `upgrade()`/`downgrade()` فقط — استدعاء على مستوى
الموديول بيفشل بـ NameError (حصل قبل كده في ٥ ملفات، commit 3eb7c45).

---

## قواعد التحقق — الجرد

المرجع `apps_script/InventoryValidation.gs`. انقل المنطق حرفيًا:

1. كل الكميات غير سالبة وأرقام صحيحة. الفراغ ⇒ `incomplete`.
2. `consumption_qty = opening_balance + received_qty − returned_qty − damaged_qty − closing_balance`
3. **`consumption_qty` سالب ⇒ رفض** بكود `INVENTORY_NEGATIVE_CONSUMPTION`
4. `row_status`: خطأ ⇒ `invalid` · ناقص ⇒ `incomplete` · كامل وسليم ⇒ `valid`
5. **عند الترحيل:** كل صنف في قائمة عد الفرع (أصناف براند الفرع ناقص استثناءاته) لازم يكون
   موجود وحالته `valid`، وإلا `SHIFT_COUNT_INCOMPLETE`
6. صنف خارج القائمة ⇒ `SHIFT_COUNT_FOREIGN_ITEM`. تكرار ⇒ `SHIFT_COUNT_DUPLICATE_LINE`

### الرصيد الافتتاحي
`opening_balance` = `closing_balance` لنفس `(branch_id, item_id)` من **آخر شفت مُرحَّل سابق**
للفرع (ترتيب `shift_date` ثم `shift_number`). لو مفيش شفت سابق مرحّل ⇒ **صفر**.

**يُحسب في السيرفر فقط.** أي قيمة `opening_balance` جاية من العميل تُتجاهل تمامًا.

---

## قواعد التحقق — الكاش

المرجع `apps_script/Validation.gs`. القواعد السبعة، كلها إلزامية عند الترحيل:

1. `mada + cash + app = total_sale` (تفاوت مسموح ‎0.01) وإلا `PAYMENT_METHODS_MISMATCH`
2. `expected_cash_deposited = cash_sales − cash_expense − cash_float_carried_forward − refund_bill`
3. `cash_expense > cash_sales` ⇒ `EXPENSE_EXCEEDS_CASH`
4. `cash_expense > 0` ⇒ `expense_type` و `expense_details` **إجباريان**
5. `cash_float_carried_forward > (cash_sales − cash_expense − refund_bill)` ⇒ `CASH_FLOAT_EXCEEDS_AVAILABLE_CASH`
6. `expected_cash_deposited < 0` ⇒ `NEGATIVE_EXPECTED_CASH`
7. `cash_variance = cash_deposited − expected_cash_deposited`.
   `abs(cash_variance) > 5` وبدون `cash_variance_reason` ⇒ `CASH_VARIANCE_REASON_REQUIRED`

الحد `5` يُقرأ من ثابت `CASH_VARIANCE_TOLERANCE` في `app/config.py` — **لا ترقيم صلب في المنطق**.
`bill_count = 0` مع `total_sale > 0` ⇒ `BILL_COUNT_REQUIRED`.

---

## نقاط النهاية — `/api/v1/shift-ops`

```
POST   /shifts                        فتح شفت (branch_id, shift_date, shift_number)
GET    /shifts                        قائمة (فلترة branch_id, date_from, date_to, status)
GET    /shifts/{id}                   تفاصيل الشفت + الجرد + الكاش
POST   /shifts/{id}/reopen            إعادة فتح — مدير فقط، بسبب إلزامي

GET    /shifts/{id}/count             الجرد + الرصيد الافتتاحي محسوبًا
PATCH  /shifts/{id}/count/lines       تعديل سطور (دفعة واحدة)
POST   /shifts/{id}/count/submit      ترحيل وقفل الجرد — مستقل

GET    /shifts/{id}/cash              الكاش الحالي + expected_cash_deposited + cash_variance محسوبين
PUT    /shifts/{id}/cash              حفظ مسودة الكاش
POST   /shifts/{id}/cash/submit       ترحيل وقفل الكاش — مستقل

GET    /reports/shift-operations      تقرير المراجعة (قراءة فقط)
```

### قواعد الترحيل والقفل — **ترحيل مستقل لكل جزء**

قرار المالك 2026-08-14: الجرد والكاش **شاشتان منفصلتان**، فالترحيل منفصل كذلك — وهذا يطابق
تصميم جوجل شيت، حيث لكل من `Inventory` و `Sales` حالة مستقلة عن حالة `Shifts`.

- `POST /shifts/{id}/count/submit` يتحقق من **قواعد الجرد فقط** ويقفل الجرد.
- `POST /shifts/{id}/cash/submit` يتحقق من **قواعد الكاش فقط** ويقفل الكاش.
- كل منهما معاملة مستقلة. فشل أحدهما **لا يؤثر** على الآخر.
- **حالة الشفت مشتقّة، لا تُضبط يدويًا:** الشفت يصير `submitted` تلقائيًا في اللحظة التي يصبح
  فيها الجرد **و** الكاش كلاهما `submitted`. لا يوجد endpoint لترحيل الشفت.
- بعد `submitted` لأي جزء: كل تعديل عليه يُرفض `409` بكود `COUNT_ALREADY_SUBMITTED` أو
  `CASH_ALREADY_SUBMITTED` — إلا بعد إعادة فتح.
- ازدواج الترحيل يُمنع بفحص الحالة قبل التنفيذ (مثل نمط `inventory.already_approved` القائم).

### ⚠️ الأثر الجانبي الذي يجب تغطيته: الشفت الجزئي

الفصل يجعل حالة جديدة ممكنة لم تكن ممكنة من قبل: **جرد مُرحَّل وكاش لم يُرحَّل أبدًا** (أو العكس)،
وينتهي اليوم دون أن ينتبه أحد. الضوابط التالية **إلزامية** لتغطيتها:

- `GET /shifts` و `GET /shifts/{id}` يرجعان `count_status` و `cash_status` **صراحةً**،
  إضافةً إلى حقل مشتق `is_partial` = true عندما يكون أحدهما `submitted` والآخر `draft`.
- تقرير المراجعة يتضمن فلتر **"الشفتات الجزئية فقط"**، ويُبرزها في المخرجات.
- `GET /shifts?partial_only=true&date_to=<أمس>` يجب أن يعمل — هذه هي الاستعلامة التي تكشف
  الشفتات المنسية. اكتب لها اختبارًا.
- سلسلة الرصيد الافتتاحي تعتمد على **الجرد المُرحَّل** فقط، ولا تتأثر بحالة الكاش إطلاقًا.

### إعادة الفتح — `POST /shifts/{id}/reopen`

إعادة فتح شفت مقفول معناها فتح سجل كاش مُرحَّل للتعديل. ده أخطر إجراء في الموديول كله،
فالضوابط دي **إلزامية وليست اختيارية**:

- **الصلاحية:** `area_manager` · `operations_manager` · `admin` · `super_admin` فقط.
  **`branch_manager` مستبعد عمدًا** — هو غالبًا المسؤول عن عهدة الكاش نفسها، فلا يُعيد فتح
  سجله بنفسه. (لو المالك قرر خلاف ذلك، يُعدَّل الجيت أولًا، لا الكود.)
- `area_manager` محصور بنطاقه عبر `core/area_manager_scope.py`.
- **السبب إلزامي:** `reason` نص بين 5 و 300 حرف. الفراغ ⇒ `422` بكود `REOPEN_REASON_REQUIRED`.
- **`target` إلزامي:** `count` أو `cash` أو `both` — لأن الترحيل منفصل، وأكثر حالة متوقعة هي
  إعادة فتح الكاش وحده لتصحيح رقم. الجزء غير المستهدف لا يُلمس.
- الجزء المستهدف يرجع `draft`، وحالة الشفت تُعاد اشتقاقها (تصير `draft`).
- يُسجَّل: `reopened_by` · `reopened_at` · `reopen_reason` · `reopen_count += 1`.
  **`submitted_by` و `submitted_at` لا تُمسح** — يفضل معروف مين رحّل قبل كده.
- شفت حالته `draft` ⇒ `409` بكود `SHIFT_NOT_SUBMITTED`.
- **يُكتب في سجل التدقيق القائم** عبر `services/audit_service.py` (قراءة/كتابة السجل مسموحة —
  هي ليست ضمن قائمة الممنوعات).
- التقرير لازم يُظهر `reopen_count` و `reopen_reason`، وفلتر "الشفتات المُعاد فتحها فقط".

### الصلاحيات
- كتابة وفتح وترحيل: `branch_user`, `branch_manager` — **على فرعهم فقط**. أي `branch_id` غير فرع
  المستخدم ⇒ `403`، ليس `404`.
- قراءة التقرير: `internal_auditor`, `admin`, `super_admin`, `operations_manager`, `area_manager`
  (مدير المنطقة محصور بنطاقه — استخدم `core/area_manager_scope.py` **للقراءة فقط**).
- التقرير **قراءة فقط**. لا يوجد أي endpoint كتابة لهذه الأدوار على هذه الجداول.

### تقرير المراجعة — الحقول
لكل شفت: الفرع · التاريخ · رقم الشفت · الحالة · من رحّل ومتى · إجمالي المبيعات · تفصيل طرق الدفع
· الكاش المتوقع · الكاش المُسلَّم · **فرق الكاش وسببه** · **عدد مرات إعادة الفتح وسببها ومن فتحها**
· عدد أصناف الجرد · إجمالي التالف · إجمالي الاستهلاك · الأصناف ذات الاستهلاك الصفري.
فلاتر: فرع · مدى تاريخي · الشفتات ذات فرق كاش فقط · الشفتات المُعاد فتحها فقط ·
**الشفتات الجزئية فقط** (جرد بلا كاش أو العكس).

---

## معايير القبول

- [ ] ملفات `git status` = ملفات القائمة المسموحة فقط، لا شيء غيرها.
- [ ] `grep -rn "replenishment_service\|stock_ledger_service\|branch_request_split_service\|inventory_service" app/services/shift_ops_service.py app/routers/shift_ops.py` ⇒ **صفر نتائج**.
- [ ] `git diff app/routers/inventory.py app/services/inventory_service.py` ⇒ **فارغ**.
- [ ] `git diff app/main.py` ⇒ سطر `include_router` واحد فقط.
- [ ] الـ migration بيشتغل `upgrade` ثم `downgrade` ثم `upgrade` تاني على قاعدة نظيفة بدون خطأ.
- [ ] `test_shift_ops_isolation.py` يثبت: ترحيل شفت **لا** يُنشئ صفًا في `replenishment_orders`
      ولا في `stock_movements`/الليدجر ولا في `branch_requests`. **هذا الاختبار إلزامي.**
- [ ] تغطية اختبار القواعد السبعة للكاش + قواعد الجرد الستة، حالة بحالة.
- [ ] اختبار: `opening_balance` من العميل يُتجاهل ويُعاد حسابه في السيرفر.
- [ ] اختبار: `branch_user` من فرع A يُمنع (403) من الكتابة على فرع B.
- [ ] اختبار: قيد `(branch_id, shift_date, shift_number)` الفريد يمنع فتح نفس الشفت مرتين.
- [ ] اختبار إعادة الفتح: `branch_user` و `branch_manager` يُمنعان (403) · `area_manager` خارج
      نطاقه يُمنع (403) · سبب فارغ أو أقل من 5 أحرف ⇒ 422 · جزء `draft` ⇒ 409 ·
      `target=cash` يُعيد فتح الكاش **ولا يلمس الجرد** · إعادة الفتح تزيد `reopen_count`
      وتحفظ `reopened_by` والسبب **دون مسح `submitted_by`**.
- [ ] اختبار الاستقلال: ترحيل الجرد وحده ينجح والكاش يفضل `draft` والعكس · فشل تحقق الكاش
      **لا** يرجّع الجرد المُرحَّل · الشفت يصير `submitted` تلقائيًا فقط عند اكتمال الاثنين.
- [ ] اختبار الشفت الجزئي: `is_partial` صحيح في الحالات الأربع ·
      `GET /shifts?partial_only=true&date_to=<أمس>` يرجّع الشفتات المنسية فقط.
- [ ] كل الاختبارات خضراء: `cd raed_inventory/backend && python -m pytest tests/ -x -q`
      — **الحزمة كاملة، ليس ملفاتك فقط.** أي كسر في اختبار قائم = `BLOCKED`.
- [ ] التقرير مكتوب مع ناتج pytest **منسوخًا حرفيًا**، وقسم `Deviations`.

## خارج النطاق

الواجهة الأمامية · تشغيل الـ migration على قاعدة الإنتاج · `git commit` · `git push` · النشر على
Railway · تعبئة قوائم الأصناف ببيانات فعلية · **إنشاء أو تعديل حسابات مستخدمي الفروع أو كلمات
مرورهم** · أي مساس بالموديول القديم · اعتماد/رفض الشفت.

## شرط الإيقاف

لو أي مطلوب هنا لا يمكن تنفيذه دون لمس ملف ممنوع — **توقّف**، اكتب `Status: BLOCKED` مع السبب،
ولا تغيّر شيئًا.
