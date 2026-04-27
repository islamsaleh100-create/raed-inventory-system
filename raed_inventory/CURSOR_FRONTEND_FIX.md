# CURSOR_FRONTEND_FIX — ISLAM (Vite + login عبر الـ proxy)

**التاريخ:** 2026-04-17  
**الحالة:** الخطوات 1–4 **ناجحة**؛ **backend** و**Vite** ما زالا يعملان (لم يُوقفا).

---

## الخطوة 1 — Backend على المنفذ 8000

| البند | النتيجة |
|--------|---------|
| `GET http://127.0.0.1:8000/api/v1/health` | **UP** — `status: healthy` (لم يُحتج لإعادة التشغيل في هذه الجلسة). |

---

## الخطوة 2 — Vite على المنفذ 3000

| البند | النتيجة |
|--------|---------|
| إيقاف ما يستمع على **3000** | تم (عبر `Get-NetTCPConnection` / `netstat` عند الحاجة). |
| تشغيل `npm run dev` | **`Start-Process npm` فشل** على Windows (`%1 is not a valid Win32 application`) لأن `npm` ليس `.exe`. **الإصلاح المستخدم:** `Start-Process -FilePath "C:\Program Files\nodejs\npm.cmd"` مع `-WorkingDirectory` = `raed_inventory/frontend`. |
| جاهزية المنفذ | **`Vite OK on port 3000`** خلال حلقة الانتظار (≤30 ثانية). |

---

## الخطوة 3 — Login عبر الـ proxy (`localhost:3000` → backend)

- انتظار **60 ثانية** قبل الطلب (تفريغ حدّ المحاولات إن وُجد).
- الطلب: `POST http://localhost:3000/api/v1/auth/login` مع `{"username":"admin","password":"Admin@2024"}`.

| البند | النتيجة |
|--------|---------|
| النجاح | **نعم** |
| `access_token` | طول **119** |
| `user.username` | **admin** |
| `user.roles` | **super_admin** |

---

## الخطوة 4 — `index.html` و `main.jsx`

| البند | النتيجة |
|--------|---------|
| `GET http://localhost:3000/` | المحتوى يطابق **`main.jsx`** — **Vite يخدم الصفحة بشكل صحيح** للتحقق البرمجي. |

---

## سجلات (أخطاء / تحذيرات)

### `frontend/vite.err.log`

يظهر **خطأ Vite داخلي** عند تحليل الوحدات (لا يمنع استجابة `/` ولا البروكسي لـ `/api` في هذا الاختبار):

```text
Failed to resolve import "@sentry/react" from "src/utils/sentry.js"
```

**التفسير:** الحزمة `@sentry/react` غير مثبّتة في `frontend/package.json` / `node_modules` بينما `src/utils/sentry.js` يستوردها ديناميكيًا — قد يظهر الخطأ عند تحميل مسار يمرّ على هذا الملف. **لم يُعالَج في هذه الجلسة** (طلبك: تشغيل + تحقق login فقط).

### `backend/uvicorn.err.log`

لم يُعاد تشغيل الـ backend هنا؛ لا توجد أخطاء جديدة مُبلَّغ عنها في هذه الخطوة.

---

## ما يفعله ISLAM بعد النجاح

1. افتح **http://localhost:3000** (وليس 5173 في هذا الإعداد الافتراضي لـ `VITE_DEV_PORT`).
2. سجّل الدخول: **admin** / **Admin@2024**.

**السيرفران يعملان:** Backend **127.0.0.1:8000** + Vite **localhost:3000** — **لم يُوقفا** بعد كتابة هذا التقرير.
