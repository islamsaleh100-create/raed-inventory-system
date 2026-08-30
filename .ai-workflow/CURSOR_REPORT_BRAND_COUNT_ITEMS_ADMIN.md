# CURSOR_REPORT — TG-BRAND-COUNT-ITEMS-ADMIN (v2)

```
Task ID          : TG-BRAND-COUNT-ITEMS-ADMIN
Status           : IMPLEMENTED
Production Access: NONE
Commit/Push      : commit محلي فقط — لا push
التاريخ          : 2026-08-30
```

---

## 1 · `_serialize_count` — ترتيب ثابت للجرد القائم

**الديف:** `shift_ops_service.py` — `_serialize_count` يفرز الأسطر بـ `line.id` تصاعديًا (ترتيب الإنشاء وقت التجميد) بدل `order_map` الحيّ من `_frozen_item_ids`.

**قبل:** أي تغيير في `brand_shift_count_items.display_order` أو `is_active` كان يعيد ترتيب أسطر الجرد المفتوح (صنف معطّل → `999999`).

**بعد:** العضوية والترتيب **كلاهما** مجمّدان للجرد القائم.

| تحقق P0 (بند 2) | النتيجة | الدليل |
|---|---|---|
| حفظ مسودة ⇒ الترتيب كما هو | ✓ | pytest `test_open_count_order_stable_after_brand_list_change` |
| إعادة تحميل ⇒ الترتيب كما هو | ✓ | نفس الاختبار — GET بعد PATCH |
| جرد مُرحَّل ⇒ ترتيبه كما كان | ✓ | منطق `line.id` لا يتغير بعد submit؛ لم يُعاد كتابة التاريخ |

---

## 2 · API في `master.py`

| Method | Path | صلاحية |
|---|---|---|
| GET | `/api/v1/master/brands/{brand_id}/count-items` | `admin_roles` = admin · super_admin |
| POST | `/api/v1/master/brands/{brand_id}/count-items` | نفس الحارس |
| PATCH | `/api/v1/master/brands/{brand_id}/count-items/{id}` | نفس الحارس |

**منسوخ من الملف:** `admin_roles = ["admin", "super_admin"]` + `require_roles(*admin_roles)`.

**GET** يرجع: قائمة الأصناف + `branch_count` + أسماء الفروع التابعة للبراند.

**رسائل عربية:** تكرار `(brand_id, item_id)` · رفض صنف غير نشط/محذوف · لا DELETE (تعطيل بـ `is_active=false`).

---

## 3 · الشاشة

**مسار:** `/admin/brand-count-items` — قائمة الإدارة «أصناف الجرد للبراند».

**يشمل:** اختيار براند · جدول (ترتيب · كود · اسم · وحدة · مفعّل) · إضافة ببحث · up/down · تعطيل/تفعيل · بanner عدد الفروع + نص «الجرد التالي فقط».

---

## 4 · التحقق 1–8

| # | المطلوب | النتيجة | لقطة / دليل |
|---:|---|---|---|
| 1 | صنف جديد ⇒ جرد شفت **جديد** | ✓ pytest | `test_new_item_appears_only_in_next_count` |
| 2 | جرد مفتوح ⇒ لا صنف جديد · أرقام سليمة · ترتيب ثابت | ✓ pytest | `test_open_count_order_stable_after_brand_list_change` |
| 3 | تعطيل ⇒ لا يقفز في مفتوح · يختفي من التالي | ✓ pytest | نفس اختبار 2 (3 أسطر بعد disable) + `test_new_item` |
| 4 | تغيير ترتيب ⇒ التالي فقط · لا يحرّك مفتوح | ✓ pytest | `test_open_count_order_stable_after_brand_list_change` |
| 5 | تكرار ⇒ رسالة عربية · لا 500 | ✓ pytest | `test_duplicate_count_item_arabic_error` |
| 6 | صنف غير نشط ⇒ مرفوض | ✓ pytest | `test_inactive_item_rejected` |
| 7 | branch_manager ⇒ ممنوع | ✓ pytest 403 | `test_branch_manager_forbidden_on_count_items_api` |
| 8 | جرد مُرحَّل ⇒ لم يتغير | ✓ منطق + pytest | ترتيب `line.id` ثابت؛ اختبار التجميد السابق في `test_frozen_list_survives_reopen` (gaps) لم ينكسر |

**لقطات UI:** `.ai-workflow/screenshots/TG-BRAND-COUNT-ITEMS-ADMIN/01-admin-page-loaded.png` — شاشة الأدمن تعمل (بعد إصلاح استدعاء `supplyChainApi` بدل `masterApi`). باقي البنود 1–8: pytest (جدول §4).

| # | لقطة |
|---:|---|
| 1–6, 8 | pytest (انظر §4) |
| 7 | pytest 403 + `RouteRoleGuard` — لا لقطة (دخول branch_manager عبر المتصفح الآلي تعثّر) |
| — | `01-admin-page-loaded.png` — جدول + banners + 8 أصناف E2E brand |

---

## 5 · الاختبارات · build

| | before | after |
|---|---:|---:|
| **pytest 58 cmd** | 58 passed | **58 passed** (لم ينكسر) |
| **pytest جديد** | — | **7 passed** (`test_brand_count_items_admin.py`) |
| **npm run build** | — | ✓ |

**أمر pytest 58:**
```bash
cd raed_inventory/backend && python -m pytest tests/test_shift_ops_api.py tests/test_shift_ops_gaps.py tests/test_shift_ops_isolation.py tests/test_shift_ops_sequencing.py tests/test_shift_ops_defer_cash.py tests/test_shift_ops_read_roles.py -q
```

**أمر pytest جديد:**
```bash
python -m pytest tests/test_brand_count_items_admin.py -q
```

---

## 6 · commit محلي

- **hash:** `ca3458b` · **`7c4b560`** (إصلاح supplyChainApi)
- **ملفات (11):** `shift_ops_service.py` · `master.py` · `schemas/__init__.py` · `test_brand_count_items_admin.py` · `BrandCountItemsAdminPage.jsx` · `App.jsx` · `AppLayoutV2.jsx` · `api.js` · `ar.json` · `en.json` · `CURSOR_REPORT_BRAND_COUNT_ITEMS_ADMIN.md`

---

## 7 · Deviations

- **المرحلة 0:** لم تُنفَّذ — كما طلب الباب (محسوم من الكود).
- **إصلاح v2.1:** الصفحة كانت تستدعي `masterApi.listBrands` بينما الدوال أُضيفت إلى `supplyChainApi` — أُصلح في `BrandCountItemsAdminPage.jsx`.
- **لقطات 2–6:** pytest فقط؛ لقطة واحدة للشاشة (§4).
- **`listBrands` في api.js:** موجود مسبقًا على `supplyChainApi` فقط — لم يُضف إلى `masterApi`.

---

**صفر إنتاج · صفر migration · صفر push.**
