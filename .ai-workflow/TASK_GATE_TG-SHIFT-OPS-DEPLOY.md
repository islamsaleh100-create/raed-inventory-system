# TASK_GATE_TG-SHIFT-OPS-DEPLOY

## Task ID
TG-SHIFT-OPS-DEPLOY

## Status
APPROVED — للمرحلتين ٠ و ١ فقط.

## Cursor Permission
**EXECUTE** للمرحلتين ٠ و ١.
**DO_NOT_EXECUTE** للمراحل ٢ · ٣ · ٤ · ٥ — ينفّذها المالك بيده على الإنتاج.

## Owner
Islam. Executor: Cursor (٠ · ١). Deploy/Migration/Seed: **Islam حصرًا**.

## قرار المالك 2026-08-16
> نشر للـ23 فرع مرة واحدة. أصناف Ronaldos والشاورما تُؤجَّل — ليست أولوية الآن.

---

# حقائق متحقَّق منها (لا تُعاد)

| # | الحقيقة | كيف تُحقّق |
|---|---|---|
| 1 | `feature/shift-ops` أمام `origin/main` بـ**28 كوميت وصفر خلفه** | `git rev-list --left-right --count origin/main...HEAD` ⇒ `0 28` |
| 2 | الدمج **fast-forward** — لا تعارضات ولا cherry-pick | نتيجة (1) |
| 3 | جداول shift-ops على الإنتاج: **0/2** | تقرير TG-PROD-READINESS-REPORT |
| 4 | `/openapi.json` الإنتاج: 134 مسارًا، **صفر** فيه `shift` | قراءة مباشرة |
| 5 | الـ23 فرعًا **كلها موجودة** في الإنتاج | تقرير الجاهزية |
| 6 | ONDA: 22 صنفًا محلولًا · RONALDOS 0/3 · SHAWARMA 0/2 | `brand_count_items.resolved.csv` |
| 7 | **فرع بلا أصناف لا ينكسر** | `_frozen_item_ids` ⇒ `[]` · `submit_count` يرى `invalid=[]` فيرحّل · `submit_cash` لا يقرأ الجرد إطلاقًا |

**البند 7 هو ما يجعل قرار "ننشر للكل" آمنًا تقنيًا.** لا تُعِد اختباره، لكن لا تبنِ عليه أكثر مما يقول:
الفرع بلا أصناف **يعمل**، لكنه **لا يعدّ شيئًا**.

---

# المرحلة ٠ · فحوصات ما قبل النشر (Cursor · EXECUTE)

## ٠.١ فحص `branch_brands` على الإنتاج — قراءة فقط

**سؤال محوري لم يُطرح في التقرير السابق:** قائمة العدّ تمرّ بخطوتين —
`branch_brands` (فرع ← براند) ثم `brand_shift_count_items` (براند ← أصناف).
نعرف أن الثانية فارغة لـRonaldos/Shawarma. **الأولى مجهولة.**

إن كانت `branch_brands` فارغة لهذه الفروع أيضًا، فإضافة الأصناف لاحقًا **لن تُظهر شيئًا** —
وسنكتشف ذلك بعد أن نظن أننا حللنا المشكلة.

استخدم نفس أسلوب الجيت السابق (`PROD_DATABASE_URL` في الجلسة فقط، قراءة فقط):

```sql
SELECT b.branch_code, b.branch_name, count(bb.brand_id) AS brands
FROM branches b LEFT JOIN branch_brands bb ON bb.branch_id = b.id
GROUP BY b.branch_code, b.branch_name ORDER BY brands, b.branch_code;
```

اكتب النتيجة كاملةً في التقرير. **أي فرع بـ`brands = 0` يُذكر صراحةً.**

## ٠.٢ الحزمة الكاملة محليًا

```powershell
cd C:\raed_inventory_system\raed_inventory\backend
python -m pytest tests/ -q --deselect tests/test_epic10_13_unittest.py
```

**خط الأساس للمقارنة هو فرع `safety/wip-before-shift-ops-backend-v2-2`، لا `TESTS_FAILURE_TRIAGE.md`**
(تاريخه ١٧ أبريل — منتهي الصلاحية).

المطلوب إثباته: **لا فشل جديد سببه shift-ops.** إن اختلف العدد عن خط الأساس، اذكر أسماء
الاختبارات المختلفة، لا الأرقام وحدها.

## ٠.٣ بناء الواجهة

```powershell
cd C:\raed_inventory_system\raed_inventory\frontend
npm run build
```

⇒ صفر أخطاء. اذكر حجم الحزمة الناتجة.

## ٠.٤ المايجريشن ذهابًا وإيابًا — على قاعدة محلية

بند القبول هذا **وُضع علامة على إنجازه سابقًا دون تشغيله فعلًا**، وهو ما أخفى تصادم
الـrevision. لا تكرّر ذلك.

```powershell
cd C:\raed_inventory_system\raed_inventory\backend
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

الثلاثة تنجح ⇒ ✔. أي فشل ⇒ **قف، ولا تكمل الجيت.**

> ملاحظة: الإنتاج بوستجرس، فقيد `EXCLUDE USING gist` سيُنشأ هناك فعلًا (مع `btree_gist`).
> محليًا قد يتخطّاه بأمان. **اذكر أيّ المسارين حدث عندك.**

---

# المرحلة ١ · تجهيزات الكود (Cursor · EXECUTE)

## ١.١ مسار الإنتاج في سكربت التجهيز

`seed_shift_ops_config.py` يرفض حاليًا أي رابط Railway. **هذا حارس مقصود — لا تحذفه ولا
تُضعِفه.** أضف بجانبه مسارًا صريحًا:

```
--production  --expect-branches 23
```

الشروط، كلها إلزامية:

1. **بدون `--production`، السلوك الحالي كما هو تمامًا** — رفض Railway، لا استثناء.
2. `--production` **لا يعمل بدون `--expect-branches N`**. يعدّ الفروع المطابَقة فعلًا، وإن
   خالفت `N` ⇒ **يتوقف قبل أي كتابة**. (الحماية من قاعدة خاطئة: العدد الصحيح على القاعدة
   الغلط مصادفة بعيدة.)
3. **تأكيد تفاعلي مكتوب.** يطبع اسم القاعدة مقنَّعًا وعدد الفروع والأصناف، ثم يطلب كتابة
   `APPLY TO PRODUCTION` حرفيًا. أي شيء آخر ⇒ خروج بلا كتابة.
4. `--production` بدون `--apply` ⇒ **عرض فقط**. الافتراضي يبقى عدم الكتابة.
5. الرابط من `PROD_DATABASE_URL` فقط. **لا يُقرأ من `.env` ولا يُكتب في أي ملف.**
6. معاملة واحدة (transaction): إما كل شيء أو لا شيء. أي استثناء ⇒ `rollback`.

**لا تشغّله على الإنتاج في هذا الجيت.** اكتبه واختبره على القاعدة المحلية فقط.

## ١.٢ عدّاد أسطر الجرد في التقرير

`build_shift_report` لا يميّز بين "عدّ 23 صنفًا" و"عدّ صفر صنف": كلاهما
`count_status = submitted`. بعد النشر ستُرحّل 13 فرعًا جردًا فارغًا يوميًا، ويقرؤه المراجع
كأنه جرد حقيقي. **بيانات نظيفة الشكل، معناها صفر** — وهذا أخطر من خطأ ظاهر.

في `app/services/shift_ops_service.py` داخل `build_shift_report`، أضف إلى `row`:

```python
# يميّز الجرد الفارغ عن الجرد الحقيقي. 13 فرعًا (Ronaldos · Shawarma) بلا أصناف عدّ
# في الإنتاج عند إطلاق 2026-08، فترحّل جردًا بصفر أسطر يبدو في التقرير مطابقًا لجرد
# مكتمل. بدون هذا الحقل يقرأ المراجع "23 فرعًا رحّلوا الجرد" وهي ليست الحقيقة.
"count_lines_total": len(shift.count.lines) if shift.count else 0,
"count_lines_filled": sum(
    1 for l in shift.count.lines if l.row_status == ShiftCountRowStatus.valid.value
) if shift.count else 0,
```

**التغيير إضافة حقلين فقط.** لا تلمس أي حقل قائم ولا منطق أي فلتر — تعديل شكل الاستجابة
القائم يكسر الواجهة.

اعرضهما في `ShiftOpsReportPage.jsx` كعمود واحد: `filled/total`. صفر ⇒ **يُميَّز بصريًا**
(رمادي أو شارة "بلا أصناف")، لا يُترك كأنه رقم عادي.

## ١.٣ اختبار واحد للسلوك المعتمَد عليه

البند 7 أعلاه أصبح **افتراض إطلاق**، ولا يحرسه اختبار. أضف في
`tests/test_shift_ops_gaps.py`:

- فرع بلا `brand_shift_count_items` ⇒ إنشاء الجرد ينجح بصفر أسطر ⇒ `submit_count` **ينجح** ⇒
  `submit_cash` ينجح ⇒ حالة الشفت `submitted`.
- التقرير لنفس الشفت ⇒ `count_lines_total == 0`.

بدون هذا الاختبار، أي تعديل مستقبلي على `submit_count` قد يكسر 13 فرعًا صامتًا.

---

# المرحلة ٢ · الدمج والنشر (Islam — لا ينفّذها Cursor)

```powershell
git checkout main
git merge --ff-only feature/shift-ops
git push origin main
```

`--ff-only` مقصود: إن فشل، فمعناه أن `main` تحرّك منذ الفحص ⇒ **قف واسأل**، لا تدمج بـmerge commit.

> **تأكيد مطلوب قبل الدفع:** Railway ينشر من أي فرع؟ إن لم يكن `main`، فادفع للفرع الذي يراقبه.
> راقب سجل النشر حتى ينتهي، ثم:
> `curl https://raed-inventory-system-production.up.railway.app/openapi.json` ⇒ يجب أن تظهر مسارات `shift`.
> **لا تكمل قبل ظهورها.**

# المرحلة ٣ · المايجريشن على الإنتاج (Islam)

تُشغَّل من Railway (أو محليًا مقابل `DATABASE_PUBLIC_URL`):

```
alembic upgrade head
```

المتوقع: `c1d2e3f4a5b6 -> a9b8c7d6e5f4`. ثم تأكيد **2/2** لجدولَي
`branch_shift_configs` و `brand_shift_count_items`.

**احتياطية القاعدة قبل هذه الخطوة.** المايجريشن يضيف 8 جداول ولا يعدّل قائمًا، فالخطر منخفض —
لكن "منخفض" ليس "صفر"، وهذه أول كتابة على الإنتاج في المسار كله.

# المرحلة ٤ · التجهيز (Islam)

```powershell
$env:PROD_DATABASE_URL = "<DATABASE_PUBLIC_URL>"
cd C:\raed_inventory_system\raed_inventory\backend\seed_shift_ops
# 1) عرض فقط — اقرأ المخرجات كاملة
python seed_shift_ops_config.py --production --expect-branches 23
# 2) التنفيذ — سيطلب كتابة APPLY TO PRODUCTION
python seed_shift_ops_config.py --production --expect-branches 23 --apply
```

**قبل الخطوة (2):** بدّل `brand_count_items.resolved.csv` ← `brand_count_items.csv`.

**وقبل ذلك، راجع سطرين بعينك** — تصحيحان دلاليان لا إملائيان، وخطؤهما يعني أن الفروع تعدّ
منتجًا غير المقصود كل يوم:

| السطر | ما اختاره Cursor | لماذا يحتاج عينك |
|---|---|---|
| `Cookies` | `SUPF-ONDA-82FF7926B8` CHOCOLATE CHIP COOKIE | Cursor ذكر مرشّحًا بديلًا `ONDA-PRD-011`. رأى اثنين واختار واحدًا. |
| `Cheese strawberry` | `SUPF-ONDA-53ED2DA6AA` Cheesecake berry | «berry» ليست «strawberry» بالضرورة. |

الثلاثة الأخرى (`BROWNIE Zatar` · `Cheesecake pekan` · `ZAATER CROISSANT`) اختلافات إملائية
واضحة — تمرّ بلا مراجعة.

`TRH 996g` بلا كود ⇒ سيُبلَّغ عنه ولن يُنشأ. **هذا مقصود.** Onda تعمل بـ22 صنفًا.

# المرحلة ٥ · اختبار دخان (Islam · فرع Onda واحد)

بحساب مدير فرع حقيقي، على الموبايل:

1. افتح شفت اليوم ⇒ تظهر **22 صنفًا**.
2. أدخل أرقامًا حقيقية ⇒ رحّل الجرد.
3. افتح شاشة الكاش ⇒ أدخل أرقام اليوم ⇒ رحّل.
4. الشفت ⇒ `submitted`.
5. بحساب admin: التقرير يعرض الشفت و`count_lines` = `22/22`.
6. **افتح فرع Ronaldos** ⇒ شاشة جرد فارغة ⇒ الترحيل ينجح ⇒ الكاش يعمل ⇒
   التقرير يعرض `0/0` **مميَّزًا بصريًا**.

الخطوة 6 ليست اختيارية — هي التحقق الحيّ من البند 7.

---

# التراجع

| مرحلة | التراجع |
|---|---|
| ٢ نشر | `git revert` + إعادة نشر. الواجهة القديمة سليمة. |
| ٣ مايجريشن | `alembic downgrade -1`. الجداول جديدة وفارغة ⇒ بلا فقد بيانات. |
| ٤ تجهيز | حذف صفوف `branch_shift_configs` و`brand_shift_count_items` فقط. **لا تلمس `items` ولا `branches`.** |

**الموديول القديم لم يتغيّر في هذا النشر**، فأي تراجع لا يمسّ التشغيل القائم.

---

# الملفات المسموح بها (المرحلتان ٠ · ١)

1. `raed_inventory/backend/seed_shift_ops/seed_shift_ops_config.py` — إضافة `--production` فقط
2. `raed_inventory/backend/app/services/shift_ops_service.py` — الحقلان في `build_shift_report` فقط
3. `raed_inventory/frontend/src/pages/shift_ops/ShiftOpsReportPage.jsx` — عمود `filled/total`
4. `raed_inventory/backend/tests/test_shift_ops_gaps.py` — اختبار ١.٣
5. `.ai-workflow/CURSOR_REPORT_TG-SHIFT-OPS-DEPLOY.md` — جديد

**ممنوع:** `git commit` · `git push` · `git merge` · أي كتابة على الإنتاج · تعديل المايجريشن
القائم · تعديل أي ملف خارج القائمة.

# معايير القبول

- [ ] ٠.١ نتيجة `branch_brands` كاملة، وكل فرع بـ`brands = 0` مذكور بالاسم.
- [ ] ٠.٢ الحزمة شُغِّلت فعلًا، ولا فشل جديد سببه shift-ops (بالأسماء لا بالأرقام).
- [ ] ٠.٣ `npm run build` ⇒ صفر أخطاء.
- [ ] ٠.٤ `upgrade → downgrade → upgrade` **شُغِّلت فعلًا** ونجحت الثلاثة.
- [ ] ١.١ بدون `--production` السلوك القديم حرفيًا · التأكيد المكتوب يعمل · `--expect-branches`
      المخالف يوقف قبل أي كتابة · لم يُشغَّل على الإنتاج.
- [ ] ١.٢ حقلان مضافان فقط، وصفر تعديل على حقل قائم.
- [ ] ١.٣ الاختبار الجديد يمرّ · `python -m pytest tests/test_shift_ops_*.py -q` ⇒ **40 passed**.
- [ ] `grep -ri "rlwy.net\|proxy.rlwy" .` في المستودع ⇒ **صفر**.
- [ ] التقرير يذكر صراحةً: **صفر كتابة على الإنتاج في هذا الجيت**.

# بند مسجَّل (لا عمل الآن)

> **13 فرعًا (Ronaldos ×10 · Shawarma ×3) ستعمل بلا جرد فعلي حتى تُنشأ أصنافها في الإنتاج.**
> قرار المالك 2026-08-16: مؤجَّل عمدًا. وعند إنشائها لاحقًا، تُضبط
> `branch_requestable=False` و`visible_in_branch_ui=False` صراحةً — الافتراضي `True`
> يجعلها تظهر فورًا في موديول طلبات الفروع القديم، وهو تسرّب خارج نطاق shift-ops.
