# TASK_GATE_TG-SHIFT-CONFIG-EXPOSURE

## Task ID
TG-SHIFT-CONFIG-EXPOSURE

## Status
IMPLEMENTED

## Cursor Permission
**EXECUTE**
**DO_NOT_EXECUTE:** `git commit` · `git push` · نشر · أي اتصال بقاعدة الإنتاج · seed.

## Owner
Islam. Executor: Cursor. Reviewer: Claude. Commit/Deploy: Islam.

---

# الباج

`available_shift_numbers` يُرسَل **داخل ملخّص كل شفت قائم** فقط
(`shift_ops_service.py::_serialize_shift_summary`)، و`GET /shifts` يعيد
`{"total": N, "items": [...]}` ولا شيء غير ذلك.

الواجهة تقرؤه هكذا — `ShiftListPage.jsx:61`:

```js
const known = items.find((i) => Array.isArray(i.available_shift_numbers))
if (known) setAvailableShiftNumbers(known.available_shift_numbers)
```

وزر الفتح: `disabled={saving || availableShiftNumbers === null}`

## أثران، لا واحد

**١ · فرع بلا أي شفت لا يستطيع فتح أول شفت أبدًا.**
`items` فارغة ⇒ القيمة تبقى `null` ⇒ الزر مُعطَّل. ينطبق على **الـ23 فرعًا كلها** يوم الإطلاق.
**التجهيز لا يحلّه** — الإعدادات ستوجد في القاعدة والزر يبقى مُعطَّلًا.

**٢ · الأدمن يرى أرقام شفتات فرع آخر.**
`items.find(...)` يأخذ **أول** عنصر فيه الحقل أيًّا كان فرعه. فرع بشفت واحد قد يعرض خيارين
لأن الدالة التقطت شفت فرع مختلف.

## مصدر الخطأ

قاعدة «عدد الشفتات لا يُثبَّت ولا يُخمَّن، مصدره `available_shift_numbers`» صحيحة، لكن الحقل
عُلِّق على ملخّصات الشفتات — وهي بالضبط ما لا يوجد قبل أول شفت. خطأ تصميم في مراجعة Claude،
مسجَّل هنا.

---

# المطلوب

## ١ · الباك إند — الحقل على مستوى الرد

`app/routers/shift_ops.py` · دالة `list_shifts` (السطر ~64):

```diff
     items = svc.list_shifts(...)
-    return {"total": len(items), "items": items}
+    # يُرسَل على مستوى الرد لا داخل العناصر: الفرع الذي لم يفتح شفتًا قط ليس له عنصر
+    # يحمل الحقل، فتُقفل شاشة الفتح ولا يستطيع فتح أول شفت إطلاقًا. وأخذه من أول عنصر
+    # يعطي الأدمن أرقام شفتات فرع آخر. المصدر هنا هو الفرع المطلوب صراحةً.
+    scope_branch = branch_id or current_user.branch_id
+    available = (
+        svc.available_shift_numbers(db, scope_branch, date_to or date.today())
+        if scope_branch else []
+    )
+    return {
+        "total": len(items),
+        "items": items,
+        "available_shift_numbers": available,
+    }
```

**قيود:**
- **لا تحذف** الحقل من `_serialize_shift_summary`. تركه لا يضرّ، وحذفه يكسر أي قارئ قائم.
- **لا تلمس** `svc.list_shifts` ولا `available_shift_numbers` نفسها — الدالة موجودة وتعمل.
- `scope_branch` فارغ (أدمن بلا فرع وبلا `branch_id`) ⇒ `[]`، لا استثناء.
- تاريخ الحساب: `date_to or date.today()` — الإعدادات لها فترة سريان، فالتاريخ جزء من السؤال.

## ٢ · الواجهة — الأعلى أولًا

`ShiftListPage.jsx` داخل `.then((r) => {...})`:

```diff
       const items = r.data?.items || []
       setRows(items)
-      const known = items.find((i) => Array.isArray(i.available_shift_numbers))
-      if (known) setAvailableShiftNumbers(known.available_shift_numbers)
+      // مستوى الرد أولًا: يصل حتى مع صفر شفتات، ويخصّ الفرع المطلوب لا أول عنصر صادفناه.
+      // القراءة من العناصر تبقى احتياطًا لو خدم قديم لم يُنشر بعد.
+      const top = r.data?.available_shift_numbers
+      if (Array.isArray(top)) {
+        setAvailableShiftNumbers(top)
+      } else {
+        const known = items.find((i) => Array.isArray(i.available_shift_numbers))
+        if (known) setAvailableShiftNumbers(known.available_shift_numbers)
+      }
```

**قائمة فارغة ليست كغائبة.** `[]` تعني «الفرع بلا إعداد شفتات» — رسالة صريحة وزر مُعطَّل.
`null` تعني «لم يصل شيء من الخادم». **لا تدمج الحالتين.**

عدّل شرط الزر ورسالة الحقل تبعًا:

```diff
-              {availableShiftNumbers === null ? (
+              {availableShiftNumbers === null || availableShiftNumbers.length === 0 ? (
                 <span className="text-xs text-amber-700 ...">
-                  {t('shift_ops.shift_config_unavailable')}
+                  {availableShiftNumbers === null
+                    ? t('shift_ops.shift_config_unavailable')
+                    : t('shift_ops.no_shift_config')}
                 </span>
```

```diff
-              disabled={saving || availableShiftNumbers === null}
+              disabled={saving || !availableShiftNumbers?.length}
```

أضف مفتاح `shift_ops.no_shift_config` إلى `i18n/dict/ar.json` و`en.json`:
- عربي: `لا يوجد إعداد شفتات لهذا الفرع — راجع الإدارة`
- إنجليزي: `No shift configuration for this branch — contact admin`

**صفر نص عربي مكتوب في JSX.** كل شيء عبر `t()`. (خُولف هذا سابقًا في `ShiftOpsReportPage.jsx`
وأُصلح — لا تكرّره.)

## ٣ · اختباران في `tests/test_shift_ops_gaps.py`

- فرع **بإعداد شفتات وبلا أي شفت** ⇒ `GET /shifts` ⇒ `items == []` **و**
  `available_shift_numbers == [1]`. هذا هو الاختبار الذي كان غيابه يخفي الباج.
- فرع **بلا أي إعداد** ⇒ `available_shift_numbers == []` (لا `null`، ولا خطأ).

اختبار ثالث إن أمكن دون تعقيد: أدمن يطلب `branch_id` لفرع بشفت واحد بينما فرع آخر بشفتين
له شفت قائم ⇒ يعود `[1]` لا `[1,2]`.

---

# الملفات المسموح بها

1. `raed_inventory/backend/app/routers/shift_ops.py` — دالة `list_shifts` فقط
2. `raed_inventory/frontend/src/pages/shift_ops/ShiftListPage.jsx` — قراءة الحقل + شرط الزر + الرسالة
3. `raed_inventory/frontend/src/i18n/dict/ar.json` · `en.json` — مفتاح واحد جديد، **إضافة فقط**
4. `raed_inventory/backend/tests/test_shift_ops_gaps.py` — اختبارات جديدة، **لا تعديل قائم**
5. `.ai-workflow/CURSOR_REPORT_TG-SHIFT-CONFIG-EXPOSURE.md` — جديد

**ممنوع:** أي ملف آخر · `shift_ops_service.py` · أي اتصال بالإنتاج · commit · push · نشر.

# معايير القبول

- [ ] `python -m pytest tests/test_shift_ops_*.py -q` ⇒ **42 passed** (40 + الجديدان).
- [ ] الاختبار الأول يفشل فعلًا لو أُعيد الراوتر لحالته السابقة. **أثبِت ذلك**: أرجعه مؤقتًا،
      شغّل الاختبار، أكّد الفشل، ثم أعِد الإصلاح. اكتب رسالة الفشل في التقرير.
- [ ] `npm run build` ⇒ صفر أخطاء.
- [ ] صفر نص عربي مكتوب في JSX (تعليقات الملف مستثناة).
- [ ] `git diff --stat` ⇒ الملفات الخمسة أعلاه فقط.
- [ ] التقرير يذكر صراحةً: **لم يُلمَس الإنتاج، ولم يُدفَع شيء.**

# ملاحظة للمالك

بعد الدمج والنشر، اختبار الدخان يبدأ من هنا: فرع Onda **لم يفتح شفتًا قط** ⇒ يفتح شاشة
الشفتات ⇒ **يجب أن يرى زر الفتح فعّالًا** وقائمة بشفت واحد. لو ظل مُعطَّلًا فالإصلاح لم يصل.
