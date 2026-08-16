# CLAUDE_EXECUTION_REPORT — TG-SHIFT-OPS (Backend V2.2 + Frontend)

**التاريخ:** 2026-08-15 · **المنفّذ:** Claude (باستثناء دور ممنوح من المالك، موثّق في `CLAUDE.md`)

> ⚠️ **اقرأ هذا أولًا:** أنا كتبت هذا الكود، فمراجعتي له **ليست مراجعة مستقلة**. البنود التي
> "مرّت" أدناه هي فحوص آلية قابلة لإعادة التشغيل، لا حكم مراجع. قبل الـcommit، لازم عين تانية.

---

## ١ · الباك إند

### ما نُفِّذ

| البند | الملف | الحجم |
|---|---|---|
| `available_shift_numbers` | `app/services/shift_ops_service.py` | دالة جديدة + بارامتر `db` اختياري |
| تمرير `db` للسيريالايزر | `app/routers/shift_ops.py` | استبدال ٤ نداءات |
| ٢١ اختبار جديد | `tests/test_shift_ops_gaps.py` | ملف جديد |

**لا migration. لا جدول جديد. لا تعديل على أي موديل.**

```python
def available_shift_numbers(db, branch_id, on_date) -> list[int]:
    # is_active AND effective_from <= on_date AND (effective_to IS NULL OR >= on_date)
```

### نتائج التشغيل الفعلي

بيئة سحابية: Python 3.11 · متطلبات المشروع مثبّتة · SQLite في الذاكرة عبر `tests/conftest.py`.
(`langdetect` لا يُبنى هناك فاستُبدل بـstub — غير مستخدم في shift-ops إطلاقًا.)

```
tests/test_shift_ops_api.py
tests/test_shift_ops_isolation.py
tests/test_shift_ops_sequencing.py
tests/test_shift_ops_validation.py
tests/test_shift_ops_gaps.py
→ 39 passed in 35.47s
```

### تغطية البنود الثمانية

| # | البند | الاختبار |
|---|---|---|
| العزل | لا حركة ليدجر | `test_submit_creates_no_ledger_movement` |
| العزل | لا طلب فرع | `test_submit_creates_no_branch_request` |
| 1 | Idempotency وهو `draft` | `test_post_count_idempotent_while_draft` |
| 1 | Idempotency وهو `submitted` | `test_post_count_idempotent_after_submit` |
| 2 | التجميد بعد إعادة الفتح | `test_frozen_list_survives_reopen` |
| 3 | تداخل الفترات ×٤ أشكال | `test_config_overlap_rejected_in_all_shapes` (parametrized) |
| 3 | نطاق غير متداخل يُقبل | `test_config_non_overlapping_range_is_accepted` |
| 5 | السقف + تجاوز admin | `test_third_reopen_is_rejected_and_admin_can_override` |
| 6 | `target=cash` لا يلمس الجرد | `test_reopen_target_cash_does_not_touch_count` |
| 7 | `is_partial` ×٤ + `partial_only` | `test_is_partial_four_states_and_filter` |
| 7 | الشفتات المنسية | `test_partial_only_filter_finds_forgotten_shifts` |
| 8 | `chain_gap` بالخمس تفاصيل | `test_chain_gap_returns_five_details_not_boolean` |
| — | `available_shift_numbers` ×٤ | `..._two_shift_branch` · `..._single_shift_branch` · `..._hides_expired_config` · `..._present_in_list` |
| — | إعادة الفتح تتطلب سببًا | `test_reopen_requires_reason` |
| — | `branch_user` لا يعيد الفتح | `test_branch_user_cannot_reopen` |

### فحص الـmapper — المخاطرة الأصلية وراء الـ١١٧ فشل

```
✓ configure_mappers() نجح — صفر أخطاء
✓ 84 جدولًا مسجّلًا · 8 جداول shift-ops
```

إضافة الموديلات **لم تكسر** إعداد الـmapper على مستوى التطبيق. هذا يستبعد الآلية الوحيدة التي
كانت تجعل shift-ops سببًا محتملًا لفشل اختبارات لا علاقة لها به.

### ⚠️ ما لم أتحقق منه

**الحزمة الكاملة.** تجاوزت ١٠ دقائق في بيئتي فانقطعت (تأخذ ٢٨ دقيقة عندك). لا يزال مطلوبًا:

```powershell
cd C:\raed_inventory_system\raed_inventory\backend
python -m pytest tests/ -q --deselect tests/test_epic10_13_unittest.py
```

**ولا تقارن بـ`TESTS_FAILURE_TRIAGE.md`** — تاريخه ١٧ أبريل، خط أساس منتهي الصلاحية.
خط الأساس الصحيح هو فرع `safety/wip-before-shift-ops-backend-v2-2`.

---

## ٢ · الواجهة

### الملفات

**جديدة (٦):** `services/shiftOpsApi.js` · `pages/shift_ops/ShiftListPage.jsx` ·
`ShiftCountPage.jsx` · `ShiftCashPage.jsx` · `ShiftOpsReportPage.jsx` · `ShiftManagerActions.jsx`

**الربط:** عبر `apply_frontend.py` في جذر المستودع — يعدّل `App.jsx` و`AppLayoutV2.jsx` و
`AppLayout.jsx` و`services/api.js` و`i18n/dict/ar.json` و`en.json`.

السكريبت **آمن للتكرار**، ويدمج مفاتيح i18n **بالإضافة فقط** (لا يستبدل ترجمة قائمة)، وإذا لم
يجد نقطة ربط يطبع `MANUAL FOLLOW-UP NEEDED` ويخرج بكود ٢ بدل أن يخمّن.

### قرارات التنفيذ

- **عدد الشفتات لا يُثبَّت ولا يُخمَّن.** مصدره `available_shift_numbers`. إذا غاب الحقل، قائمة
  الاختيار تُقفل وتظهر رسالة صريحة — لا افتراض بأن كل فرع بشفت واحد.
- **التجاوز لا يُرسل تلقائيًا أبدًا.** عند `PREVIOUS_SHIFT_NOT_CLOSED` تتوقف الشاشة وتُظهر أن
  الشفت السابق سيُقفل استثنائيًا، وتطلب سببًا، قبل إعادة الإرسال بـ`override=true`.
- **`opening_balance` لا يُرسل إطلاقًا** — معروض فقط، والسيرفر يملكه.
- **الحركة السالبة لا تمنع الترحيل.** ما يمنعه هو غياب السبب. الكارت يتلوّن ويطلب السبب فقط.
- **كارت رأسي لكل صنف** — لا جدول بأربعة أعمدة. ٢٣ صنفًا على موبايل في جدول أفقي مصنع أخطاء.
- **`refund_bill` في قسم "معلومات فقط"** بصريًا منفصل، ومعادلة الواجهة
  `cash − expense − float` بدونه، مع تعليق يشرح السبب في `shiftOpsApi.js`.
- **`branch_manager` مستبعد من `ShiftManagerActions`**، مع تعليق يوضح أن إخفاء الزر ليس الضابط —
  الضابط حارس المسار والباك إند.
- **صفر نص عربي مكتوب في JSX** — كل شيء عبر `useT()`.

### فحوص أُجريت

- `esbuild` على الملفات الستة ⇒ **صفر أخطاء نحوية**.
- تحقق من وجود كل استيراد خارجي في المستودع الفعلي: `PageLoader` · `selectUser` ·
  `selectUserRoles` · `todayString` · `useT` · الـ١١ أيقونة في نسخة `lucide-react` المثبتة ·
  `interpolate` يدعم `{n}` فعلًا.

### ⚠️ ما لم أتحقق منه

```powershell
cd C:\raed_inventory_system
python apply_frontend.py
cd raed_inventory\frontend
npm run build
```

**ولقطات ٣٩٠px للشاشات الثلاث + لقطتَي إثبات إخفاء الجرد القديم بحساب `branch_user`** — وهما
شرط إطلاق في جيت الواجهة، لا رفاهية.

---

## ٣ · الانحرافات

| # | الانحراف | السبب |
|---|---|---|
| 1 | ملف اختبار **خامس** `test_shift_ops_gaps.py` بدل التعديل داخل الأربعة | diff أنظف للمراجعة، وفصل ما كتبتُه عمّا كتبه Cursor |
| 2 | مكوّن **سابع** `ShiftManagerActions.jsx` غير مدرج في الجيت | الأزرار تتكرر في شاشتين، والقاعدة الأمنية يجب أن تعيش في مكان واحد |
| 3 | `CLAUDE.md` عُدِّل | توثيق استثناء الدور الممنوح — نصّ في `CLAUDE.md` كان يمنع ما فعلته |

---

## ٤ · ملفات مؤقتة تركتها على جهازك — امسحها

```powershell
cd C:\raed_inventory_system
Remove-Item raed_inventory\backend\_*_snapshot.tgz, raed_inventory\backend\_app_*.tgz
Remove-Item -Recurse -Force _to_delete, _claude_out
```

`_to_delete/` و`_claude_out/` من أدواتي (لا تستطيع حذف الملفات)، والأرشيفات من نقل الكود لبيئتي.
**لا شيء منها يخص المشروع.**

---

## ٥ · الحالة والخطوة التالية

```
Backend  = مُنفَّذ · 39/39 خضراء محليًا · الحزمة الكاملة لم تُشغَّل بعد
Frontend = مكتوب · فحص نحوي واستيرادات مرّ · build لم يُشغَّل بعد
Commit   = NO    Push = NO    Production = NO
```

**بندان مستقلان لم يُنفَّذا:**

1. **باج المرتجع في `apps_script/Validation.gs`** — يخصم `refund_bill` من رقم صافي أصلًا، فيولّد
   عجزًا وهميًا بقيمة المرتجع ويُجبر موظف الفرع على توقيع سبب عجز لم يقع. **ضرره يقع الآن**، لا
   لاحقًا. جيت منفصل + مراجعة أي فروق كاش سُجّلت على الفروع في شفتات بها مرتجعات.
2. **بيانات التشغيل:** قوائم أصناف البراندات · `branch_shift_configs` لـ٢٣ فرعًا (٥ منها بشفتين)
   · حسابات الفروع بكلمات مرور **مختلفة**. ولم يتأكد أحد بعد أن الـ٢٣ فرعًا موجودون أصلًا في
   قاعدة إنتاج Railway.
