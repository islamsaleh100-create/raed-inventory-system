# Phase 7 — Self-review & smoke notes (ISLAM)

## 1. Code review

### (أ) `backend/app/services/audit_service.py` — أربعة أسطر

1. **قبل:** قراءة `AUDIT_LOG_ENABLED` مرة عند استيراد الوحدة؛ تغيير `os.environ` لاحقًا لا يؤثر على الكتابة حتى restart.
2. **بعد:** كل استدعاء لـ `log()` يقرأ البيئة عبر `_audit_writes_enabled()` فيقرر التخطي أو الكتابة لحظيًا.
3. **تأثير على callers خارج الاختبارات:** **نعم بحدّ ضئيل** فقط إن وُجد تبديل للمتغير بعد التحميل دون restart؛ في التشغيل المعتاد بملف `.env` عند البدء السلوك كما كان تقريبًا.
4. **عقد idempotency:** **لا ينطبق** على هذا المسار (لا `client_request_id`).

### (ب) `backend/app/services/inventory_service.py` — `approve_inventory_for_user` — أربعة أسطر

1. **قبل:** جرد `approved` → رفع 409 قبل فحص idempotency؛ إعادة الطلب بنفس المفتاح كانت تُرجع 409 بدل replay.
2. **بعد:** بناء `replay_payload` ثم `_try_begin_idempotent_operation` أولًا؛ عند سجل مكتمل لنفس المفتاح → إرجاع replay؛ وإلا فحص «موافق مسبقًا» ثم الموافقة.
3. **تأثير على callers خارج الاختبارات:** **نعم** لمسار واحد: إعادة نفس `client_request_id` بعد نجاح الموافقة → **200 + replay** بدل **409** (سلوك idempotency المتوقع).
4. **عقد idempotency:** **نعم** — نفس `client_request_id` بعد اكتمال العملية يعيد نفس فئة النجاح (**200**) مع `_idempotency.replayed` وpayload مبني من الحالة الحالية.

### Concerns

- **`audit_service`:** زيادة طفيفة في تكلفة `getenv` لكل سطر audit (عادة غير مؤثرة). لا يوجد تخزين مؤقت لقيمة المعطّل — مقصود للوضوح.
- **`approve_inventory_for_user`:** `replay_payload` يُبنى قبل التحقق من الحالة؛ إن كان الجرد لا يزال `submitted` في الطلب الأول ولم يكتمل السجل بعد، السلوك كما كان. لا تغيير على مسار «لا يوجد `client_request_id`».
- **Smoke (ج) — يحتاج متابعة ISLAM:** لم يظهر **429** على `/api/v1/auth/login` بعد 25 طلبًا متتاليًا بكلمة مرور خاطئة (كل الاستجابات **401**). الـ `.env` المحلي يعرّف `RATE_LIMIT_ENABLED=true` و`RATE_LIMIT_AUTH=20/minute`. الأسباب المحتملة: ترتيب الـ decorators مع FastAPI، أو أن الـ worker لم يحمّل `.env` كما توقّعت، أو إصدار/تهيئة slowapi. **لم يُجرَ أي تعديل على الكود من أجل الـ smoke.**

---

## 2. Smoke test results

**البيئة:** `python -m uvicorn app.main:app --host 127.0.0.1 --port 8765` من مجلد `raed_inventory/backend` (مهمة خلفية ثم انتظار ~3 ثوانٍ).

| الاختبار | النتيجة | التفاصيل |
|-----------|---------|-----------|
| **(أ) OpenAPI** | **نجح** | في `openapi.json` ظهر المساران: `/api/v1/orders/{order_id}/close` و `/api/v1/orders/{order_id}/timeline`. |
| **(ب) `X-Request-ID`** | **نجح** | `GET http://127.0.0.1:8765/api/v1/health` — الهيدر `X-Request-ID` = `f034df05e58946daa3b5b5daeb609322` (32 حرفًا hex، غير فارغ). |
| **(ج) Rate limit على login** | **فشل (regression مقلق لـ Phase 7)** | حلقة 25 طلبًا `POST /api/v1/auth/login` بجسم `nonexistent` / `wrong` — **جميع** الردود **401** (`Incorrect username or password`)، **بدون أي 429**. |

**ملاحظة تنفيذ:** أوامر التوقف الافتراضية لـ `Stop-Job -Force` قد لا تكون مدعومة في إصدار PowerShell هنا؛ يُنصح بمراجعة عمليات `python`/المنفذ 8765 يدويًا إن لزم.

---

## 3. Git

**Git not found — ISLAM must run these commands manually:**  
لم يُعثر على `git` في PATH ولا في المسارات: `C:\Program Files\Git\bin\git.exe`, `C:\Program Files\Git\cmd\git.exe`, `%LOCALAPPDATA%\Programs\Git\bin\git.exe`.

```powershell
cd c:\raed_inventory_system\raed_inventory
git init
git branch -M main
git add -A
git commit -m "Phase 7 hardening + test suite to 195 passed

- Add CI/CD workflows (.github/workflows/ci.yml, security.yml)
- Add request_id middleware + Sentry scaffold (backend + frontend)
- Add shared slowapi limiter + per-route limit on /auth/login
- Add backup_db.sh + RESTORE_PROCEDURE.md + pre-commit config
- Add /orders/{id}/close and /orders/{id}/timeline endpoints
- Add ADMIN_GUIDE.md + BRANCH_USER_GUIDE.md (Arabic)
- Fix 15 remaining failing tests (5 categories)
- audit_service: read AUDIT_LOG_ENABLED per-call
- inventory_service: idempotency replay before already-approved check"

git log --oneline
```

لا يوجد `push` من هذه الجلسة.
