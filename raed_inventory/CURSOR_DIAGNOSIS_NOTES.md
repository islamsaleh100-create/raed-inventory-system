# تشخيص rate limiting (ج) — ISLAM

---

## Fix applied (2026-04-17)

### الخطوة 1 — `pip install -r requirements.txt`

- **المجلد:** `raed_inventory/backend`
- **Python:** `C:\Users\islam\AppData\Local\Programs\Python\Python311\python.exe` (نفس الـ runtime الذي يُشغَّل منه `pytest`/`uvicorn` هنا).
- **الأمر:** `pip install -r requirements.txt`
- **النتيجة:** تثبيت **`slowapi==0.1.9`** (مع تبعيات `limits`، إلخ).  
  ملاحظة جانبية: تم استبدال إصدارات بعض الحزم لتطابق الملف (مثل **`pytest` 9.x → 8.2.0** حسب `requirements.txt`) — **`pytest --tb=short -q` → 195 passed** بعد تعديل `limiter.py`.

### التحقق من slowapi

- `import slowapi` ناجح؛ الوحدة لا تعرض دائمًا `__version__` — الإصدار مضمّن في اسم الحزمة المثبّتة **`slowapi==0.1.9`**.

### سجل التشغيل (Rate limiting)

عند `import app.main` مع `logging` مفعّل يظهر:

```text
Rate limiting enabled: default=200/minute, auth=20/minute
```

### Smoke (ج) بعد التثبيت — 25× `POST /api/v1/auth/login` (خاطئ)

| الطلبات | رمز HTTP | الملاحظة |
|---------|-----------|----------|
| 1–20 | **401** | `Incorrect username or password` |
| 21–25 | **429** | `Rate limit exceeded: 20 per 1 minute` |

**النتيجة:** يطابق التوقّع (20/minute على مسار login).

### الخطوة 2 — تعديل `app/core/limiter.py` (fail-loud / warning)

**الغرض:** منع **الصمت الخطير** في الإنتاج عندما `RATE_LIMIT_ENABLED=true` لكن `slowapi` غير مثبّت؛ مع إبقاء السلوك متسامحًا في غير الإنتاج مع **تحذير صريح** في السجلات.

**ما أُضيف:**

1. بعد `try/except ImportError`: إن **`not _slowapi_available` و `RATE_LIMIT_ENABLED` و `is_production`** → **`raise RuntimeError(...)`** يوقف التشغيل فورًا.
2. وإلا إن **`not _slowapi_available` و `RATE_LIMIT_ENABLED`** (مثلاً local/staging) → **`logging.warning(...)`** يوضّح أن الحدود معطّلة.

**لماذا لا تعارض مع `pytest`:** `tests/conftest.py` يضبط **`RATE_LIMIT_ENABLED=false`** قبل استيراد التطبيق، فلا يُرفع الخطأ ولا يُصدَر تحذير غير مرغوب في الاختبارات.

**Diff منطقي (ملخّص):** إضافة `import logging`؛ بعد تعريف `_slowapi_available` يُنفَّذ شرط **RuntimeError** للإنتاج، ثم شرط **warning** لأي بيئة فيها تفعيل للحدود دون حزمة.

```diff
+import logging
 from typing import Any, Callable, Optional
 ...
 except ImportError:
     ...
     _slowapi_available = False

+# Fail-loud in production if limits are required but slowapi is missing.
+if not _slowapi_available and settings.RATE_LIMIT_ENABLED and settings.is_production:
+    raise RuntimeError(...)
+
+# In local/staging: explicit warning instead of silent no-op.
+if not _slowapi_available and settings.RATE_LIMIT_ENABLED:
+    logging.getLogger(__name__).warning(...)
+
 limiter: Optional[Any] = None
```

### Pytest بعد التعديل

```text
195 passed
```

---

## التشخيص الأصلي (قبل الإصلاح) — جذر المشكلة

**الخلاصة (جذر المشكلة):** الحزمة **`slowapi` غير مثبّتة** في بيئة Python التي شُغّل منها الـ smoke test و`uvicorn`. عندها يبقى `app.core.limiter.limiter == None`، والـ decorator `limit()` يصبح **no-op** (يُعيد الدالة كما هي)، ولا يُضاف `SlowAPIMiddleware` في `main.py` لأن الشرط `if _shared_limiter is not None` لا يتحقق. لذلك كل طلبات login تُرجع **401** فقط وليس **429**.

هذا **ليس** خطأ في ترتيب الـ decorators ولا تعارض FastAPI 0.111 مع sync handlers في هذه البيئة — التشخيص توقّف عند غياب الحزمة.

---

## المهمّة 1 — تحميل `.env` في runtime

| خطوة | الأمر / الفحص | النتيجة |
|------|----------------|---------|
| 1 | `Get-Content .env \| Select-String "RATE_LIMIT"` من `raed_inventory/backend` | `RATE_LIMIT_ENABLED=true`, `RATE_LIMIT_DEFAULT=200/minute`, `RATE_LIMIT_AUTH=20/minute` — **موجودة وصحيحة**. |
| 2 | `$env:ENV_FILE` | القيمة **` .env`** (ليست فارغة؛ مقبولة حسب شرطك «فارغة أو `.env`»). |
| 3 | `uvicorn ... \| Select-String "Rate limiting"` | **لم يُشغَّل uvicorn هنا**؛ بدلًا منه: استيراد `app.main` مع `logging.basicConfig` **لم يطبع** سطر `"Rate limiting enabled"` لأن فرع التفعيل في `main.py` لا يُنفَّذ أصلًا عندما `limiter is None`. |
| 4 | `python -c "from app.config import settings; ..."` من نفس المجلد | `RATE_LIMIT_ENABLED: True`, `RATE_LIMIT_AUTH: 20/minute`, `RATE_LIMIT_DEFAULT: 200/minute`، و`ENV_FILE` من البيئة يظهر كـ `.env` عند التحقق السابق. |

**تحقق حاسم إضافي (نفس الـ process الذي يشغّل التطبيق):**

```text
python -c "from app.core.limiter import limiter; from app.config import settings; print(limiter); print(settings.RATE_LIMIT_ENABLED)"
```

النتيجة: **`limiter object: None`** مع **`RATE_LIMIT_ENABLED: True`**.

```text
python -c "import importlib.util; print(importlib.util.find_spec('slowapi'))"
```

النتيجة: **`None`** → الحزمة غير موجودة في الـ interpreter.

```text
python -c "import slowapi"
```

النتيجة: **`ModuleNotFoundError: No module named 'slowapi'`**.

**تصنيف حالة المهمّة 1:** الإعدادات من `.env` تُحمَّل عبر Pydantic بشكل صحيح (`RATE_LIMIT_ENABLED=true`). المشكلة **ليست** أن الإعداد يُقرأ `False`. عدم ظهور سجل `"Rate limiting enabled"` يعكس أن **الـ limiter لم يُنشأ أصلًا** (وليس أن السجل مخفي فقط).

---

## المهمّة 2 — فحص slowapi (decorator / تسجيل الحدود)

**لم تُضف** الـ endpoint المقترح `/api/v1/auth/_debug/rate-limit-status` لأن الفحص البرمجي أعلاه أثبت أن **`limiter is None`** قبل أي حاجة لاستعراض `_route_limits` أو أسماء المسارات داخل slowapi. أي endpoint تشخيصي كان سيعيد شيئًا مثل:

- `limiter_configured: false`
- `app_state_has_limiter: false` (لأن `main.py` لا يضع `app.state.limiter` إلا داخل `if _shared_limiter is not None`)

**لو ثُبّت `slowapi` لاحقًا:** يمكن إعادة فتح المهمّة 2 (endpoint أو تتبع تسجيل الحدود) إذا بقي السلوك غير متوقع.

---

## المهمّة 3 — استدعاء مباشر بدون `wrapper` في `limiter.py`

**لم يُنفَّذ** الاستبدال المؤقت `@limiter.limit(...)` على `login` لأن **`limiter` هو `None`**: أي استخدام مباشر لـ `limiter.limit(...)` سيرمي **`AttributeError`** عند التعريف أو عند أول طلب.

بالتالي **لا يمكن** تمييز «فشل الـ wrapper في `limit()`» مقابل «مشكلة slowapi + FastAPI sync» في **هذه** البيئة قبل تثبيت الحزمة.

**الخطوة المنطقية التالية (بعد قرارك):** تثبيت الاعتماديات من `requirements.txt` (يحتوي `slowapi==0.1.9`) على البيئة التي تشغّل الإنتاج/الـ smoke، ثم إعادة اختبار (ج). إذا ظهرت 429 بعد التثبيت، يُغلق التشخيص. إذا لم تظهر، عندها يستحق إعادة فتح المهمّة 2 و3.

---

## مراجع سريعة في الكود

- `app/core/limiter.py`: عند `ImportError` لـ slowapi → `_slowapi_available = False` → `limiter` يبقى `None` → `limit()` يعيد الدالة دون تغيير.
- `app/main.py`: `SlowAPIMiddleware` و`app.state.limiter` فقط عند `_shared_limiter is not None`.
- `requirements.txt`: يذكر `slowapi==0.1.9` — التعارض هنا بين **الملف** و**البيئة الفعلية غير المثبتة**.

---

*التشخيص الأصلي اكتمل ثم طُبّق الإصلاح (تثبيت الاعتماديات + تعديل `limiter.py`)؛ smoke (ج) نجح بعد `pip install`.*
