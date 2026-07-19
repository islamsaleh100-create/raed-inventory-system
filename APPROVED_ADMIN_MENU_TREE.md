# APPROVED_ADMIN_MENU_TREE
## شجرة قوائم Admin المعتمدة — نسخة كاملة

**التاريخ:** 2026-07-12
**الفرع:** `release/lan-trial-2026-06-16` @ `cd0739f`
**الحالة:** `APPROVED FOR ROLE-MATRIX DESIGN` — لا تنفيذ قبل اعتماد Role Menu Matrix

---

## ملاحظات عامة

- Admin يرى النظام القديم والجديد ويعمل في الاثنين
- super_admin يتجاوز كل Route Guard تلقائيًا
- admin مذكور صراحةً في كل `allowed[]` في الكود الحالي
- المسمى المعتمد: «طلبات» وليس «طلبيات» — استثناء واحد: «الطلبية اليومية» اسم الصفحة القديمة
- internal_auditor: قراءة وتصدير فقط في الجودة والتدريب والوثائق والتسوية والالتزام
- quality_visitor: زيارات الجودة فقط — بدون الإجراءات التصحيحية حتى تعديل Backend

---

## 1. الرئيسية

```
الرئيسية
├── لوحة التحكم                    /dashboard
│   الأدوار: الكل
└── الإشعارات                      /notifications
    الأدوار: الكل
```

---

## 2. التشغيل الحالي

```
التشغيل الحالي
│
├── لوحة العمليات                  /operations
│   الأدوار: operations_manager, admin, super_admin
│
├── متابعة سلسلة الإمداد           /supply-chain/control
│   الأدوار: جميع الأدوار التشغيلية + admin, super_admin
│   [صفحة جديدة مطلوبة — حاليًا redirect للـdashboard]
│
├── طلبات التوريد
│   ├── قائمة طلبات التوريد        /supply-chain/branch-requests
│   │   الأدوار: branch_user, branch_manager, area_manager,
│   │            internal_auditor, admin, super_admin
│   └── إنشاء طلب توريد           /supply-chain/branch-requests/new
│       الأدوار: branch_user, branch_manager, admin, super_admin
│       [Route جديد مطلوب — حاليًا يُفتح من داخل قائمة الطلبات]
│
├── اعتماد طلبات الفروع            /supply-chain/approvals
│   الأدوار: area_manager, internal_auditor, admin, super_admin
│
├── أوامر الإنتاج                  /supply-chain/kitchen
│   الأدوار: kitchen_section_manager, internal_auditor,
│            admin, super_admin
│
├── تنفيذ المستودع                 /supply-chain/warehouse
│   الأدوار: warehouse_user, warehouse_manager,
│            internal_auditor, admin, super_admin
│
└── أوامر التوصيل                  /supply-chain/delivery
    الأدوار: delivery_user, internal_auditor, admin, super_admin
```

**ملاحظة تنفيذ:** `/supply-chain/branch-requests/:id` موجود في الكود بـRoute مكسور (`\` بدل `/`) — يحتاج إصلاح.

---

## 3. المخزون والتحويلات

```
المخزون والتحويلات
│
├── الجرد اليومي للفرع
│   ├── سجل الجردات                /inventory
│   │   الأدوار: branch_user, branch_manager, admin, super_admin
│   └── إدخال جرد جديد            /inventory/new
│       الأدوار: branch_user, branch_manager, admin, super_admin
│
├── مراجعة الجرد اليومي            /reports/inventory
│   الأدوار: area_manager, operations_manager,
│            internal_auditor, admin, super_admin
│   [component مستقل مطلوب — حاليًا نفس InventoryListPage]
│   الوظيفة: كل الفروع، الفروع التي سجلت، التي لم تسجل،
│             الفروقات، المقارنة، التصدير
│
├── أرصدة الفروع                   /branch-stock
│   الأدوار: branch_user, branch_manager, area_manager,
│            operations_manager, internal_auditor,
│            admin, super_admin
│   ملاحظة: area_manager يرى فروع منطقته — Backend يطبق النطاق
│
├── أرصدة المستودعات               /warehouse/stock
│   الأدوار: warehouse_user, warehouse_manager,
│            internal_auditor, admin, super_admin
│   ملاحظة: Admin يختار أي مستودع — canSelectWarehouse=isAdmin
│
├── حركات المخزون                  [Route جديد — وحدة جديدة مطلوبة]
│   الأدوار: branch_manager, warehouse_manager,
│            operations_manager, internal_auditor,
│            admin, super_admin
│   الوظيفة: read-only — لا تعديل ولا حذف للحركة
│   الفلاتر: المستودع/الفرع، الصنف، نوع الحركة، التاريخ،
│             المستخدم، رقم الطلب، المرجع التشغيلي
│   النطاق: branch_manager = فرعه، warehouse_manager = مستودعه،
│           Backend يطبق النطاق
│
├── الجرد الفعلي                   [وحدة Full Stack جديدة مطلوبة]
│   ├── جلسات الجرد                [Route جديد]
│   │   الأدوار: branch_manager, warehouse_manager,
│   │            operations_manager, internal_auditor,
│   │            admin, super_admin
│   └── إنشاء جلسة جرد            [Route جديد]
│       الأدوار: branch_manager, warehouse_manager,
│                admin, super_admin
│   دورة الحالة: مسودة → مفتوح → تم الإدخال →
│               بانتظار المراجعة → معتمد → تم ترحيل التسوية
│   حالات إضافية: مرفوض، ملغي، يحتاج إعادة عد
│
└── التحويلات بين الفروع
    ├── قائمة التحويلات            /stock/inter-branch-transfer
    │   الأدوار: branch_manager, area_manager,
    │            operations_manager, admin, super_admin
    ├── إنشاء طلب تحويل           [داخل صفحة التحويلات أو Route مستقل]
    │   الأدوار: branch_manager, admin, super_admin
    └── اعتماد التحويلات           /operations/inter-branch-approvals
        الأدوار: area_manager, operations_manager,
                 admin, super_admin
```

**قيود تنفيذ القسم الثالث:**
1. حركات المخزون: يتحدد حجم Backend بعد فحص وجود جدول `stock_movements`
2. الجرد الفعلي: وحدة Full Stack مستقلة — نماذج + migrations + روتر + frontend
3. area_manager على `/branch-stock`: Backend يفلتر بـ`City + Brand` + اختبار سلبي

---

## 4. المراجعة الداخلية

```
المراجعة الداخلية
│
├── لوحة المراجعة الداخلية        /audit/dashboard
│   الأدوار: internal_auditor, admin, super_admin
│   المحتوى: ملاحظات مفتوحة، اعتمادات سريعة مشبوهة،
│             صرف جزئي بدون سبب، ازدحام سلسلة الإمداد
│
├── مراجعة الطلبات                /audit/orders
│   الأدوار: internal_auditor, admin, super_admin
│   [Route جديد يدمج daily-orders وorder-history في صفحة واحدة]
│   Tab 1: طلبات اليوم     ← todayOnly=true, scopeAll
│   Tab 2: سجل الطلبات    ← scopeAll, بلا فلتر تاريخ
│   [تبقى الروابط القديمة كـRedirects:
│    /audit/daily-orders  → /audit/orders?tab=today
│    /audit/order-history → /audit/orders?tab=history]
│
├── مراجعة مخزون المستودعات       /audit/warehouse-stock
│   الأدوار: internal_auditor, admin, super_admin
│   الوضع: قراءة فقط
│   [إصلاح مطلوب: تطبيق is_read_only() في warehouse router]
│
├── ملاحظات المراجعة              /audit/findings
│   الأدوار في Nav:
│     internal_auditor → جميع الملاحظات + إنشاء
│     admin, super_admin → جميع الملاحظات + إنشاء + إغلاق
│     area_manager → ملاحظات نطاقه + إقرار ورد
│     operations_manager → ملاحظات العمليات + إقرار ورد
│   [مطلوب: Backend Scope لـarea_manager وops_manager]
│
├── طلبات تغيير الأصناف           /audit/item-change-requests
│   الأدوار: internal_auditor (اعتماد/رفض), admin, super_admin
│   [تحسين مطلوب: استبدال window.prompt بـModal حقيقي]
│
├── سجل العمليات                  /audit/trail
│   الأدوار: internal_auditor, admin, super_admin
│   [إضافة لاحقة: modules inventory وstock_movements وphysical_inventory]
│
├── مراجعة جلسات الجرد            /audit/physical-inventory
│   الأدوار: internal_auditor, admin, super_admin
│   [يُبنى مع وحدة الجرد الفعلي — read-only للمراجع]
│
└── مراجعة حركات المخزون          /audit/stock-movements
    الأدوار: internal_auditor, admin, super_admin
    [يُبنى مع وحدة الحركات — read-only للمراجع]
```

**Fix Brief — Audit-01:**
ملف: `backend/app/routers/warehouse.py`
المطلوب: تطبيق `is_read_only(get_user_roles(current_user))` في كل write endpoint
الاختبار: internal_auditor يحاول POST/PATCH → 403

---

## 5. قنوات المبيعات

⚠ **تعارض تنفيذي:** جميع `/delivery/*` ملفوفة حاليًا بـ`TrialLegacyRouteGuard` — هذا يعني بعض الأدوار المستهدفة (branch_manager، area_manager، ops، internal_auditor) قد تُمنع رغم إضافتها للNav. قنوات المبيعات Module حالي مستقل وليس نظامًا قديمًا. عند التنفيذ: لكل route في هذا القسم — تأكد أنه ليس legacy، أزل الـLegacy blocking غير المناسب، احتفظ بـRBAC Guard، واختبر Nav + Route + Backend scope.

```
قنوات المبيعات
│                                   [تحتاج مراجعة TrialLegacyRouteGuard لكل route]
├── لوحة متابعة المبيعات           /delivery
│   الأدوار: sales_manager, operations_manager,
│            area_manager, admin, super_admin
│
├── الإدخال اليومي                 /delivery/daily-entry
│   الأدوار: branch_manager, sales_manager,
│            area_manager, admin, super_admin
│
├── كشوف الحسابات                  /delivery/statements
│   الأدوار: sales_manager, admin, super_admin
│
├── التسوية                        /delivery/reconciliation
│   الأدوار: branch_manager, area_manager, operations_manager,
│            sales_manager, internal_auditor, admin, super_admin
│   internal_auditor: قراءة ومراجعة فقط
│
├── إقفال الفترات                  /delivery/closures
│   الأدوار: sales_manager, admin, super_admin
│
├── الالتزام                       /delivery/compliance
│   الأدوار: branch_manager, area_manager, operations_manager,
│            sales_manager, internal_auditor, admin, super_admin
│   internal_auditor: قراءة ومراجعة فقط
│
├── أداء الفروع                    /delivery/branch-stats
│   الأدوار: sales_manager, operations_manager,
│            area_manager, admin, super_admin
│
├── أداء العلامات التجارية         /delivery/brands
│   الأدوار: sales_manager, operations_manager,
│            area_manager, admin, super_admin
│
├── استيراد البيانات               /delivery/import
│   الأدوار: sales_manager, admin, super_admin
│
├── ربط فروع قنوات المبيعات        /delivery/branches
│   الأدوار: sales_manager, admin, super_admin
│
└── المعاملات غير المطابقة         /delivery/unmatched
    الأدوار: sales_manager, admin, super_admin
    [كانت orphan route — تُضاف للNav]
```

---

## 6. الجودة والتدريب

```
الجودة والتدريب
│
├── الجودة
│   ├── زيارات الجودة              /quality
│   │   الأدوار في Nav:
│   │     quality_visitor: يرى ويُنشئ ويراجع زياراته
│   │     quality_manager, branch_manager, area_manager,
│   │     internal_auditor, admin, super_admin: كل الزيارات
│   │   ملاحظة: quality_visitor لا يصل للإجراءات التصحيحية
│   │           حتى تعديل Backend — دوره الحالي محدود
│   │
│   ├── الإجراءات التصحيحية المفتوحة  /quality/open-actions
│   │   الأدوار: quality_manager, branch_manager, area_manager,
│   │            internal_auditor, admin, super_admin
│   │   [quality_visitor مستبعد حتى قرار Backend]
│   │
│   └── تحليلات الجودة             /quality/analytics
│       الأدوار: quality_manager, branch_manager, area_manager,
│                internal_auditor, admin, super_admin
│
└── التدريب
    ├── التقييمات التدريبية         /training
    │   الأدوار: area_manager, branch_manager, quality_manager,
    │            operations_manager, internal_auditor,
    │            admin, super_admin
    │
    └── تحليلات التدريب            /training/analytics
        الأدوار: quality_manager, operations_manager,
                 internal_auditor, admin, super_admin
```

**صلاحية internal_auditor في هذا القسم:** قراءة وتصدير فقط — لا إنشاء زيارة، لا إنشاء تقييم، لا تغيير حالة.
⚠ المنع حسب Module وليس منعًا عامًا:
- في التشغيل والمخزون والجودة والتدريب والوثائق والمبيعات: منع POST/PATCH/PUT/DELETE
- في قسم المراجعة الداخلية: مسموح بإنشاء ملاحظة + تحديث ملاحظاته + اعتماد/رفض طلب تعديل صنف
- في كل الحالات: لا تعديل على الطلبات أو الإنتاج أو المخزون نفسه
الـBanner في ar.json توثيق UI فقط — ليس حماية. المطلوب: إخفاء أزرار + Backend 403 + اختبارات سلبية لكل module.

**إجراءات داخل الصفحات (بدون nav entry):**
- إنشاء زيارة جودة: quality_visitor, quality_manager, admin
- إنشاء تقييم تدريبي: area_manager, admin

---

## 7. الوثائق والرخص

```
الوثائق والرخص
│
├── قائمة الوثائق                  /documents
│   الأدوار في Nav:
│     admin, super_admin, area_manager, branch_manager,
│     quality_manager, warehouse_manager, internal_auditor
│   internal_auditor: قراءة وتصدير فقط
│
└── الوثائق المقاربة للانتهاء      /documents/expiring
    الأدوار: نفس السابق

إجراءات داخل الصفحات:
  إنشاء وثيقة جديدة → admin, area_manager, branch_manager, quality_manager
  [warehouse_manager وinternal_auditor: قراءة فقط]
```

---

## 8. التحليلات

```
التحليلات
│
├── تقارير الطلبات                 /reports/orders
│   الأدوار: operations_manager, admin, super_admin
│   [نُقل من section_operations — تقرير إداري وليس تشغيلًا]
│
├── اتجاه الاستهلاك                /analytics/consumption-trend
│   الأدوار: branch_manager, warehouse_manager, area_manager,
│            operations_manager, admin, super_admin
│
├── تأخر الطلبات                   /analytics/order-delay
│   الأدوار: operations_manager, warehouse_manager,
│            area_manager, internal_auditor,
│            admin, super_admin
│
└── الإجراءات التصحيحية للفروع     /analytics/branches-open-actions
    الأدوار: quality_manager, area_manager, operations_manager,
             internal_auditor, admin, super_admin
```

---

## 9. إدارة النظام

```
إدارة النظام
│
├── المستخدمون والصلاحيات          /admin/users
│   الأدوار: admin, super_admin
│
├── الفروع                         /admin/branches
│   الأدوار: admin, super_admin
│
├── موظفو الفروع                   /branch-employees
│   الأدوار: branch_manager, admin, super_admin
│
├── المستودعات                     /admin/warehouses
│   الأدوار: admin, super_admin
│
├── المطابخ وأقسام الإنتاج         /admin/kitchens
│   الأدوار: admin, super_admin
│
├── دليل الأصناف                   /admin/items
│   الأدوار: admin, super_admin
│
├── ربط الأصناف بالفروع            /operations/branch-items
│   الأدوار: area_manager, admin, super_admin
│
├── إعدادات قنوات المبيعات         /admin/sales-channels
│   الأدوار: sales_manager, admin, super_admin
│   [نُقلت من nav.section_delivery]
│
├── اقتراحات المساعد               /admin/suggestions
│   الأدوار: admin, super_admin
│
└── إعدادات النظام                 /admin/settings
    الأدوار: admin, super_admin
```

---

## 10. النظام السابق

```
النظام السابق                      [جميع الصفحات: TrialLegacyRouteGuard]
│                                   [مرئية للـAdmin دائمًا — مخفية للأدوار التشغيلية]
│
├── نظام الفرع السابق
│   ├── طلبات الفروع القديمة        /orders
│   │   الأدوار: branch_user, branch_manager, area_manager,
│   │            operations_manager, internal_auditor,
│   │            admin, super_admin
│   │
│   ├── الطلبية اليومية القديمة     /orders/daily
│   │   الأدوار: branch_manager, admin, super_admin
│   │
│   ├── الطلب الاستثنائي القديم     /orders/exceptional
│   │   الأدوار: branch_user, branch_manager,
│   │            admin, super_admin
│   │   [كانت orphan route — تُضاف للNav]
│   │
│   └── استلامات الفروع القديمة    /receiving
│       الأدوار: branch_user, branch_manager,
│                admin, super_admin
│
└── نظام المستودع السابق
    ├── طلبات المستودع القديمة      /warehouse/orders
    │   الأدوار: warehouse_user, warehouse_manager,
    │            internal_auditor, admin, super_admin
    │
    ├── تجهيز المستودع القديم       /warehouse/picking
    │   الأدوار: warehouse_user, warehouse_manager,
    │            admin, super_admin
    │
    ├── صرف المستودع القديم         /warehouse/dispatch
    │   الأدوار: warehouse_user, warehouse_manager,
    │            admin, super_admin
    │
    └── تقارير المستودع القديمة     /warehouse/reports
        الأدوار: warehouse_user, warehouse_manager,
                 admin, super_admin
```

**ملاحظة تنفيذية:** `/warehouse/stock` موجود في **المخزون والتحويلات** كصفحة حالية نشطة — لا يُكرر هنا.
عند التنفيذ يجب إخراجه من `LEGACY_TRIAL_BLOCKED_PATHS` حتى يراه warehouse_manager/user باعتباره صفحة حالية وليس legacy.

---

## صفحات وRoutes جديدة أو مطلوب استكمالها

| العنصر | الحالة | المطلوب |
|---|---|---|
| `/supply-chain/control` | Route موجود — يعمل Redirect | بناء الصفحة |
| `/reports/inventory` | Route موجود — component مشترك مع `/inventory` | component مستقل |
| `/supply-chain/branch-requests/new` | Route غير موجود | Route + صفحة جديدة |
| `/audit/orders` | Route غير موجود | Route + صفحة بـTabs يدمج daily-orders وorder-history |
| حركات المخزون | Route وصفحة غير موجودَين | فحص DB أولًا ثم Route + وحدة |
| الجرد الفعلي | Routes وصفحات غير موجودة | وحدة Full Stack مستقلة |
| `/audit/physical-inventory` | Route غير موجود | يُبنى مع وحدة الجرد الفعلي |
| `/audit/stock-movements` | Route غير موجود | يُبنى مع وحدة الحركات |

## Routes تُحوَّل لـRedirects (لا تُلغى)

لا نحذف الروابط القديمة حفاظًا على Favorites والروابط المحفوظة:

| Route القديم | Redirect إلى |
|---|---|
| `/audit/daily-orders` | `/audit/orders?tab=today` |
| `/audit/order-history` | `/audit/orders?tab=history` |

## إصلاحات تقنية مطلوبة قبل التنفيذ

| الإصلاح | الملف | الأولوية |
|---|---|---|
| `/supply-chain/branch-requests/:id` — كود المصدر يحتوي `\` بدل `/` | `App.jsx` | SOURCE_DEFECT_FOUND / RUNTIME_RETEST_REQUIRED — لا أمر إصلاح قبل تأكيد الفشل على Runtime المرجعي |
| `is_read_only()` غير مطبقة في warehouse router | `routers/warehouse.py` | حرجة |
| Backend Scope لـarea_manager وops_manager في `/audit/findings` | `routers/audit_findings.py` | عالية |
| hardcoded labels: `أصناف الفروع` و`طلبات تغييرات الأصناف` | `AppLayoutV2.jsx` | منخفضة |
