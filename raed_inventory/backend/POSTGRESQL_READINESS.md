# PostgreSQL Readiness

## الهدف

هذه الوثيقة تشرح الحد الأدنى المطلوب لتشغيل `Raed Inventory System` على PostgreSQL بدل SQLite.

النقطة الأساسية:

- SQLite مقبول محليًا للديفلوبمنت أو الديمو المحدود
- PostgreSQL مطلوب لأي `staging` أو `production`

## ما تم تطبيقه في الكود

1. `ENVIRONMENT=staging` أو `ENVIRONMENT=production` لم يعد يسمح بـ SQLite.
2. إذا كانت `DATABASE_URL` تبدأ بـ `sqlite` في staging/production، فالإقلاع يفشل مباشرة.
3. `lock_row()` يسجل warning واضح عند استخدام SQLite.

## متغيرات البيئة المطلوبة

### Staging

استخدم:

`ENV_FILE=.env.staging`

ويجب أن تحتوي على:

```env
ENVIRONMENT=staging
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DBNAME
SECRET_KEY=replace-with-staging-secret
DEBUG=false
ADMIN_PASSWORD=replace-with-strong-password
```

### Production

استخدم:

`ENV_FILE=.env.production`

ويجب أن تحتوي على:

```env
ENVIRONMENT=production
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DBNAME
SECRET_KEY=replace-with-production-secret
DEBUG=false
ADMIN_PASSWORD=replace-with-strong-password
```

## أوامر التشغيل

### تطبيق المايجريشن

```bash
alembic upgrade head
```

### تشغيل التطبيق

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## التحقق السريع

بعد تطبيق المايجريشن وتشغيل التطبيق:

1. افحص:

```bash
alembic current
```

2. تأكد أن الـ API تعمل:

```bash
curl http://localhost:8000/health
```

3. جرّب تسجيل الدخول
4. جرّب مسار Supply Chain demo

## قاعدة تشغيل مهمة

أي بيئة اسمها:

- `staging`
- `production`

يجب ألا تعتمد على:

- `sqlite:///...`

وإذا حدث هذا، فالإقلاع يجب أن يفشل.

## ما التالي بعد هذه الخطوة

بعد الجاهزية الأساسية لـ PostgreSQL، الأولويات التالية تكون:

1. تعديل `require_roles` admin bypass
2. تعديل `RouteRoleGuard`
3. إضافة `Partial Delivery`
4. إكمال `Kitchen Material Request`
