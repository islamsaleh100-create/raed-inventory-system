# CURSOR_REPORT — TG-SHIFT-OPS-BACKEND-V2.2 (revision)

## Status
IMPLEMENTED — awaiting Claude re-review after مانع ١ + مانع ٢ mapping

---

## مانع ١ · الحزمة الكاملة (بدون `-x`)

**الأمر:**
```powershell
cd C:\raed_inventory_system\raed_inventory\backend
python -m pytest tests/ -q --deselect tests/test_epic10_13_unittest.py
```

**الملخّص الأخير (حرفيًا):**
```
= 117 failed, 399 passed, 221 skipped, 22 deselected, 10 warnings in 1694.85s (0:28:14) =
```

**shift-ops في نفس التشغيل:**
```
tests\test_shift_ops_api.py ....                                         [ 88%]
tests\test_shift_ops_isolation.py ..                                     [ 88%]
tests\test_shift_ops_sequencing.py .......                               [ 89%]
tests\test_shift_ops_validation.py .....                                 [ 90%]
```
→ **18/18 passed** — صفر فشل في اختبارات الجيت.

**هل هناك فشل جديد من shift-ops؟**

| فحص | النتيجة |
|-----|---------|
| أي `FAILED tests/test_shift_ops_*` | **لا** |
| `TESTS_FAILURE_TRIAGE.md` (قبل الجيت) | **105 FAILED** + 82 ERROR — نفس العائلات (login path قديم، schema setup، 404 vs 200) |
| الفشل الحالي | **117 FAILED** — نفس الملفات المعروفة (`test_security_and_workflow_fixes_*`, `test_settings_g3`, `test_supply_chain_phase1_*`, epic suites…) |

**الاستنتاج:** الفشل **ليس جديدًا** من diff shift-ops؛ موثّق مسبقًا في `TESTS_FAILURE_TRIAGE.md`. **لا `DO_NOT_COMMIT` بسبب فشل جديد مُنسوب للجيت** — لكن معيار الجيت «الحزمة كاملة خضراء» **لم يتحقق** (117 failed قائمة).

---

## مانع ٢ · تغطية البنود الثمانية

| # | البند | الاختبار المغطّي | الحالة |
|---|--------|-------------------|--------|
| 1 | **Idempotency:** `POST /count` مرتين ⇒ نفس `count_id` + `items_frozen_at`؛ على `submitted` ⇒ 200 لا 409 | `test_post_count_is_idempotent` (`test_shift_ops_sequencing.py`) | **جزئي** — يغطي draft/idempotency فقط؛ **لا** اختبار لنداء ثانٍ على جرد `submitted` |
| 2 | **التجميد:** إضافة صنف للبراند بعد الإنشاء لا تغيّر السطور؛ عند إعادة الفتح لا يظهر | `test_frozen_list_ignores_new_brand_item` (`test_shift_ops_api.py`) | **جزئي** — يغطي «لا تغيير السطور» فقط؛ **لا** اختبار إعادة فتح |
| 3 | **تداخل `effective_from/to`:** تداخل من الجهتين، احتواء كامل، نطاق مفتوح | `test_config_overlap_rejected` (`test_shift_ops_sequencing.py`) | **جزئي** — حالة واحدة فقط (نطاق مفتوح يبدأ داخل نطاق مغلق)； **لا** تداخل عكسي ولا احتواء كامل |
| 4 | **نافذة إعادة الفتح:** من وقت الترحيل (مثال 23:50 → بعد 30 ساعة) | `test_reopen_window_from_submission_time` (`test_shift_ops_sequencing.py`) | **✅** |
| 5 | **سقف إعادة الفتح:** الثالثة ⇒ 409؛ `admin` يتجاوز | — | **❌ بلا اختبار** |
| 6 | **`target=cash`** لا يلمس الجرد؛ `submitted_by` لا يُمسح | — | **❌ بلا اختبار** (نداء reopen بـ `target=cash` موجود في #4 لكن **بدون** assert على الجرد/`submitted_by`) |
| 7 | **`is_partial`** في الحالات الأربع + `partial_only=true&date_to=<أمس>` | `test_independent_count_and_cash_submit` (`test_shift_ops_api.py`) | **جزئي** — حالة واحدة (count submitted / cash draft)؛ **لا** الحالات الثلاث الأخرى ولا فلتر `partial_only` |
| 8 | **`chain_gap`** بالتفاصيل الخمسة لا boolean | — | **❌ بلا اختبار** |

### اختبارا العزل — الثلاثة صراحةً

| العزل المطلوب | الاختبار | الحالة |
|---------------|----------|--------|
| **لا أمر تجديد** (`replenishment_orders`) | `test_count_submit_does_not_touch_replenishment` | **✅** |
| **لا حركة ليدجر** | — | **❌ بلا اختبار** |
| **لا طلب فرع** (`branch_requests`) | — | **❌ بلا اختبار** |
| (إضافي) منع استيراد خدمات محظورة | `test_shift_ops_service_has_no_forbidden_imports` | **✅** (grep static فقط — ليس runtime DB) |

---

## Pytest shift-ops فقط (مرجع)

```
18 passed, 6 warnings in ~22s
```

---

## Deviations

1. الحزمة الكاملة **117 failed** — pre-existing triage، ليس regression من shift-ops.
2. **4 بنود** من الثمانية **بلا اختبار**؛ **4 بنود** جزئية؛ **2 من 3** عزل runtime **بلا اختبار** (ledger + branch_request).
3. لا commit / push (حسب التعليمات).

## Recommended next step (for gate closure)

إضافة اختبارات في الملفات المسموحة فقط (`test_shift_ops_*.py`) لتغطية البنود ❌ والجزئيات — gate revision منفصل أو تمديد EXECUTE بعد موافقة Claude.
