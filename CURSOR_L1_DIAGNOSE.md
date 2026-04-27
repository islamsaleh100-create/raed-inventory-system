# Cursor Handoff — L1: تشخيص + إصلاح أخطاء API على صفحات الجودة/التدريب/التحليلات

## الوضع الحالي
- ✅ K1/K2 تمّوا: مفيش ErrorBoundary crashes، كل الصفحات بتفتح
- ❌ الـ toast errors الظاهرة دلوقتي (مش crashes):
  - "تعذّر تحميل الإجراءات التصحيحية" → `GET /api/v1/quality/open-actions`
  - "خطأ في تحميل الزيارات" → `GET /api/v1/quality/`
  - "خطأ في تحميل التقييمات" → `GET /api/v1/training/`
  - "تحليلات التدريب حدث خطأ" → `GET /api/v1/training/analytics/verdict-distribution`
  - "تأخير الطلبيات حدث خطأ" → `GET /api/v1/dashboard/order-delay-analytics`

## السياق المهم (ليه ممكن يكون شكل DB)
- DB حالياً على `alembic current = a3b4c5d6e7f8 (head)` لكن اتعالجت يدوياً:
  - أعمدة `text_en` / `benchmark_en` اتضافت بـ `ALTER TABLE` يدوي (مش من migration 0007)
  - migration 0011 اتعملها patch لتكون idempotent
  - migration 0012 seed **اتخطّى** (emoji encoding) → قوالب التدريب قد تكون فاضية
- الـ backend شغال نظيف على 8010 بدون startup crashes

## مطلوب منك — 5 خطوات بالترتيب

### الخطوة 1: التقط tracebacks من uvicorn
خلّي الخادم شغّال، ومن نافذة تانية:

```powershell
# طلبات الـ 5 endpoints مباشرةً مع cookie/token من المتصفح
# أو ببساطة: افتح المتصفح، سجّل دخول، افتح /quality، وخد screenshot للـ uvicorn terminal
```

افتح نافذة uvicorn وخد الـ **tracebacks كاملة** (آخر 100 سطر). لو مفيش tracebacks وبس HTTP status codes، سجّل الـ status code لكل endpoint:

| Endpoint | Status Code | Traceback موجود؟ |
|----------|-------------|-----------------|
| `/api/v1/quality/` | | |
| `/api/v1/quality/open-actions` | | |
| `/api/v1/training/` | | |
| `/api/v1/training/analytics/verdict-distribution` | | |
| `/api/v1/dashboard/order-delay-analytics` | | |

### الخطوة 2: تشخيص DB schema
شغّل السكريبت ده (علشان نتأكد إن الأعمدة المطلوبة موجودة):

```powershell
cd c:\raed_inventory_system\raed_inventory\backend
$env:PYTHONPATH = (Get-Location).Path

python -c "
import sqlite3, os
db_path = 'raed_inventory_local.db'
if not os.path.exists(db_path):
    print('DB not found:', db_path); exit(1)
con = sqlite3.connect(db_path)
cur = con.cursor()

# الجداول المطلوبة
required_tables = [
    'quality_visits', 'quality_visit_responses', 'quality_checklist_items',
    'quality_visit_attachments', 'training_assessments', 'training_templates',
    'training_template_items', 'replenishment_orders',
]
cur.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")
existing = {row[0] for row in cur.fetchall()}
print('=== TABLES ===')
for t in required_tables:
    status = 'OK' if t in existing else 'MISSING'
    print(f'  [{status}] {t}')

# الأعمدة الحرجة
print()
print('=== CRITICAL COLUMNS ===')
checks = [
    ('training_template_items', 'text_en'),
    ('training_template_items', 'benchmark_en'),
    ('replenishment_orders', 'submitted_to_warehouse_at'),
    ('replenishment_orders', 'dispatched_at'),
    ('replenishment_orders', 'received_at'),
    ('replenishment_orders', 'destination_branch_id'),
    ('quality_visit_responses', 'corrective_action'),
    ('quality_visit_responses', 'action_owner'),
    ('quality_visit_responses', 'due_date'),
    ('quality_visit_responses', 'resolved_at'),
]
for tbl, col in checks:
    if tbl not in existing:
        print(f'  [SKIP] {tbl}.{col} (table missing)')
        continue
    cur.execute(f'PRAGMA table_info({tbl})')
    cols = {row[1] for row in cur.fetchall()}
    status = 'OK' if col in cols else 'MISSING'
    print(f'  [{status}] {tbl}.{col}')

# seed counts
print()
print('=== SEED DATA ===')
for tbl in ['training_templates', 'training_template_items', 'quality_checklist_items']:
    if tbl in existing:
        cur.execute(f'SELECT COUNT(*) FROM {tbl}')
        print(f'  {tbl}: {cur.fetchone()[0]} rows')

con.close()
"
```

ابعتلي الـ output كامل.

### الخطوة 3: إصلاح حسب النتيجة

#### الحالة أ — لو أعمدة ناقصة في `quality_visit_responses`
```powershell
python -c "
import sqlite3
con = sqlite3.connect('raed_inventory_local.db')
cur = con.cursor()
# idempotent
for col_def in [
    'corrective_action TEXT',
    'action_owner VARCHAR(100)',
    'due_date DATE',
    'resolved_at DATETIME',
    'resolved_by INTEGER',
    'resolution_notes TEXT',
]:
    col_name = col_def.split()[0]
    cur.execute('PRAGMA table_info(quality_visit_responses)')
    cols = {r[1] for r in cur.fetchall()}
    if col_name not in cols:
        try:
            cur.execute(f'ALTER TABLE quality_visit_responses ADD COLUMN {col_def}')
            print(f'Added {col_name}')
        except Exception as e:
            print(f'Failed {col_name}: {e}')
    else:
        print(f'Skip {col_name} (exists)')
con.commit(); con.close()
"
```

#### الحالة ب — لو جداول ناقصة (`quality_visit_attachments` مثلاً)
```powershell
# أوقف uvicorn أولاً (Ctrl+C أو Get-NetTCPConnection...Stop-Process)
# خد نسخة احتياطية
Copy-Item raed_inventory_local.db "raed_inventory_local.db.bak.$(Get-Date -Format yyyyMMdd_HHmmss)"

# stamp alembic لـ baseline ثم أعد الترقية
alembic stamp a1b2c3d4e5f6
alembic upgrade head
```

#### الحالة ج — لو قوالب التدريب فاضية (training_templates = 0 rows)
```powershell
python seed_quality_training.py
# هيستخدم K2 fix بتاعي اللي فيه sys.stdout.reconfigure → emoji-safe
```

### الخطوة 4: إعادة تشغيل الخادم واختبار
```powershell
# أعد تشغيل uvicorn على 8010
uvicorn app.main:app --reload --port 8010
```

بعدها افتح المتصفح على `http://localhost:3001/`، سجّل دخول admin، وتأكد إن الـ 5 toast errors مختفت.

### الخطوة 5: رد مختصر
- ✅ كله تمام + اللي كان ناقص = ...
- ❌ لسه فيه traceback = [الصق الـ traceback كامل هنا]

---

## ملاحظة
**ممنوع** تحذف DB أو تعمل `alembic downgrade base` — الـ DB دي فيها patches يدوية متراكمة ومحتاج نحافظ عليها لحد ما نصلح مشكلة fresh-DB chain (migration 0004 → quality tables) كـ task منفصل لاحقاً.
