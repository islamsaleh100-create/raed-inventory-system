# Raed Inventory System
## Production Stabilization Plan

**Source:** `FULL_PRODUCTION_AUDIT_V2_READABLE_REPORT.md`

## الهدف

تحويل النظام من:

- Demo / LAN trial ready

إلى:

- Staging ready
- ثم Production ready

بدون فتح Features جديدة خارج الأولويات الحرجة.

## القرار التنفيذي

المرحلة القادمة ليست Feature phase.

المرحلة القادمة هي:

**Stabilization Phase**

وتركيزها على:

- قاعدة البيانات
- الصلاحيات
- صحة المخزون
- دقة التوصيل
- التخزين

## الأولويات القصوى

### Priority 1 — Database Hardening

**الهدف:** إخراج النظام من SQLite إلى PostgreSQL

المهام:

1. تجهيز `PostgreSQL` كقاعدة التشغيل الأساسية.
2. منع SQLite تمامًا في `staging` و`production`.
3. تشغيل `alembic upgrade head` على PostgreSQL نظيفة.
4. اختبار الإقلاع الكامل على PostgreSQL بدل البيئة الحالية.
5. تشغيل supply chain demo الكامل على PostgreSQL.

تم إنجازه جزئيًا الآن:

- منع SQLite في `staging/production`
- إضافة `POSTGRESQL_READINESS.md`
- إضافة `.env.postgres.local`
- إضافة `docker-compose.lan.yml`
- إضافة `LAN_POSTGRES_DEMO_RUNBOOK.md`

**النتيجة المطلوبة:**

- لا توجد بيئة تشغيل حقيقية تعتمد SQLite.

---

### Priority 2 — Permission Hardening

**الهدف:** تقليل التوسع الخطير لصلاحية `admin`

المهام:

1. تعديل `require_roles()` بحيث لا يكون bypass عامًا لـ `admin`.
2. الإبقاء على `super_admin` فقط كـ elevated override إن لزم.
3. مراجعة كل route حساسة وإضافة `admin` صراحة فقط عند الحاجة.
4. تعديل `RouteRoleGuard` في الواجهة بنفس المنطق.
5. إعادة اختبار:
   - `delivery`
   - `quality`
   - `supply-chain`
   - `admin`

**النتيجة المطلوبة:**

- `admin` لا يمر تلقائيًا في كل شيء.

---

### Priority 3 — Delivery Correctness

**الهدف:** جعل التوصيل يعكس الواقع لا الشحن النظري

المهام:

1. إضافة دعم `Partial Delivery`.
2. إضافة `received_qty` على مستوى السطر.
3. دعم `damaged / missing / shortage reason`.
4. تحديث `BranchStock` حسب المستلم فعليًا.
5. تحديث statuses:
   - `PARTIAL_DELIVERED`
   - `DELIVERED`
6. تحديث التقارير والواجهة لتعرض ذلك.

**النتيجة المطلوبة:**

- لا يتم اعتبار كل dispatched qty أنها delivered qty تلقائيًا.

---

### Priority 4 — Kitchen Materials Workflow

**الهدف:** إكمال مسار خامات المطبخ بدل بقائه نصف موصول

المهام:

1. إضافة:
   - approve material request
   - issue material request
   - reject material request
2. ربط material request بـ warehouse movement فعلي.
3. إضافة ledger transaction واضح لهذا المسار.
4. إعادة production order من `WAITING_FOR_MATERIALS` إلى المسار الصحيح بعد الصرف أو الرفض.

**النتيجة المطلوبة:**

- زر `Request Materials` يصبح Workflow حقيقيًا وليس dead-end.

---

### Priority 5 — File Storage Hardening

**الهدف:** منع ضياع الملفات بعد restart / deploy

المهام:

1. استبدال local-only storage بآلية persistent.
2. إضافة abstraction بسيطة للتخزين.
3. دعم volume أو S3-compatible storage.
4. منع الاعتماد على `./uploads` داخل container transient.
5. مراجعة download paths.

**النتيجة المطلوبة:**

- مرفقات الجودة والمستندات لا تضيع بعد إعادة التشغيل.

## الأولويات الثانوية بعد ذلك

### Priority 6 — Procurement Completion

المطلوب:

- Purchase Order
- Goods Receipt
- Supplier replenishment flow

### Priority 7 — Historical Snapshot Completion

المطلوب:

- snapshots في:
  - delivery lines
  - production orders
  - kitchen material requests
  - replenishment order lines
  - stock transactions

### Priority 8 — Upload Security

المطلوب:

- streaming uploads
- real file type sniffing
- request size protection

### Priority 9 — Audit Improvement

المطلوب:

- old/new values أوضح
- audit على receive / label generation / partial delivery

### Priority 10 — Observability

المطلوب:

- health checks أفضل
- readiness checks
- backup strategy
- runtime monitoring

## الترتيب العملي المقترح

### Sprint A

1. PostgreSQL migration
2. SQLite block in staging
3. require_roles hardening
4. RouteRoleGuard hardening

### Sprint B

1. Partial delivery
2. Delivery stock correctness
3. Kitchen material workflow

### Sprint C

1. Storage abstraction
2. Upload safety
3. Procurement completion

## تعريف النجاح

نعتبر النظام جاهزًا للمرحلة التالية عندما يتحقق الآتي:

1. النظام يعمل على PostgreSQL فقط في staging.
2. Supply chain demo الكامل ينجح على PostgreSQL.
3. `admin` لا يمر تلقائيًا في كل المسارات.
4. partial delivery مدعوم ويؤثر على المخزون بشكل صحيح.
5. kitchen materials workflow مكتمل.
6. الملفات لا تضيع بعد restart أو redeploy.

## ما لا نفعله الآن

في هذه المرحلة لا نبدأ:

- redesign
- analytics جديدة
- modules جديدة غير procurement المطلوب
- polishing كبير للواجهة

التركيز فقط على:

**production stabilization**
