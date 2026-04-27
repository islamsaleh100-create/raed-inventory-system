# Cursor Handoff — L3: تشغيل seed قوالب التدريب

## السياق
- الـ DB حالياً على head بعد الإصلاحات السابقة (L1: أعمدة ناقصة اتضافت)
- قوالب التدريب **مفقودة**: migration 0012 seed اتخطّى على Windows بسبب emoji encoding
- `backend/seed_quality_training.py` متحطّش عليه K2 fix (UTF-8 reconfigure + _safe_print) فالتشغيل المباشر المفروض يشتغل

## الناقص من واجهة `/training/new`
1. **نموذج تقييم الباريستا** (`role_type=branch_employee`) — 8 أقسام (المهارات الفنية، الخدمة، الالتزام، السرعة، التنظيم، التعلم، المظهر، الكاشير)
2. **نموذج تقييم مدير الفرع** (`role_type=branch_manager`) — 7 أقسام (العمليات، القيادة، الجودة، خدمة العملاء، الإدارة المالية، التقارير، البلدية)

كلاهما معرّف في `seed_quality_training.py` لكن مش موجودين في DB لأن الـ seed ماركضش.

## المطلوب

### 1) تأكد إن الملف فيه K2 fix
```powershell
cd c:\raed_inventory_system\raed_inventory\backend

# لازم يطلع True:
python -c "import pathlib; t = pathlib.Path('seed_quality_training.py').read_text(encoding='utf-8'); print('K2 OK:', 'sys.stdout.reconfigure' in t and '_safe_print' in t)"
```

لو طلع `K2 OK: False` ابعتلي وأنا هطلع الإصلاح. لو `True` كمّل.

### 2) شغّل الـ seed
```powershell
$env:PYTHONPATH = (Get-Location).Path
python seed_quality_training.py
```

المتوقع تشوف سطور زي:
- `Section created: الجودة`
- `Template created: نموذج تقييم الباريستا`
- `Template created: نموذج تقييم مدير الفرع`
- أو `Template updated: ...` لو فيه سجلات قديمة

**لو طلع `UnicodeEncodeError`**: معناه K2 fix مش مطبّق صح. ابعتلي الـ traceback.

**لو طلع خطأ SQL** (مثلاً `no such column`): معناه لسه فيه أعمدة ناقصة — L1 ما كملتش. ابعتلي اسم العمود.

### 3) تحقق من DB مباشرة
```powershell
python -c "
import sqlite3
con = sqlite3.connect('raed_inventory_local.db')
cur = con.cursor()
cur.execute('SELECT id, name_ar, role_type FROM training_templates ORDER BY id')
rows = cur.fetchall()
print(f'Templates in DB: {len(rows)}')
for r in rows: print(' ', r)

cur.execute('SELECT template_id, COUNT(*) FROM training_template_sections GROUP BY template_id')
print()
print('Sections per template:')
for r in cur.fetchall(): print(' ', r)

cur.execute('SELECT section_id, COUNT(*) FROM training_template_items GROUP BY section_id LIMIT 5')
print()
print('Items per section (first 5):')
for r in cur.fetchall(): print(' ', r)
con.close()
"
```

**المتوقع**: 2 templates، والأقسام بالعدد الصحيح (8 للباريستا + 7 للمدير = 15 قسماً)، وبنود في كل قسم.

### 4) اختبار عملي من المتصفح
(بعد التأكد إن DB فيها القوالب)

- افتح `/training/new`
- في الـ dropdown اللي بعنوان "اختر القالب"، لازم تلاقي:
  - نموذج تقييم الباريستا
  - نموذج تقييم مدير الفرع
- اختار واحد منهم — لازم يعرض كل الأقسام والبنود (مش warning card "القالب فاضي")

### 5) رد مختصر
- ✅ اتنين قوالب موجودين في الـ dropdown وبيفتحوا بالبنود
- ❌ + tracebacks من خطوة 2 أو 3

## لو الـ dropdown لسه فاضي بعد seed ناجح
افحص الـ API response:
```powershell
python -c "
from app.main import app
from fastapi.testclient import TestClient
from app.core.security import create_access_token
client = TestClient(app)
token = create_access_token(subject='1')
r = client.get('/api/v1/training/templates', headers={'Authorization': f'Bearer {token}'})
print('Status:', r.status_code)
print('Body:', r.json())
"
```

لو 200 وفاضي = الاستعلام بيفلتر. لو 200 وفيه قوالب = الـ frontend مش بينزلها. لو 500 = ابعت الـ traceback.
