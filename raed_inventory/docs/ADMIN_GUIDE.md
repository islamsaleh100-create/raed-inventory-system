# دليل المسؤول — نظام رائد للمخزون

> الجمهور: مدير النظام (super_admin) / المدير العام (admin) / مدير العمليات
> (operations_manager).

---

## ١. نظرة عامة

نظام **رائد** يدير المخزون اليومي لـ **٣٢ فرع** + **مستودعَيْن** + **٥٤ صنفًا**
لسلسلة مقاهي/مطاعم. يغطّي:

- جرد يومي لكل فرع مع دورة اعتماد.
- طلبيات تعويض (يومية + استثنائية) بدورة مراجعة متعدّدة الطبقات.
- تحويلات بين الفروع والمستودعات.
- زيارات الجودة وتقييمات التدريب.
- تحليلات تطبيقات التوصيل.

التوقيت الرسمي: **Asia/Riyadh**. كل تاريخ يُخزَّن UTC ويُعرض AST.

---

## ٢. الأدوار والصلاحيات

| الدور                 | الوصف                                                                |
|-----------------------|----------------------------------------------------------------------|
| `super_admin`         | صلاحية كاملة — لا يُستخدم في التشغيل اليومي.                         |
| `admin`               | إدارة المستخدمين والبيانات الأساسية وتقارير النظام.                 |
| `operations_manager`  | يعتمد الطلبيات على مستوى المنظّمة، يُشرف على الدورات.               |
| `area_manager`        | **يرى فروع منطقته فقط** (بناءً على city/area match).                |
| `branch_manager`      | يرى فرعه فقط — يُنشئ الجرد والطلبيات.                              |
| `branch_user`         | إدخال البيانات داخل فرعه فقط.                                      |
| `warehouse_manager`   | يعتمد وصرف الطلبيات من مستودعه.                                     |
| `warehouse_user`      | picking / dispatch / receive داخل مستودعه.                          |
| `quality_manager`     | تصميم الفحوص واعتمادها على مستوى المنظّمة.                         |
| `quality_visitor`     | زيارات الجودة الميدانية.                                            |

> **ملاحظة هامة:** مدير المنطقة لا يرى خارج منطقته. إذا احتاج فرع في منطقة أخرى
> (حالة استثنائية) ارفع الصلاحية مؤقتًا عن طريق `admin`.

---

## ٣. التشغيل الأول

### ٣.١ ضبط متغيّرات البيئة

انسخ `backend/.env.example` إلى `backend/.env.production` وحدِّد:

```
DATABASE_URL=postgresql://raed:STRONG_PASSWORD@db-host:5432/raed
SECRET_KEY=ولِّد قيمة عشوائية ٤٨ حرفًا — لا تستخدم الافتراضي!
ENVIRONMENT=production
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@yourdomain.com
ADMIN_PASSWORD=كلمة مرور قوية ≥ ١٢ حرف
DEFAULT_TIMEZONE=Asia/Riyadh
RATE_LIMIT_ENABLED=true
RATE_LIMIT_DEFAULT=200/minute
RATE_LIMIT_AUTH=20/minute
ALLOWED_ORIGINS=https://app.yourdomain.com
SENTRY_DSN=             # اختياري — لتفعيل Sentry
```

### ٣.٢ تشغيل migrations

```bash
cd backend
alembic upgrade head
```

تحقّق من الـ revision الحالي:

```bash
alembic current
```

### ٣.٣ seed البيانات الأوّلية

```bash
python seed.py               # ينشئ admin + الأدوار + categories/units
python insert_branches.py    # الفروع والمستودعات
python create_branch_users.py  # مستخدم لكل فرع
```

### ٣.٤ التحقّق الأوّلي

- افتح `/api/docs` → تأكّد من ظهور الـ Swagger.
- سجّل دخول كـ admin → غيّر كلمة المرور فورًا.
- افتح `/api/v1/health` → يجب أن يرجع `{"status": "healthy"}`.

---

## ٤. إدارة المستخدمين

### ٤.١ إنشاء مستخدم

من واجهة الـ frontend: **المستخدمون → إضافة**. المطلوب:

- الاسم الكامل، username (فريد)، email.
- الدور (واحد أو أكثر).
- للـ branch_user / branch_manager: `branch_id`.
- للـ warehouse_user / warehouse_manager: `warehouse_id`.
- كلمة مرور تلبّي: ٨+ أحرف، حرف كبير، رقم.

### ٤.٢ تعطيل مستخدم

- **لا تحذف** — عيّن `status = inactive`. يحافظ على سجلّات التدقيق.
- إذا ترك الموظّف العمل نهائيًا: `DELETE /api/v1/users/{id}` ينفّذ soft-delete.

### ٤.٣ إعادة تعيين كلمة مرور

من لوحة admin: **المستخدمون → {{user}} → إعادة تعيين كلمة المرور**. يُرسل للمستخدم
كلمة مؤقّتة (يغيّرها عند أوّل دخول).

---

## ٥. البيانات الأساسية (Master Data)

### ٥.١ المستودعات والفروع

- المستودعات أوّلاً، ثم الفروع (كل فرع ينتمي لمستودع).
- حقل **المنطقة/المدينة** (`city` / `area`) يحدّد نطاق مدير المنطقة —
  تأكّد من تعبئته بشكل متسق (مثال: "الرياض"، "جدة"، لا تخلطهم بـ "الرياض العليا").

### ٥.٢ الأصناف (Items)

- كل صنف له `unit_id` وحد أدنى (`min_stock`) وحد أعلى (`max_stock`).
- `active=false` يُخفيه من القوائم الجديدة لكنه يبقى في السجلّات.

### ٥.٣ فئات الأصناف (Categories)

- هرمية: category → items. يُستخدم في تقارير PDF والـ filters.

---

## ٦. دورة الطلبيات (Orders Lifecycle)

```
draft → branch_review → warehouse_review → approved → picking →
dispatched → received → closed
```

- `cancel` ممكن قبل `dispatched`. بعد `dispatched` الإلغاء ممنوع (لازم `close` مع فرق).
- `close` (جديد) يُنهي الطلبية بعد استلامها ويقفل السطر في ledger.
- `timeline` endpoint يرجع كل أحداث الطلبية مع timestamps.

**قاعدة الـ idempotency:** كل endpoint حسّاس يقبل header `X-Idempotency-Key`
(UUID). تكرار نفس الـ key خلال ٢٤ ساعة يرجع نفس الاستجابة بدون تنفيذ مضاعف.

---

## ٧. النسخ الاحتياطي

- السكربت: `backend/scripts/backup_db.sh`.
- يشغَّل يوميًا عبر cron على الخادم — راجع التعليق في رأس السكربت.
- الرفع على S3 اختياري — عيّن `S3_BUCKET` في env.
- **اختبار الاستعادة شهريًا** — راجع `backend/scripts/RESTORE_PROCEDURE.md`.

> **تذكِرة:** نسخة لم تُختبر = لا توجد.

---

## ٨. المراقبة والتنبيهات

- لوج JSON على stdout — جمِّعه عبر journalctl/CloudWatch/ELK.
- كل سطر لوج يحتوي `request_id` — تتبّع الـ request عبر الخدمات.
- Sentry (اختياري) — عيّن `SENTRY_DSN`.
- `/health` و`/api/v1/health` للـ liveness/readiness probes.
- الـ metric الأهم للمراقبة: معدّل إستجابة `POST /api/v1/auth/login` (< 1s p99)
  ومعدّل 4xx على `/api/v1/orders/*`.

---

## ٩. استكشاف الأعطال الشائعة

| العطل | السبب المحتمل | الحل |
|---|---|---|
| "Login failed — 404" | `ENV_FILE` خاطئ | تأكّد من تحميل `.env.production` |
| طلبية لا تنتقل لـ approved | لم يُدخَل مراجعة الفرع | افتح التـ `timeline` وتحقّق |
| رصيد سلبي في فرع | خطأ إدخال جرد | تحقّق من `stock_transactions` ledger |
| لا تصل إشعارات email | SMTP غير مضبوط | راجع phase 7C settings (بعد تفعيلها) |
| 429 على login | hit لـ RATE_LIMIT_AUTH | طبيعي — أعد المحاولة بعد دقيقة |

---

## ١٠. روابط سريعة

- Swagger: `/api/docs`
- Health: `/api/v1/health`
- Admin seed password: ⚠️ يجب تغييره فور التثبيت.
- دليل الـ migrations: `backend/MIGRATIONS.md`.
- نمط الـ idempotency: `backend/IDEMPOTENCY_PATTERN.md`.
- إجراء الاستعادة: `backend/scripts/RESTORE_PROCEDURE.md`.

---

*آخر تحديث: 2026-04-17 — نسخة v1.0*
