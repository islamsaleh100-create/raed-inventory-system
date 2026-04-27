# CURSOR_SERVER_FIX — ISLAM (backend + admin reset)

**التاريخ:** 2026-04-17  
**المنصة:** Windows / PowerShell  
**ملاحظة:** خادم `uvicorn` ما زال يعمل على المنفذ **8000** بعد هذه الجلسة (لم يُوقف عمدًا).

**ملخص سريع:** الخطوات 1–4 كلها **ناجحة**.

---

## حالة الخطوات

| الخطوة | الحالة | ملاحظات |
|--------|--------|---------|
| **1** — إيقاف Python/uvicorn وفحص journal | **نجح** | `Get-Process` ثم `Stop-Process`؛ لا يوجد `raed_inventory_local.db-journal` بشكل دائم (بعد الانتظار). |
| **2** — `reset_password.py` + التحقق من الـ DB | **نجح** | `python reset_password.py` → `Done!` / `Username: admin` / `Password: Admin@2024`. استعلام SQLite: **`Admin row: ('admin', 60)`** (طول bcrypt). *أول محاولة لـ `python -c` مع SQL فشلت بسبب quoting في PowerShell؛ أُعيد التحقق باستعلام آمن بـ `?`.* |
| **3** — `slowapi` + تشغيل uvicorn على 8000 | **نجح** | `slowapi OK`. `$env:ENV_FILE = ".env"`. التشغيل: `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` مع إعادة توجيه إلى `uvicorn.out.log` / `uvicorn.err.log` تحت `raed_inventory/backend/`. |
| **4** — login برمجي بعد 65 ثانية | **نجح** | بعد `Start-Sleep -Seconds 65`: **`Login OK`** — طول `access_token` ≈ **119**، `user.username` = **admin**. |

---

## DATABASE_URL (كما يقرأها التطبيق عند التحميل من `.env`)

```text
sqlite:///C:/raed_inventory_system/raed_inventory/backend/raed_inventory_local.db
```

الأمر المستخدم للطباعة: `python -c "from app.config import settings; print(settings.DATABASE_URL)"` مع `$env:ENV_FILE = ".env"` من مجلد `backend`.

---

## سجلات التشغيل (الخطوة 3)

- **`uvicorn.err.log` (آخر أسطر):** يظهر `Uvicorn running on http://127.0.0.1:8000`.
- **سطر rate limiting:** يظهر في **`uvicorn.out.log`** (stdout من التطبيق)، مثال:
  - `[INFO ...] app.main | Rate limiting enabled: default=200/minute, auth=20/minute`

---

## نتيجة login البرمجي (الخطوة 4)

- **الطلب:** `POST http://127.0.0.1:8000/api/v1/auth/login` مع `{"username":"admin","password":"Admin@2024"}`.
- **النتيجة:** نجاح — `access_token` موجود و`user.username` = `admin`.
- **لم يظهر 401 أو 429** بعد انتظار 65 ثانية (تفريغ حدّ المحاولات السابقة إن وُجد).

---

## ما تفعله بعد النجاح (ISLAM)

1. افتح الواجهة: **http://localhost:5173**
2. سجّل الدخول: **`admin` / `Admin@2024`**

**الخادم:** `uvicorn` ما زال في الخلفية على **127.0.0.1:8000** (PID الظاهر في `netstat`: **10836** عند التحقق). لإيقافه لاحقًا: `Stop-Process -Id 10836 -Force` (أو إيقاف كل `python` بحذر).

---

## ملفات السجل المحلية

- `raed_inventory/backend/uvicorn.out.log`
- `raed_inventory/backend/uvicorn.err.log`
