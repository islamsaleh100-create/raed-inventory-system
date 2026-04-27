# Cursor Handoff — تطبيق إصلاحات K1 + إعادة التشغيل

## السياق
تم إصلاح crashes في ErrorBoundary على صفحات الجودة / التدريب / الوثائق.
التغييرات محفوظة بالفعل في الـ repo. مطلوب منك:

1. تشغّل الـ backend من جديد (فيه تعديلات حرجة في services كانت عاملة syntax errors).
2. تشغّل / تعيد build للـ frontend.
3. تتأكد إن 3 صفحات بتفتح بدون ErrorBoundary.

---

## الملفات اللي اتعدّلت (للمرجع فقط، لا تعدّلها أنت)

### Backend
- `backend/app/services/quality_service.py` — أُغلق dict مفتوح في `compliance_trend` (كان بيكسر import)
- `backend/app/services/inter_branch_service.py` — أُغلق `return {` مفتوح في `reject_inter_branch_order`
- `backend/app/services/document_service.py` — guards لـ null `expiry_date`
- `backend/app/routers/documents.py` — try/except على `/expiring`
- `backend/app/main.py` — auto-seed لـ training templates عند الـ startup

### Frontend
- `frontend/src/pages/training/TrainingPages.jsx` — null-safe على sections/items
- `frontend/src/pages/quality/QualityPages.jsx` — null-safe على checklist/responses
- `frontend/src/pages/documents/DocumentsPages.jsx` — Array.isArray guards + catch handlers

---

## المطلوب تنفيذه

### 1) Backend — إعادة التشغيل
```bash
cd backend

# تحقق من صحة Python syntax أولاً
python -c "import ast; 
for f in ['app/services/quality_service.py','app/services/inter_branch_service.py','app/services/document_service.py','app/routers/documents.py','app/main.py']:
    ast.parse(open(f).read())
print('backend syntax OK')"

# شغّل alembic عشان الـ migrations تتطبّق
alembic upgrade head

# شغّل الخادم (استخدم الأمر المعتاد في المشروع)
uvicorn app.main:app --reload --port 8000
```

تحقق إن الـ log يطبع:
- `J1: training templates auto-seeded on startup` (لو أول تشغيل)
- **لا** يطبع `SyntaxError` أو `ImportError`

### 2) Frontend — إعادة التشغيل
```bash
cd frontend

# تحقق من JSON الـ i18n
node -e "JSON.parse(require('fs').readFileSync('src/i18n/dict/en.json')); JSON.parse(require('fs').readFileSync('src/i18n/dict/ar.json')); console.log('i18n JSON OK')"

# شغّل dev server
npm run dev
```

أو لو production build:
```bash
npm run build && npm run preview
```

### 3) التحقق الوظيفي (يدوياً في المتصفح)
سجّل دخول كـ admin وافتح الصفحات دي بالترتيب. لازم **كلها** تفتح بدون شاشة "حدث خطأ غير متوقع":

- [ ] `/documents` — صفحة إدارة الوثائق
- [ ] `/documents/expiring` — وثائق مقاربة على الانتهاء
- [ ] `/documents/new` — إنشاء وثيقة جديدة
- [ ] `/training` — قائمة تقييمات التدريب
- [ ] `/training/new` — تقييم جديد (اختر قالب واتأكد إنه يعرض بنود أو يعرض warning card لو فاضي)
- [ ] `/quality` — قائمة زيارات الجودة
- [ ] `/quality/new` — زيارة جديدة (لازم يعرض checklist)
- [ ] `/quality/open-actions` — الإجراءات المفتوحة

### 4) لو ظهرت ErrorBoundary في أي صفحة
افتح DevTools → Console → ابحث عن السطر اللي بيبدأ بـ:
```
[ErrorBoundary] caught:
```
انسخ الـ stack trace كاملاً وارجعلي به. لا تحاول تصلحها بنفسك — الإصلاح يحتاج context من الـ conversation السابقة.

### 5) لو الخادم رفض يشتغل
- تأكد إن الـ DB متصل وإن الـ migrations طبّقت بنجاح
- شوف logs الـ startup عشان تشيك auto-seed errors
- لو `seed_quality_training` رمى exception، مش مشكلة — هيكمل بدون crash (مجرد warning في الـ log)

---

## الخلاصة
بعد التنفيذ، رد عليّا بـ:
- ✅ لو كل الصفحات بتفتح
- ❌ + stack trace لو فيه صفحة لسه بتكرّش
