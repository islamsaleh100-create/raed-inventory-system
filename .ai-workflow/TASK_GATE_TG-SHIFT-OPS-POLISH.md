# TASK_GATE_TG-SHIFT-OPS-POLISH

## Task ID
TG-SHIFT-OPS-POLISH

## Status
IMPLEMENTED

## Cursor Permission
**EXECUTE**
**DO_NOT_EXECUTE:** `git commit` · `git push` · نشر · أي اتصال بقاعدة الإنتاج · seed.

## Owner
Islam. Executor: Cursor. Reviewer: Claude. Commit/Deploy: Islam.

---

# لماذا دفعة واحدة

اكتُشفت ثلاثة عيوب متتالية بثلاث نشرات منفصلة (حظر الشاشات القديمة · `available_shift_numbers` ·
مفاتيح الترجمة). الاكتشاف كان تسلسليًا: كل عيب ظهر من لقطة شاشة، لا من فحص منهجي. **هذا خطأ
منهج في المراجعة، لا نفاد صبر من المالك.**

أُجري الآن فحص شامل لكل سطح shift-ops. ما يلي **قائمة كاملة** بما تبقّى.

## فُحص ولا يحتاج عملًا — لا تُعِد فحصه

| الفحص | النتيجة |
|---|---|
| نص عربي مكتوب في JSX عبر `pages/shift_ops/` | **صفر** ✓ |
| فروع المفاتيح الديناميكية مقابل enums الباك إند (`status` · `section_status` · `exception_type` · `reopen_target` · `expense_type`) | **كاملة في العربي والإنجليزي** ✓ |
| أكواد أخطاء التحقق التسعة في `shift_ops_validation.py` | **كلها مترجمة** بعد إصلاح Claude ✓ |
| مفاتيح الترجمة الثابتة (66 مفتاحًا) | **صفر ناقص** بعد إصلاح Claude ✓ |

## أُصلح فعلًا على القرص (Claude) — لا تكرّره، فقط تحقّق أنه موجود

سبعة مفاتيح كانت مفقودة تمامًا، تظهر للمستخدم كنص خام:

```
common.date_from · common.date_to · common.load_failed · common.save_failed · common.saved
shift_ops.error.MOVEMENT_EXCEPTION_REASON_REQUIRED
shift_ops.error.NEGATIVE_VALUE
```

`common.saved` أخطرها عمليًا: تظهر بعد **كل** حفظ ناجح، فكان مدير الفرع سيرى `common.saved`
كل مرة.

**تحقّق فقط** أن السبعة موجودة في `ar.json` و`en.json`، وأن الملفين JSON صالح. لا تعدّلهما.

---

# المطلوب — بند واحد

## اختصارا «الجرد» و«الكاش» في القائمة الجانبية

**الوضع الآن:** بند واحد `/shift-ops` ⇒ المستخدم يفتح الشفت ⇒ يظهر سطر ⇒ منه رابطان.
ثلاث ضغطات يوميًا لعمل يتكرّر كل يوم في 23 فرعًا.

**المطلوب:** بندان مباشران في القائمة. لكن الصفحتين تحتاجان `shiftId`
(`/shift-ops/:shiftId/count` و `/cash`)، فالبند لا يستطيع الربط مباشرةً.

### التصميم — مسار محوِّل، لا فتح ضمني

أنشئ مسارين:

```
/shift-ops/today/count
/shift-ops/today/cash
```

مكوّن واحد `ShiftTodayRedirect({ target })`:

1. ينادي `shiftOpsApi.listShifts({ date_from: today, date_to: today })`.
2. **وُجد شفت اليوم** ⇒ `navigate(`/shift-ops/${id}/${target}`, { replace: true })`.
3. **لا يوجد** ⇒ `navigate('/shift-ops?open=1', { replace: true })` — شاشة القائمة مع فورم
   الفتح مفتوحًا.
4. أثناء التحميل ⇒ `<PageLoader />`. عند فشل النداء ⇒ `toast.error(t('common.load_failed'))`
   ثم التحويل إلى `/shift-ops`.

> **ممنوع منعًا باتًا: فتح شفت تلقائيًا من هذا المسار.** فتح الشفت فعل متعمَّد — يثبّت التاريخ
> ورقم الشفت ويبدأ سلسلة الأرصدة، ومنطق «الشفت السابق غير مقفل» يجب أن يظهر في شاشة الفتح
> حيث يفهمه المستخدم، لا كأثر جانبي لضغطة على «الكاش».

في `ShiftListPage.jsx`: اقرأ `?open=1` من `useSearchParams` واجعل `openForm` تبدأ `true`.
(النمط مستخدم فعلًا في `ShiftCashPage.jsx` مع `?manage=1` — اتبعه.)

### القائمة

في `AppLayoutV2.jsx`، أضف بندين **بعد** بند `/shift-ops` القائم (لا تحذفه — هو مدخل السجل
والتقارير):

```js
{ to: '/shift-ops/today/count', icon: ClipboardList, labelKey: 'nav.shift_count',
  roles: ['branch_user','branch_manager','area_manager','operations_manager','admin','super_admin'] },
{ to: '/shift-ops/today/cash',  icon: Wallet,        labelKey: 'nav.shift_cash',
  roles: ['branch_user','branch_manager','area_manager','operations_manager','admin','super_admin'] },
```

**نفس قائمة الأدوار حرفيًا** كبند `/shift-ops`. لا توسّعها ولا تضيّقها.
`Wallet` من `lucide-react` — **تأكّد أنها موجودة في النسخة المثبّتة** قبل الاستيراد؛ إن لم تكن،
استخدم أيقونة موجودة واذكر البديل في التقرير.

### مفاتيح الترجمة

`nav.shift_count` · `nav.shift_cash` في `ar.json` و`en.json`:

| المفتاح | عربي | إنجليزي |
|---|---|---|
| `nav.shift_count` | جرد الشفت | Shift count |
| `nav.shift_cash` | كاش الشفت | Shift cash |

**إضافة فقط.** لا تلمس مفتاحًا قائمًا، ولا تعِد ترتيب الملف.

### المسارات في `App.jsx`

```jsx
<Route path="/shift-ops/today/count" element={<RouteRoleGuard allowed={[...نفس القائمة]}><ShiftTodayRedirect target="count" /></RouteRoleGuard>} />
<Route path="/shift-ops/today/cash"  element={<RouteRoleGuard allowed={[...نفس القائمة]}><ShiftTodayRedirect target="cash"  /></RouteRoleGuard>} />
```

**ضعهما قبل** `/shift-ops/:shiftId/count` في ترتيب المسارات، وإلا التقط `:shiftId` كلمة
`today` وذهب النداء إلى `/shifts/today` فأعاد 422.

---

# اختبار

اختبار واجهة غير مطلوب. المطلوب:

1. `npm run build` ⇒ صفر أخطاء.
2. `python -m pytest tests/test_shift_ops_*.py -q` ⇒ **43 passed** (لم ينكسر شيء — لا تغيير في الباك إند).
3. فحص آلي: صفر نص عربي مكتوب في JSX عبر `pages/shift_ops/` و`components/layout/`.
4. فحص آلي: `nav.shift_count` و`nav.shift_cash` موجودان في اللغتين، والملفان JSON صالح.

---

# الملفات المسموح بها

1. `frontend/src/pages/shift_ops/ShiftTodayRedirect.jsx` — جديد
2. `frontend/src/pages/shift_ops/ShiftListPage.jsx` — قراءة `?open=1` فقط
3. `frontend/src/App.jsx` — مساران جديدان فقط
4. `frontend/src/components/layout/AppLayoutV2.jsx` — بندان جديدان فقط
5. `frontend/src/i18n/dict/ar.json` · `en.json` — مفتاحان جديدان، **إضافة فقط**
6. `.ai-workflow/CURSOR_REPORT_TG-SHIFT-OPS-POLISH.md` — جديد

**ممنوع:** أي ملف باك إند · `AppLayout.jsx` القديم · أي شيء في `seed_shift_ops/` · commit · push · نشر.

# معايير القبول

- [ ] الاختصاران يظهران لمدير الفرع، وبنفس أدوار `/shift-ops` حرفيًا.
- [ ] المساران الجديدان **قبل** `/shift-ops/:shiftId/...` في ترتيب `App.jsx`. أثبِت بالسطور.
- [ ] `ShiftTodayRedirect` **لا يفتح شفتًا** في أي مسار. أثبِت بأن الملف لا يستدعي `openShift`.
- [ ] بلا شفت اليوم ⇒ يحوّل إلى `/shift-ops?open=1` وفورم الفتح يبدأ مفتوحًا.
- [ ] السبعة مفاتيح التي أصلحها Claude موجودة، والملفان JSON صالح.
- [ ] `npm run build` ⇒ صفر أخطاء · `pytest tests/test_shift_ops_*.py` ⇒ 43 passed.
- [ ] صفر نص عربي في JSX.
- [ ] `git diff --stat` ⇒ الملفات الستة أعلاه فقط.

# بعد هذا الجيت

commit ⇒ push ⇒ نشرة **واحدة** تحمل الترجمة والاختصارين معًا.
ثم التجهيز (seed) — وهو آخر خطوة قبل تشغيل الفروع.
