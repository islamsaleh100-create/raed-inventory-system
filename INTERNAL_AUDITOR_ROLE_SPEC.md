# Internal Auditor Role — مواصفات الدور والتنفيذ

**الإصدار:** 1.0
**التاريخ:** 2026-04-26
**الحالة:** مقترح — جاهز للتنفيذ
**المالك:** Raed Food Corporation — Office Compliance Team

---

## 1. الفلسفة الإدارية

دور `internal_auditor` (المراجع الداخلي) هو دور **مراقبة وتدقيق** للعمليات اليومية في النظام، يهدف إلى:

1. التحقق من أن جميع المستخدمين يتبعون التعليمات والإجراءات
2. رصد الانحرافات (variances) بين المُتوقَّع والفعلي
3. توثيق الملاحظات (findings) للمراجعة الإدارية اللاحقة
4. ضمان اكتمال سجل التتبّع (audit trail) لكل عملية حساسة

### القاعدة الذهبية

> المراجع يرى **كل شيء** عبر النظام، ويكتب **ملاحظات** على ما يراه،
> لكنه **لا يلمس أي زرار** يغيّر بيانات تشغيلية.

هذا يميّزه عن:
- `admin` / `super_admin` — يملكون صلاحية التعديل
- `operations_manager` — يقرأ التقارير لكن قد يتدخل في عمليات معينة
- `quality_visitor` / `quality_manager` — يراجع جودة الفروع ميدانيًا (نطاق مختلف)

---

## 2. النطاق (Scope) — ماذا يرى

### 2.1 Supply Chain V1 (سلسلة الإمداد)
| الكيان | صلاحية |
|--------|--------|
| `branch_requests` (كل البراندات، كل الفروع، كل الحالات) | READ |
| `production_orders` (كل الأقسام: Pizza / Bakery / Meat) | READ |
| `warehouse_lines` (BRANCH_REQUEST + KITCHEN_OUTPUT) | READ |
| `delivery_orders` + lines + receiver_name + timestamps | READ |
| `kitchen_material_requests` | READ |
| Split outcomes (warehouse vs kitchen split decisions) | READ |

### 2.2 Audit Trail (الأهم لدوره)
| الكيان | صلاحية |
|--------|--------|
| `audit_logs` (كل العمليات، كل المستخدمين، كل التواريخ) | READ + Filter + Export |
| الفلاتر المطلوبة | user, date_range, action, entity_type, entity_id |
| التصدير | CSV / Excel للمراجعة الخارجية |

### 2.3 Stock & Reconciliation
| الكيان | صلاحية |
|--------|--------|
| `warehouse_stock` (current_qty + reserved_qty + available_qty) | READ |
| `branch_stock` | READ |
| `stock_transactions` / `stock_movements` | READ |
| Variance reports (expected vs actual) | READ |

### 2.4 Quality & Training (للسياق فقط)
| الكيان | صلاحية |
|--------|--------|
| `quality_visits` + responses + signatures | READ |
| `open_actions` (الإجراءات التصحيحية المفتوحة) | READ |
| `training_assessments` | READ |

### 2.5 Sales Channels
| الكيان | صلاحية |
|--------|--------|
| `daily_sales` | READ |
| `app_statements` + reconciliation | READ |
| `commission_rates` | READ |
| `monthly_closures` (DON'T close/reopen) | READ |

### 2.6 Documents
| الكيان | صلاحية |
|--------|--------|
| `documents` (كل الوثائق + expiring) | READ |

### 2.7 Master Data
| الكيان | صلاحية |
|--------|--------|
| `users` (قائمة بدون كلمات مرور) | READ |
| `branches`, `warehouses`, `brands`, `kitchen_sections`, `items` | READ |
| `area_manager_assignments`, `kitchen_section_assignments` | READ |

---

## 3. الصلاحيات الصريحة (Permissions Matrix)

| العملية | internal_auditor | ملاحظة |
|---------|:-----------------:|--------|
| Login | ✅ | بحساب مخصص |
| GET أي endpoint من القوائم أعلاه | ✅ | كل البيانات |
| POST/PATCH/PUT/DELETE على بيانات تشغيلية | ❌ | بدون استثناء |
| Approve/Reject branch requests | ❌ | |
| Modify-and-approve | ❌ | |
| Split branch request | ❌ | |
| Start/Complete production | ❌ | |
| Issue/Partial-issue warehouse | ❌ | |
| Out-for-delivery / Deliver | ❌ | |
| Edit users / reset passwords | ❌ | |
| Stock adjustments | ❌ | |
| Close/reopen monthly closure | ❌ | |
| Upload documents | ❌ | |
| Run quality visits | ❌ | (دور `quality_visitor`) |
| **POST /audit/findings** (ملاحظة جديدة) | ✅ | **الإضافة الوحيدة بالكتابة** |
| **PATCH /audit/findings/{id}** (تعديل ملاحظته) | ✅ | فقط ملاحظاته الخاصة |
| **DELETE /audit/findings/{id}** | ❌ | لا حتى ملاحظاته (immutable record) |
| **GET /audit/findings** | ✅ | يرى كل الـ findings (حتى من مراجعين آخرين) |
| Export reports as CSV/Excel | ✅ | يحتفظ بنسخة للمراجعة الخارجية |

---

## 4. التغييرات في قاعدة البيانات

### 4.1 إضافة `internal_auditor` إلى `RoleName` enum

```python
# backend/app/models/__init__.py
class RoleName(str, enum.Enum):
    super_admin = "super_admin"
    admin = "admin"
    operations_manager = "operations_manager"
    area_manager = "area_manager"
    branch_manager = "branch_manager"
    branch_user = "branch_user"
    warehouse_manager = "warehouse_manager"
    warehouse_user = "warehouse_user"
    delivery_user = "delivery_user"
    kitchen_section_manager = "kitchen_section_manager"
    sales_manager = "sales_manager"
    quality_manager = "quality_manager"
    quality_visitor = "quality_visitor"
    trainer = "trainer"
    internal_auditor = "internal_auditor"  # ← NEW
```

### 4.2 جدول `audit_findings` الجديد

```sql
CREATE TABLE audit_findings (
    id              SERIAL PRIMARY KEY,
    finding_no      VARCHAR(40) UNIQUE NOT NULL,         -- AF-000001
    entity_type     VARCHAR(50) NOT NULL,                -- 'branch_request' | 'production_order' | etc.
    entity_id       INTEGER NOT NULL,
    severity        VARCHAR(20) NOT NULL,                -- 'info' | 'warning' | 'violation'
    title           VARCHAR(200) NOT NULL,
    description     TEXT NOT NULL,
    created_by      INTEGER NOT NULL REFERENCES users(id),
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    acknowledged_by INTEGER REFERENCES users(id),       -- area_mgr/ops_mgr who responded
    acknowledged_at TIMESTAMP,
    response_text   TEXT,
    status          VARCHAR(20) NOT NULL DEFAULT 'open', -- 'open' | 'acknowledged' | 'closed'
    INDEX idx_findings_entity (entity_type, entity_id),
    INDEX idx_findings_severity (severity),
    INDEX idx_findings_status (status),
    INDEX idx_findings_created_by (created_by)
);
```

**Severity values:**
- `info` — ملاحظة معلوماتية فقط
- `warning` — تنبيه يستحق المتابعة
- `violation` — مخالفة واضحة لسياسة معتمدة

### 4.3 Alembic Migration

```bash
alembic revision -m "add_internal_auditor_role_and_audit_findings"
```

ضروري:
- إضافة قيمة `internal_auditor` إلى enum `rolename` في PostgreSQL (`ALTER TYPE ... ADD VALUE IF NOT EXISTS`)
- إنشاء جدول `audit_findings`
- INSERT row في `roles` table بـ `name='internal_auditor'`, `display_name='مراجع داخلي'`

### 4.4 Seed
سكريبت `seed_internal_auditor.py`:
```python
# Username: audit.officer
# Password: Raed@2025
# Role: internal_auditor
# Email: audit@raed.com
# Full name: المراجع الداخلي
```

---

## 5. التغييرات في الـ Backend

### 5.1 إضافة الدور للـ READ tuples في كل router

في كل router من supply_chain، sales_channels، quality، etc:

```python
# مثال في branch_requests.py
SCOPED_ROLES = (
    "branch_user",
    "branch_manager",
    "area_manager",
    "internal_auditor",  # ← NEW
    "admin",
    "super_admin",
)
```

نفس الـ pattern في:
- `production_orders.py`
- `warehouse_lines.py`
- `delivery_orders.py`
- `audit.py` (audit_logs)
- `dashboard.py`
- `sales_channels.py` (READ tuples فقط)
- `quality.py`
- `documents.py`
- `master.py` (READ endpoints)

**نقطة حرجة:** لا تضيف `internal_auditor` للـ WRITE tuples أبداً.

### 5.2 Permission helper

في `backend/app/core/sales_permissions.py` (أو ملف جديد `audit_permissions.py`):

```python
_READ_ONLY_ROLES = {"internal_auditor"}

def is_read_only(roles: Iterable[str]) -> bool:
    """Returns True if the user is restricted to read-only access."""
    return bool(set(roles or ()) & _READ_ONLY_ROLES)
```

استخدامه: في الـ middleware أو في كل write endpoint كـ defense-in-depth:

```python
if is_read_only(get_user_roles(current_user)):
    raise HTTPException(403, "Internal auditor cannot perform write operations")
```

### 5.3 Endpoints جديدة لـ audit_findings

ملف جديد: `backend/app/routers/audit_findings.py`

```python
GET    /api/v1/audit/findings                    # list with filters
GET    /api/v1/audit/findings/{id}               # detail
POST   /api/v1/audit/findings                    # create — internal_auditor + admin only
PATCH  /api/v1/audit/findings/{id}               # update own finding (creator only) or acknowledge (managers)
GET    /api/v1/audit/findings/by-entity/{type}/{id}  # all findings on a specific entity
GET    /api/v1/audit/dashboard                   # internal_auditor dashboard KPIs
```

**Filters للـ list:**
- `severity` (info/warning/violation)
- `status` (open/acknowledged/closed)
- `entity_type`
- `created_by` (user_id)
- `from_date`, `to_date`
- `page`, `page_size`

### 5.4 Schemas

```python
# backend/app/schemas/audit_findings.py
class AuditFindingCreate(BaseModel):
    entity_type: str
    entity_id: int
    severity: Literal["info", "warning", "violation"]
    title: str = Field(min_length=5, max_length=200)
    description: str = Field(min_length=10)

class AuditFindingAcknowledge(BaseModel):
    response_text: str = Field(min_length=10)

class AuditFindingOut(BaseModel):
    id: int
    finding_no: str
    entity_type: str
    entity_id: int
    severity: str
    title: str
    description: str
    created_by: int
    created_by_name: Optional[str]
    created_at: datetime
    acknowledged_by: Optional[int]
    acknowledged_by_name: Optional[str]
    acknowledged_at: Optional[datetime]
    response_text: Optional[str]
    status: str
```

### 5.5 Audit dashboard endpoint

`GET /api/v1/audit/dashboard` يرجع:

```json
{
  "open_findings_total": 12,
  "violations_open": 3,
  "warnings_open": 7,
  "info_open": 2,
  "average_approval_time_seconds": 145,
  "fast_approvals_under_30_seconds": [{"area_manager": "am_riyadh", "count": 5}],
  "delays_without_reason": 8,
  "branches_late_in_entry": [...],
  "top_variance_items": [...]
}
```

---

## 6. التغييرات في الـ Frontend

### 6.1 Sidebar — قسم جديد

في `frontend/src/components/layout/AppLayoutV2.jsx`:

```jsx
{
  sectionKey: 'nav.section_audit',
  roles: ['internal_auditor', 'admin', 'super_admin'],
  items: [
    { to: '/audit/dashboard', icon: ShieldCheck, labelKey: 'nav.audit_dashboard',
      roles: ['internal_auditor', 'admin', 'super_admin'] },
    { to: '/audit/findings', icon: Flag, labelKey: 'nav.audit_findings',
      roles: ['internal_auditor', 'admin', 'super_admin'] },
    { to: '/audit/trail', icon: History, labelKey: 'nav.audit_trail',
      roles: ['internal_auditor', 'admin', 'super_admin'] },
  ]
}
```

### 6.2 i18n keys

**ar.json:**
```json
"section_audit": "المراجعة الداخلية",
"audit_dashboard": "لوحة المراجع",
"audit_findings": "ملاحظات المراجعة",
"audit_trail": "سجل العمليات",
"audit_finding_severity_info": "للعلم",
"audit_finding_severity_warning": "تحذير",
"audit_finding_severity_violation": "مخالفة",
"audit_finding_status_open": "مفتوحة",
"audit_finding_status_acknowledged": "تم الرد",
"audit_finding_status_closed": "مُغلقة"
```

**en.json:**
```json
"section_audit": "Internal Audit",
"audit_dashboard": "Auditor Dashboard",
"audit_findings": "Audit Findings",
"audit_trail": "Audit Trail",
"audit_finding_severity_info": "Info",
"audit_finding_severity_warning": "Warning",
"audit_finding_severity_violation": "Violation",
"audit_finding_status_open": "Open",
"audit_finding_status_acknowledged": "Acknowledged",
"audit_finding_status_closed": "Closed"
```

### 6.3 الصفحات الـ 3

#### `/audit/dashboard` (`AuditDashboardPage.jsx`)
- 6 KPI cards: open findings (info/warning/violation breakdown)
- جدول "Fast approvals under 30s" — area managers يعتمدون بسرعة مشبوهة
- جدول "Partial issues without reason"
- زر تصدير PDF/Excel

#### `/audit/findings` (`AuditFindingsPage.jsx`)
- جدول الـ findings
- فلاتر: severity, status, date range, created_by
- زر "+ إضافة ملاحظة" (للـ internal_auditor)
- نقرة على finding تفتح modal فيه:
  - تفاصيل الملاحظة
  - رابط مباشر للـ entity (branch_request/order/etc)
  - حقل الـ acknowledge (لو المستخدم area_manager/ops_manager)

#### `/audit/trail` (`AuditTrailPage.jsx`)
- جدول كل audit_logs
- فلاتر متقدمة: user, action, entity_type, entity_id, date range
- زر export CSV
- Modal تفاصيل لكل log entry يعرض old_values vs new_values

### 6.4 Inline finding indicator

في صفحات supply_chain (مثل branch_requests detail)، أضف:
- شريط علوي لو فيه findings مفتوحة على هذا الـ entity
- زر "+ إضافة ملاحظة" يظهر للـ internal_auditor فقط

```jsx
{user.roles.includes('internal_auditor') && (
  <button onClick={() => setShowFindingModal(true)}>
    + إضافة ملاحظة مراجعة
  </button>
)}
```

### 6.5 RouteRoleGuard

تحديث `App.jsx`:
```jsx
<Route path="/audit/dashboard" element={
  <RouteRoleGuard allowed={['internal_auditor']}>
    <AuditDashboardPage />
  </RouteRoleGuard>
} />
```

(الـ `RouteRoleGuard` بالفعل يمرر admin/super_admin تلقائيًا)

---

## 7. ملاحظات أمنية

### 7.1 Defense in depth
حتى لو نسي أحد إضافة `internal_auditor` لـ READ tuple، أو أضافه بالخطأ لـ WRITE tuple:
- أضف middleware في `backend/app/main.py` يفحص الـ HTTP method:

```python
@app.middleware("http")
async def block_writes_for_auditor(request, call_next):
    if request.method in ("POST", "PATCH", "PUT", "DELETE"):
        user = await get_user_from_token(request)
        if user and "internal_auditor" in get_user_roles(user):
            # Allow only audit_findings write paths
            if not request.url.path.startswith("/api/v1/audit/findings"):
                return JSONResponse(403, {"detail": "Internal auditor is read-only"})
    return await call_next(request)
```

### 7.2 Audit logging للـ auditor نفسه
كل عملية يقوم بها `internal_auditor` (حتى الـ reads المهمة) لازم تنزل في audit_logs:
- تسجيل دخول
- تصدير CSV/Excel (متى، أي filter)
- إنشاء finding
- تعديل finding

### 7.3 إخفاء بيانات حساسة
- لا يرى `hashed_password` لأي مستخدم
- لا يرى المفاتيح/التوكنز
- لا يرى صيغة الاتصال بقواعد البيانات الخارجية

---

## 8. سيناريوهات الاستخدام

### سيناريو 1: المراجعة الشهرية الدورية
1. المراجع يفتح `/audit/dashboard`
2. يلاحظ "5 طلبات اعتمدها am_riyadh في أقل من 30 ثانية"
3. يضغط على كل طلب، يقرأ البيانات
4. يضيف finding على كل طلب: `warning — approval time below threshold`
5. يصدّر تقرير PDF للـ owner

### سيناريو 2: متابعة variance
1. branch_user1 طلب 100 كوب
2. wh.user1 صرف 80 (BRANCH_REQUEST PARTIAL)
3. الـ delay_reason فاضي
4. المراجع يلاحظ ذلك في dashboard
5. يضيف finding: `violation — partial issue without delay reason (policy 4.2)`
6. wh.mgr1 يفتح الـ finding، يضيف response: "نعتذر، نسي الموظف. تم تدريبه."
7. الـ status يبقى `acknowledged`

### سيناريو 3: التحقق من corrective actions
1. quality_visitor عمل زيارة لفرع، فتح 3 corrective actions
2. بعد شهر، فيه 2 لسه مفتوحة
3. internal_auditor يضيف finding على الفرع: `violation — corrective actions overdue`
4. التقرير يطلع للـ branch_manager وللـ area_manager

---

## 9. خطة التنفيذ

| المرحلة | المحتوى | التقدير |
|---------|---------|---------|
| **P1 — DB + Role** | Alembic migration + enum + seed account | 1 ساعة |
| **P2 — Backend READ permissions** | إضافة الدور لكل READ tuples | 1.5 ساعة |
| **P3 — audit_findings router** | CRUD endpoints + schemas | 2 ساعة |
| **P4 — Audit dashboard endpoint** | KPI calculations | 1.5 ساعة |
| **P5 — Frontend pages** | 3 صفحات + nav + i18n | 2 ساعة |
| **P6 — Middleware defense** | Block writes from auditor | 30 دقيقة |
| **P7 — Tests** | Unit tests للـ permissions + findings | 1.5 ساعة |
| **P8 — Documentation** | README للمستخدم النهائي | 30 دقيقة |
| **Total** | | **~10 ساعات شغل** |

---

## 10. Acceptance Criteria

النظام يعتبر جاهزاً لاختبار `internal_auditor` لو:

- [ ] حساب `audit.officer` / `Raed@2025` يقدر يـ login
- [ ] يشوف القسم "المراجعة الداخلية" في الـ sidebar
- [ ] يفتح أي صفحة supply chain ويشوف البيانات (read-only)
- [ ] محاولة POST/PATCH/PUT/DELETE على أي endpoint غير `/audit/findings` ترجع 403
- [ ] يقدر يضيف finding جديد بنجاح
- [ ] الـ finding يظهر في صفحة `/audit/findings`
- [ ] الـ finding يظهر inline على entity detail page
- [ ] area_manager يقدر يـ acknowledge الـ finding
- [ ] auditor ما يقدرش يحذف finding (حتى لو هو اللي عمله)
- [ ] التصدير CSV يعمل صح في كل الصفحات الـ 3
- [ ] كل تصدير ينزل في audit_logs

---

## 11. ما لم يُتضمَّن في النسخة الأولى (v2 candidates)

- ⏳ تنبيهات تلقائية للمراجع لما يحصل anomaly (مثل approval متأخر)
- ⏳ Email/SMS notifications للـ findings الـ violations
- ⏳ Workflow معتمد لإغلاق finding (closure approval)
- ⏳ Templates للـ findings الشائعة
- ⏳ Integration مع أنظمة compliance خارجية (SAMA reports)
- ⏳ صلاحية مختلفة للـ "Lead Auditor" يقدر يحذف findings

هذه ميزات لاحقة. نبدأ بالـ MVP أولاً.

---

## 12. الملاحظات النهائية

- **اسم الحساب الافتراضي:** `audit.officer`
- **كلمة المرور الافتراضية:** `Raed@2025` — لازم تتغيّر بعد أول تسجيل دخول
- **الإيميل:** `audit@raed.com`
- **الاسم بالعربي:** "المراجع الداخلي"
- **الدور تقني:** `internal_auditor`

**التحضير لمراجعة خارجية (SAMA/شركة محاسبة):** المراجع يقدر يصدّر:
- تقرير الـ findings كاملاً
- audit_logs لفترة معينة
- تقرير الـ variance بين الطلبات والصرف

كل التصديرات تنزل في audit_logs بنفسها — بحيث لو حد طلب نسخة من النظام، عندنا proof.

---

**نهاية المواصفات.**
