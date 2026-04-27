# Cursor Handoff — الخطوة الأخيرة: إعادة تشغيل الخادم والاختبار

## حالة DB الحالية
- `alembic current`: `a3b4c5d6e7f8 (head)` ✅
- أعمدة `text_en` / `benchmark_en` موجودة في `training_template_items` ✅
- migration 0012 اكتملت (seed تخطّى بسبب emoji encoding على Windows — معالج الآن)

## إصلاح جديد أُضيف (K2)
`backend/seed_quality_training.py`:
- force UTF-8 على stdout/stderr via `sys.stdout.reconfigure`
- fallback `_safe_print` يحوّل emojis لـ `?` بدل رفع UnicodeEncodeError
- النتيجة: J1 auto-seed في `main.py` هيشتغل نظيف على Windows عند إعادة تشغيل uvicorn.

---

## المطلوب منك الآن (خطوات مختصرة)

### 1) أوقف أي uvicorn شغّال
```powershell
# لو في process شغّال على المنفذ 8010 أو 8000:
Get-NetTCPConnection -LocalPort 8010 -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
}
# أو يدويًا: Ctrl+C على النافذة اللي بيها uvicorn
```

### 2) شغّل uvicorn من جديد على 8010
```powershell
cd c:\raed_inventory_system\raed_inventory\backend
$env:PYTHONPATH = (Get-Location).Path
uvicorn app.main:app --reload --port 8010
```

**تحقق من logs الـ startup**. المتوقع:
- ✅ `Application startup complete.`
- ✅ مفيش `J1: auto-seed wrapper crashed`
- قد يظهر `J1: training templates auto-seeded on startup` (مرة واحدة فقط، لو كانت فاضية)
- ⚠️ لو ظهرت مشكلة emoji تانية، معناها الـ reconfigure مش ماشي على نسخة Python القديمة — ارجعلي الـ log.

### 3) شغّل Vite (إذا لم يكن شغّالًا)
```powershell
cd c:\raed_inventory_system\raed_inventory\frontend
npm run dev
```

### 4) افتح المتصفح واختبر الصفحات الثمانية
افتح `http://localhost:5173/` (أو المنفذ اللي Vite بيستخدمه)، سجّل دخول كـ admin، ومن الـ sidebar افتح بالترتيب:

| المسار | المتوقع |
|--------|---------|
| `/documents` | قائمة وثائق (حتى لو فاضية) — مش ErrorBoundary |
| `/documents/expiring` | قائمة وثائق مقاربة على الانتهاء |
| `/documents/new` | فورم إنشاء وثيقة |
| `/training` | قائمة تقييمات التدريب |
| `/training/new` | اختر قالب → يعرض بنود أو warning card "القالب لا يحتوي على بنود" |
| `/quality` | قائمة زيارات الجودة |
| `/quality/new` | فورم زيارة جديدة — يعرض checklist |
| `/quality/open-actions` | الإجراءات المفتوحة |

### 5) النتيجة
- **لو كل الصفحات تفتح** (بدون شاشة "حدث خطأ غير متوقع"): رد بـ ✅
- **لو فيه صفحة بتكرّش**: 
  1. افتح DevTools → Console
  2. ابحث عن السطر `[ErrorBoundary] caught:`
  3. انسخ الـ Error message + componentStack **كاملين**
  4. ارجعلي بهم — لا تحاول الإصلاح

---

## ملاحظة عن مشكلة fresh-DB (خارج نطاق اليوم)
رصدت إن `_chain_full.db` من الصفر بيتوقف عند migration 0004 (`no such table: quality_visits`) — ده يعني baseline ما بيخلقش الجداول الكاملة. ده إصلاح منفصل، مش ضروري دلوقتي لأن الـ DB الحالي سليم. سجّله لاحقًا كـ task منفصل.
