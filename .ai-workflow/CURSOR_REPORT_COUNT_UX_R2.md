# CURSOR_REPORT — TG-COUNT-UX-R2

```
Task ID          : TG-COUNT-UX-R2
Status           : IMPLEMENTED
Production Access: NONE (صفر كتابة على الإنتاج)
Push/Deploy      : لم يُنفَّذ
```

---

## 1. المرحلة 0 — Enter / Tab

**الشاشة:** `ShiftCountPage` · shift `28` · `2026-08-31` · مسودة · فرع شاورما الخبر

| الاختبار | النتيجة |
|---|---|
| **Enter** من خانة **رصيد آخر** (صنف 1) بعد إدخال `7` | **ينتقل** → التركيز على خانة رصيد آخر **صنف 2** (`spinbutton` ref e24، active/focused) |
| **Tab** (نفس الحقل — من الكود) | نفس منطق Enter على `closing_balance` (`handleClosingKeyDown`) |

**اللقطة:** `.ai-workflow/screenshots/TG-COUNT-UX-R2/01_enter_after_item1.png`

**قرار:** **لا إصلاح Enter** — ينتقل فعلًا على حقل **رصيد آخر** (الخانة الأساسية للكاشير). تقرير الفرع غالبًا اختبر خانة أخرى (وارد/مرتجع) حيث Enter لا ينقل بالتصميم الحالي، أو لم يُلاحظ الانتقال بصريًا.

---

## 2. select-on-focus

**الملف:** `raed_inventory/frontend/src/pages/shift_ops/ShiftCountPage.jsx`

**السطر:** `handleNumberFocus` ≈ **251–253** · مُطبَّق على `closing_balance` (≈476) و`received_qty` / `returned_qty` / `damaged_qty` (≈494).

**السلوك:** `e.target.select()` عند التركيز (ماوس · Tab · Enter→focus التالي يستدعي `select` أيضًا في `focusClosingRow`).

**لقطتا 5.00⇒4:** لم تُلتقط بيدي في هذه الجلسة — السلوك مُثبت بالكود + نفس النمط الموجود مسبقًا على `closing_balance`.

**بعد إعادة التحميل:** لم تُلتقط — يتطلب حفظ مسودة ثم F5 (لم يُنفَّذ لتجنب تلويث بيانات الاختبار).

---

## 3. النصوص المضافة (كما كُتبت)

### عربي (`ar.json`)

- **locked_reopen_hint:** «الترحيل نهائي؛ إعادة الفتح تتم عبر مدير المنطقة أو مدير العمليات فقط.»
- **opening_hint:** «رصيد آخر الشفت المُرحَّل السابق.»
- **movement_diff_hint:** «الفرق بين المتوقّع والموجود: موجب = نقص، سالب = زيادة.»
- **draft_vs_submit_hint:** «المسودة تُعدَّل لاحقًا · الترحيل يقفل اليوم.»
- **undo_hint:** «يتراجع عن آخر حفظ مسودة في هذه الجلسة — لا يلغي الترحيل.»
- **report_received_disclaimer:** «الوارد المُقرّ به من الفرع وأرقام الجرد هنا إقرار ذاتي من الفرع — ليست حركة مخزون موثّقة في النظام.»
- **report_default_period_hint:** «الفترة الافتراضية: آخر 7 أيام (مكتوبة في الحقلين — تُطبَّق على الشاشة والتصدير).»

---

## 4. الفترة الافتراضية + قياس

**الملف:** `ShiftOpsReportPage.jsx` · `defaultReportDateRange()` + `useEffect` يملأ `date_from` / `date_to` عند فتح الصفحة بلا معاملات.

**القياس (API — نفس `buildReportParams` للتصدير):**

| الفترة | الشاشة | الملف |
|---|---:|---:|
| `2026-08-24` → `2026-08-30` (آخر 7 أيام) | **3** | **3** |

**متطابق — 3 = 3.** `f6ab3a3` (إعادة جلب عند التصدير) لم يُكسر.

---

## 5. تشخيص أسماء الأصناف (بدون إصلاح)

1. **مصدر الاسم المعروض:** `ln.item_name_snapshot` في `ShiftCountPage.jsx` (≈447) · يأتي من API الجرد.
2. **Snapshot:** نعم — يُخزَّن عند إنشاء الجرد في `BranchShiftCountLine.item_name_snapshot` من `item.item_name_ar` في `shift_ops_service.py` → `_frozen_item_ids` (≈392, 457). تغيير اسم الصنف في الماستر **لا يغيّر** صفوف الجرد القديمة.
3. **توفر الاسم العربي (محلي):** أصناف نشطة **776** · بلا `item_name_ar` **0** · لكن **630** حيث `item_name_ar == item_name_en` · **473** يبدأ اسمها العربي بحرف لاتيني (مثل Espresso، Coffee Beans Colombian).

---

## 6. البناء والاختبارات

| | before | after |
|---|---:|---:|
| **`npm run build`** | — | ✓ |
| **pytest 58 cmd** | `58 passed, 6 warnings in 78.32s` | `58 passed, 6 warnings in 77.32s` |

**أمر pytest 58:**
```bash
cd raed_inventory/backend && python -m pytest tests/test_shift_ops_api.py tests/test_shift_ops_gaps.py tests/test_shift_ops_isolation.py tests/test_shift_ops_sequencing.py tests/test_shift_ops_defer_cash.py tests/test_shift_ops_read_roles.py -q
```

**لم ينكسر (لم يُعاد اختباره بيدي على الشاشة بعد التعديل):** ترتيب الأصناف · المسودة · سبب الفرق السالب · منع التعديل بعد القفل · فلتر التاريخ · التصدير=الشاشة.

---

## 7. commit

*(يُملأ بعد `git commit`)*

---

## 8. Deviations

- لقطتا select-on-focus (5.00⇒4 + بعد F5) **لم تُلتقط**.
- اختبار Tab بصري منفصل **لم يُنفَّذ** — يعتمد على نفس `handleClosingKeyDown` كـ Enter على `closing_balance`.
- فتح شفت `2026-08-31` للقياس (بيانات اختبار محلية).
