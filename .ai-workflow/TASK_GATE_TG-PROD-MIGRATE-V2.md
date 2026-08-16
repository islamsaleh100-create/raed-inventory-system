# TASK_GATE_TG-PROD-MIGRATE-V2

## Task ID
TG-PROD-MIGRATE-V2 (يكمل TG-PROD-MIGRATE الذي توقّف عند 1.2)

## Status
IMPLEMENTED

## Cursor Permission
**EXECUTE** — بالترتيب وبالشروط. كل مرحلة مشروطة بنتيجة ما قبلها.
**DO_NOT_EXECUTE:** تجهيز البيانات (seed) · `git commit` · `git push` ·
أي `INSERT`/`UPDATE`/`DELETE` على بيانات · `alembic downgrade` · `DROP` أو `ALTER COLUMN` أيًّا كان.

## Owner
Islam. Executor: Cursor. Reviewer: Claude.

---

# ما استقرّ من الجيت السابق (لا يُعاد فحصه)

| # | الحقيقة |
|---|---|
| 1 | `trialLegacy.js` مؤكَّد داخل `0d619e6` — إصلاح الحظر على الإنتاج |
| 2 | مراجعة الإنتاج: **`89aedce3fd41`** |
| 3 | المعلَّق: `c1d2e3f4a5b6` ثم `a9b8c7d6e5f4` — **كلاهما إضافي بحت** (مفحوص) |
| 4 | `branch_item_availability` و `item_change_requests` **موجودان** على الإنتاج، أنشأهما `create_all` وقت التشغيل قبل نقلهما إلى Alembic |
| 5 | جداول shift-ops: **0** |
| 6 | `pg_dump` المحلي 16.13 مقابل خادم 18.4 ⇒ **لا تُحاول النسخ محليًا.** النسخة تُؤخذ من واجهة Railway، وهي مسؤولية المالك |

**لماذا لا نختم مباشرةً:** `create_all` يبني من الموديل، والمراجعة `c1d2e3f4a5b6` تضيف
**عشرة فهارس مسمّاة** وقيد تفرّد. إن لم يعلنها الموديل فهي غير موجودة على الإنتاج، و
`alembic stamp` يجعل Alembic يعتقد أنها موجودة — فيبقى الفرق مخفيًا بلا أي إشارة لاحقة.

---

# المرحلة ١ · المقارنة (قراءة فقط)

```powershell
railway variables                # DATABASE_PUBLIC_URL — لا DATABASE_URL
$env:PROD_DATABASE_URL = "<القيمة الكاملة، بلا أقواس مدبَّبة>"
cd C:\raed_inventory_system\raed_inventory\backend\seed_shift_ops
python compare_c1d2e3f4a5b6_schema.py
```

انسخ المخرجات كاملةً في التقرير. الحكم في آخر سطر:

| النتيجة | إلى أين |
|---|---|
| `✓ مطابق` | المرحلة ٣ مباشرةً |
| `⚠️ ينقص N فهرسًا/قيدًا` | المرحلة ٢ |
| `❌ فرق في الأعمدة` أو جدول مفقود | **قف. اكتب التقرير وانتهِ.** هذه تحتاج قرار مالك، لا أمرًا. |

---

# المرحلة ٢ · سدّ الفهارس الناقصة (فقط عند `⚠️`)

**أولًا احسب الحجم:**

```sql
SELECT 'branch_item_availability' AS t, count(*) FROM branch_item_availability
UNION ALL
SELECT 'item_change_requests', count(*) FROM item_change_requests;
```

- **أي جدول > 10000 صف** ⇒ **قف واكتب العدد.** `CREATE INDEX` العادي يقفل الكتابة أثناء
  البناء، وعلى جدول كبير على نظام حيّ هذا انقطاع. البديل `CREATE INDEX CONCURRENTLY` قرار مالك.
- **أقل من ذلك** ⇒ نفّذ جمل `CREATE INDEX` / `ADD CONSTRAINT` التي طبعها السكربت **حرفيًا كما
  طبعها**، بلا تعديل ولا إضافة.

ثم **أعد تشغيل** `compare_c1d2e3f4a5b6_schema.py` ⇒ يجب أن يصبح `✓ مطابق`.
إن لم يصبح، قف واكتب الفرق الباقي.

---

# المرحلة ٣ · الختم والترقية

**شرط بشري قبل أي شيء في هذه المرحلة:** اسأل المالك في المحادثة:
> «هل أخذت نسخة احتياطية من Railway (Postgres → Backups)؟»

**لا تبدأ قبل نعم صريحة منه**، واكتب في التقرير أنه أكّد. لا تفترض، ولا تكتفِ بأنها "مذكورة
في جيت سابق".

```powershell
cd C:\raed_inventory_system\raed_inventory\backend
$env:DATABASE_URL = "<نفس الرابط الكامل>"
alembic stamp c1d2e3f4a5b6
alembic upgrade head
alembic current
```

`alembic current` ⇒ يجب أن يعود **`a9b8c7d6e5f4`**.

**فشل في المنتصف ⇒ لا تشغّل `downgrade`.** انسخ الخطأ كاملًا وقف. المراجعات إضافية،
فالقاعدة تبقى صالحة والتطبيق يعمل. قرار التراجع للمالك.

## التحقق

```sql
SELECT count(*) FROM information_schema.tables
WHERE table_name IN ('branch_shift_configs','brand_shift_count_items');   -- المتوقع: 2

SELECT count(*) FROM information_schema.tables
WHERE table_name LIKE 'branch_shift%' OR table_name LIKE 'brand_shift%';  -- المتوقع: 8
```

وتحقّق أن قيد منع التداخل أُنشئ فعلًا (المراجعة تتسامح مع فشله):

```sql
SELECT conname FROM pg_constraint WHERE conrelid = 'branch_shift_configs'::regclass;
```

**إن لم يوجد قيد `EXCLUDE`، فهذا ليس فشلًا للجيت** — الخدمة تتحقّق من التداخل في طبقة
الكود أيضًا (`validate_config_no_overlap`). لكن **اذكره صراحةً**: يعني أن الحارس طبقة واحدة
لا طبقتان.

## الإغلاق

```powershell
Remove-Item Env:\DATABASE_URL
Remove-Item Env:\PROD_DATABASE_URL
```

نفّذها وأكّدها في التقرير. نسيانها يجعل أي أمر محلي لاحق يضرب على الإنتاج.

---

# الملفات المسموح بها

`.ai-workflow/CURSOR_REPORT_TG-PROD-MIGRATE-V2.md` — جديد. **لا شيء غيره. لا كود.**

# معايير القبول

- [ ] مخرجات المقارنة كاملة + الحكم النهائي منقولًا حرفيًا.
- [ ] (٢) عدد صفوف الجدولين مذكور · الجمل المنفَّذة منقولة كما طُبعت · إعادة المقارنة ⇒ `✓`.
- [ ] (٣) تأكيد المالك على النسخة الاحتياطية **مكتوب في التقرير**.
- [ ] (٣) `alembic current` ⇒ `a9b8c7d6e5f4` · جدولان **2** · جداول shift-ops **8**.
- [ ] حالة قيد `EXCLUDE` مذكورة (موجود / غير موجود).
- [ ] متغيّرا البيئة مُسحا.
- [ ] `grep -ri "rlwy.net\|proxy.rlwy" .` ⇒ **صفر**.
- [ ] التقرير يذكر صراحةً: **صفر تعديل على بيانات قائمة — إنشاء جداول وفهارس فقط.**

# بعد هذا الجيت

الجداول موجودة وفارغة. التجهيز (seed) **لم يبدأ** وهو خارج النطاق — ينتظر مراجعة المالك
لسطرَي `Cookies` و`Cheese strawberry` في `brand_count_items.resolved.csv`.
