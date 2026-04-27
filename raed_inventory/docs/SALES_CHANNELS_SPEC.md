# مشروع: توحيد قنوات البيع والمطابقة المالية

**Sales Channels Unification & Reconciliation System**

- **اسم الموديول في الكود:** `sales_channels`
- **الإصدار:** v3 (نهائي — جاهز للتنفيذ)
- **التاريخ:** 2026-04-21
- **الحالة:** Approved — المرحلة ١ مُرخَّصة للبدء
- **المستفيدون:** مدير الفرع، مدير المنطقة، مدير المبيعات والتوصيل، الإدارة العامة
- **العلاقة بالكود الحالي:** توسعة لقسم `delivery_analytics` الموجود

## تغييرات v3 عن v2

- **إضافة `orders_count`** إلى `branch_daily_sales` و `app_monthly_statements` — **إجباري للـ delivery_app، ممنوع للـ payment_method**
- **شاشة الإدخال اليومي:** خانتان لكل تطبيق (عدد + قيمة)، خانة واحدة لطرق الدفع (قيمة فقط)
- **المطابقة ثنائية البُعد:** count + amount
- **قاعدة صريحة لـ `variance_percent`** عند `app_reported_amount = 0`
- **Partial unique indexes + CHECK** على `monthly_closures` بدل UNIQUE بسيط
- **توضيح `commission_rate`:** الافتراضي (sales_channels) vs snapshot (app_monthly_statements)
- **Glossary** لمصطلح "استثنائي" في RBAC

---

## ١) الهدف

توسيع قسم "التوصيل" الحالي ليصبح **نظام متكامل لقنوات البيع**، مع **إدخال مزدوج** يكشف الفروقات بين ما يُسجَّل في الفرع يومياً وما يُعلنه كل تطبيق شهرياً، لتحقيق:

- معرفة دقيقة لمبيعات كل فرع يومياً (عدد طلبات + قيمة)
- كشف التسرّب والأخطاء التشغيلية
- ضمان دقة التحويلات المالية من منصات التوصيل
- مقارنة أداء الفروع والتطبيقات بموضوعية (AOV ثنائي البُعد)

---

## ٢) القنوات المشمولة في MVP (١٠ قنوات)

### أ) تطبيقات التوصيل الخارجية — ٧ تطبيقات

| # | الاسم العربي | الاسم الإنجليزي | Code |
|---|---|---|---|
| 1 | جاهز | Jahez | `jahez` |
| 2 | هنجرستيشن | HungerStation | `hungerstation` |
| 3 | كيتا | Keeta | `keeta` |
| 4 | نينجا | Ninja | `ninja` |
| 5 | ذا شيفز | The Chefz | `thechefz` |
| 6 | نون | Noon Food | `noon` |
| 7 | تو يو | ToYou | `toyou` |

### ب) طرق الدفع داخل الفرع — ٣ طرق

| # | الاسم العربي | الاسم الإنجليزي | Code |
|---|---|---|---|
| 1 | كاش | Cash | `cash` |
| 2 | مدي | Mada | `mada` |
| 3 | ماستركارد | Mastercard | `mastercard` |

### ج) مُعلَّق خارج MVP

| الاسم | الحالة | السبب |
|---|---|---|
| Koinz (كوينز) | معلَّق | آلية التحصيل غير واضحة (قناة دفع كاملة، خصم ولاء، أو loyalty adjustment). يُدرَج بعد قرار الإدارة. |

---

## ٣) المفهوم الأساسي — الإدخال المزدوج

### المستوى الأول: إدخال يومي من الفرع
مدير الفرع يُدخل في نهاية الدوام من كل القنوات العشرة:
- **للتطبيقات:** عدد الطلبات + قيمة المبيعات
- **لطرق الدفع:** قيمة المبيعات فقط

### المستوى الثاني: إدخال شهري من مدير المبيعات
عند استلام كشف كل تطبيق، يرفعه (CSV أو يدوي) مع:
- قيمة كشف التطبيق لكل فرع
- عدد الطلبات (إذا أتاحه التطبيق)
- نسبة العمولة المعتمدة لهذا الشهر

### المقارنة الشهرية (Reconciliation):
مقارنة ثنائية البُعد لكل (فرع × تطبيق × شهر):
- فارق القيمة (amount variance)
- فارق العدد (count variance) — حين يكون متاحاً من التطبيق

---

## ٣.١) تعريف `amount` (معتمد)

```
amount = branch gross amount
       = إجمالي المبيعات المنفَّذة فعلياً في الفرع لذلك اليوم،
         شامل الضريبة، قبل عمولة التطبيق،
         كما يسجّلها الفرع تشغيلياً دون انتظار تسويات التطبيق الشهرية
```

**تفصيل:**
- **شامل الضريبة** (VAT 15%) — الرقم التشغيلي الكامل
- **قبل العمولة** — الخصم يحسبه النظام تلقائياً من كشف التطبيق
- **يعكس إدخال الفرع فقط** — لا يُنتظر من الفرع رصد المرتجعات/الإلغاءات التي لا تظهر إلا في كشف التطبيق الشهري
- **الفارق مقصود** — المرتجعات والخصومات والتسويات تظهر طبيعياً كفارق في تقرير المطابقة الشهري

---

## ٣.٢) تعريف `orders_count` (جديد في v3)

```
orders_count = عدد الطلبات المنفَّذة فعلياً في الفرع لذلك اليوم عبر التطبيق المحدد
```

**قواعد العمل:**

| نوع القناة | orders_count | amount |
|---|---|---|
| `delivery_app` | ✅ **إجباري** | ✅ إجباري |
| `payment_method` | ❌ **ممنوع (NULL)** | ✅ إجباري |

**قواعد التحقق:**
- `type='delivery_app'` AND `amount > 0` → `orders_count > 0` إجباري
- `type='delivery_app'` AND `amount = 0` → `orders_count = 0` مسموح (لا طلبات ذلك اليوم)
- `type='payment_method'` → `orders_count IS NULL` دائماً
- في `app_monthly_statements`: `orders_count` اختياري (بعض التطبيقات لا يُتيحه)

**لماذا التمييز:**
- طلب واحد قد يُقسَّم بين أكثر من طريقة دفع (جزء كاش + جزء مدي)، فلا معنى لعدّه في طريقة معيّنة
- التطبيقات تُصدر رقم الطلب بوضوح، فلا غموض

---

## ٣.٣) العلاقات الحسابية

```
-- على مستوى القيمة (لكل الأنواع)
branch_monthly_total  = Σ (branch_daily_sales.amount) عن الشهر
app_reported_amount   = القيمة في كشف التطبيق الرسمي
commission_amount     = app_reported_amount × commission_rate
net_amount            = app_reported_amount − commission_amount

-- على مستوى العدد (delivery_app فقط)
branch_monthly_count  = Σ (branch_daily_sales.orders_count) عن الشهر
app_reported_count    = عدد الطلبات في كشف التطبيق

-- حساب الفارق للقيمة
variance_amount       = branch_monthly_total − app_reported_amount

IF app_reported_amount = 0:
    IF branch_monthly_total = 0  → variance_percent = 0,    status = 'match'
    IF branch_monthly_total > 0  → variance_percent = 'N/A', status = 'major'
ELSE:
    variance_percent  = variance_amount / app_reported_amount × 100

-- AOV (Average Order Value) — delivery_app فقط
aov_branch  = branch_monthly_total / branch_monthly_count   (إذا count > 0)
aov_app     = app_reported_amount / app_reported_count      (إذا count > 0)
```

---

## ٤) نموذج البيانات (Data Model)

### جدول `sales_channels` — تعريف القنوات

```
id                INT PK
code              VARCHAR(30) UNIQUE         -- 'jahez', 'cash', ...
name_ar           VARCHAR(100)
name_en           VARCHAR(100)
type              ENUM('delivery_app', 'payment_method')
commission_rate   DECIMAL(5,2) NULL          -- النسبة الافتراضية الحالية (delivery_app فقط)
is_active         BOOLEAN DEFAULT true
sort_order        INT
created_at        TIMESTAMP
```

> **commission_rate هنا** = النسبة الافتراضية الحالية للتطبيق، قابلة للتعديل من شاشة "إعدادات العمولات".

### جدول `branch_daily_sales` — مبيعات الفرع اليومية

```
id                INT PK
branch_id         INT FK -> branches
sales_date        DATE
channel_id        INT FK -> sales_channels
amount            DECIMAL(12,2) NOT NULL
orders_count      INT NULL                   -- إجباري لـ delivery_app، NULL لـ payment_method

-- Audit fields
submitted_at      TIMESTAMP NOT NULL
submitted_by      INT FK -> users NOT NULL
last_edited_at    TIMESTAMP NULL
last_edited_by    INT FK -> users NULL
edit_reason       TEXT NULL

UNIQUE (branch_id, sales_date, channel_id)
INDEX  (branch_id, sales_date)
INDEX  (sales_date)
```

**Validation على مستوى Service Layer:**
```python
if channel.type == 'delivery_app':
    assert orders_count is not None
    if amount > 0:
        assert orders_count > 0
elif channel.type == 'payment_method':
    assert orders_count is None
```

> `is_locked` لا يُخزَّن — يُشتق من `monthly_closures` عبر JOIN أو computed property.

### جدول `app_monthly_statements` — كشوف التطبيقات

```
id                    INT PK
channel_id            INT FK -> sales_channels (حيث type='delivery_app')
branch_id             INT FK -> branches
statement_month       CHAR(7)                 -- 'YYYY-MM'
app_reported_amount   DECIMAL(12,2) NOT NULL
app_reported_count    INT NULL                -- اختياري، حين يُتيحه التطبيق
commission_rate       DECIMAL(5,2) NOT NULL   -- snapshot وقت الإدخال
commission_amount     DECIMAL(12,2)           -- محسوب: amount × rate
net_amount            DECIMAL(12,2)           -- محسوب: amount − commission
import_source         ENUM('manual', 'csv')
csv_filename          VARCHAR(255) NULL
created_by            INT FK -> users
created_at            TIMESTAMP
updated_at            TIMESTAMP

UNIQUE (channel_id, branch_id, statement_month)
```

> **commission_rate هنا** = snapshot تاريخي مجمَّد وقت إنشاء الكشف. لو تغيّرت النسبة الافتراضية لاحقاً في `sales_channels`، يبقى هذا السجل بنسبته الأصلية — وهذا المعتمد في المطابقة والتقارير التاريخية.

> **المرحلة ٢.١:** سيُضاف لاحقاً: `payout_date`, `bank_reference`, `statement_reference` لربط الأرقام بالتحويلات البنكية.

### جدول `monthly_closures` — إقفال الشهور

```
id                INT PK
month             CHAR(7) NOT NULL            -- 'YYYY-MM'
scope_type        ENUM('all', 'branch') NOT NULL
branch_id         INT FK -> branches NULL     -- NOT NULL حين scope_type='branch'
closed_by         INT FK -> users NOT NULL
closed_at         TIMESTAMP NOT NULL
reopen_reason     TEXT NULL
reopened_by       INT FK -> users NULL
reopened_at       TIMESTAMP NULL

-- CHECK constraint
CHECK (
  (scope_type = 'all' AND branch_id IS NULL)
  OR
  (scope_type = 'branch' AND branch_id IS NOT NULL)
)
```

**Partial unique indexes (PostgreSQL):**
```sql
CREATE UNIQUE INDEX ux_closures_all
  ON monthly_closures (month)
  WHERE scope_type = 'all';

CREATE UNIQUE INDEX ux_closures_branch
  ON monthly_closures (month, branch_id)
  WHERE scope_type = 'branch';
```

> **ملاحظة SQLite (development):** SQLite يدعم partial indexes منذ v3.8. في حالة استخدام قاعدة بيانات لا تدعمها، يُضاف check إضافي في service layer يمنع التكرار.

**قواعد القفل:**
- `scope_type='all'` + `branch_id=NULL` → قفل شامل على كل الفروع لهذا الشهر
- `scope_type='branch'` + `branch_id=X` → قفل جزئي على فرع محدد
- بعد القفل: لا `INSERT/UPDATE/DELETE` على `branch_daily_sales` أو `app_monthly_statements` لهذا النطاق
- إعادة الفتح: `sales_manager` أو `super_admin` + `reopen_reason` إجباري

### جدول `reconciliation_snapshots` — يُولَّد عند القفل

```
id                     INT PK
closure_id             INT FK -> monthly_closures
channel_id             INT FK -> sales_channels
branch_id              INT FK -> branches
statement_month        CHAR(7)

-- Amount reconciliation
branch_total           DECIMAL(12,2)
app_total              DECIMAL(12,2)
variance_amount        DECIMAL(12,2)
variance_percent       DECIMAL(5,2) NULL       -- NULL عند app_total = 0 و branch_total > 0

-- Count reconciliation (delivery_app only)
branch_count           INT NULL
app_count              INT NULL
count_variance         INT NULL

-- Status
status                 ENUM('match', 'minor', 'major') NOT NULL
commission_rate_used   DECIMAL(5,2) NULL
generated_at           TIMESTAMP NOT NULL
```

> قبل القفل: المطابقة تُحسب **on-demand** (بدون snapshot). عند القفل: توليد snapshot مجمَّد لكل (branch × channel) للشهر.

---

## ٥) الصلاحيات (RBAC) — v3

### جدول الصلاحيات

| الدور | إدخال يومي بالفرع | كشوف التطبيقات | إعدادات العمولات | شاشة المطابقة | قفل الشهر |
|---|---|---|---|---|---|
| `branch_manager` | ✅ فرعه فقط (تعديل خلال ٢٤س) | ❌ | ❌ | قراءة فرعه | ❌ |
| `area_manager` | **استثنائي** + يوافق على تعديل > ٢٤س | ❌ | ❌ | قراءة منطقته | ❌ |
| `sales_manager` | استثنائي لكل الفروع + يوافق أي وقت | ✅ إدخال + رفع | ✅ كامل | ✅ كامل | ✅ قفل/فتح |
| `operations_manager` | ❌ | ❌ | ❌ | قراءة فقط | ❌ |
| `super_admin` | ✅ | ✅ | ✅ | ✅ | ✅ |

### Glossary — تعريف "استثنائي"

```
استثنائي (Exceptional):
  - ليس مسار التشغيل الافتراضي لهذا الدور
  - يُستخدم فقط عند تعذّر المسار الطبيعي (غياب/عطل/خطأ)
  - يستلزم edit_reason نصي إجباري
  - يُسجَّل في audit trail مع user_id والتاريخ
  - يظهر مميَّزاً في شاشة Compliance Dashboard
```

### تطبيق الـ RBAC على الأدوار

**`area_manager`:** الدور الطبيعي = مراجعة + اعتماد + الإدخال الاستثنائي فقط. ليس مسؤولاً عن الإدخال اليومي بديلاً عن الفرع.

**`sales_manager`:** الدور الطبيعي = كشوف التطبيقات + المطابقة + القفل. الإدخال اليومي مسار استثنائي يُسجَّل في audit trail.

---

## ٦) الشاشات المطلوبة (٧ شاشات)

### شاشة ١: الإدخال اليومي — مدير الفرع

- محدد التاريخ (افتراضي: اليوم)
- **قسم التطبيقات (٧ تطبيقات):** خانتان لكل صف — `عدد الطلبات` + `القيمة`
- **قسم طرق الدفع (٣ طرق):** خانة واحدة لكل صف — `القيمة` فقط
- مجموع تلقائي: إجمالي القيمة + إجمالي عدد طلبات التوصيل
- زر "حفظ"
- جدول سجل آخر ٣٠ يوم مع حالة القفل لكل يوم
- تحقق: لا إدخال مكرر، المبالغ >= 0، قواعد orders_count حسب النوع، الشهر غير مقفول

**Layout مقترح:**
```
┌─ تطبيقات التوصيل ─────────────────────┐
│ التطبيق    | عدد الطلبات | القيمة (ر.س) │
│ جاهز       |      32     |   1,450.00  │
│ هنجرستيشن  |      28     |   1,200.00  │
│ كيتا       |      15     |     680.00  │
│ ...                                     │
├─ طرق الدفع في الفرع ──────────────────┤
│ الطريقة   | القيمة (ر.س)               │
│ كاش       |   850.00                   │
│ مدي       | 2,100.00                   │
│ ماستركارد |   430.00                   │
├─ الإجمالي ──────────────────────────────┤
│ إجمالي الطلبات (توصيل): 75              │
│ إجمالي القيمة: 6,710.00 ر.س             │
└─────────────────────────────────────────┘
```

### شاشة ٢: كشوف التطبيقات — مدير المبيعات

- اختيار التطبيق + الشهر
- جدول بجميع الفروع مع خانتين لكل فرع: `القيمة` + `عدد الطلبات` (إن توفر)
- بديل: زر "رفع CSV"
- عرض الإجمالي + العمولة المحسوبة + الصافي

### شاشة ٣: إعدادات العمولات

- جدول بالتطبيقات السبعة
- حقل نسبة عمولة لكل تطبيق (النسبة الافتراضية)
- ملاحظة توضيحية: "تغيير هذه النسبة يؤثر على الكشوف الجديدة فقط؛ الكشوف السابقة تحتفظ بنسبتها التاريخية"
- سجل تاريخي لتغيرات النسب

### شاشة ٤: تقرير المطابقة (Reconciliation)

- فلترة: الشهر + الفرع (أو كل الفروع) + التطبيق
- **جدول المقارنة ثنائي البُعد:**

| التطبيق | مجموع الفرع (ر.س) | كشف التطبيق (ر.س) | فارق القيمة | % | عدد الفرع | عدد التطبيق | فارق العدد | الحالة |
|---|---|---|---|---|---|---|---|---|
| جاهز | 12,400 | 12,350 | -50 | 0.4% | 280 | 278 | -2 | ✅ |
| هنجر | 8,200 | 9,100 | +900 | 11% | 180 | 195 | +15 | 🔴 |

- ترميز لوني: ✅ <٥٪، 🟡 ٥–١٠٪، 🔴 >١٠٪
- زر "تصدير Excel"
- زر "قفل الشهر" (للـ sales_manager فقط) — يولّد snapshots

### شاشة ٥: تقرير الفرع الواحد

- توزيع المبيعات الشهرية على كل قناة (Pie chart للقيمة)
- نسبة الاعتماد على التوصيل مقابل البيع المباشر
- AOV لكل تطبيق خلال الشهر
- مقارنة مع الشهر السابق
- اتجاه يومي (Line chart للقيمة والعدد)

### شاشة ٦: تقرير الإدارة العامة

- مصفوفة: كل الفروع × كل القنوات
- ترتيب الفروع حسب الإجمالي
- AOV مقارنة بين الفروع
- أعلى/أدنى فرع اعتماداً على التوصيل
- تنبيهات المطابقة غير المحلولة

### شاشة ٧: لوحة الالتزام (Compliance Dashboard)

- مصفوفة: فرع × أيام الشهر → أخضر (مُدخل) / أحمر (ناقص) / رمادي (مستقبلي) / أصفر (استثنائي)
- عمود "نسبة الالتزام الشهرية" لكل فرع
- عمود "آخر إدخال"
- عمود "عدد الإدخالات الاستثنائية"
- ترتيب الفروع حسب نسبة الالتزام
- تنبيه أحمر لكل فرع دون ٩٠٪
- للـ `area_manager`: منطقته فقط، للـ `sales_manager`: كل الفروع

---

## ٧) تدفّق العمل (Workflow)

### يومياً — الفرع
1. نهاية الدوام: مدير الفرع يفتح شاشة الإدخال
2. يُدخل عدد + قيمة لكل تطبيق (٧)، وقيمة لكل طريقة دفع (٣)
3. يحفظ — النظام يسجّل `submitted_by`, `submitted_at`
4. التحقق: لا إدخال سابق، الشهر غير مقفول، قواعد orders_count حسب النوع

### خلال ٢٤ ساعة — تعديل ذاتي
5. مدير الفرع يستطيع تعديل مع `edit_reason`

### بعد ٢٤ ساعة وخلال ٧ أيام — تعديل بموافقة
6. التعديل يتطلب موافقة `area_manager`
7. بعد ٧ أيام: يتطلب `sales_manager`

### أسبوعياً — النظام
8. تنبيه تلقائي للفروع التي لم تُدخل أي يوم في الأسبوع السابق
9. تحديث Compliance Dashboard

### شهرياً — مدير المبيعات
10. بداية كل شهر: يرفع كشوف التطبيقات السبعة للشهر السابق
11. النظام يحسب المطابقة **on-demand** (قيمة + عدد) لكل (فرع × تطبيق)
12. مراجعة التقرير، التحقيق في الفوارق الكبيرة
13. **قفل الشهر** → توليد `reconciliation_snapshots` مجمَّدة
14. بعد القفل: لا تعديل دون إعادة فتح بمبرر

---

## ٨) القرارات النهائية (معتمدة — v3)

| # | القرار | المعتمد |
|---|---|---|
| 1 | حد التنبيه للفارق | ٥٪ (أصفر) / ١٠٪ (أحمر) |
| 2 | سماح التعديل الذاتي من الفرع | ٢٤ ساعة |
| 3 | تعديل بعد ٢٤س وقبل ٧ أيام | يحتاج `area_manager` |
| 4 | تعديل بعد ٧ أيام | يحتاج `sales_manager` |
| 5 | دورة كشف التطبيق | شهري |
| 6 | Koinz | مُعلَّق خارج MVP |
| 7 | CSV import للتطبيقات | يدوي + CSV |
| 8 | مرحلة تجريبية | فرعين شهر واحد ثم تقييم |
| 9 | أرقام نقدية ظاهرة لـ `area_manager` | نعم |
| 10 | Reconciliation قبل القفل | on-demand calculation |
| 11 | Reconciliation بعد القفل | snapshot مجمَّد |
| 12 | تعريف `amount` | branch gross — شامل الضريبة، قبل العمولة، يوم-الفرع فقط |
| 13 | **`orders_count` للتطبيقات** | **إجباري لـ delivery_app، NULL لـ payment_method** |
| 14 | variance_percent عند app=0 | match لو branch=0، major + N/A لو branch>0 |
| 15 | `monthly_closures` uniqueness | partial unique indexes + CHECK constraint |
| 16 | `commission_rate` | default في channels، snapshot في statements |

---

## ٩) خطة التنفيذ المرحلية

### المرحلة ١: الأساس (1-2 أسبوع)
- Alembic migrations للجداول الخمسة
- CHECK constraints + partial unique indexes على `monthly_closures`
- Seed: إدخال الـ ١٠ قناة
- SQLAlchemy models + Pydantic schemas (مع validators لـ orders_count حسب النوع)
- Service layer: حسابات، validation، lock enforcement، variance_percent safeguard
- Unit tests شاملة للقواعد الشرطية

### المرحلة ٢: Backend APIs (أسبوع)
- `GET/POST/PUT /api/v1/sales/daily-entry` (مع lock check + validation)
- `GET/POST /api/v1/sales/monthly-statements`
- `GET /api/v1/sales/reconciliation?month=...&branch_id=...` (ثنائي البُعد)
- `POST /api/v1/sales/closures` (قفل شهر)
- `POST /api/v1/sales/closures/{id}/reopen`
- `GET /api/v1/sales/compliance?month=...`
- `GET /api/v1/sales/channels` + `GET /api/v1/sales/commissions`
- RBAC decorators
- Integration tests

### المرحلة ٣: Frontend (2 أسبوع)
- Redux slice + API client
- الشاشات السبع
- i18n (ar/en)
- UI لثنائية الإدخال (count + amount للتطبيقات، amount فقط لطرق الدفع)
- مؤشرات حالة القفل والالتزام
- Cypress smoke tests

### المرحلة ٤: الترحيل (أسبوع)
- ترحيل بيانات قسم delivery القديم (إن وجدت)
- إعادة ربط endpoints الحالية
- التأكد من التوافق الخلفي

### المرحلة ٥: تجربة (شهر)
- تفعيل على ٢ فروع
- قياسات: نسبة الالتزام، متوسط الفارق، AOV، وقت الإدخال
- تجميع ملاحظات المستخدمين
- تعديلات حسب الحاجة

### المرحلة ٦: التعميم
- باقي الفروع تدريجياً
- جلسات تدريب
- دليل مستخدم بالعربي

### المرحلة ٢.١ (بعد MVP): تعزيزات
- payout_date + bank_reference + statement_reference
- ربط بالتحويلات البنكية
- معالجة Koinz بعد الحسم
- Admin UI لإدارة القنوات
- تقارير AOV متقدمة

---

## ١٠) المخاطر والتخفيف

| الخطر | الاحتمال | الأثر | التخفيف |
|---|---|---|---|
| إهمال الفروع للإدخال اليومي | عالي | عالي | تنبيهات + Compliance Dashboard + ربط بتقييم الأداء |
| إدخال orders_count خاطئ | متوسط | متوسط | قواعد validation + AOV كـ sanity check |
| اختلاف توقيت التطبيق vs الفرع | متوسط | متوسط | مقارنة شهرية + تعريف amount واضح |
| تضارب مع قسم delivery القديم | متوسط | عالي | خطة ترحيل + deprecation period |
| إعادة فتح شهور دون ضبط | منخفض | عالي | مبرر إجباري + قصر الصلاحية + سجل كامل |
| بعض التطبيقات لا تُتيح count في الكشف | متوسط | منخفض | count في statements اختياري، المطابقة تُبنى على المتاح |

---

## ١١) الخلاصة التنفيذية

هذا النظام يحوّل "التوصيل" من مجرد تسجيل أرقام إلى **أداة حوكمة وتدقيق مالية ثنائية البُعد**، تعطي:

- **للفرع:** صورة يومية واضحة (عدد + قيمة)
- **لمدير المبيعات:** كشف تلقائي للفروقات في القيمة **والعدد** + قدرة على تجميد الأرقام شهرياً
- **للإدارة:** ثقة في الأرقام + مؤشرات AOV لكل فرع وكل تطبيق
- **للمحاسبة:** ربط مباشر (في المرحلة ٢.١)

**الحالة:** الوثيقة v3 نهائية ومعتمدة. المرحلة ١ مُرخَّصة للبدء الفوري.

---

*وثيقة حيّة — تُحدَّث مع كل قرار نطاق جديد.*
