# إجراء استعادة قاعدة البيانات (Disaster Recovery)

هذا الملف يُوثّق خطوات استرجاع قاعدة بيانات نظام رائد من نسخة احتياطية
أنشأها `scripts/backup_db.sh`.

## ١. تحديد النسخة

النسخ في `${BACKUP_DIR}` (افتراضيًا `/var/backups/raed/`) بصيغة:

```
raed_YYYYMMDD_HHMMSSZ.sql.gz
```

إذا كانت النسخة على S3، نزِّلها أوّلاً:

```bash
aws s3 cp s3://${S3_BUCKET}/raed/raed_20260417_000000Z.sql.gz ./
```

## ٢. التحقق من السلامة قبل الاستعادة

```bash
gzip -t raed_20260417_000000Z.sql.gz   # لازم يرجع بدون output
ls -lh raed_20260417_000000Z.sql.gz    # لازم > 0
```

## ٣. تجهيز قاعدة بيانات نظيفة

**⚠️ لا تستعد فوق قاعدة إنتاج مباشرةً.** استخدم قاعدة بديلة أو أعد إنشاء
قاعدة الإنتاج بعد تأكيد النسخة.

```bash
# أنشئ قاعدة جديدة (أو امسح القديمة بعد تصدير نسخة طوارئ)
psql -U postgres -c 'CREATE DATABASE raed_restored;'
```

## ٤. تنفيذ الاستعادة

```bash
gunzip -c raed_20260417_000000Z.sql.gz | psql -U postgres -d raed_restored
```

## ٥. التحقق بعد الاستعادة

```sql
-- عدد الفروع والأصناف والمخزون
SELECT COUNT(*) FROM branches;
SELECT COUNT(*) FROM items;
SELECT COUNT(*) FROM branch_stock;
SELECT COUNT(*) FROM replenishment_orders;

-- آخر طلبية (يجب أن تكون قبل وقت النسخة)
SELECT id, status, created_at FROM replenishment_orders ORDER BY id DESC LIMIT 5;

-- الـ alembic revision الحالي
SELECT * FROM alembic_version;
```

## ٦. التبديل

- أوقف التطبيق (backend + frontend).
- حدِّث `DATABASE_URL` في `.env.production` ليشير للقاعدة المستعادة
  (أو أعد تسمية القاعدتين).
- شغّل الـ migrations لو كان فيه revisions أحدث من وقت النسخة:
  ```bash
  alembic upgrade head
  ```
- شغّل التطبيق وراقب `/health` لمدة ١٥ دقيقة.

## ٧. اختبار الاستعادة دوريًا

> **قاعدة ذهبية:** نسخة لم تُختبر = لا توجد. اختبر الاستعادة **شهريًا** على
> staging. أبقِ آخر 3 تقارير اختبار في `backend/scripts/restore_drill_logs/`.

## ٨. أوقات الاسترجاع المستهدفة (RTO / RPO)

- **RPO** (Recovery Point Objective): ≤ 24 ساعة (نسخة يومية).
- **RTO** (Recovery Time Objective): ≤ 2 ساعة لعودة الخدمة الأساسية.
- لتقليل الـ RPO: فعِّل WAL archiving / PITR (غير متوفر في السكربت الحالي).
