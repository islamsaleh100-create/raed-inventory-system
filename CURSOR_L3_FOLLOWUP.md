# Cursor Handoff — L3 Follow-up: لماذا القوالب لا تظهر في UI رغم وجودها في DB؟

## ما نعرفه من الـ probe السابق
- `training_templates: 2 rows` ✅
- `training_template_items: 38 rows` ⚠️ (قليل جداً — باريستا لوحده لازم يكون ~60+ بند)
- كل الـ 5 endpoints بترجع 200 في الـ TestClient

## الاحتمالات الثلاث (بالترتيب)
1. **uvicorn بيستخدم DB مختلف** — ملف تاني غير اللي عالجنا فيه
2. **الـ seed ركض جزئياً** — التمبليتس اتضافت لكن بنودها ناقصة
3. **القوالب `is_active=False`** — الـ API فيلتر بـ `TrainingTemplate.is_active == True`

## المطلوب — 3 فحوصات متتالية

### فحص 1: تأكد من مسار DB اللي uvicorn بيستخدمه

```powershell
cd c:\raed_inventory_system\raed_inventory\backend
$env:PYTHONPATH = (Get-Location).Path

python -c "
from app.database import engine
print('DB URL uvicorn uses:', engine.url)
print('Resolved path:', engine.url.database)
import os
if engine.url.database and os.path.exists(engine.url.database):
    print('File exists:', os.path.abspath(engine.url.database))
    print('Size:', os.path.getsize(engine.url.database), 'bytes')
    print('Modified:', os.path.getmtime(engine.url.database))
else:
    print('WARNING: file does not exist at that path!')
"
```

قارن الـ path ده بالملف اللي ضفتلك الأعمدة فيه (`raed_inventory_local.db`). لو مختلفين = السبب لقيناه.

### فحص 2: محتوى القوالب + is_active + عدد بنود كل قسم

```powershell
python -c "
import sqlite3, os
# استخدم نفس الـ path اللي طلع من فحص 1
from app.database import engine
db_path = engine.url.database
con = sqlite3.connect(db_path)
cur = con.cursor()

print('=== TEMPLATES ===')
cur.execute('SELECT id, name_ar, role_type, is_active, version FROM training_templates')
for r in cur.fetchall(): print(' ', r)

print()
print('=== SECTIONS per template ===')
cur.execute('''
  SELECT t.id, t.name_ar, COUNT(s.id) as section_count
  FROM training_templates t
  LEFT JOIN training_template_sections s ON s.template_id = t.id
  GROUP BY t.id
''')
for r in cur.fetchall(): print(' ', r)

print()
print('=== ITEMS per section (with section names) ===')
cur.execute('''
  SELECT s.id, s.name_ar, t.name_ar as template, COUNT(i.id) as item_count
  FROM training_template_sections s
  LEFT JOIN training_template_items i ON i.section_id = s.id
  LEFT JOIN training_templates t ON t.id = s.template_id
  GROUP BY s.id
  ORDER BY t.id, s.id
''')
for r in cur.fetchall(): print(f'  section={r[0]:>3} items={r[3]:>3}  {r[2][:20]:<20} → {r[1]}')

con.close()
"
```

**المتوقع**:
- Barista: 8 sections، كل قسم ~5-8 بنود
- Manager: 7 sections، كل قسم ~5-8 بنود
- إجمالي: ~90-120 بند

**لو لقيت**:
- `is_active=0` على أي template → حدّثه لـ 1
- أقسام بـ 0 بنود → الـ seed ركض جزئياً، هنعيده
- Templates مش موجودة أصلاً → Drop & re-seed

### فحص 3: هل الـ endpoint بيرجع القوالب فعلاً؟

```powershell
python -c "
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token
client = TestClient(app)
token = create_access_token(subject='1')
r = client.get('/api/v1/training/templates', headers={'Authorization': f'Bearer {token}'})
print('Status:', r.status_code)
import json
data = r.json()
print('Count:', len(data) if isinstance(data, list) else 'NOT A LIST')
if isinstance(data, list):
    for t in data:
        print(f\"  id={t.get('id')} name={t.get('name_ar')} role={t.get('role_type')} sections={len(t.get('sections', []))}\")
"
```

**المتوقع**: `Count: 2` واتنين قوالب بأقسام.

لو `Count: 0` مع وجود templates في DB → غالباً `is_active=False` أو role_type filter.

## الإصلاح حسب النتيجة

### أ) DB path مختلف
```powershell
# شوف في app/config.py أو .env
python -c "from app.database import engine; print(engine.url)"
# لو بيشاور على ملف تاني، نسخ القوالب للملف الصح:
python -c "
import shutil
# استبدل SRC بمسار الـ DB اللي فيه القوالب، DEST بمسار اللي uvicorn بيستخدمه
shutil.copy('SRC', 'DEST')
"
# أو حدّث الـ config ليبص على الصح
```

### ب) قوالب is_active=False
```powershell
python -c "
import sqlite3
from app.database import engine
con = sqlite3.connect(engine.url.database)
con.execute('UPDATE training_templates SET is_active = 1')
con.commit(); con.close()
print('All templates activated')
"
```

### ج) bنود ناقصة (seed جزئي)
```powershell
# نمسح بس الـ templates + sections + items ونعيد seed من الأول
python -c "
import sqlite3
from app.database import engine
con = sqlite3.connect(engine.url.database)
for tbl in ['training_template_items', 'training_template_sections', 'training_templates']:
    con.execute(f'DELETE FROM {tbl}')
con.commit(); con.close()
print('Training template tables cleared')
"
python seed_quality_training.py
```

بعدها فحص 2 تاني علشان نتأكد العدد صح.

### د) Drop & re-seed كامل لو كله مكسّر
لا تلجأله إلا كآخر حل.

## الخطوة النهائية — اختبار المتصفح
1. أعد تشغيل uvicorn (Ctrl+C ثم شغّله تاني — علشان الـ ORM session يرفريش)
2. في المتصفح اعمل **hard refresh** (Ctrl+Shift+R)
3. افتح `/training/new` وتأكد من الـ dropdown

## الرد
- ✅ + عدد القوالب في الـ dropdown بعد الإصلاح
- ❌ + output الفحوصات الثلاث كاملة
