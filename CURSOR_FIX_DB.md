# Cursor Handoff — إصلاح حالة SQLite غير المتسقة + ضبط Vite Proxy

## التشخيص (من تقريرك السابق)
- `alembic upgrade head` فشل في migration `f2a3b4c5d6e7` (0011) لأن جدول `quality_visit_attachments` غير موجود — مع أن migration `c9d0e1f2a3b4` (0008) يُفترض أنه أنشأه.
- `J1 auto-seed` فشل على `no such column: training_template_items.text_en` — العمود تمت إضافته في migration `b8c9d0e1f2a3` (0007).
- **الاستنتاج**: قاعدة SQLite القديمة (`raed_inventory_local.db`) في حالة مبتورة — إما `alembic_version` متقدّم أكثر من الجداول الفعلية، أو الجداول من نسخة سابقة قبل إضافة هذه الـ migrations.
- سلسلة الـ migrations نفسها **سليمة** (تحققت من 0001 → 0012؛ لا توجد فجوات في `down_revision`).

## الحل

### 1) تصفير قاعدة SQLite المحلية وإعادة الترقية
```powershell
cd c:\raed_inventory_system\raed_inventory\backend

# 1. احتفظ بنسخة احتياطية (اختياري لكن مستحسن)
Copy-Item raed_inventory_local.db raed_inventory_local.db.bak -ErrorAction SilentlyContinue

# 2. احذف قاعدة البيانات المحلية
Remove-Item raed_inventory_local.db -ErrorAction SilentlyContinue

# 3. أعد تشغيل الترقية من الصفر
$env:PYTHONPATH = (Get-Location).Path
alembic upgrade head
```

**المتوقع**: تمرّ كل الـ migrations من `a1b2c3d4e5f6` (baseline) حتى `a3b4c5d6e7f8` (seed training templates) بدون أخطاء. لو ظهر خطأ في migration معيّنة، أوقف التنفيذ وارسل الـ stack trace كاملاً.

### 2) تشغيل الخادم على 8010 (لأن 8000 محجوز)
```powershell
$env:PYTHONPATH = (Get-Location).Path
uvicorn app.main:app --reload --port 8010
```

**تحقق من logs الـ startup**:
- ✅ `Application startup complete.`
- ✅ **عدم** ظهور `J1: auto-seed wrapper crashed`
- ✅ **مبدئياً** قد يظهر `J1: training templates auto-seeded on startup` (لو migration 0012 لم تُدرج البيانات، سيقوم الـ startup hook بذلك)

### 3) ضبط Vite Proxy على 8010
أنشئ أو عدّل الملف `frontend/.env.development`:
```
VITE_API_URL=http://localhost:8010
VITE_DEV_PROXY_TARGET=http://localhost:8010
```

ثم شغّل الـ frontend:
```powershell
cd c:\raed_inventory_system\raed_inventory\frontend
npm run dev
```

### 4) اختبار الصفحات الثمانية (يدوياً)
سجّل دخول كـ admin وافتح:
- `/documents`
- `/documents/expiring`
- `/documents/new`
- `/training`
- `/training/new` (اختر قالب — لازم يظهر بنود التقييم، وإلا warning card)
- `/quality`
- `/quality/new`
- `/quality/open-actions`

### 5) لو ظهرت ErrorBoundary في أي صفحة
افتح DevTools → Console → ابحث عن السطر:
```
[ErrorBoundary] caught: <Error> <componentStack>
```
انسخ **كلاً** من `Error message` و `componentStack` كاملين وارجعلي بهم. لا تحاول الإصلاح بنفسك.

### 6) لو فشلت migration معيّنة في الخطوة 1
أرسل لي:
- اسم الـ migration (revision id)
- الـ stack trace كاملاً
- output `alembic current` قبل الفشل

---

## لماذا تصفير DB آمن؟
- البيانات الحالية محلية/تجريبية فقط (SQLite file على جهاز المطوّر).
- الـ migrations تحتوي على seed data للمستخدمين الأساسيين والقوالب — عند إعادة الترقية ستتكرر البيانات المطلوبة.
- نسخة `.bak` محفوظة لو احتجت الرجوع لأي سبب.

**لا تنفّذ هذه الخطوة على DB إنتاج.** هذا للـ local/dev فقط.

---

## الخلاصة المطلوبة منك
بعد التنفيذ، رد:
- ✅ + لقطة من الصفحات السبع الرئيسية لو كلها تعمل
- ❌ + stack trace لو migration فشلت أو صفحة لسه فيها crash
