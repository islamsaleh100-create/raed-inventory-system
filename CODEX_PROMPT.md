# 📋 برومبت لـ Codex — تطبيق إصلاحات نظام رائد للجرد

انسخ **كل المحتوى بالأسفل** والصقه لـ Codex كـ prompt واحد.

---

## 🔐 بيانات الدخول (Superadmin — للاختبار النهائي)

```
Username: admin
Password: Admin@2025
```

> ملاحظة: دي البيانات الافتراضية من `backend/seed.py` السطر 56-59. لو تم تغييرها في الإنتاج استعمل البيانات الحالية. لإعادة تعيينها محلياً شغّل `reset_admin_password.bat` من جذر المشروع.

---

## 🎯 المهمة

مشروع **Raed Inventory System** — نظام جرد لسلسلة قهوة/مطاعم سعودية (32 فرع، 2 مستودع، 54 صنف).
- **Backend:** FastAPI + SQLAlchemy + Alembic (SQLite محلي / PostgreSQL إنتاج)
- **Frontend:** React/Vite (RTL / Arabic)
- **Timezone:** Asia/Riyadh (AST UTC+3)

تم عمل مراجعة شاملة وُجدت فيها 55 مشكلة، والمطلوب تطبيق **6 مراحل إصلاح متكاملة** مع اختبار كل مرحلة. المسار الجذري للمشروع هو `raed_inventory/`.

---

## ✅ المرحلة 1 — إصلاحات أمنية حرجة

### 1.1 `backend/app/core/config.py`
- احذف أي `default` من `SECRET_KEY` — يجب أن يُقرأ من متغير بيئة فقط، ويرفع `ValueError` لو غير موجود.
- اجعل `DATABASE_URL` حقل مطلوب بدون fallback للـ SQLite في prod. اسمح فقط بـ SQLite fallback لما `ENV=local`.
- أضف validators لـ `ACCESS_TOKEN_EXPIRE_MINUTES >= 5`, و `DEFAULT_TIMEZONE` (افتراضي `Asia/Riyadh`).

### 1.2 إغلاق IDOR
في كل endpoint بيقبل `{id}` وفيها ربط ببرانش/مستودع/مستخدم، استدعِ `can_access_branch(current_user, branch_id)` أو `can_access_warehouse(...)` قبل إرجاع أو تعديل السجل. راجع خصوصاً:
- `backend/app/routers/inventory.py` — `GET/POST/PUT /inventory/{id}`
- `backend/app/routers/orders.py` — كل العمليات على `/orders/{id}`
- `backend/app/routers/dashboard.py` — `/branch/{id}`, `/warehouse/{id}`, `/stock/*`

### 1.3 RBAC موحد
تأكد من أن كل endpoint يستخدم `Depends(require_roles(...))` بأدوار محددة، بلا `Depends(get_current_user)` الفضفاض إلا في `/auth/me`.

---

## ✅ المرحلة 2 — سلامة المخزون

### 2.1 قفل الصفوف (Row-level locks)
في `backend/app/services/orders_service.py` و `stock_adjustment_service.py` — كل تعديل على `branch_stock` أو `warehouse_stock` لازم يكون ضمن `SELECT ... FOR UPDATE` (باستخدام `with_for_update()` في SQLAlchemy).

### 2.2 منع الـ Deadlocks
لما يتم قفل صفين في نفس المعاملة (مثل transfer branch→branch)، اقفلهم **مرتبين بـ id تصاعدياً**:
```python
first_id, second_id = sorted([source_branch_id, destination_branch_id])
```

### 2.3 منع الأرقام السالبة
قبل أي `UPDATE … SET current_qty = current_qty - X`، تحقق:
```python
available = stock.current_qty - stock.reserved_qty
if available < qty:
    raise HTTPException(400, "الكمية المتاحة غير كافية")
```

### 2.4 Idempotency
في endpoints الحساسة (approve, dispatch, receive, transfer) اقبل `client_request_id` اختياري في الـ body/header. لو موجود، استخدمه key في جدول `idempotency_keys` لتفادي التكرار.

---

## ✅ المرحلة 3 — ترحيلات قاعدة البيانات

### 3.1 إنشاء migration جديدة
`backend/alembic/versions/20260417_0004_e5f6a7b8c9d0_phase3_integrity_indexes.py`

**محتواها:**
- CHECK constraints:
  - `branch_stock.current_qty >= 0`
  - `branch_stock.reserved_qty >= 0`
  - `warehouse_stock.current_qty >= 0`
  - `items.min_level >= 0`, `items.max_level >= items.min_level`
- Indexes (كلها dialect-aware):
  - `users (username)`, `users (email)`, `users (is_active)`
  - `branches (code)`, `branches (is_active)`, `branches (region)`
  - `items (category_id)`, `items (is_active)`
  - `branch_stock (branch_id, item_id)` unique, `branch_stock (branch_id, current_qty)`
  - `warehouse_stock (warehouse_id, item_id)` unique
  - `daily_inventory (branch_id, inventory_date)`, `(status, inventory_date)`
  - `replenishment_orders (branch_id, created_at)`, `(status)`, `(warehouse_id, status)`
  - `stock_transactions (item_id, created_at)`, `(branch_id, item_id)`, `(warehouse_id, item_id)`
  - `audit_logs (user_id, created_at)`, `(entity_type, entity_id)`
  - `quality_visits (branch_id, visit_date)`, `(visitor_id, status)`
  - `training_assessments (branch_id, assessment_date)`, `(assessor_id, status)`
  - `delivery_records (branch_id, period_start)`, `(brand_id, period_start)`
- استخدم helpers:
  ```python
  def _is_postgresql(): return op.get_bind().dialect.name == "postgresql"
  def _is_sqlite():     return op.get_bind().dialect.name == "sqlite"
  def _safe_create_index(name, table, cols, unique=False):
      try: op.create_index(name, table, cols, unique=unique)
      except Exception: pass
  ```
- على SQLite استعمل `with op.batch_alter_table(...)` لأي ADD CONSTRAINT.

### 3.2 تشغيل
```bash
cd backend && alembic upgrade head
```

---

## ✅ المرحلة 4 — Scheduler و Timezone

### 4.1 `backend/app/core/timezone.py` (ملف جديد)
```python
from datetime import datetime, date
from functools import lru_cache
from zoneinfo import ZoneInfo
from app.core.config import settings

@lru_cache(maxsize=4)
def _get_zone(name: str) -> ZoneInfo:
    return ZoneInfo(name)

def app_tz() -> ZoneInfo:
    return _get_zone(settings.DEFAULT_TIMEZONE or "Asia/Riyadh")

def now_tz() -> datetime:
    return datetime.now(app_tz())

def today_tz() -> date:
    return now_tz().date()

def to_tz(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(app_tz())

def to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=app_tz())
    return dt.astimezone(ZoneInfo("UTC"))

def utcnow_aware() -> datetime:
    return datetime.now(ZoneInfo("UTC"))

def format_tz(dt: datetime, fmt: str = "%Y-%m-%d %H:%M") -> str:
    return to_tz(dt).strftime(fmt)
```

### 4.2 `backend/app/services/scheduler_service.py` (ملف جديد)
Scheduler بسيط بالـ asyncio (بدون APScheduler):
- دالة `_next_run_at(hour, minute)` ترجع datetime الـ run القادم بتوقيت Asia/Riyadh.
- دالة `run_auto_replenishment_once(db, days_of_cover=3)`:
  - جيب كل `Branch.is_active == True`
  - لكل فرع: جيب آخر `DailyInventory` بـ `status=approved`
  - لو موجود وفي أصناف تحت الحد، استدعِ `orders_service.generate_replenishment_order(db, branch_id, system_user, days_of_cover)` مع `client_request_id` ثابت يومي `f"auto-replen-{branch_id}-{today_tz().isoformat()}"` (idempotent).
- دالة `_system_user(db)` ترجع أول super_admin ثم admin.
- دالة `_scheduler_loop()` loop لا نهائي `while not stop_event.is_set()` ينام حتى `_next_run_at(6, 0)` (6 ص AST) ثم يشغّل.
- `start_scheduler(app)` يخزن `asyncio.create_task(_scheduler_loop())` في `app.state.scheduler_task`.
- `stop_scheduler(app)` يعمل cancel + await.

### 4.3 `backend/app/main.py`
```python
from app.services.scheduler_service import start_scheduler, stop_scheduler

@app.on_event("startup")
async def startup_event():
    # ... الكود الموجود
    start_scheduler(app)

@app.on_event("shutdown")
async def shutdown_event():
    await stop_scheduler(app)
    # ... الكود الموجود
```

### 4.4 Endpoint يدوي
في `backend/app/routers/orders.py` أضف:
```python
@router.post("/auto-replenishment/run")
async def run_auto_replenishment(
    days_of_cover: int = Query(3, ge=1, le=14),
    current_user: User = Depends(require_roles("admin","super_admin","operations_manager")),
    db: Session = Depends(get_db),
):
    result = await run_in_threadpool(run_auto_replenishment_once, db, days_of_cover)
    return {"status":"ok","summary":result}
```

---

## ✅ المرحلة 5 — إصلاحات الواجهة

### 5.1 `frontend/src/components/common/ErrorBoundary.jsx` (ملف جديد)
React class component مع:
- `getDerivedStateFromError` — يرجع `{ hasError: true, error }`
- `componentDidCatch(error, errorInfo)` — console.error
- في fallback UI: عرض عربي "حدث خطأ غير متوقع" + زر "إعادة تحميل الصفحة" (`window.location.reload()`) + زر "العودة للرئيسية" (`window.location.href='/'`)
- تفاصيل الخطأ مرئية فقط في dev: `{import.meta.env.DEV && <details>...</details>}`
- أضف export في `frontend/src/components/common/index.jsx`:
  ```js
  export { default as ErrorBoundary } from './ErrorBoundary'
  ```

### 5.2 `frontend/src/App.jsx`
لف المحتوى كله بـ `<ErrorBoundary>`:
```jsx
import { ErrorBoundary, PageLoader } from './components/common'

export default function App() {
  return (
    <ErrorBoundary>
      <Provider store={store}>
        <Toaster position="top-center" toastOptions={{ duration: 3500 }} />
        <Suspense fallback={<PageLoader />}>
          <AppRoutes />
        </Suspense>
      </Provider>
    </ErrorBoundary>
  )
}
```

### 5.3 `frontend/src/pages/auth/LoginPage.jsx`
لف بيانات الـ demo:
```jsx
{import.meta.env.DEV && (
  <div className="demo-credentials">...</div>
)}
```

### 5.4 `frontend/vite.config.js`
```js
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const devPort   = parseInt(env.VITE_DEV_PORT || '5173', 10)
  const proxyTarget = env.VITE_DEV_PROXY_TARGET || 'http://localhost:8000'
  return {
    plugins: [react()],
    server: {
      port: devPort,
      proxy: { '/api': { target: proxyTarget, changeOrigin: true } },
    },
    build: {
      sourcemap: env.VITE_SOURCEMAP === 'true',
      outDir: 'dist',
    },
  }
})
```

### 5.5 `frontend/src/utils/helpers.js`
أضف:
```js
export const displayItemName   = (i) => i?.item_name_ar   || i?.item_name_en   || i?.code || '-'
export const displayBranchName = (b) => b?.branch_name_ar || b?.branch_name    || b?.code || '-'
export const displayWarehouseName = (w) => w?.warehouse_name_ar || w?.warehouse_name || w?.code || '-'
export const safeText = (v) => (v === null || v === undefined || v === '') ? '-' : String(v)
```

---

## ✅ المرحلة 6 — ميزات جديدة

### 6.1 نوع طلبية جديد: `inter_branch`
في `backend/app/models/__init__.py` — class `OrderType(str, Enum)`:
```python
inter_branch = "inter_branch"
```

### 6.2 Migration للـ enum
`backend/alembic/versions/20260417_0005_f6a7b8c9d0e1_add_order_type_inter_branch.py`
```python
def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE ordertype ADD VALUE IF NOT EXISTS 'inter_branch'")
    # SQLite: no-op (مخزن VARCHAR)

def downgrade():
    # PostgreSQL لا يدعم حذف قيمة enum ببساطة — اتركها فارغة
    pass
```

### 6.3 Transfer بين الفروع
في `backend/app/services/stock_adjustment_service.py` أضف:
```python
def transfer_branch_to_branch(
    db, source_branch_id, destination_branch_id,
    item_id, qty, reason, current_user, reference_no=None, client_request_id=None,
):
    if source_branch_id == destination_branch_id:
        raise HTTPException(400, "لا يمكن التحويل لنفس الفرع")
    if not can_access_branch(current_user, source_branch_id):
        raise HTTPException(403, "لا صلاحية على الفرع المصدر")
    if not can_access_branch(current_user, destination_branch_id):
        raise HTTPException(403, "لا صلاحية على الفرع المستقبل")

    # قفل في ترتيب ثابت لمنع deadlock
    first_id, second_id = sorted([source_branch_id, destination_branch_id])
    _ = db.query(BranchStock).filter_by(branch_id=first_id,  item_id=item_id).with_for_update().first()
    _ = db.query(BranchStock).filter_by(branch_id=second_id, item_id=item_id).with_for_update().first()

    src = db.query(BranchStock).filter_by(branch_id=source_branch_id,      item_id=item_id).first()
    dst = db.query(BranchStock).filter_by(branch_id=destination_branch_id, item_id=item_id).first()
    if not src:
        raise HTTPException(400, "الصنف غير موجود في مخزون الفرع المصدر")
    available = src.current_qty - src.reserved_qty
    if available < qty:
        raise HTTPException(400, f"الكمية المتاحة ({available}) أقل من المطلوب ({qty})")

    src.current_qty -= qty
    if not dst:
        dst = BranchStock(branch_id=destination_branch_id, item_id=item_id, current_qty=0, reserved_qty=0)
        db.add(dst)
    dst.current_qty += qty

    db.add(StockTransaction(
        transaction_type=TransactionType.transfer,
        item_id=item_id, qty=qty,
        source_branch_id=source_branch_id, destination_branch_id=destination_branch_id,
        user_id=current_user.id, reference_no=reference_no,
        notes=f"Inter-branch transfer: {reason}",
    ))
    db.commit()
    return {"status":"ok","source":source_branch_id,"destination":destination_branch_id,"qty":qty}
```

### 6.4 Endpoint
في `backend/app/routers/stock.py`:
```python
_INTER_BRANCH_ROLES = ("area_manager","operations_manager","admin","super_admin")

class TransferBranchToBranchRequest(BaseModel):
    source_branch_id: int
    destination_branch_id: int
    item_id: int
    qty: float = Field(..., gt=0)
    reason: str = Field(..., min_length=3)
    reference_no: Optional[str] = None
    client_request_id: Optional[str] = None

@router.post("/transfer/branch-to-branch")
def transfer_branch_to_branch_endpoint(
    body: TransferBranchToBranchRequest,
    current_user: User = Depends(require_roles(*_INTER_BRANCH_ROLES)),
    db: Session = Depends(get_db),
):
    return stock_adjustment_service.transfer_branch_to_branch(
        db, **body.dict(), current_user=current_user
    )
```

### 6.5 Frontend API helper
في `frontend/src/services/api.js` داخل `stockApi`:
```js
transferBranchToBranch: (data) => api.post('/stock/transfer/branch-to-branch', data),
```

### 6.6 سكريبت إنشاء مستخدمين للفروع
`backend/create_branch_users.py` (ملف موجود — راجعه وأكمله):
- idempotent — يتخطى أي فرع عنده يوزر بالدور المطلوب
- مولّد كلمة مرور قوية (8+ حروف، كبير + صغير + رقم)
- CLI: `--role user|manager`, `--domain`, `--dry-run`
- يُخرِج CSV: `branch_users_generated_YYYYMMDD_HHMMSS.csv`
- يدعم env var: `DEFAULT_BRANCH_PASSWORD` (لو موجود يستعمله بدل العشوائي)
- تشغيل: `python create_branch_users.py --role user`

---

## 🧪 التحقق النهائي

### Backend
```bash
cd raed_inventory/backend
python -m compileall -q app/
pip install -r requirements.txt
alembic upgrade head
pytest
uvicorn app.main:app --reload
```
ثم اختبر بالـ credentials المذكورة فوق:
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Admin@2025"}'
```

### Frontend
```bash
cd raed_inventory/frontend
npm install
npm run build
npm run dev
```
افتح `http://localhost:5173` وسجّل دخول بالبيانات فوق.

### سيناريوهات اختبار لازم تنجح
1. تسجيل دخول admin → تحويل `/operations`
2. إنشاء daily inventory لفرع → approve → توليد طلبية تعويض يدوية
3. `POST /stock/transfer/branch-to-branch` بصلاحية `area_manager` بين فرعين
4. تشغيل `POST /orders/auto-replenishment/run` وتأكد من إنشاء طلبيات لكل الفروع التي تحتاج
5. محاولة transfer بكمية أكبر من المتاح → يجب رفض بـ 400
6. محاولة `GET /inventory/{id}` من يوزر فرع آخر → يجب 403
7. `python create_branch_users.py --role user --dry-run` يعرض القائمة بدون كتابة

---

## 📦 متغيرات البيئة المطلوبة

```env
# backend/.env
ENV=production
SECRET_KEY=<توليد قوي عشوائي 64 حرف>
DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/raed
ACCESS_TOKEN_EXPIRE_MINUTES=60
DEFAULT_TIMEZONE=Asia/Riyadh
DEFAULT_BRANCH_PASSWORD=<اختياري — كلمة مرور موحدة لكل يوزرز الفروع الجدد>

# frontend/.env
VITE_API_URL=https://api.raed.example.com
VITE_DEV_PORT=5173
VITE_DEV_PROXY_TARGET=http://localhost:8000
VITE_SOURCEMAP=false
```

---

## 🚀 خطوات النشر بعد الإصلاح

1. `git checkout -b fix/phase-1-to-6-comprehensive`
2. تطبيق كل المراحل بالترتيب (1 ثم 2 ثم 3 ...)
3. بعد كل مرحلة: commit مستقل بعنوان واضح (`fix(security): close IDOR on inventory endpoints`, ...)
4. `cd backend && alembic upgrade head && pytest`
5. `cd ../frontend && npm run build`
6. `git push -u origin fix/phase-1-to-6-comprehensive`
7. افتح PR يشرح كل مرحلة + نتائج الاختبار

---

**التعليمات لـ Codex:** نفذ كل المراحل الست بدون ما ترجع لي بأسئلة. استخدم التحقق النهائي كـ gate — لو فشل أي سيناريو صلّح السبب وأعد التشغيل. عند الانتهاء، أرسل ملخص نهائي يحتوي:
- عدد الملفات المعدّلة
- نتائج الـ pytest
- نتائج `npm run build`
- أي قرار اتخذته خارج السبك المذكور
