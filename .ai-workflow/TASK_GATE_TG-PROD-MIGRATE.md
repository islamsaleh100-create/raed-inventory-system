# TASK_GATE_TG-PROD-MIGRATE

## Task ID
TG-PROD-MIGRATE

## Status
IMPLEMENTED — Phase 2 blocked (see CURSOR_REPORT_TG-PROD-MIGRATE.md)

## Cursor Permission
**EXECUTE** — المراحل ٠ · ١ · ٢ بالشروط المكتوبة فيها.
**DO_NOT_EXECUTE:** تجهيز البيانات (seed) · `git commit` · `git push` · أي `INSERT`/`UPDATE`/`DELETE`
على بيانات الإنتاج · أي `alembic downgrade`.

## Owner
Islam. Executor: Cursor. Reviewer: Claude.

> هذا أول تعديل يُكتب على قاعدة الإنتاج في هذا المسار كله. الجيت مبني على أن الكتابة الوحيدة
> المسموحة هي **إنشاء جداول جديدة**، ولا شيء غير ذلك.

---

# الحالة الآن (متحقَّق منها)

| # | الحقيقة | الدليل |
|---|---|---|
| 1 | `main` = `0d619e6`، مدفوع | `git push` نجح |
| 2 | الباك إند منشور وshift-ops حيّ | `GET /api/v1/shift-ops/shifts` ⇒ **401** (لا 404) |
| 3 | الخدمة سليمة | `/health` ⇒ `healthy` بـtimestamp جديد |
| 4 | `/openapi.json` ⇒ **404** بعد الدمج | تغيّر مقصود في `app/main.py` — التوثيق مُقفَل في الإنتاج. **ليس عطلًا.** |
| 5 | رأس المايجريشنات محليًا `a9b8c7d6e5f4`، بلا تفرّع | `alembic heads` |
| 6 | جداول shift-ops على الإنتاج: **0/2** | تقرير TG-PROD-READINESS-REPORT |
| 7 | عنصر قائمة `/shift-ops` ظاهر لـ`branch_manager` وغيره | `AppLayoutV2.jsx:29` |

**البند 7 + البند 6 = الواجهة سبقت القاعدة.** أي مستخدم يضغط العنصر الآن يصل إلى جداول غير
موجودة. هذا سبب استعجال هذا الجيت.

---

# المرحلة ٠ · تحقّق من الكوميت (لا يحتاج اتصالًا)

```powershell
cd C:\raed_inventory_system
git show --stat HEAD
git status
```

**الشرط:** `raed_inventory/frontend/src/utils/trialLegacy.js` **مذكور بالاسم** في مخرجات
`git show --stat HEAD`.

- **موجود** ⇒ إصلاح الحظر وصل الإنتاج فعلًا. كمّل.
- **غير موجود** ⇒ **قف فورًا واكتب ذلك في التقرير.** 67 حسابًا نشطًا ما زالت محجوبة عن
  `/orders` و`/warehouse/*` و`/delivery/*`، ونحن نظن أننا أصلحنا ولم نُصلح. هذا يسبق المايجريشن.

انسخ مخرجات الأمرين حرفيًا في التقرير.

---

# المرحلة ١ · استطلاع القاعدة + نسخة احتياطية

## ١.١ الرابط

```powershell
railway status
railway link                 # إن لزم
railway variables            # خذ DATABASE_PUBLIC_URL — لا DATABASE_URL
$env:DATABASE_URL = "<القيمة الحقيقية>"
```

> **تنبيه:** القيمة تُلصق كاملةً بلا أقواس مدبَّبة. `"<DATABASE_PUBLIC_URL>"` نصًّا حرفيًا
> فشل مرتين بالفعل — إن رأيت `Could not parse SQLAlchemy URL` فهذا هو السبب.

**متغيّر جلسة فقط. لا يُكتب في `.env` ولا في أي ملف.**

## ١.٢ نسخة احتياطية — إلزامية قبل أي كتابة

```powershell
pg_dump "$env:DATABASE_URL" -Fc -f C:\raed_inventory_system\_backup_pre_shiftops.dump
```

**الشرط:** الملف موجود وحجمه > 0. اذكر الحجم في التقرير.
إن لم يكن `pg_dump` مثبتًا ⇒ **قف واكتب ذلك.** لا تكمل بلا نسخة احتياطية.

> الملف في جذر المستودع ويجب ألا يُسجَّل في git. تأكّد أن `.gitignore` يغطّي `*.dump`،
> وإلا فأضفه — هذا الاستثناء الوحيد المسموح خارج قائمة الملفات أدناه.

## ١.٣ ما الذي سيُشغَّل بالضبط

```powershell
cd C:\raed_inventory_system\raed_inventory\backend
alembic current
alembic history --verbose
```

اكتب في التقرير:
1. **مراجعة الإنتاج الحالية** (`alembic current`).
2. **القائمة الكاملة للمراجعات المعلَّقة** بين الحالية و`a9b8c7d6e5f4`، بالأسماء والترتيب.

## ١.٤ افحص محتوى كل مراجعة معلَّقة — هذا شرط التنفيذ

افتح ملف كل مراجعة معلَّقة في `alembic/versions/` واقرأ دالة `upgrade()`.

**التنفيذ مسموح فقط إذا كانت كل المراجعات المعلَّقة تفعل هذا حصرًا:**
`create_table` · `create_index` · `create_unique_constraint` · `create_foreign_key` ·
`CREATE EXTENSION` · `EXCLUDE` constraint على جدول أنشأته المراجعة نفسها.

**قف فورًا واكتب في التقرير إن وجدت أيًّا من:**
`drop_table` · `drop_column` · `alter_column` · `op.execute` بـ`UPDATE`/`DELETE`/`INSERT` ·
أي تعديل على جدول موجود مسبقًا.

هذه ليست شكليات: مراجعة واحدة تعدّل جدولًا قائمًا تحوّل هذه العملية من "إضافة جداول" إلى
"تعديل بيانات حيّة"، وهي عملية خارج صلاحية هذا الجيت.

اذكر لكل مراجعة سطرًا واحدًا: `<revision> — N جدولًا جديدًا — إضافي بحت ✔` أو سبب التوقف.

---

# المرحلة ٢ · التنفيذ (فقط إذا مرّت شروط ١.٢ و ١.٤)

```powershell
alembic upgrade head
```

ثم التحقق — **بنفس الاتصال، قراءة فقط:**

```sql
SELECT count(*) FROM information_schema.tables
WHERE table_name IN ('branch_shift_configs','brand_shift_count_items');
-- المتوقع: 2

SELECT count(*) FROM information_schema.tables
WHERE table_name LIKE 'branch_shift%' OR table_name LIKE 'brand_shift%';
-- المتوقع: 8
```

و`alembic current` ⇒ يجب أن يعود `a9b8c7d6e5f4`.

**ثم امسح المتغيّر فورًا:**

```powershell
Remove-Item Env:\DATABASE_URL
```

نسيانه يجعل أي أمر محلي لاحق يضرب على الإنتاج. امسحه، ثم أكّد في التقرير أنه مُسح.

---

# ما لا يُنفَّذ في هذا الجيت

**تجهيز البيانات (`seed_shift_ops_config.py --production`) خارج النطاق تمامًا.**
بعد المايجريشن ستكون الجداول موجودة وفارغة — وهذا هو الوضع المطلوب عند نهاية هذا الجيت.
التجهيز يحتاج مراجعة المالك لسطرَي `Cookies` و`Cheese strawberry` أولًا، وهي مراجعة بشرية
لم تتم بعد.

---

# التراجع

فشل المايجريشن في المنتصف ⇒ **لا تشغّل `downgrade`.** اكتب الخطأ كاملًا في التقرير وقف.
المراجعات إضافية بحتة، فالقاعدة تبقى صالحة والتطبيق القديم يعمل — والنسخة الاحتياطية موجودة.
قرار التراجع للمالك، لا للمنفّذ.

# الملفات المسموح بها

1. `.ai-workflow/CURSOR_REPORT_TG-PROD-MIGRATE.md` — جديد
2. `.gitignore` — إضافة `*.dump` فقط، وفقط إن لم تكن مغطّاة

**لا شيء غيرهما. لا كود. لا CSV. لا سكربتات.**

# معايير القبول

- [ ] ٠ مخرجات `git show --stat HEAD` منسوخة، و`trialLegacy.js` مؤكَّد بالاسم.
- [ ] ١.٢ ملف النسخة الاحتياطية موجود وحجمه مذكور.
- [ ] ١.٣ مراجعة الإنتاج الحالية + قائمة المعلَّقات بالأسماء.
- [ ] ١.٤ حكم سطر واحد لكل مراجعة معلَّقة (إضافي بحت / سبب التوقف).
- [ ] ٢ `alembic current` ⇒ `a9b8c7d6e5f4` · جدولا الإعداد **2** · جداول shift-ops **8**.
- [ ] `Remove-Item Env:\DATABASE_URL` نُفِّذ ومذكور.
- [ ] `grep -ri "rlwy.net\|proxy.rlwy" .` في المستودع ⇒ **صفر**.
- [ ] التقرير يذكر صراحةً: **صفر تعديل على بيانات قائمة — إنشاء جداول فقط.**
