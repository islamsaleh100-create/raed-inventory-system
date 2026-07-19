# Role Menu Matrix — مصفوفة قوائم الأدوار

**الحالة:** قيد التطوير
**آخر تحديث:** 2026-07-12

## أعمدة الجدول الرسمية

| القائمة | Current Nav (LAN) | Target Nav | Current Route | Target Mode | Scope | Backend Status | القرار |

**قيم Backend Status:**
- `VERIFIED` — تم قراءة الـ Router/Service مباشرةً وتأكيد السلوك
- `NEEDS_VERIFICATION` — الدور مسموح في `allowed[]` لكن فلتر النطاق أو الـ Service لم يُختبر
- `REQUIRED_FOR_NEW_MODULE` — الـ endpoint غير موجود، يحتاج كتابة
- `MISSING` — الـ route أو الصفحة غير موجودة

**علامة البلوك في LAN Trial:**
```
Current Nav in LAN:  NO — مخفي بـ isLegacyHiddenForTrial
Direct Route in LAN: BLOCKED — TrialLegacyRouteGuard يمنع الدخول
Source Route Roles:  ALLOWED OUTSIDE TRIAL
Target:              HIDDEN FOR OPERATIONAL ROLE
```

---

## الإجراءات المشتركة — جميع الأدوار

| ID | الإجراء | التفاصيل |
|---|---|---|
| X-01 | `/supply-chain/control` — إخفاء من أدوار التنفيذ | يُحذف من nav: branch_user، branch_manager، area_manager، kitchen_section_manager، warehouse_user، warehouse_manager، delivery_user. يبقى في الـ target tree لـ: operations_manager، internal_auditor، admin، super_admin — بعد بناء الصفحة الفعلية |
| X-02 | `/audit/findings` لـ area_manager وoperations_manager — بناء Scope أولاً | لا تُضاف للـ nav حتى يُنفَّذ فلتر النطاق في الـ backend. area_manager يجب أن يرى ملاحظات city+brand فقط. بعد التنفيذ تُضاف للـ nav |
| X-03 | توحيد الاسم: "تأخر الطلبات" | تصحيح في `ar.json`: `analytics_order_delay` |
| X-04 | Fix Audit-01: تطبيق `is_read_only()` في warehouse_lines.py | internal_auditor يستطيع حالياً تنفيذ receive/issue/partial-issue — هذا خطأ. يُصلَح بإضافة guard بعد `_require_warehouse_access` |
| X-05 | التحقق من Scope للجودة والتدريب والوثائق والتحليلات | قراءة quality_service + training + documents + analytics routers للتأكد من فلتر النطاق لـ area_manager |
| X-06 | إعادة اختبار Kitchen E2E | التحقق من أن الدورة الكاملة تعمل runtime بعد ثبوت الـ migration والبيئة |

---

## الأدوار

| الدور | الحالة |
|---|---|
| `branch_user` | APPROVED CONCEPTUALLY — Backend scopes: PENDING VERIFICATION |
| `branch_manager` | APPROVED CONCEPTUALLY — Backend scopes: PENDING VERIFICATION |
| `area_manager` | APPROVED CONCEPTUALLY — Quality/Docs/Analytics scope: PENDING VERIFICATION |
| `kitchen_section_manager` | APPROVED CONCEPTUALLY — Runtime E2E: PENDING RETEST |
| `warehouse_user` | APPROVED CONCEPTUALLY — WH-ADJ-01، WH-SEC-01، FIX-WH-02/03: مُسجَّلة |
| `warehouse_manager` | APPROVED CONCEPTUALLY — WH-ADJ-01، WH-XFER-01، WH-SEC-01: مُسجَّلة |
| `delivery_user` | APPROVED CONCEPTUALLY — Backend auth+scope: VERIFIED. DU-02 (assignment) يحتاج قرار تصميم |
| `operations_manager` | APPROVED CONCEPTUALLY — متابعة لا اعتماد بديل. OP-NAV-01 (5 orphan) + OP-QA-01 (backend verify أولاً): مُسجَّلة |
| `sales_manager` | APPROVED CONCEPTUALLY — Global scope + Import + Branch CRUD: VERIFIED. SM-01/02/03: مُسجَّلة |
| `quality_visitor` | APPROVED CONCEPTUALLY — **QV-02 P0 IDOR مكتشف** (delete بلا ownership). QV-01 مُحسوم + QV-03/04 مُسجَّلة |
| `quality_manager` | APPROVED CONCEPTUALLY — global scope مقبول. QM-01 (analytics verify) مستقل عن FIX-OP-02 |
| `internal_auditor` | APPROVED CONCEPTUALLY — قراءة global VERIFIED. FIX-WH-01 P0 مُسجَّل. IA-01/04: قرارات nav مُحسومة — PENDING IMPL |
| `admin` | APPROVED CONCEPTUALLY — Full menu coverage and backend parity pending verification. ADM-03 (findings parity) + ADM-04 (section_legacy) + ADM-05/06: PENDING |
| `super_admin` | APPROVED CONCEPTUALLY — Central bypass verified in require_roles; custom service predicates and complete menu coverage pending verification (ADM-06) |

---

---

## area_manager — (مُحدَّث بالتصحيحات)

**نطاق البيانات:** `AreaManagerAssignment (brand_id, city, user_id)` — مُطبَّق تلقائياً في الـ backend.

**قواعد الاعتماد الموثَّقة بالكود:**
1. يرى طلبات `status != DRAFT` فقط (branch_requests.py:164)
2. يعتمد SUBMITTED فقط — `_ensure_submitted` قبل كل approve/reject
3. تعديل الكميات: qty_approved ≤ qty_requested فقط
4. auto-split يُشغَّل فورياً في نفس الـ transaction عند الاعتماد

---

### قسم 1: سلسلة التوريد

| القائمة | Current Nav (LAN) | Target Nav | Current Route | Target Mode | Scope | Backend Status | القرار |
|---|---|---|---|---|---|---|---|
| لوحة تحكم التوريد | YES — مرئي | ❌ يُخفى (X-01) | `/supply-chain/control` → REDIRECT /dashboard | — | — | VERIFIED | مخفي حتى بناء الصفحة |
| طلبات الفروع | YES | YES | `/supply-chain/branch-requests` | قراءة نطاق (غير-DRAFT فقط) | `AreaManagerAssignment (brand_id, city)` | VERIFIED (`_area_scope_filter` :151-165) | ✓ مقبول |
| تفاصيل الطلب | — | — | `/supply-chain/branch-requests/:id` | قراءة + اعتماد/رفض | نفس الفلتر عبر `_can_view` | VERIFIED (`_require_view` :181) | ✓ مقبول |
| مراجعة الطلبات | YES | YES | `/supply-chain/approvals` | اعتماد / تعديل+اعتماد / رفض | `_require_area_review` + scope | VERIFIED (approve/modify-and-approve/split/reject — كلها تشترط area_manager) | ✓ مقبول |

---

### قسم 2: قنوات المبيعات (legacy — مبلوكة في LAN Trial)

> area_manager في `TRIAL_SUPPLY_CHAIN_ROLES` → `/delivery/*` مخفي بـ `isLegacyHiddenForTrial` ومبلوك بـ `TrialLegacyRouteGuard`.

| القائمة | Current Nav (LAN) | Target Nav | القرار |
|---|---|---|---|
| جميع شاشات /delivery/* | **NO — LEGACY_BLOCKED** | يظهر بعد إزالة area_manager من TRIAL_SUPPLY_CHAIN_ROLES أو نقل الشاشات | يُؤجَّل — يُنظر فيه مع مرحلة المبيعات |

---

### قسم 3: المراجعة الداخلية (مُصحَّح — X-02)

| القائمة | Current Nav (LAN) | Target Nav | Current Route | Target Mode | Backend Status | القرار |
|---|---|---|---|---|---|---|
| ملاحظات التدقيق | **NO** — مستثنى من nav section_audit | **BLOCKED حتى تنفيذ Scope** (X-02) | `/audit/findings` — RouteRoleGuard يشمل area_manager (App.jsx:2044) | قراءة + Acknowledge — لا إنشاء ولا إغلاق | UNSAFE: area_manager يستطيع رؤية كل النتائج بلا فلتر (لم يُنفَّذ بعد) | **لا تُضاف للـ nav الآن** — تنفيذ scope (city+brand) أولاً |

---

### قسم 4: الجودة والتدريب (مُصحَّح — X-05)

| القائمة | Current Nav (LAN) | Target Nav | Current Route | Target Mode | Backend Status | القرار |
|---|---|---|---|---|---|---|
| زيارات الجودة (قراءة) | YES | YES | `/quality` | قراءة فقط (لا إنشاء) | NEEDS_VERIFICATION — فلتر النطاق في quality_service لم يُقرأ | مقبول مبدئياً — يحتاج تحقق |
| الإجراءات المفتوحة | YES | YES | `/quality/open-actions` | قراءة — **bulk-resolve: PENDING SCOPE VERIFICATION** | NEEDS_VERIFICATION — قد يحل إجراءات خارج نطاقه | **لا يُعتمَد bulk-resolve حتى التحقق** |
| تحليلات الجودة | YES | YES | `/quality/analytics` | قراءة | NEEDS_VERIFICATION | مقبول مبدئياً |
| تقييمات التدريب | YES | YES | `/training` | قراءة / إجراء | NEEDS_VERIFICATION | مقبول مبدئياً |

---

### قسم 5: الوثائق

| القائمة | Current Nav (LAN) | Target Nav | Current Route | Backend Status | القرار |
|---|---|---|---|---|---|
| قائمة الوثائق | YES | YES | `/documents` + `/documents/new` + `/documents/:id` | NEEDS_VERIFICATION | مقبول مبدئياً |
| وثائق تنتهي قريباً | YES | YES | `/documents/expiring` | NEEDS_VERIFICATION | مقبول مبدئياً |

---

### قسم 6: التحليلات

| القائمة | Current Nav (LAN) | Target Nav | Current Route | Backend Status | القرار |
|---|---|---|---|---|---|
| اتجاه الاستهلاك | YES | YES | `/analytics/consumption-trend` | NEEDS_VERIFICATION | مقبول مبدئياً |
| تأخر الطلبات | YES | YES (بعد تصحيح الاسم X-03) | `/analytics/order-delay` | NEEDS_VERIFICATION | مقبول مبدئياً |
| إجراءات الفروع المفتوحة | YES | YES | `/analytics/branches-open-actions` | NEEDS_VERIFICATION | مقبول مبدئياً |

**Status: APPROVED CONCEPTUALLY — Quality scope، Audit Findings scope: PENDING VERIFICATION**

---

---

## kitchen_section_manager — (مُحدَّث بالتصحيحات)

**نطاق البيانات:** `KitchenSectionAssignment (user_id, kitchen_section_id, service_city)`.

---

### قسم 1: سلسلة التوريد

| القائمة | Current Nav (LAN) | Target Nav | Current Route | Target Mode | Scope | Backend Status | القرار |
|---|---|---|---|---|---|---|---|
| لوحة تحكم التوريد | YES | ❌ يُخفى (X-01) | REDIRECT /dashboard | — | — | VERIFIED | مخفي حتى بناء الصفحة |
| صفحة المطبخ | YES | YES | `/supply-chain/kitchen` | تشغيل كامل (تفاصيل أدناه) | `KitchenSectionAssignment` | VERIFIED | ✓ مقبول |

### تفاصيل صفحة المطبخ — Authorization vs Runtime

| الإجراء | Authorization | Section Scope | Runtime E2E |
|---|---|---|---|
| عرض قائمة أوامر الإنتاج | VERIFIED | VERIFIED | PENDING RETEST (X-06) |
| عرض تفاصيل أمر الإنتاج | VERIFIED | VERIFIED | PENDING RETEST |
| بدء الإنتاج (start) | VERIFIED | VERIFIED | PENDING RETEST |
| جاهز جزئي (mark-partial-ready) | VERIFIED | VERIFIED | PENDING RETEST |
| جاهز كامل (mark-ready) | VERIFIED | VERIFIED | PENDING RETEST |
| إرسال للمستودع (send-to-warehouse) | VERIFIED | VERIFIED | PENDING RETEST — يُنشئ WarehouseLine + stock transaction |
| طلب مواد خام (request-materials) | VERIFIED | VERIFIED | PENDING RETEST |
| **اعتماد طلب مواد** | ❌ ليس من صلاحياته | — | VERIFIED (MATERIAL_APPROVE_ROLES = warehouse_manager/admin/super_admin فقط) |
| **إصدار مواد** | ❌ ليس من صلاحياته | — | VERIFIED (MATERIAL_ISSUE_ROLES لا تشمله) |
| طلبيات يومية Legacy | VERIFIED | نفس scope | PENDING RETEST |

### باقي الأقسام
kitchen_section_manager لا يرى أي قسم آخر — قائمته: `/supply-chain/control` (سيُخفى) + `/supply-chain/kitchen` فقط.

**Status: APPROVED CONCEPTUALLY — Runtime E2E (X-06): PENDING RETEST**

---

---

## warehouse_user

**القائمة المستهدفة المعتمدة:**
```
الرئيسية
├── لوحة التحكم
└── الإشعارات
التشغيل الحالي
└── تنفيذ المستودع   (/supply-chain/warehouse)
المخزون والتحويلات
├── أرصدة المستودعات (/warehouse/stock — يخرج من Legacy)
└── حركات المخزون    (عند البناء — قراءة فقط)
```

**نطاق البيانات:** `user.warehouse_id` — مُطبَّق في `_require_warehouse_access` (warehouse_lines.py:98-109).

**قواعد الدور المعتمدة (Authorization VERIFIED / Design Decisions أدناه):**
1. Scope: `Branch.warehouse_id = user.warehouse_id` — سطور الـ lines (warehouse_lines.py:187-191)
2. استلام (receive): PENDING → AVAILABLE للـ branch-request، idempotent للـ kitchen-output
3. صرف كامل (issue): qty = pending_qty — AVAILABLE → READY_FOR_DISPATCH
4. صرف جزئي (partial-issue): qty < pending_qty + delay_reason إلزامي → PARTIAL
5. تسجيل سبب التأخير (delay-reason): issued_qty=0 → BACKORDER
6. إصدار مواد معتمدة للمطبخ (issue-material): مسموح — `MATERIAL_ISSUE_ROLES`

**قرارات التصميم (تتجاوز الكود الحالي):**
- ❌ **WH-ADJ-01:** تعديل المخزون المباشر `DENIED` للموظف — وجوده في `_WH_ROLES` لا يعني اعتماد التصميم
- ❌ **WH-XFER-01:** إنشاء تحويلات WH↔Branch `DENIED` — الموظف لا يملك هذه الصلاحية
- ❌ اعتماد طلبات المواد `DENIED` — `MATERIAL_APPROVE_ROLES` لا تشمله (VERIFIED)

---

### قسم 1: التشغيل الحالي (سلسلة التوريد)

| القائمة | Current Nav (LAN) | Target Nav | Current Route | Target Mode | Scope | Backend Status | القرار |
|---|---|---|---|---|---|---|---|
| لوحة تحكم التوريد | YES | ❌ يُخفى (X-01) | REDIRECT /dashboard | — | — | VERIFIED | مخفي حتى بناء الصفحة |
| تنفيذ المستودع | YES | YES | `/supply-chain/warehouse` | تنفيذ warehouse_lines (تفاصيل أدناه) | `user.warehouse_id` | VERIFIED | ✓ مقبول |

#### تفاصيل تنفيذ المستودع — warehouse_user

| الإجراء | Endpoint | Authorization | Scope | Backend Status | القرار |
|---|---|---|---|---|---|
| عرض قائمة الـ lines | `GET /warehouse-lines` | VERIFIED (WAREHOUSE_ROLES) | `Branch.warehouse_id = user.warehouse_id` | VERIFIED | ✓ |
| تفاصيل line | `GET /warehouse-lines/{id}` | VERIFIED | `_require_warehouse_access` | VERIFIED | ✓ |
| استلام | `POST /warehouse-lines/{id}/receive` | VERIFIED | `_require_warehouse_access` | VERIFIED | ✓ |
| صرف كامل | `POST /warehouse-lines/{id}/issue` | VERIFIED | `_require_warehouse_access` + stock deduct | VERIFIED | ✓ |
| صرف جزئي | `POST /warehouse-lines/{id}/partial-issue` | VERIFIED | `_require_warehouse_access` + delay_reason | VERIFIED | ✓ |
| سبب تأخير | `POST /warehouse-lines/{id}/delay-reason` | VERIFIED | `_require_warehouse_access` | VERIFIED | ✓ |
| إصدار مواد معتمدة للمطبخ | `POST /material-requests/{id}/issue` | VERIFIED (MATERIAL_ISSUE_ROLES) | `_require_material_warehouse_access` | VERIFIED | ✓ |
| **اعتماد طلب مواد** | `POST /material-requests/{id}/approve` | ❌ مستثنى | — | VERIFIED | DENIED |
| **تعديل المخزون** | `POST /stock/warehouses/{id}/adjust` + `bulk-adjust` | موجود في `_WH_ROLES` لكن **مرفوض تصميماً** | ⚠️ WH-SEC-01 + WH-ADJ-01 | NEEDS_VERIFICATION | **DENIED بقرار تصميم** |
| **تحويل WH↔Branch** | `/stock/transfer/*` | ❌ `_MGMT_ROLES` لا تشمله | — | VERIFIED | DENIED |

---

### قسم 2: المخزون والتحويلات

| القائمة | Current Nav (LAN) | Target Nav | Current Route | Target Mode | Scope | Backend Status | القرار |
|---|---|---|---|---|---|---|---|
| أرصدة المستودعات | **NO — LEGACY_BLOCKED** (`/warehouse/stock` في `LEGACY_TRIAL_BLOCKED_PATHS`) | ✅ YES — بعد تنفيذ FIX-WH-02 | `/warehouse/stock` — يخرج من Legacy | عرض فقط (مستودعه) | `user.warehouse_id` | NEEDS_VERIFICATION — route موجود لكن يحتاج scope فلتر للـ warehouse_user | **FIX-WH-02 + FIX-WH-03** |
| حركات المخزون | NO | YES — عند البناء | جديد | قراءة فقط (مستودعه) | `user.warehouse_id` | REQUIRED_FOR_NEW_MODULE | يُبنى لاحقاً |

---

### قسم 3: باقي الأقسام

warehouse_user لا يرى: analytics، documents، quality، audit، admin.

---

### ملخص التغييرات — warehouse_user

| # | التغيير | النوع |
|---|---|---|
| WU-01 | إخفاء `/supply-chain/control` (X-01) | nav fix |
| WU-02 | إزالة warehouse_user من `_WH_ROLES` في stock.py (WH-ADJ-01) | Backend design fix |
| WU-03 | FIX-WH-02: إخراج `/warehouse/stock` من `LEGACY_TRIAL_BLOCKED_PATHS` | trialLegacy.js |
| WU-04 | FIX-WH-03: **حماية Backend إلزامية** — warehouse_user يرى مستودعه فقط حسب `current_user.warehouse_id`؛ فلترة Frontend للـ UX فقط ولا تُعتبر حماية | Backend (إلزامي) + Frontend (UX) |

**Status: APPROVED CONCEPTUALLY — WH-ADJ-01، WH-SEC-01، FIX-WH-02/03: مُسجَّلة في Fix Register أدناه**

---

---

## warehouse_manager

**القائمة المستهدفة المعتمدة:**
```
الرئيسية
├── لوحة التحكم
└── الإشعارات
التشغيل الحالي
└── تنفيذ المستودع         (/supply-chain/warehouse)
المخزون والتحويلات
├── أرصدة المستودعات       (/warehouse/stock — عرض + تصدير)
├── حركات المخزون          (قراءة مستودعه)
├── الجرد الفعلي           (إنشاء جلسة جرد للمستودع)
└── التحويلات المعتمدة     (تنفيذ تحويل موجود + اعتماد — لا إنشاء حر)
التحليلات
├── اتجاه الاستهلاك        (/analytics/consumption-trend)
└── تأخر الطلبات           (/analytics/order-delay)
الوثائق والرخص
├── قائمة الوثائق          (/documents — قراءة فقط)
└── الوثائق المقاربة للانتهاء (/documents/expiring)
```

**نطاق البيانات:** `user.warehouse_id` — نفس scope الـ warehouse_user.

**قرارات التصميم (تتجاوز الكود الحالي):**
- ❌ **WH-ADJ-01:** التعديل المباشر للمخزون لا يُعرض كزر عادي — المسار الوحيد: الجرد الفعلي → فرق → مراجعة → اعتماد → تسوية
- ❌ **WH-XFER-01:** إنشاء تحويل حر `DENIED` — يُنفِّذ تحويلاً معتمداً فقط، مع: فرع مرسل/مستلم + سبب + حركة مخزون + Audit Trail
- `/documents/new`: مستثنى من allowed[] (App.jsx:2060) — يقرأ الوثائق لكن لا ينشئها ✓

---

### قسم 1: التشغيل الحالي (سلسلة التوريد)

| القائمة | Current Nav (LAN) | Target Nav | Current Route | Target Mode | Scope | Backend Status | القرار |
|---|---|---|---|---|---|---|---|
| لوحة تحكم التوريد | YES | ❌ يُخفى (X-01) | REDIRECT /dashboard | — | — | VERIFIED | مخفي حتى بناء الصفحة |
| تنفيذ المستودع | YES | YES | `/supply-chain/warehouse` | تشغيل كامل | `user.warehouse_id` | VERIFIED | ✓ مقبول |

#### صلاحيات warehouse_manager الإضافية داخل صفحة التنفيذ

| الإجراء | Endpoint | Authorization | Scope | Backend Status | القرار |
|---|---|---|---|---|---|
| كل صلاحيات warehouse_user | — | موروثة | — | VERIFIED | ✓ |
| **اعتماد طلب مواد مطبخ** | `POST /material-requests/{id}/approve` | VERIFIED (MATERIAL_APPROVE_ROLES) | `_require_material_warehouse_access (user.warehouse_id → branch.warehouse_id)` | VERIFIED | ✓ |
| **رفض طلب مواد** | `POST /material-requests/{id}/reject` | VERIFIED (MATERIAL_APPROVE_ROLES) | نفس scope | VERIFIED | ✓ |
| **تنفيذ تحويل معتمد (WH→Branch)** | `POST /stock/transfer/warehouse-to-branch` | موجود في `_MGMT_ROLES` لكن **مقيَّد بالتصميم** | ⚠️ WH-SEC-01: warehouse_id من URL بلا scope check | NEEDS_VERIFICATION | **APPROVED TRANSFERS ONLY — WH-XFER-01** |
| **تحويل فرع→WH** | `POST /stock/transfer/branch-to-warehouse` | موجود في `_MGMT_ROLES` | ⚠️ WH-SEC-01 | NEEDS_VERIFICATION | **APPROVED TRANSFERS ONLY — WH-XFER-01** |
| **تعديل مباشر للمخزون** | `POST /stock/warehouses/{id}/adjust` | موجود في `_WH_ROLES` | ⚠️ WH-SEC-01 + WH-ADJ-01 | NEEDS_VERIFICATION | **CONTROLLED WORKFLOW ONLY — عبر الجرد الفعلي** |

---

### قسم 2: المخزون والتحويلات

| القائمة | Current Nav (LAN) | Target Nav | Current Route | Target Mode | Scope | Backend Status | القرار |
|---|---|---|---|---|---|---|---|
| أرصدة المستودعات | **NO — LEGACY_BLOCKED** | ✅ YES — بعد FIX-WH-02 | `/warehouse/stock` | عرض + تصدير (مستودعه) | `user.warehouse_id` | NEEDS_VERIFICATION (scope + export) | FIX-WH-02 + FIX-WH-03 |
| حركات المخزون | NO | YES | جديد أو موجود — NEEDS_VERIFICATION | قراءة مستودعه | `user.warehouse_id` | NEEDS_VERIFICATION | يُبنى أو يُتحقق |
| الجرد الفعلي | NO | YES | جديد | إنشاء جلسة + إدخال + مراجعة | warehouse scope | REQUIRED_FOR_NEW_MODULE | مرحلة لاحقة |
| التحويلات المعتمدة | NO | YES | جديد / مُدمَج | تنفيذ تحويل معتمد فقط — لا إنشاء حر | warehouse scope | REQUIRED_FOR_NEW_MODULE | يحتاج workflow module |

---

### قسم 3: التحليلات

> لا تقع في `LEGACY_TRIAL_BLOCKED_PATHS` — تظهر في LAN Trial.

| القائمة | Current Nav (LAN) | Target Nav | Current Route | Backend Status | القرار |
|---|---|---|---|---|---|
| اتجاه الاستهلاك | YES | YES | `/analytics/consumption-trend` | NEEDS_VERIFICATION (scope في Service) | ✓ مقبول مبدئياً |
| تأخر الطلبات | YES | YES (اسم مُصحَّح X-03) | `/analytics/order-delay` | NEEDS_VERIFICATION | ✓ مقبول مبدئياً |

---

### قسم 4: الوثائق

| القائمة | Current Nav (LAN) | Target Nav | Current Route | ملاحظة | القرار |
|---|---|---|---|---|---|
| قائمة الوثائق | YES | YES | `/documents` | قراءة فقط — `/documents/new` يستثني warehouse_manager (App.jsx:2060 VERIFIED) | ✓ مقبول |
| وثائق تنتهي قريباً | YES | YES | `/documents/expiring` | قراءة فقط | ✓ مقبول |

---

### ملخص التغييرات — warehouse_manager

| # | التغيير | النوع |
|---|---|---|
| WM-01 | إخفاء `/supply-chain/control` (X-01) | nav fix |
| WM-02 | FIX-WH-02: إخراج `/warehouse/stock` من `LEGACY_TRIAL_BLOCKED_PATHS` | trialLegacy.js |
| WM-03 | FIX-WH-03: **حماية Backend إلزامية** — warehouse_manager يرى مستودعه فقط حسب `current_user.warehouse_id`؛ فلترة Frontend للـ UX فقط ولا تُعتبر حماية | Backend (إلزامي) + Frontend (UX) |
| WM-04 | FIX-WH-05: Transfer workflow — تحويل معتمد فقط (WH-XFER-01) | Backend + Frontend |
| WM-05 | WH-SEC-01: التحقق من scope في stock_adjustment_service | Security verification |
| WM-06 | NEEDS_VERIFICATION للتحليلات | قراءة analytics routers |

**Status: APPROVED CONCEPTUALLY — WH-SEC-01، WH-ADJ-01، WH-XFER-01، FIX-WH-02/03: مُسجَّلة في Fix Register أدناه**

---

---

## Fix Register — سجل الإصلاحات المطلوبة

> هذه مهام Cursor — لا تُنفَّذ الآن. تُسجَّل للاعتماد والتفويض لاحقاً.

| ID | الوصف | الأولوية | الملفات المتأثرة | الحالة |
|---|---|---|---|---|
| **SEC-C-01** | **JWT in localStorage — Production Blocker:** التوكن محفوظ في localStorage — عرضة لـ XSS. الإصلاح: الانتقال إلى HttpOnly cookie. لا يُستخدَم كذريعة لتعطيل أي إصلاح آخر. May remain deferred during the current design and LAN-trial preparation phase, but must be resolved and verified before any production release. | **P0 — RELEASE GATE BEFORE PRODUCTION** | `frontend/src/` — auth token storage | DEFERRED |
| FIX-WH-01 | **Fix Audit-01 (X-04):** تقسيم `WAREHOUSE_ROLES` إلى `WAREHOUSE_READ_ROLES` + `WAREHOUSE_WRITE_ROLES` في warehouse_lines.py. internal_auditor يجب أن يحصل على 403 لكل POST endpoint. اختبارات Backend مطلوبة: `internal_auditor POST receive → 403`، `issue → 403`، `partial-issue → 403`، `delay-reason → 403` | **P0 — حرج** | `warehouse_lines.py` | PENDING |
| FIX-WH-02 | إخراج `/warehouse/stock` من `LEGACY_TRIAL_BLOCKED_PATHS` وإضافته كصفحة حالية للدورين | P1 | `trialLegacy.js`، `AppLayoutV2.jsx` | PENDING |
| FIX-WH-03 | Scope فلتر لـ `/warehouse/stock`: **الحماية في Backend إلزامية** — warehouse_user وwarehouse_manager يريان مستودعهم فقط بناءً على `current_user.warehouse_id`؛ admin/super_admin يختار أي مستودع. فلترة Frontend اختيارية للـ UX فقط ولا تُعتبر حماية. | P1 | Backend router (إلزامي) + Frontend WarehouseStockPage (اختياري UX) | PENDING |
| FIX-WH-04 | **WH-ADJ-01:** إزالة warehouse_user من `_WH_ROLES` في stock.py — الموظف لا يُعدِّل المخزون مباشرةً | P1 | `stock.py` | PENDING |
| FIX-WH-05 | **WH-XFER-01:** تحويل WH↔Branch يصبح "تنفيذ تحويل معتمد فقط" — كل تحويل يحتاج: طلب + سبب + اعتماد + حركة مخزون + Audit Trail. **إذا أثبت WH-SEC-01 أن الـ endpoint الحالي يتجاوز الاعتماد → يرتفع إلى P0** | **P1 (P0 إذا ثبت الـ bypass)** | Backend (stock.py + service) + Frontend | PENDING |
| FIX-WH-06 | **WH-ADJ-01 لـ warehouse_manager:** منع التعديل المباشر للمخزون لمدير المستودع أيضاً. المسار الوحيد المعتمد: الجرد الفعلي → فرق → مراجعة → اعتماد → تسوية. Admin/Super Admin فقط يملكان تدخلاً استثنائياً بشرط: سبب إلزامي + رصيد قبل/بعد + مرجع + Audit Trail + Idempotency | P1 | `stock.py` + `stock_adjustment_service.py` | PENDING |
| **WH-SEC-01** | **Object-level Scope — SECURITY INVESTIGATION:** كل endpoint يأخذ `warehouse_id`/`branch_id` من URL path يجب أن يتحقق من `current_user.warehouse_id == warehouse_id` (إلا admin/super_admin). الـ Endpoints المشمولة: `adjust`، `bulk-adjust`، `transfer/warehouse-to-branch`، `transfer/branch-to-warehouse`. **لم يُقرأ `stock_adjustment_service.py` بعد — إذا ثبت غياب الفلتر فالأولوية P0** | **P0 IF CONFIRMED** | `stock_adjustment_service.py` | **SECURITY INVESTIGATION** |
| **FIX-DU-02** | **DU-02 — Delivery Assignment:** قرار تصميم: (أ) إسناد أمر لمندوب محدد (`assigned_to_user_id`) + منع غير المسند من تنفيذ out-for-delivery/deliver، أو (ب) آلية Claim (`claimed_by_user_id` عند out-for-delivery) + تسجيل من نفَّذ، أو (ج) الإبقاء على الحال الراهن مع تسجيل `executed_by` في Audit Trail إلزامياً. الاختيار بين (أ/ب/ج) مطلوب قبل تنفيذ أي كود. | **DESIGN DECISION** | `delivery_orders.py` + Frontend | PENDING DECISION |
| **FIX-OP-01** | **OP-NAV-01:** إضافة nav items لـ 5 Orphan Routes في `AppLayoutV2.jsx` موزَّعة على أقسامها الصحيحة: **التشغيل الحالي:** `/operations` — **المخزون والتحويلات:** `/reports/inventory`، `/stock/inter-branch-transfer`، `/operations/inter-branch-approvals` — **التحليلات:** `/reports/orders`. قراءة محتوى كل صفحة مطلوبة أولاً لتحديد التسمية العربية الدقيقة. | **P1** | `AppLayoutV2.jsx` | PENDING — يحتاج قراءة صفحات أولاً |
| **FIX-OP-02** | **OP-QA-01 — NAV/ROUTE MISMATCH:** قبل تعديل `App.jsx:2029` يجب: (1) قراءة quality analytics backend لتأكيد أن operations_manager مدعوم وأن النطاق صحيح (global للـ ops_manager؟)؛ (2) إذا ثبت الدعم: يُضاف operations_manager لـ `allowed[]` في `App.jsx:2029`. | **P1** | قراءة quality router أولاً → `App.jsx:2029` | PENDING BACKEND VERIFY |
| **FIX-SM-01** | **SM-01 — مُحسوم:** إضافة `/delivery/daily-entry` (الإدخالات اليومية) لـ nav `section_delivery` لـ sales_manager. التحكم في الإجراءات من Backend (Service layer يُطبِّق نافذة >7أيام) لا من إخفاء القائمة. | **P1** | `AppLayoutV2.jsx` — nav item | PENDING |
| **FIX-SM-02** | **SM-02:** إضافة `/delivery/unmatched` لـ `section_delivery` nav بـ `roles: ['sales_manager', 'admin', 'super_admin']` — متابعة تشغيلية يومية للمعاملات غير المطابقة | **P1** | `AppLayoutV2.jsx` | PENDING |
| **FIX-SM-03** | **SM-03:** نقل nav item الخاص بـ `/admin/sales-channels` من `section_delivery` إلى `section_admin` مع إبقاء `roles: ['sales_manager', 'admin', 'super_admin']` — المسار معتمد ويظهر لـ sales_manager في قسم الإدارة | **P1** | `AppLayoutV2.jsx` | PENDING |
| **FIX-QV-02** | **P0 IDOR CONFIRMED — QV-02:** `delete_visit` في quality_service.py يتحقق من status==DRAFT فقط — **لا ownership check** — quality_visitor يحذف Draft أي مستخدم آخر بمعرفة الـ ID. يُصلَح بإضافة: `if visit.visitor_id != current_user.id and not is_platform_admin(user): raise 403`. quality_manager وadmin exempt. | **P0** | `quality_service.py` (delete_visit) | PENDING |
| **FIX-QV-03** | **QV-03 — Object Scope تحقق شامل:** فحص ownership في: تعديل مسودة + submit + تفاصيل بالـ ID + المرفقات. هل يوجد `created_by` check في أي منها؟ | **P1** | `quality_service.py` | SECURITY VERIFY |
| **FIX-QV-04** | **QV-04 — إنشاء زيارة:** (1) إجبار `visitor_id = current_user.id` لـ quality_visitor في service — لا يستطيع الإنشاء باسم غيره؛ (2) قرار تصميم: هل يُقيَّد quality_visitor بفروع محددة؟ | **P1** (visitor_id) + Design (branch) | `quality_service.py` + قرار تصميم | PENDING |
| **FIX-QV-01** | **QV-01 مُحسوم:** (1) إضافة quality_visitor لـ `allowed[]` في App.jsx:2028؛ (2) إضافة Backend scope في `list_open_actions`: filter عبر علاقة الإجراء بالزيارة: `QualityVisit.visitor_id == current_user.id` — يرى إجراءات زياراته فقط؛ (3) قراءة فقط — لا route لـ resolve متاح | **P1** | `App.jsx:2028` + `quality.py` (list_open_actions) | PENDING |

---

---

---

## delivery_user

**ملخص الدور:** مندوب التوصيل. يأخذ أوامر التوصيل الجاهزة ويُسلِّمها للفروع. نطاقه محدود بـ `user.warehouse_id`.

**⚠️ تنبيه: تشابه اسم فقط**
قسم `/delivery/*` (قنوات المبيعات) لا علاقة له بـ `delivery_user`. delivery_user يعمل على `/supply-chain/delivery` فقط ويتعامل مع `DeliveryOrder` لا `SalesChannel`.

**نطاق البيانات (VERIFIED من الكود — delivery_orders.py:104-132):**
- `_require_order_access`: delivery_user مُقيَّد بـ `user.warehouse_id == branch.warehouse_id`
- `list_ready_delivery_orders`: فلتر `Branch.warehouse_id == user.warehouse_id` (:193)
- `list_delivery_orders`: نفس الفلتر (:251)

**قواعد الدور المعتمدة (VERIFIED):**
```
DELIVERY_VIEW_ROLES   = (delivery_user, warehouse_user, warehouse_manager, internal_auditor, admin, super_admin)
DELIVERY_CREATE_ROLES = (warehouse_user, warehouse_manager, admin, super_admin)   ← delivery_user مستثنى
DELIVERY_EXECUTE_ROLES = (delivery_user, admin, super_admin)
```
1. delivery_user **لا يُنشئ** أوامر التوصيل — هذا دور المستودع
2. delivery_user يرى **كل** أوامر التوصيل الجاهزة في مستودعه — الـ scope هو `warehouse_id` لا `user_id`؛ لو وُجد أكثر من مندوب في نفس المستودع فأي منهم يستطيع تنفيذ أمر مندوب آخر (DU-02 — يحتاج قرار تصميم)
3. `out-for-delivery`: READY → OUT_FOR_DELIVERY
4. `deliver`: تسليم كامل أو جزئي — qty_delivered ≤ qty_dispatched، shortage_reason إلزامي عند النقص
5. عند التسليم: BranchStock يُحدَّث، stock_ledger_service يُسجَّل حركة، BranchRequest status يُعاد حساب — **هذا أثر جانبي آلي للتأكيد، لا تعديل مخزون مباشر**
6. لا يملك **Direct Stock Adjustment** — لا يُنشئ warehouse_lines، لا write على stock خارج مسار التسليم المعتمد

---

### قسم 1: التشغيل الحالي (سلسلة التوريد)

| القائمة | Current Nav (LAN) | Target Nav | Current Route | Target Mode | Scope | Backend Status | القرار |
|---|---|---|---|---|---|---|---|
| لوحة تحكم التوريد | YES (جميع الأدوار) | ❌ يُخفى (X-01) | REDIRECT /dashboard | — | — | VERIFIED | مخفي حتى بناء الصفحة |
| تنفيذ التوصيل | YES | YES | `/supply-chain/delivery` — RouteRoleGuard يشمل delivery_user (App.jsx:2055) | تفاصيل أدناه | `user.warehouse_id` | VERIFIED | ✓ مقبول |

#### تفاصيل تنفيذ التوصيل — delivery_user

| الإجراء | Endpoint | Authorization | Scope | Backend Status | القرار |
|---|---|---|---|---|---|
| عرض أوامر التوصيل الجاهزة | `GET /delivery-orders/ready` | VERIFIED (DELIVERY_VIEW_ROLES) | `Branch.warehouse_id = user.warehouse_id` (:193) | VERIFIED | ✓ |
| قائمة كل أوامر التوصيل | `GET /delivery-orders` | VERIFIED (DELIVERY_VIEW_ROLES) | نفس الفلتر (:251) | VERIFIED | ✓ |
| تفاصيل أمر | `GET /delivery-orders/{id}` | VERIFIED | `_require_order_access` | VERIFIED | ✓ |
| تحريك للتوصيل | `POST /delivery-orders/{id}/out-for-delivery` | VERIFIED (DELIVERY_EXECUTE_ROLES) | `_require_order_access` | VERIFIED | ✓ |
| تسجيل التسليم (كامل أو جزئي) | `POST /delivery-orders/{id}/deliver` | VERIFIED (DELIVERY_EXECUTE_ROLES) | `_require_order_access` | VERIFIED — يُحدِّث BranchStock + stock_ledger | ✓ |
| طباعة ملصقات | `GET /delivery-orders/{id}/labels` | VERIFIED (DELIVERY_VIEW_ROLES) | `_require_order_access` | VERIFIED | ✓ |
| **إنشاء أمر توصيل** | `POST /delivery-orders` | ❌ ليس من صلاحياته | — | VERIFIED (DELIVERY_CREATE_ROLES لا تشمله) | DENIED |

---

### قسم 2: Legacy (مبلوك في LAN Trial)

> delivery_user في `TRIAL_SUPPLY_CHAIN_ROLES` → جميع مسارات `/delivery/*` (قنوات المبيعات) في `LEGACY_TRIAL_BLOCKED_PATHS` + ليست في nav roles له.

| القائمة | الحالة |
|---|---|
| `/delivery` وكل مسارات قنوات المبيعات | ❌ ليست في nav roles + LEGACY_BLOCKED — صحيح تماماً |

---

### قسم 3: باقي الأقسام

delivery_user لا يرى: analytics، documents، quality، audit، admin. لا توجد أي ملاحظات إضافية.

---

### ملخص التغييرات — delivery_user

| # | التغيير | النوع |
|---|---|---|
| DU-01 | إخفاء `/supply-chain/control` (X-01) | nav fix |
| DU-02 | **FIX-DU-02 — Delivery Assignment:** قرار تصميم مطلوب: (أ) إسناد أمر لمندوب محدد + منع غير المسند من التنفيذ، أو (ب) آلية Claim (يأخذ المندوب الأمر لنفسه ثم يصبح هو المسؤول)، أو (ج) الإبقاء على الوضع الحالي (أي مندوب في المستودع ينفّذ) مع تسجيل `executed_by` في Audit Trail | Design decision — PENDING |

**Status: APPROVED CONCEPTUALLY — يحتاج قرار DU-02 واختبار منع التكرار عند التسليم**

---

---

## operations_manager

**ملخص الدور:** مدير العمليات. مسؤول عن الإشراف الشامل على سلسلة التوريد والتقارير والتحويلات. **ليس في `TRIAL_SUPPLY_CHAIN_ROLES`** — لا تُطبَّق عليه Legacy blocks.

**مستوى الوصول في الـ Backend (supply_chain.py:84 — VERIFIED):**
```python
elevated = is_platform_admin(current_user) or "operations_manager" in roles or "internal_auditor" in roles
```
في `supply-chain/dashboard` API: operations_manager يرى **كل البيانات بلا فلتر نطاق** — elevated access مُطبَّق في الـ backend.

**قرارات التصميم المُعتمدة لـ operations_manager:**
1. **متابعة — لا اعتماد بديل:** يرى كل طلبات الفروع للمتابعة. اعتماد مدير المنطقة يظل إلزامياً ولا يُعوَّض بـ operations_manager.
2. **مراقبة المراحل:** يرى مراحل Kitchen/Warehouse/Delivery للمتابعة فقط — لا ينفذ إنتاجاً أو صرفاً أو توصيلاً بنفسه.
3. **تحويلات الفروع:** يُدير ويعتمد تحويلات الفروع حسب Workflow التحويلات (`_INTER_BRANCH_ROLES` يشمله في stock.py).
4. **النطاق Global:** operations_manager يرى البيانات بلا فلتر نطاق — هذا تعريف الدور المقصود. لا Assignment مطلوب حالياً (يُعاد النظر إذا نشأت حاجة مستقبلية لتقسيم الإشراف بحسب المدينة أو العلامة).

**⚠️ NAV_GAP حرج مكتشف:**
operations_manager هو دور الإشراف الشامل على سلسلة التوريد، لكن لا يرى أي صفحة عملية في قسم supply_chain حالياً — كل nav items مُقيَّدة بأدوار التنفيذ، و`/supply-chain/control` redirect ميت.

---

### قسم 1: سلسلة التوريد — الحالة الراهنة والمستهدفة

| القائمة | Current Nav (LAN) | Target Nav | Current Route | الحالة | القرار |
|---|---|---|---|---|---|
| لوحة تحكم التوريد | YES (جميع الأدوار) | ✅ YES — **أولوية عالية** بعد بناء الصفحة | `/supply-chain/control` → REDIRECT — لا محتوى | Backend elevated access موجود — Frontend فقط ناقص | أهم صفحة للـ operations_manager بعد بنائها |
| طلبات الفروع (متابعة) | **NO** — ليس في nav roles (:66) | يُضاف للـ Target Tree | Route `/supply-chain/branch-requests` لا يشمله (RouteRoleGuard :2051) | **NAV_GAP** | يحتاج إضافة للـ Route + Nav — قراءة فقط |
| مراجعة وتدخل | **NO** — ليس في approvals nav roles (:67) | يُقيَّم | Route `/supply-chain/approvals` لا يشمله | NAV_GAP — هل يحتاج التدخل أم المتابعة فقط؟ | NEEDS DECISION |

---

### قسم 2: الـ Orphan Routes — موجودة في App.jsx، غائبة من nav

> هذه المسارات لم تُضَف لأي section في `AppLayoutV2.jsx` — operations_manager يصل إليها بالـ URL مباشرةً فقط. التوزيع المعتمد أدناه يحدد القسم المستهدف لكل route.

#### 2أ — قسم التشغيل الحالي (section_operations — جديد أو مدمج في supply_chain)

| القائمة | Current Nav | Target Section | Route | Backend Status | القرار |
|---|---|---|---|---|---|
| لوحة العمليات | ORPHAN | **التشغيل الحالي** | `/operations` (App.jsx:1975) | NEEDS_VERIFICATION — محتوى OperationsDashboard لم يُقرأ | يُضاف — OP-NAV-01 |

#### 2ب — قسم المخزون والتحويلات (section_stock — جديد أو مدمج)

| القائمة | Current Nav | Target Section | Route | Backend Status | القرار |
|---|---|---|---|---|---|
| تقرير الجرد | ORPHAN | **المخزون والتحويلات** | `/reports/inventory` — ops_mgr, wh_mgr, area_mgr (App.jsx:1994) | NEEDS_VERIFICATION | يُضاف — OP-NAV-01 |
| تحويل بين الفروع | ORPHAN | **المخزون والتحويلات** | `/stock/inter-branch-transfer` — area_mgr, ops_mgr, branch_mgr (App.jsx:1969) | VERIFIED لـ `_INTER_BRANCH_ROLES` — object-level scope NEEDS_VERIFICATION | يُضاف — OP-NAV-01 |
| اعتمادات التحويل | ORPHAN | **المخزون والتحويلات** | `/operations/inter-branch-approvals` — ops_mgr, area_mgr (App.jsx:1982) | NEEDS_VERIFICATION | يُضاف — OP-NAV-01 |

#### 2ج — قسم التحليلات (section_analytics — موجود، يحتاج nav item فقط)

| القائمة | Current Nav | Target Section | Route | Backend Status | القرار |
|---|---|---|---|---|---|
| سجل الطلبيات | ORPHAN | **التحليلات** | `/reports/orders` — ops_mgr فقط + admin (App.jsx:2002) | NEEDS_VERIFICATION | يُضاف — OP-NAV-01 |

**OP-NAV-01 — ملاحظة:** قراءة محتوى كل صفحة مطلوبة قبل التنفيذ لتحديد التسمية العربية الدقيقة وترتيب العناصر.

---

### قسم 3: قنوات المبيعات (متاحة — ليست legacy لـ operations_manager)

> operations_manager **ليس في** `TRIAL_SUPPLY_CHAIN_ROLES` → `/delivery/*` غير مبلوكة.

| القائمة | Current Nav (LAN) | Target Nav | Current Route | القرار |
|---|---|---|---|---|
| لوحة المبيعات | YES | YES | `/delivery` — Route يشمل operations_manager (App.jsx:2009) | ✓ مقبول |
| مطابقة المبيعات | YES | YES | `/delivery/reconciliation` (App.jsx:2012) | ✓ مقبول |
| امتثال | YES | YES | `/delivery/compliance` (App.jsx:2014) | ✓ مقبول |
| أداء الفروع | YES | YES | `/delivery/branch-stats` (App.jsx:2017) | ✓ مقبول |
| أداء العلامات | YES | YES | `/delivery/brands` (App.jsx:2018) | ✓ مقبول |
| إدخال يومي | **NO** — ليس في nav roles (:79 — area_manager, branch_manager فقط) | لا | Route (App.jsx:2010) يستثنيه | صحيح |
| بيانات المبيعات | **NO** — sales_manager فقط | لا | صحيح |

---

### قسم 4: المراجعة الداخلية

| القائمة | Current Nav (LAN) | Target Nav | Current Route | القرار |
|---|---|---|---|---|
| ملاحظات التدقيق | **NO** — مستثنى من nav section_audit | **BLOCKED حتى تنفيذ Scope** (X-02) | `/audit/findings` — Route يشمل operations_manager (App.jsx:2044) | لا تُضاف للـ nav حتى بناء scope — نفس قرار area_manager |

---

### قسم 5: الجودة والتدريب

| القائمة | Current Nav (LAN) | Target Nav | Current Route | الملاحظة | القرار |
|---|---|---|---|---|---|
| زيارات الجودة | **NO** — ليس في nav roles (:108) | لا | Route (App.jsx:2026) يستثنيه | صحيح — operations_manager لا ينفذ زيارات | ✓ |
| الإجراءات المفتوحة | **NO** — ليس في nav roles (:109) | لا | Route (App.jsx:2028) يستثنيه | صحيح | ✓ |
| تحليلات الجودة | **YES** في nav (:110 يشمل operations_manager) | **⚠️ MISMATCH — BLOCKED حتى تحقق Backend** | Route (App.jsx:2029): `allowed={['quality_manager', 'branch_manager', 'area_manager', 'internal_auditor', 'admin', 'super_admin']}` — **operations_manager غائب!** | operations_manager يرى nav item لكن يُحجب عند الدخول | **OP-QA-01: يجب قراءة quality backend أولاً — هل يسمح للـ operations_manager؟ وما نطاق بياناته؟ قبل تعديل RouteRoleGuard** |
| تقييمات التدريب | YES — nav (:111) + Route (App.jsx:2033) | YES | ✓ متسق | — | ✓ مقبول |
| تحليلات التدريب | YES — nav (:112) + Route (App.jsx:2035) | YES | ✓ متسق | — | ✓ مقبول |

---

### قسم 6: التحليلات

| القائمة | Current Nav (LAN) | Target Nav | Current Route | القرار |
|---|---|---|---|---|
| اتجاه الاستهلاك | YES | YES | App.jsx:2074 يشمل operations_manager | ✓ مقبول |
| تأخر الطلبات | YES | YES (بعد X-03) | App.jsx:2075 يشمل operations_manager | ✓ مقبول |
| إجراءات الفروع المفتوحة | YES | YES | App.jsx:2076 يشمل operations_manager | ✓ مقبول |

---

### قسم 7: باقي الأقسام

| القسم | الحالة |
|---|---|
| الوثائق | ❌ `section_documents` لا يشمل operations_manager + Route يستثنيه — صحيح |
| الإدارة | ❌ admin/super_admin فقط — صحيح |

---

### ملخص التغييرات — operations_manager

| # | التغيير | النوع | الأولوية |
|---|---|---|---|
| OP-01 | **OP-NAV-01:** إضافة nav items لـ 5 Orphan Routes بتوزيعها على أقسامها الصحيحة (التشغيل + المخزون والتحويلات + التحليلات) — قراءة محتوى كل صفحة أولاً | nav fix | P1 |
| OP-02 | **OP-QA-01:** قراءة quality analytics backend أولاً للتحقق من صلاحية operations_manager وScope البيانات — ثم تعديل RouteRoleGuard (App.jsx:2029) إذا ثبت الدعم | Backend verify + Bug fix | P1 |
| OP-03 | إضافة operations_manager لـ supply chain nav (branch-requests قراءة فقط + approvals للمتابعة) — مع التأكد أنه لا يعتمد بدل area_manager | Design + nav | P2 |
| OP-04 | `/audit/findings` — بناء Scope أولاً ثم إضافة للـ nav (X-02) | PENDING SCOPE | — |

**Status: APPROVED CONCEPTUALLY — متابعة لا اعتماد بديل. OP-NAV-01 وOP-QA-01 مُسجَّلتان**

---

---

---

## sales_manager

**ملخص الدور:** مدير حسابات التوصيل (Model C — 2026-04-24). يُدير كشوفات قنوات المبيعات، معدلات العمولة، الإغلاق الشهري، والتحليلات. **لا يُدخل البيانات اليومية** — هذا دور الفرع.

**نطاق البيانات (VERIFIED من sales_channels.py:155-166):**
```python
if "sales_manager" in roles or "operations_manager" in roles:
    return None   # None = كل الفروع، بلا فلتر
```
sales_manager يرى **جميع الفروع** — نطاقه Global بلا assignment.

**قواعد الدور (VERIFIED من sales_channels.py):**
```
لا يُدخل البيانات اليومية (_DAILY_ENTRY_ROLES: branch_manager, area_manager فقط)
يُعدِّل بيانات قديمة فقط في نافذة >7 أيام (_DAILY_EDIT_ROLES يشمله — Service layer يُطبِّق النافذة)
_STATEMENT_WRITE_ROLES = ("sales_manager",) ← الوحيد غير الـ admin الذي يُدير الكشوفات
يُغلق ويُعيد فتح الإغلاق الشهري مع سبب
operations_manager: READ-ONLY في هذا الـ router (backend يمنع الكتابة)
```

**ليس في `TRIAL_SUPPLY_CHAIN_ROLES`** → `/delivery/*` مُتاحة كاملاً، لا Legacy blocks.

---

### قسم 1: سلسلة التوريد

> sales_manager **ليس في** `section_supply_chain` roles (AppLayoutV2.jsx:63) → القسم **مخفي بالكامل**.

| الحالة | التفاصيل |
|---|---|
| section_supply_chain | HIDDEN ENTIRELY — بتصميم صحيح. sales_manager ليس دور تشغيل سلسلة توريد |

---

### قسم 2: قنوات المبيعات — نطاق العمل الكامل

| القائمة | Current Nav (LAN) | Target Nav | Current Route (App.jsx) | Backend Status | الدور في الإجراء | القرار |
|---|---|---|---|---|---|---|
| لوحة المبيعات | YES | YES | `:2009` — `TrialLegacyRouteGuard` — sales_manager ✓ | VERIFIED — global scope (`_authorized_branch_ids` → None) | عرض إجمالي كل الفروع | ✓ مقبول |
| الإدخالات اليومية | **NO في nav حالياً** | **YES — يُضاف (SM-01 مُحسوم)** | `:2010` — sales_manager ✓ | VERIFIED — `_DAILY_EDIT_ROLES` يشمله؛ Service layer يُطبِّق نافذة >7أيام | مراجعة وتصحيح الحالات القديمة المسموح بها فقط — **التحكم من Backend لا من إخفاء القائمة** | ✓ مقبول — يظهر في nav |
| الكشوفات | YES | YES | `:2011` — sales_manager ✓ | VERIFIED — `_STATEMENT_WRITE_ROLES = (sales_manager,)` | الوحيد المُدير للكشوفات غير الـ admin | ✓ مقبول |
| المطابقة | YES | YES | `:2012` — sales_manager ✓ | VERIFIED — `_RECON_READ_ROLES` يشمله | قراءة global | ✓ مقبول |
| الإغلاق الشهري | YES | YES | `:2013` — sales_manager ✓ | VERIFIED — إغلاق + إعادة فتح مع سبب | صلاحية حرجة: close + reopen | ✓ مقبول |
| الامتثال | YES | YES | `:2014` — sales_manager ✓ | VERIFIED — `_COMPLIANCE_READ_ROLES` يشمله | قراءة global | ✓ مقبول |
| أداء الفروع | YES | YES | `:2017` — sales_manager ✓ | VERIFIED (global scope) | قراءة تحليلية | ✓ مقبول |
| أداء العلامات | YES | YES | `:2018` — sales_manager ✓ | VERIFIED (global scope) | قراءة تحليلية | ✓ مقبول |
| استيراد بيانات التوصيل | YES | YES | `:2015` — sales_manager ✓ | VERIFIED — `POST /api/v1/delivery/import` — `_DELIVERY_WRITE_ROLES = (sales_manager, admin)` | يُحمِّل بيانات التوصيل بالجملة من Excel | ✓ مقبول |
| إدارة فروع التوصيل | YES | YES | `:2016` — sales_manager ✓ | VERIFIED — `GET/POST/PUT + alias CRUD` — `_DELIVERY_WRITE_ROLES` يشمله — operations_manager READ-ONLY | إنشاء + تعديل + aliases للفروع في منصة التوصيل | ✓ مقبول — WRITE كامل VERIFIED |

---

### قسم 3: Orphan Route

| المسار | الحالة | التفاصيل | القرار |
|---|---|---|---|
| `/delivery/unmatched` | **ORPHAN ROUTE** — موجود في Route :2019 (`allowed: [sales_manager, admin, super_admin]`) لكن **غائب من nav** (lines 77-89) | sales_manager يصل إليه بالـ URL فقط — متابعة تشغيلية يومية للمعاملات غير المطابقة | **يُضاف للـ nav — SM-02 (P1)** |

---

### قسم 4: باقي الأقسام

| القسم | الحالة |
|---|---|
| المراجعة الداخلية | ❌ sales_manager مستثنى من كل audit routes — صحيح |
| الجودة والتدريب | ❌ section_quality_training لا يشمل sales_manager — صحيح |
| الوثائق | ❌ section_documents لا يشمل sales_manager — صحيح |
| التحليلات (consumption/delay/open-actions) | ❌ section_analytics لا يشمل sales_manager — صحيح (لديه تحليلاته الخاصة في section_delivery) |
| الإدارة | section_admin مُقيَّد بـ admin/super_admin. **`/admin/sales-channels` ينتمي لهذا القسم** — يظهر لـ sales_manager + admin + super_admin (Route :2070 VERIFIED). مكانه في شجرة الإدارة: **الإدارة → قنوات المبيعات** |

---

### ملخص التغييرات — sales_manager

| # | التغيير | النوع | الأولوية |
|---|---|---|---|
| SM-01 | **مُحسوم:** إضافة `/delivery/daily-entry` (الإدخالات اليومية) للـ nav — التحكم من Backend (نافذة >7أيام لـ sales_manager) لا من إخفاء القائمة | nav fix | P1 |
| SM-02 | إضافة `/delivery/unmatched` لـ nav `section_delivery` بـ `roles: ['sales_manager', 'admin', 'super_admin']` | nav fix | **P1** |
| SM-03 | نقل `/admin/sales-channels` nav item من `section_delivery` إلى `section_admin` مع إبقاء `roles: ['sales_manager', 'admin', 'super_admin']` | nav restructure | P1 |

**Status: APPROVED CONCEPTUALLY — Global scope VERIFIED، الإدخالات اليومية مُحسومة بوضع مراجعة، Import/Branch Management: VERIFIED**

---

---

---

## quality_visitor و quality_manager

> الصفحات مشتركة — الفرق في الإجراءات والنطاق. المصفوفتان مدمجتان للوضوح.

**قواعد RBAC (VERIFIED من quality.py):**
```
_VISITOR_ROLES        = (quality_visitor, quality_manager, admin, super_admin)
_REVIEWER_ROLES       = (quality_manager, admin, super_admin)
_VIEW_ROLES           = (quality_visitor, quality_manager, branch_manager, area_manager, internal_auditor, admin, super_admin)
_ACTION_RESOLVER_ROLES = (quality_manager, branch_manager, area_manager, admin, super_admin)
```

**نطاق البيانات (VERIFIED من quality.py:72-73):**
```python
if "quality_visitor" in user_roles and "quality_manager" not in user_roles:
    visitor_id = current_user.id    # الزائر يرى زياراته فقط
# quality_manager: لا scope filter — يرى كل الزيارات
```

---

### قسم 1: الجودة — الصفحات المشتركة والمنفردة

| القائمة | quality_visitor Current Nav | quality_manager Current Nav | Target Nav | Route | Backend — quality_visitor | Backend — quality_manager | القرار |
|---|---|---|---|---|---|---|---|
| قائمة الزيارات | YES (nav :108) | YES (nav :108) | YES لكليهما | `:2026` — `_VIEW_ROLES` | VERIFIED — `visitor_id = current_user.id` (زياراته فقط) | VERIFIED — يرى كل الزيارات | ✓ لكليهما |
| إنشاء زيارة جديدة | YES (عبر `/quality/new`) | YES | YES لكليهما | `:2027` — `_VISITOR_ROLES` | NEEDS_FIX — يستطيع إنشاء لأي فرع + `visitor_id` من الـ payload (يستطيع انتحال زائر آخر) — QV-03 + QV-04 | VERIFIED | ✓ quality_manager — QV-03/04 للـ visitor |
| تفاصيل زيارة | YES (عبر `/quality/:id`) | YES | YES لكليهما | `:2030` — `_VIEW_ROLES` | Backend لا يتحقق من ownership — يرى أي زيارة بالـ ID (design question — هل مقبول؟) | VERIFIED | QV-03: NEEDS DECISION |
| الإجراءات المفتوحة | **NAV/ROUTE MISMATCH** | YES (nav :109) | **يُصلَح (QV-01 مُحسوم)** | `:2028` — quality_visitor غائب من `allowed[]` | **QV-01 مُحسوم:** يُضاف للـ Route + **Backend scope يُضاف:** يرى إجراءات زياراته فقط (visitor_id filter) + قراءة فقط | VERIFIED — يرى كل الإجراءات | يُضاف للـ Route + Backend scope |
| تحليلات الجودة | **NO** (nav :110 لا يشمله) | YES (nav :110) | لا لـ visitor / YES لـ manager | `:2029` — quality_visitor غائب | N/A | NEEDS_VERIFICATION — QM-01: backend scope للـ analytics | ✓ quality_manager فقط |

---

### قسم 2: إجراءات الجودة — الفارق بين الدورين

| الإجراء | quality_visitor | quality_manager | Backend — الحالة | القرار |
|---|---|---|---|---|
| إنشاء زيارة | ✓ (`_VISITOR_ROLES`) | ✓ | **IDOR risk:** `visitor_id` من payload — يستطيع إنشاء باسم زائر آخر. لا فلتر فروع | QV-04: يُصلَح (visitor_id يُجبر = current_user.id لـ quality_visitor) |
| تعديل زيارة (مسودة) | ✓ (يُفترض) | ✓ | NEEDS_VERIFICATION — هل يوجد ownership check في service؟ | QV-03: تحقق مطلوب |
| حذف زيارة | ✓ (`_VISITOR_ROLES`) | ✓ | **P0 IDOR CONFIRMED:** `delete_visit` يتحقق من status==DRAFT فقط — **لا ownership check** — quality_visitor يحذف Draft زائر آخر | **FIX-QV-02: إضافة `visit.visitor_id == current_user.id` في service** |
| رفع للمراجعة (submit) | ✓ (`_VISITOR_ROLES`) | ✓ | NEEDS_VERIFICATION — ownership check؟ | QV-03: تحقق مطلوب |
| مراجعة واعتماد/رفض | ❌ (`_REVIEWER_ROLES` يستثنيه) | ✓ | VERIFIED | ✓ |
| حل إجراء تصحيحي (resolve) | ❌ (`_ACTION_RESOLVER_ROLES` يستثنيه) | ✓ | VERIFIED | ✓ |
| حل جماعي (bulk-resolve) | ❌ (`_ACTION_RESOLVER_ROLES` يستثنيه) | ✓ | VERIFIED | ✓ |

---

### قسم 3: التدريب والوثائق والتحليلات

| القسم | quality_visitor | quality_manager | القرار |
|---|---|---|---|
| تقييمات التدريب (`/training`) | ❌ — ليس في nav roles (:111) + Route (:2033) | YES — nav (:111) + Route (:2033) | قد يحتاج quality_visitor الوصول — DESIGN DECISION |
| تحليلات التدريب (`/training/analytics`) | ❌ | YES — nav (:112) + Route (:2035) | quality_manager فقط — صحيح |
| الوثائق (`/documents`) | ❌ — ليس في section_documents (:117) + Route (:2058) | YES — nav (:119) + Route (:2058) | ✓ صحيح |
| تحليلات العمليات (consumption/delay) | ❌ | ❌ | صحيح — ليس دورهم |
| إجراءات الفروع المفتوحة (analytics) | ❌ | YES — Route (:2076) | quality_manager فقط — صحيح |

---

### قسم 4: باقي الأقسام

كلا الدورين لا يملكان وصولاً لـ: section_supply_chain، section_delivery، section_audit، section_admin. صحيح بتصميم.

---

### ملخص التغييرات — quality_visitor

| # | التغيير | النوع | الأولوية |
|---|---|---|---|
| QV-01 | **مُحسوم:** إضافة quality_visitor لـ `allowed[]` في App.jsx:2028 + Backend scope لـ `list_open_actions`: يرى إجراءات زياراته فقط (filter بـ `visitor_id = current_user.id`) + قراءة فقط (لا resolve) | P1 — Route fix + Backend scope | PENDING |
| QV-02 | **P0 IDOR CONFIRMED:** `delete_visit` في quality_service لا يتحقق من ownership — quality_visitor يحذف Draft زيارة أي مستخدم آخر. يُصلَح بإضافة `visit.visitor_id == current_user.id` + `quality_manager`/`admin` exempt | **P0** | PENDING |
| QV-03 | تحقق من ownership في: تعديل مسودة + submit + تفاصيل بالـ ID — هل توجد فجوات مشابهة لـ delete؟ | Security verify | P1 |
| QV-04 | **إنشاء زيارة:** إجبار `visitor_id = current_user.id` للـ quality_visitor (لا يستطيع الإنشاء باسم زائر آخر) + تحديد نطاق الفروع المسموح له بزيارتها إن كان مطلوباً | P1 (visitor_id) / Design (branch scope) | PENDING DECISION لـ branch scope |

**Status: APPROVED CONCEPTUALLY — QV-02 P0 مكتشف ومُسجَّل**

---

### ملخص التغييرات — quality_manager

| # | التغيير | النوع | الأولوية |
|---|---|---|---|
| QM-01 | **مستقل:** التحقق من quality analytics backend — هل يعطي quality_manager نطاقاً صحيحاً (global مقبول لمدير جودة وحيد للشركة)؟ ثم بشكل منفصل: إضافة operations_manager لـ RouteRoleGuard `:2029` إذا ثبت الدعم (FIX-OP-02) | Backend verify | P1 |
| QM-02 | **X-05 Scope:** bulk-resolve وresolve — التحقق أن area_manager لا يحل إجراءات خارج نطاقه (quality_manager: global بتصميم) | Backend verify | P2 |

**Status: APPROVED CONCEPTUALLY — QM-01 مستقل عن FIX-OP-02. نطاق Global مقبول مبدئياً**

---

---

---

## internal_auditor

**ملخص الدور:** مراجع داخلي. مساران منفصلان:
1. **قراءة تشغيلية شاملة** — يرى كل البيانات عبر جميع الوحدات بلا فلتر نطاق. لا يُنفِّذ أي عملية تشغيلية.
2. **كتابة داخل وحدة المراجعة فقط** — ينشئ ملاحظات التدقيق (findings)، يُعدِّل ملاحظاته، يصدِّر سجل المراجعة.

**مبدأ التصميم المُطبَّق (audit_permissions.py — VERIFIED):**
```python
_READ_ONLY_ROLES = {"internal_auditor"}

def is_read_only(roles): return bool(set(roles) & _READ_ONLY_ROLES)
# internal_auditor → True → يجب أن يمنعه من كل write خارج وحدة المراجعة

def can_create_audit_finding(roles): return "internal_auditor" in roles or admin...    # يُنشئ ✓
def can_acknowledge_audit_finding(roles): return set(roles) & _AUDITOR_FINDING_MANAGER_ROLES
# _AUDITOR_FINDING_MANAGER_ROLES لا يشمل internal_auditor → لا يعترف بملاحظاته ← منع تضارب مصالح
```

**P0 BUG موثَّق (FIX-WH-01):** `is_read_only()` موجود لكن لم يُستدعَ في `warehouse_lines.py` write endpoints → internal_auditor يُنفِّذ receive/issue/partial-issue/delay-reason.

---

### قسم 1: سلسلة التوريد — قراءة شاملة (observer)

> internal_auditor في section_supply_chain roles (nav :63) → القسم كاملاً مرئي.
> `_has_global_access()` في warehouse_lines.py يعيد True لـ internal_auditor → يرى كل المستودعات بلا فلتر.

| القائمة | Current Nav (LAN) | Target Nav | Route | Backend — المسموح | Backend — المحظور | القرار |
|---|---|---|---|---|---|---|
| لوحة تحكم التوريد | YES | ❌ يُخفى حالياً (REDIRECT — لا محتوى) | REDIRECT | — | — | مخفي مؤقتاً — Target بعد بناء الصفحة: يظهر كلوحة متابعة شاملة read-only (ليس X-01 دائماً) |
| طلبات الفروع | YES | YES | `:2051` — `_READ_ROLES` includes internal_auditor | قراءة global (all branches) | لا write | ✓ قراءة فقط |
| مراجعة الطلبات | YES | YES | `:2052` — includes internal_auditor | قراءة فقط | approve/reject: area_manager فقط | ✓ |
| مرحلة المطبخ | YES | YES | `:2053` — includes internal_auditor | قراءة global | لا write | ✓ |
| مرحلة المستودع | YES | YES | `:2054` — includes internal_auditor | `_has_global_access` → يرى كل المستودعات | **P0 BUG: write ممكن (FIX-WH-01)** | ❌ يُصلَح بـ FIX-WH-01 |
| مرحلة التوصيل | YES | YES | `:2055` — `DELIVERY_VIEW_ROLES` includes internal_auditor | قراءة global | لا execute | ✓ |

---

### قسم 2: المراجعة الداخلية — نطاق الكتابة المعتمد

> section_audit (nav :93-102): `['internal_auditor', 'admin', 'super_admin']` — القسم الأساسي.

| القائمة | Current Nav (LAN) | Target Nav | Route | Backend Status | الإجراءات المسموحة | القرار |
|---|---|---|---|---|---|---|
| لوحة المراجعة | YES | YES | `:2039` — `_AUDIT_READ` | VERIFIED | قراءة إحصاءات + summary | ✓ |
| مراجعة الطلبيات | YES (بندان منفصلان حالياً) | YES — **بند واحد مع tabs** | Target: `/audit/orders?tab=today\|history` — المسارات القديمة `:2040` `:2041` تبقى Redirects | VERIFIED — `scopeAll readOnly` | قراءة اليوم + الأرشيف (tabs) | ✓ |
| مخزون المستودعات | YES | YES | `:2042` — `_AUDIT_READ` | VERIFIED — `readOnly` prop | قراءة فقط | ✓ |
| طلبات تغييرات الأصناف | YES | YES | `:2043` — `_AUDIT_READ` | VERIFIED | قراءة | ✓ |
| ملاحظات التدقيق | YES | YES | `:2044` — includes internal_auditor | VERIFIED (audit_permissions.py) | **ينشئ** finding + **يُعدِّل** ملاحظاته فقط (created_by check) + **لا يعترف** (can_acknowledge → False — تضارب مصالح) | ✓ تصميم سليم |
| سجل التدقيق (Audit Trail) | YES | YES | `:2045` — `_AUDIT_READ` | VERIFIED — `GET /audit/logs` + export.csv | قراءة + تصدير CSV (مُسجَّل في الـ trail) | ✓ |

#### تفاصيل Findings Workflow (VERIFIED):
```
POST   /audit/findings        → can_create_audit_finding → internal_auditor ✓ (ينشئ)
PATCH  /audit/findings/{id}   → created_by == current_user.id (فقط ملاحظاته) ✓
GET    /audit/findings        → _READ_ROLES → global (كل الملاحظات) ✓
POST   /audit/findings/{id}/acknowledge → can_acknowledge → internal_auditor ✗ (مُحظور بتصميم) ✓
```

---

### قسم 3: Orphan Routes — مرئية بالـ URL، غائبة من nav

> section_delivery و section_quality_training و section_documents و section_analytics لا تشمل internal_auditor → مخفية كلياً في nav.
> لكن بعض routes تسمح بالوصول:

| المسار | Route Status | Backend | القرار |
|---|---|---|---|
| `/delivery/reconciliation` | `:2012` — includes internal_auditor | `_RECON_READ_ROLES` ← يشمله | **IA-01 مُحسوم:** يُضاف للـ nav في section_delivery — قراءة فقط |
| `/delivery/branch-stats` | `:2017` — includes internal_auditor | VERIFIED | **IA-01 مُحسوم:** لا يُضاف للـ nav حالياً |
| `/delivery/brands` | `:2018` — includes internal_auditor | VERIFIED | **IA-01 مُحسوم:** لا يُضاف للـ nav حالياً |
| `/delivery/compliance` | `:2014` — includes internal_auditor | VERIFIED | **IA-01 مُحسوم:** يُضاف للـ nav في section_delivery — قراءة فقط |
| `/quality` (قائمة زيارات) | `:2026` — `_VIEW_ROLES` includes internal_auditor | VERIFIED | **IA-02 مُحسوم:** يُضاف للـ nav في section_quality_training — قراءة فقط |
| `/quality/open-actions` | `:2028` — includes internal_auditor | VERIFIED (READ — لا resolve) | **IA-02 مُحسوم:** يُضاف للـ nav — قراءة فقط |
| `/quality/:id` | `:2030` — includes internal_auditor | VERIFIED | **IA-02:** تفاصيل زيارة — مُضمَّن في nav list (لا بند مستقل) |
| `/documents` | `:2058` — includes internal_auditor | VERIFIED | **IA-03 مُحسوم:** يُضاف للـ nav في section_documents — قراءة فقط |
| `/documents/expiring` | `:2059` — includes internal_auditor | VERIFIED | **IA-03 مُحسوم:** يُضاف للـ nav — قراءة فقط |
| `/analytics/order-delay` | `:2075` — includes internal_auditor | VERIFIED | **IA-04 مُحسوم:** يُضاف للـ nav في section_analytics — قراءة فقط |
| `/analytics/branches-open-actions` | `:2076` — includes internal_auditor | VERIFIED | **IA-04 مُحسوم:** يُضاف للـ nav في section_analytics — قراءة فقط |

---

### قسم 4: باقي الأقسام

| القسم | الحالة |
|---|---|
| section_admin | ❌ admin/super_admin فقط — صحيح |
| `/quality/analytics` | ❌ internal_auditor ليس في allowed (:2029) — صحيح |
| `/audit/findings` لـ area_manager وoperations_manager | ✓ Route (:2044) يشملهم — موثَّق في X-02 |

---

### ملخص التغييرات — internal_auditor

| # | التغيير | النوع | الأولوية |
|---|---|---|---|
| IA-BUG-01 | **FIX-WH-01 (موثَّق سابقاً):** إزالة internal_auditor من write endpoints في warehouse_lines.py بتطبيق `is_read_only()` guard | **P0** | مُسجَّل |
| IA-01 | **مُحسوم:** يُضاف للـ nav في section_delivery: التسوية (`/delivery/reconciliation`) + الالتزام (`/delivery/compliance`) — قراءة فقط. لا يُضاف `/delivery/branch-stats` ولا `/delivery/brands` حالياً | Design resolved | PENDING IMPL |
| IA-02 | **مُحسوم:** يُضاف للـ nav في section_quality_training: قائمة الزيارات + الإجراءات المفتوحة + تحليلات الجودة (بعد توافق Route+Backend — QM-01) + تقييمات التدريب + تحليلات التدريب — كلها قراءة فقط | Design resolved | PENDING IMPL |
| IA-03 | **مُحسوم:** يُضاف للـ nav في section_documents: قائمة الوثائق + الوثائق المقاربة للانتهاء — قراءة فقط، لا إنشاء أو تعديل أو حذف | Design resolved | PENDING IMPL |
| IA-04 | **مُحسوم:** يُضاف للـ nav في section_analytics: تأخر الطلبات + الإجراءات التصحيحية للفروع — قراءة فقط | Design resolved | PENDING IMPL |

**Status: APPROVED CONCEPTUALLY — لا يصبح آمناً للتشغيل قبل إغلاق FIX-WH-01 P0 واختبارات 403 لكل عمليات الكتابة التشغيلية**

---

## admin / super_admin

> مصفوفة مدمجة مقابل الشجرة المعتمدة (10 أقسام). الهدف الوظيفي واحد لكليهما. الفوارق التقنية في التنفيذ الحالي مُوثَّقة في قسم مستقل أدناه.

### قواعد الرؤية

| القاعدة | admin | super_admin |
|---|---|---|
| `isElevatedUser` (Frontend) | ✓ — يرى كل nav بلا استثناء (جميع الأقسام) | ✓ |
| `isTrialLegacyBlocked()` | يعيد `false` — معفى من TrialLegacyRouteGuard | ✓ معفى |
| `require_roles()` backend | يُدرَج صراحةً في كل `allowed` tuple | bypass تلقائي — لا حاجة للإدراج |
| `can_access_branch()` | True دائماً — global scope | True دائماً |
| `can_access_warehouse()` | True دائماً — global scope | True دائماً |
| `_PLATFORM_ADMINS` (sales_permissions) | لا — يُدرَج فردياً في كل predicate | نعم — bypass تلقائي لكل predicates |

> **تحذير:** `require_roles()` bypass لـ super_admin يعطي Authorization فقط. لا ينشئ route مفقوداً، لا يضيف nav item، لا يبني صفحة، لا يصلح Scope. يجب اختبار super_admin على كل endpoint بشكل مستقل — بعض custom role checks تقع خارج الـ helper المركزي.

---

### القسم 1 — الرئيسية

| القائمة | Current Route | Current Nav | Target Nav | Backend Status | القرار |
|---|---|---|---|---|---|
| لوحة التحكم | `/dashboard` | YES — section_main (roles: []) | YES | VERIFIED | ✓ |
| الإشعارات | `/notifications` (:1990) | YES — section_main (roles: []) | YES | VERIFIED | ✓ |

---

### القسم 2 — التشغيل الحالي

> يدمج section_operations + section_supply_chain الحاليين. بعض عناصر section_operations تنتقل لأقسام أخرى (موثَّق أدناه).

| القائمة | Current Route | Current Nav | Target Nav | Backend Status | القرار |
|---|---|---|---|---|---|
| لوحة العمليات | `/operations` (:1975) | YES — section_operations | YES | VERIFIED | ✓ |
| متابعة سلسلة الإمداد | `/supply-chain/control` (:2049) | YES — section_supply_chain (REDIRECT) | YES — بعد بناء الصفحة | REQUIRED_FOR_NEW_MODULE | صفحة تُبنى |
| قائمة طلبات التوريد | `/supply-chain/branch-requests` (:2051) | YES — section_supply_chain | YES | VERIFIED | ✓ |
| اعتماد طلبات الفروع | `/supply-chain/approvals` (:2052) | YES — section_supply_chain | YES | VERIFIED | ✓ |
| أوامر الإنتاج | `/supply-chain/kitchen` (:2053) | YES — section_supply_chain | YES | VERIFIED | ✓ |
| تنفيذ المستودع | `/supply-chain/warehouse` (:2054) | YES — section_supply_chain | YES | VERIFIED | ✓ |
| أوامر التوصيل | `/supply-chain/delivery` (:2055) | YES — section_supply_chain | YES | VERIFIED | ✓ |
| إنشاء طلب توريد | `/supply-chain/branch-requests/new` | [إجراء داخل قائمة الطلبات] | — | NEEDS_VERIFICATION — Route مستقل أو modal داخل القائمة | إجراء — لا nav item مستقل |

**عناصر section_operations مُحسومة ومنقولة لأقسامها:**
- `/reports/inventory` → القسم 3 (المخزون والتحويلات) — موثَّق هناك
- `/reports/orders` → القسم 8 (التحليلات) — موثَّق هناك
- `/operations/branch-items` → القسم 9 (الإدارة) — موثَّق هناك

---

### القسم 3 — المخزون والتحويلات

| القائمة | Current Route | Current Nav | Target Nav | Backend Status | القرار |
|---|---|---|---|---|---|
| الجرد اليومي للفرع | `/inventory` (:1941) | YES — section_branch (roles: [branch_user, branch_manager]؛ admin يراه عبر isElevatedUser) | YES — يُنقل لـ section_inventory (ADM-05) | VERIFIED — RouteRoleGuard [branch_user, branch_manager, admin, super_admin] | ✓ (زر «إدخال جرد جديد» → `/inventory/new` داخل الصفحة) |
| مراجعة الجرد اليومي | `/reports/inventory` (:1994) | YES — section_operations (اسم مضلل: «تقارير المخزون») | YES — يُنقل لـ section_inventory ويُعاد بناء الـ component | EXISTS — COMPONENT REBUILD REQUIRED (يستخدم InventoryListPage حالياً) | نقل + إعادة بناء |
| أرصدة الفروع | `/branch-stock` (:1957) | YES — section_branch (roles include admin) | YES — ينتقل لـ section_inventory | VERIFIED | ✓ |
| أرصدة المستودعات | `/warehouse/stock` (:1965) | YES — section_warehouse (roles: [warehouse_user, warehouse_manager]؛ admin يراه عبر isElevatedUser) | YES — ينتقل لـ section_inventory (FIX-WH-02) | VERIFIED — ليس Legacy وظيفياً | ✓ (FIX-WH-02 + FIX-WH-03) |
| حركات المخزون | لا يوجد — صفحة جديدة | — | YES — يُبنى | REQUIRED_FOR_NEW_MODULE | صفحة جديدة |
| الجرد الفعلي | لا يوجد — صفحة جديدة | — | YES — يُبنى (يحتوي: قائمة جلسات الجرد + إنشاء جلسة [إجراء داخل الصفحة]) | REQUIRED_FOR_NEW_MODULE | صفحة جديدة |
| قائمة التحويلات بين الفروع | `/stock/inter-branch-transfer` (:1969) | YES — section_branch (roles include admin) | YES — ينتقل لـ section_inventory | VERIFIED | ✓ |
| إنشاء طلب تحويل | [إجراء داخل قائمة التحويلات] | — | — | VERIFIED | إجراء — لا nav item مستقل |
| اعتماد التحويلات | `/operations/inter-branch-approvals` (:1983) | YES — section_operations (roles include admin) | YES — ينتقل لـ section_inventory | VERIFIED | ✓ |

---

### القسم 4 — المراجعة الداخلية

| القائمة | Current Route | Current Nav | Target Nav | Backend Status | القرار |
|---|---|---|---|---|---|
| لوحة المراجعة | `/audit/dashboard` (:2039) | YES — section_audit | YES | VERIFIED | ✓ |
| مراجعة الطلبيات | `/audit/daily-orders` (:2040) + `/audit/order-history` (:2041) — بندان حالياً | YES (بندان) | YES — بند واحد + tabs | VERIFIED | ✓ |
| مخزون المستودعات | `/audit/warehouse-stock` (:2042) | YES | YES | VERIFIED | ✓ |
| طلبات تغييرات الأصناف | `/audit/item-change-requests` (:2043) | YES | YES | VERIFIED | ✓ |
| ملاحظات التدقيق | `/audit/findings` (:2044) | YES | YES | VERIFIED — ADM-03 يحكم التعديل | ✓ ADM-03 |
| سجل التدقيق | `/audit/trail` (:2045) | YES | YES | VERIFIED — append-only | ✓ |

---

### القسم 5 — قنوات المبيعات

> **ليست Legacy وظيفياً** — وحدة قنوات مبيعات حالية. وجودها في `LEGACY_TRIAL_BLOCKED_PATHS` سبب تقني (trial guard للأدوار التشغيلية). admin/super_admin معفيان منه.

| القائمة | Current Route | Current Nav | Target Nav | Backend Status | القرار |
|---|---|---|---|---|---|
| لوحة قنوات المبيعات | `/delivery` (:2009) | YES — section_delivery | YES | VERIFIED | ✓ |
| الإدخالات اليومية | `/delivery/daily-entry` (:2010) | YES (بلا sales_manager حالياً — FIX-SM-01) | YES | VERIFIED | ✓ |
| كشوف الحسابات | `/delivery/statements` (:2011) | YES | YES | VERIFIED | ✓ |
| التسوية | `/delivery/reconciliation` (:2012) | YES | YES | VERIFIED | ✓ |
| الإغلاقات | `/delivery/closures` (:2013) | YES | YES | VERIFIED | ✓ |
| الالتزام | `/delivery/compliance` (:2014) | YES | YES | VERIFIED | ✓ |
| أداء الفروع | `/delivery/branch-stats` (:2017) | YES | YES | VERIFIED | ✓ |
| أداء البراندات | `/delivery/brands` (:2018) | YES | YES | VERIFIED | ✓ |
| استيراد بيانات | `/delivery/import` (nav :86) | YES | YES | VERIFIED | ✓ |
| إدارة فروع التوصيل | `/delivery/branches` (:2016) | YES | YES | VERIFIED | ✓ |
| المعاملات غير المطابقة | `/delivery/unmatched` (:2019) | **NO nav item** — FIX-SM-02 | YES | VERIFIED | NAV_GAP — ينتظر FIX-SM-02 |

---

### القسم 6 — الجودة والتدريب

| القائمة | Current Route | Current Nav | Target Nav | Backend Status | القرار |
|---|---|---|---|---|---|
| قائمة الزيارات | `/quality` (:2026) | YES — section_quality_training | YES | VERIFIED | ✓ |
| الإجراءات المفتوحة | `/quality/open-actions` (:2028) | YES | YES | VERIFIED | ✓ |
| تحليلات الجودة | `/quality/analytics` (:2029) | YES | YES | VERIFIED — admin مُدرَج | ✓ |
| تقييمات التدريب | `/training` (:2033) | YES | YES | VERIFIED | ✓ |
| إنشاء تقييم | `/training/new` (:2034) | [إجراء داخل الصفحة] | — | VERIFIED | إجراء — لا nav item مستقل |
| تحليلات التدريب | `/training/analytics` (:2035) | YES | YES | VERIFIED | ✓ |

---

### القسم 7 — الوثائق والرخص

| القائمة | Current Route | Current Nav | Target Nav | Backend Status | القرار |
|---|---|---|---|---|---|
| الوثائق | `/documents` (:2058) | YES — section_documents | YES | VERIFIED | ✓ |
| الوثائق المقاربة للانتهاء | `/documents/expiring` (:2059) | YES | YES | VERIFIED | ✓ |
| إنشاء وثيقة | `/documents/new` (:2060) | [إجراء داخل الصفحة] | — | VERIFIED — admin مُدرَج | إجراء — لا nav item مستقل |

---

### القسم 8 — التحليلات

| القائمة | Current Route | Current Nav | Target Nav | Backend Status | القرار |
|---|---|---|---|---|---|
| اتجاه الاستهلاك | `/analytics/consumption-trend` (:2074) | YES — section_analytics | YES | VERIFIED | ✓ |
| تأخر الطلبات | `/analytics/order-delay` (:2075) | YES | YES | VERIFIED | ✓ |
| إجراءات الفروع المفتوحة | `/analytics/branches-open-actions` (:2076) | YES — section_analytics | YES | VERIFIED | ✓ |
| تقارير الطلبيات | `/reports/orders` (:2002) | YES — section_operations (ينتقل) | YES — ينتقل لـ section_analytics | VERIFIED | ✓ — يُنقل |

---

### القسم 9 — الإدارة

> مرئي لـ admin وsuper_admin. `/admin/sales-channels` يظهر أيضاً لـ sales_manager.

| القائمة | Current Route | Current Nav | Target Nav | Backend Status | القرار |
|---|---|---|---|---|---|
| المستخدمون | `/admin/users` (:2064) | YES — section_admin | YES | VERIFIED | ✓ |
| الفروع | `/admin/branches` (:2066) | YES | YES | VERIFIED | ✓ |
| المستودعات | `/admin/warehouses` (:2067) | YES | YES | VERIFIED | ✓ |
| المطابخ | `/admin/kitchens` (:2068) | YES | YES | VERIFIED | ✓ |
| الأصناف | `/admin/items` (:2065) | YES | YES | VERIFIED | ✓ |
| اقتراحات المساعد | `/admin/suggestions` (:2069) | YES | YES | VERIFIED | ✓ |
| الإعدادات | `/admin/settings` (:2071) | YES | YES | VERIFIED | ✓ |
| قنوات المبيعات | `/admin/sales-channels` (:2070) | YES — في section_delivery حالياً (FIX-SM-03) | YES — ينتقل لـ section_admin | VERIFIED — [sales_manager, admin, super_admin] | ✓ ينتظر FIX-SM-03 |
| موظفو الفروع | `/branch-employees` (:1958) | YES — section_branch (roles include admin) | YES — ينتقل لـ section_admin | VERIFIED | ✓ — يُنقل |
| ربط الأصناف بالفروع | `/operations/branch-items` (:1988) | YES — section_operations (roles include admin) | YES — ينتقل لـ section_admin | VERIFIED | ✓ — يُنقل |

---

### القسم 10 — النظام السابق (admin / super_admin فقط)

> يحتاج إنشاء `section_legacy` في AppLayoutV2 بـ `roles: ['admin', 'super_admin']` (ADM-04). `/warehouse/stock` **محذوف من هنا** — اعتُمد كصفحة حالية (أرصدة المستودعات في القسم 3).

#### نظام الفرع السابق

| القائمة | Current Route | Current Nav | Target Nav | Route Guard | القرار |
|---|---|---|---|---|---|
| الطلبات القديمة | `/orders` (:1944) | YES — section_branch (roles: [branch_user, branch_manager]؛ admin يراه عبر isElevatedUser) | YES — يُنقل لـ section_legacy | TrialLegacyRouteGuard | ✓ — يُنقل |
| الطلبية اليومية القديمة | `/orders/daily` (:1947) | YES — section_branch (roles include admin, super_admin) | YES — يُنقل لـ section_legacy | TrialLegacyRouteGuard | ✓ — يُنقل |
| الطلب الاستثنائي القديم | `/orders/exceptional` (:1945) | **NO nav item** | YES — يُضاف لـ section_legacy | TrialLegacyRouteGuard | يُضاف — ADM-04 |
| الاستلامات القديمة | `/receiving` (:1955) | YES — section_branch (roles: [branch_user, branch_manager]؛ admin يراه عبر isElevatedUser) | YES — يُنقل لـ section_legacy | TrialLegacyRouteGuard | ✓ — يُنقل |

#### نظام المستودع السابق

| القائمة | Current Route | Current Nav | Target Nav | Route Guard | القرار |
|---|---|---|---|---|---|
| قائمة الطلبيات القديمة | `/warehouse/orders` (:1961) | YES — section_warehouse (isElevatedUser) | YES — يُنقل لـ section_legacy | TrialLegacyRouteGuard | ✓ — يُنقل |
| التجهيز القديم | `/warehouse/picking` (:1963) | YES — section_warehouse (isElevatedUser) | YES — يُنقل لـ section_legacy | TrialLegacyRouteGuard | ✓ — يُنقل |
| الصرف القديم | `/warehouse/dispatch` (:1964) | YES — section_warehouse (isElevatedUser) | YES — يُنقل لـ section_legacy | TrialLegacyRouteGuard | ✓ — يُنقل |
| التقارير القديمة | `/warehouse/reports` (:1966) | YES — section_warehouse (isElevatedUser) | YES — يُنقل لـ section_legacy | TrialLegacyRouteGuard | ✓ — يُنقل |

---

### قيود ثابتة — لا يتجاوزها admin أو super_admin

| القيد | السبب |
|---|---|
| Audit Trail: لا DELETE ولا PATCH | الـ Trail append-only — محظور على مستوى service layer |
| فحص الكميات عند إرسال طلب | service layer يتحقق — لا bypass بالدور |
| قيود دورة الإنتاج | نفس service layer — القيود لا تُرفع بالدور |

---

### الفارق التقني في التنفيذ الحالي (ليس هدفاً وظيفياً)

| الجانب | admin الحالي | super_admin الحالي | الهدف الوظيفي |
|---|---|---|---|
| `require_roles()` | يُدرَج صراحةً في كل route | bypass تلقائي | الاثنان يملكان نفس الصلاحية — الفرق تنفيذي فقط |
| `audit_findings PATCH` | `created_by == current_user.id` فقط | يُعدِّل أي finding | **ADM-03:** admin يُعدِّل أي finding مع سبب + old_value + Audit Trail |
| `_is_platform_admin` (sales_permissions) | يُدرَج فردياً في كل predicate | bypass تلقائي | الاثنان يملكان كل صلاحيات sales |
| Endpoints مستقبلية | يحتاج إدراجاً صريحاً | يرث تلقائياً | يجب اختبار admin على كل endpoint جديد بشكل مستقل |

> ⚠️ **تحذير:** bypass `require_roles()` لـ super_admin يعطي Authorization فقط — لا ينشئ Route مفقوداً، لا يضيف nav item، لا يبني صفحة جديدة، لا يصلح Workflow أو Scope. يجب اختبار super_admin على كل endpoint بشكل مستقل، خصوصاً custom role checks خارج الـ helper المركزي.

---

### ملخص التغييرات — admin / super_admin

| # | التغيير | النوع | الأولوية | الحالة |
|---|---|---|---|---|
| ADM-01 | نقل `/admin/sales-channels` من section_delivery إلى section_admin في nav (FIX-SM-03) | nav fix | P1 | مُسجَّل في FIX-SM-03 |
| ADM-02 | إضافة `/delivery/daily-entry` لـ sales_manager في section_delivery nav (FIX-SM-01) | nav fix | P1 | مُسجَّل في FIX-SM-01 |
| **ADM-03** | **Audit Finding Parity:** admin يستطيع تعديل أي finding بشرط: سبب إلزامي في payload + حفظ old_value + تسجيل Audit Trail. لا تعديل صامت | Backend fix | **P1** | PENDING |
| **ADM-04** | **section_legacy:** إنشاء قسم "النظام السابق" في AppLayoutV2 بـ `roles: ['admin', 'super_admin']`. يحتوي: الطلبات القديمة + الطلبية اليومية + الطلب الاستثنائي + الاستلامات + طلبيات المستودع + التجهيز + الصرف + التقارير القديمة. تُنقل العناصر من section_branch وsection_warehouse الحاليين | nav build | **P1** | PENDING |
| **ADM-05** | **الجرد اليومي للفرع:** نقل بند `/inventory` من `section_branch` إلى `section_inventory` وإعادة تسميته «الجرد اليومي للفرع»؛ زر «إدخال جرد جديد» داخل الصفحة يفتح `/inventory/new` (إجراء — لا nav item مستقل) | nav move | P1 | PENDING |
| **ADM-06** | **تحقق شامل:** اختبار admin وsuper_admin على كل endpoint في: quality.py، audit_findings.py، sales_channels.py، delivery_analytics.py — تأكيد عدم وجود custom role checks خارج helper المركزي | Security verify | P1 | PENDING |

**Admin/Super Admin menu tree: APPROVED FOR IMPLEMENTATION PLANNING.**

Admin-specific completion remains pending: ADM-03, ADM-04, ADM-06, FIX-WH-02/03.

**Full Role Menu Matrix: APPROVED CONCEPTUALLY.**
Final verification remains pending according to the complete Fix Register, security investigations, scope checks, design decisions, and runtime retests.

---

*آخر تحديث: 2026-07-12*
