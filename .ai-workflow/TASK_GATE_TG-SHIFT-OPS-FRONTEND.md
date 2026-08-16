# TASK_GATE_TG-SHIFT-OPS-FRONTEND

## Task ID
TG-SHIFT-OPS-FRONTEND

## Status
APPROVED

## Cursor Permission
EXECUTE — بالتوازي مع إنهاء `TG-SHIFT-OPS-BACKEND-V2.2`

## Owner
Islam. Executor: Cursor. Reviewer: Claude. Commit/Deploy: Islam.

## الهدف بجملة واحدة
**موظف الفرع يقدر يعمل جرد الشفت والكاش من شاشة.** الباك إند جاهز، والموظف مش هيستخدم API.

---

# ⛔ ممنوعات مطلقة — أي خرق = `DO_NOT_COMMIT`

- **ممنوع لمس أي ملف باك إند.** لا `app/`، لا `alembic/`، لا `tests/` الخاصة بالباك إند.
- **ممنوع لمس موديول الجرد القديم** — `pages/branch/InventoryListPage.jsx` و
  `InventoryEntryPage.jsx` **لا تُعدَّل ولا تُحذف**. الإخفاء يتم من التوجيه والقوائم فقط.
- **ممنوع** استدعاء أي endpoint غير `/api/v1/shift-ops/*`. تحديدًا: ممنوع `/inventory`،
  `/orders`, `/stock`, `/branch-requests`, `/supply-chain`.
- **ممنوع** اختراع سير عمل جديد. لا اعتماد، لا رفض، لا أي حالة غير الموجودة في الباك إند.
- **ممنوع** `git commit` · `git push` · النشر · الدمج في `main` · تشغيل migration على الإنتاج.
- **ممنوع** إضافة أو حذف أي اعتمادية في `package.json`.

---

# نقاط النهاية المتاحة — استخدمها كما هي، لا تخترع غيرها

قاعدة المسار: `/api/v1/shift-ops`

```
POST   /shifts                        فتح شفت (override + override_reason اختياريان)
GET    /shifts                        قائمة + فلاتر
GET    /shifts/{id}                   تفاصيل + count_status + cash_status + is_partial
POST   /shifts/{id}/reopen            مدير — target + reason إلزاميان
POST   /shifts/{id}/close-no-activity مدير — exception_type + reason

POST   /shifts/{id}/count             إنشاء الجرد — idempotent، آمن للتكرار
GET    /shifts/{id}/count             السطور + opening محسوبًا من السيرفر
PATCH  /shifts/{id}/count/lines       تعديل سطور دفعة واحدة
POST   /shifts/{id}/count/submit      ترحيل الجرد

GET    /shifts/{id}/cash
PUT    /shifts/{id}/cash              حفظ مسودة
POST   /shifts/{id}/cash/submit       ترحيل الكاش

GET    /reports/shift-operations      تقرير المراجعة — قراءة فقط
```

**قبل كتابة أي شاشة:** افتح `app/routers/shift_ops.py` واقرأ أشكال الطلب والاستجابة الفعلية.
لا تفترض أسماء حقول. لو حقل ناقص في الاستجابة، **قف واكتبه في التقرير** — ولا تعدّل الباك إند.

---

# الملفات المسموح بها

**جديدة**
1. `frontend/src/pages/shift_ops/ShiftListPage.jsx`
2. `frontend/src/pages/shift_ops/ShiftCountPage.jsx`
3. `frontend/src/pages/shift_ops/ShiftCashPage.jsx`
4. `frontend/src/pages/shift_ops/ShiftOpsReportPage.jsx`
5. `frontend/src/services/shiftOpsApi.js`
6. `.ai-workflow/CURSOR_REPORT_TG-SHIFT-OPS-FRONTEND.md`

**تعديل محدود**
7. `frontend/src/App.jsx` — إضافة مسارات جديدة + **تضييق أدوار مسارات `/inventory` القديمة**
8. `frontend/src/components/layout/AppLayoutV2.jsx` — بند قائمة جديد + تضييق أدوار البند القديم
9. `frontend/src/components/layout/AppLayout.jsx` — نفس الشيء
10. `frontend/src/i18n/dict/ar.json` — مفاتيح جديدة فقط
11. `frontend/src/i18n/dict/en.json` — مفاتيح جديدة فقط
12. `frontend/src/services/api.js` — تصدير `shiftOpsApi` فقط، بنفس نمط `stockApi` القائم

أي ملف خارج القائمة ⇒ `Status: BLOCKED`.

---

# ١ · إخفاء موديول الجرد القديم — **شرط إطلاق، نفّذه أولًا**

**السبب — تحقق منه في الكود:** `routers/inventory.py:28` فيه
`_APPROVAL_ROLES = ("branch_manager", "admin", "super_admin")`، واعتماد أي جرد ينادي
`replenishment_service.generate_replenishment_order()` تلقائيًا. أي **مدير فرع يقدر يولّد أمر
تجديد للمستودع من الشاشة القديمة**. وجود شاشتين اسمهما "جرد" أمام الفرع = استخدام خاطئ مضمون.

**المطلوب — تضييق الأدوار فقط، بلا حذف:**

في `App.jsx` أسطر 1941–1943، المسارات `/inventory` و `/inventory/new` و `/inventory/:id`:
```diff
- allowed={['branch_user', 'branch_manager', 'admin', 'super_admin']}
+ allowed={['admin', 'super_admin']}
```

في `AppLayoutV2.jsx:29` و `AppLayout.jsx:24` — بند `الجرد اليومي` / `nav.daily_inventory`:
```diff
- roles: ['branch_user', 'branch_manager']
+ roles: ['admin', 'super_admin']
```

**لا تلمس** `/branch-stock` ولا `/reports/inventory` — دول عرض حالة وتقارير، مش إدخال جرد.
**لا تحذف** الصفحات ولا المسارات. الإدارة تفضل تشوفها.

---

# ٢ · التسمية — تفرقة إلزامية

| البند | العربية | `labelKey` |
|---|---|---|
| الجديد | **عمليات الشفت** | `nav.shift_ops` |
| القديم (للإدارة فقط) | الجرد اليومي (قديم) | `nav.daily_inventory_legacy` |

كل نصوص الواجهة عبر `i18n` — **ممنوع نص عربي مكتوب مباشرة في JSX**. اتبع نمط المفاتيح القائم
في `ar.json`، وأضف نفس المفاتيح في `en.json`.

---

# ٣ · الشاشات

## ٣-أ · `/shift-ops` — قائمة الشفتات (نقطة الدخول)

- شفتات الفرع مرتبة بالأحدث، مع فلتر مدى تاريخي.
- **كل صف يعرض حالتين منفصلتين:** `count_status` و `cash_status`. ممنوع دمجهما في حالة واحدة.
- **شارة "ناقص" بارزة** لما `is_partial = true`. دي أهم إشارة في الشاشة — الفصل بين ترحيل
  الجرد والكاش يخلق شفتات نص مرحّلة، والموظف لازم يشوفها من غير ما يدوّر.
- زر **"فتح شفت جديد"**: يختار التاريخ ورقم الشفت.
  - الفرع بشفت واحد ⇒ رقم الشفت مثبّت على 1 وغير قابل للتعديل.
  - الفرع بشفتين ⇒ اختيار بين 1 و 2.
  - عدد شفتات الفرع يجي من الباك إند. **ممنوع تثبيته في الواجهة.**

> ### ⚠️ فجوة مؤكَّدة في الباك إند — تحقق منها Claude قبل كتابة هذا الجيت
> `BranchShiftConfig` يُقرأ داخليًا فقط (تحقق التداخل، `shift_ops_service.py:186`)،
> و`_serialize_shift_summary` (سطر 109) **لا يرجع أي معلومة عن إعدادات الشفتات**.
> لا يوجد `available_shift_numbers` ولا `shift_config` في أي استجابة.
>
> **القاعدة:** لو `GET /shifts` أو `GET /shifts/{id}` لا يرجعان `available_shift_numbers`
> أو `shift_config` ⇒ **قف فورًا واكتب `Status: BLOCKED`**. **ممنوع منعًا باتًا** تثبيت عدد
> الشفتات في الواجهة، وممنوع استنتاجه من الشفتات الموجودة، وممنوع افتراض أن كل فرع بشفت واحد.
>
> السد يتم في الباك إند ضمن مراجعة `TG-SHIFT-OPS-BACKEND-V2.2`، لا هنا.
> باقي الشاشات (الجرد، الكاش، التقرير) **لا تعتمد على هذا الحقل** — أكمل بناءها ولا تتوقف عنها.
- الشفت المقفول (`submitted` / `exception_locked`) يفتح **للعرض فقط**، وكل الحقول معطّلة.

## ٣-ب · `/shift-ops/{id}/count` — الجرد

- سطر لكل صنف، والسطور جاية من الباك إند بعد التجميد. **ممنوع تولّد القائمة في الواجهة.**
- **`opening_balance` للعرض فقط** — محسوب في السيرفر. ممنوع إرساله أو السماح بتعديله.
- أربع خانات إدخال: وارد · مرتجع · تالف · رصيد آخر.
- **`movement_diff` معروض ومحسوب، غير قابل للتعديل.**
  - سالب ⇒ **مسموح**، مش خطأ. اعرضه بتمييز بصري + خانة `movement_exception_reason` تظهر
    وتبقى إلزامية. **ممنوع** منع الترحيل بسببه.
- عدّاد جاهزية: "٢٠ من ٢٣ مكتمل".
- زر **"ترحيل الجرد"** يستدعي `/count/submit` — يقفل الجرد وحده.
- `POST /count` **idempotent**: نادِه بأمان عند فتح الصفحة. ممنوع معالجة تكراره كخطأ.
- **ممنوع كلمة "استهلاك" أو `consumption`** في أي نص أو اسم متغير. الاسم: **"فرق حركة"**.

## ٣-ج · `/shift-ops/{id}/cash` — الكاش (شاشة مستقلة)

ثلاث مجموعات: **المبيعات** · **المرتجعات والخصومات** · **تسوية الصندوق**.

- محسوب في الواجهة **للعرض الفوري فقط**، والباك إند هو المرجع:
  ```
  expected_deposited = cash_sales − cash_expense − cash_float_carried_forward
  ```
  **ممنوع طرح `refund_bill` — القاعدة `net`، أرقام الكاشير صافية أصلًا.**
- `cash_variance` معروض بلون حسب الإشارة.
- **`cash_variance_reason` تظهر فقط لما `|variance| > 5`** وتبقى إلزامية ساعتها.
- `cash_expense > 0` ⇒ نوع المصروف وتفاصيله إلزاميان.
- **`refund_bill` و `exchange_amount` و `expiry_amount`:** الاستجابة بتعلّمهم
  `informational_fields`. اعرضهم في قسم **"معلومات فقط"** بصريًا واضح إنهم مش داخلين
  أي حساب. **ممنوع** إدخالهم في أي معادلة في الواجهة.
- زر **"ترحيل الكاش"** يستدعي `/cash/submit` — يقفل الكاش وحده.
- أخطاء التحقق من الباك إند تتعرض **جنب حقلها** بالـ`field` الراجع، مش كرسالة عامة فوق.

## ٣-د · إجراءات المدير

تظهر لـ`area_manager` · `operations_manager` · `admin` · `super_admin` **فقط**.
**`branch_manager` مستبعد عمدًا** — طرف في عهدة الكاش.

- **إعادة فتح:** اختيار `target` (`count` / `cash` / `both`) + **سبب إلزامي**. ممنوع إرسال بلا سبب.
- **إغلاق بلا نشاط:** اختيار `exception_type` (`branch_closed` / `manual_gap`) + سبب إلزامي.
- **تجاوز فتح شفت:** لما `POST /shifts` يرجّع `PREVIOUS_SHIFT_NOT_CLOSED`، اعرض تأكيدًا واضحًا
  بأن **الشفت السابق هيتقفل استثنائيًا**، مع سبب إلزامي، قبل إعادة الإرسال بـ`override=true`.
  **ممنوع** إرسال `override` تلقائيًا بلا موافقة صريحة.

## ٣-هـ · `/shift-ops/report` — تقرير المراجعة

- لـ`internal_auditor` · `admin` · `super_admin` · `operations_manager` · `area_manager`.
- **قراءة فقط. صفر أزرار كتابة.**
- الفلاتر: فرع · مدى تاريخي · فرق كاش فقط · مُعاد فتحها فقط · جزئية فقط · استثنائية فقط.
- يعرض أحداث إعادة الفتح **كلها** بأسبابها ومن نفّذها — مش آخر سبب فقط.

### ٣-و · مصفوفة الصلاحيات — إلزامية في `RouteRoleGuard` وفي القوائم

| المسار | الأدوار المسموحة |
|---|---|
| `/shift-ops` | `branch_user` · `branch_manager` · `area_manager` · `operations_manager` · `admin` · `super_admin` |
| `/shift-ops/:id/count` | نفس القائمة أعلاه |
| `/shift-ops/:id/cash` | نفس القائمة أعلاه |
| `/shift-ops/report` | `internal_auditor` · `area_manager` · `operations_manager` · `admin` · `super_admin` |

**شرط جوهري: الأزرار حسب الصلاحية، وليس مجرد فتح الصفحة.**
`area_manager` يفتح شاشة الكاش ليراجع، لكن أزرار الإدخال والترحيل تخص الفرع.
و`branch_manager` يفتح الشاشة لكن **لا يرى** إعادة الفتح ولا الإغلاق الاستثنائي ولا التجاوز.
إخفاء الزر وحده لا يكفي بلا حارس المسار، وحارس المسار وحده لا يكفي بلا إخفاء الزر — **الاثنان معًا**.

---

# ٤ · ابدأ بمسار أوندا

أوندا **٢٣ صنف**، وفيها ٥ فروع بشفتين — الحالة الأثقل. رونالدوز ٣ أصناف والشاورما صنفان.
**اضبط الشاشة على أوندا أولًا**: لو ٢٣ صنفًا اشتغلوا كويس على الموبايل، الباقي أسهل تلقائيًا.

**الموبايل ليس اختياريًا** — الموظف بيقفل الشفت من تليفونه. سطر الصنف لازم يكون كارت رأسي،
مش جدول أفقي بأربع أعمدة.

---

# ٥ · معايير القبول

- [ ] ملفات `git status` = القائمة المسموحة فقط.
- [ ] `grep -rn "api\.\(get\|post\|put\|patch\)" src/pages/shift_ops/` ⇒ كل النداءات عبر
      `shiftOpsApi` وكلها `/shift-ops/*`. صفر نداءات لـ`/inventory` أو `/orders` أو `/stock`.
- [ ] `git diff src/pages/branch/` ⇒ **فارغ**. الجرد القديم لم يُلمس.
- [ ] `git diff src/App.jsx` ⇒ مسارات جديدة + تضييق أدوار `/inventory` فقط.
- [ ] `grep -rni "consumption\|استهلاك" src/pages/shift_ops/ src/i18n/dict/` ⇒ **صفر**.
- [ ] `grep -rn "refund" src/pages/shift_ops/ShiftCashPage.jsx` ⇒ لا يظهر داخل أي معادلة.
- [ ] `movement_diff` سالب: يُعرض ويُقبل ويطلب سببًا، **ولا يمنع الترحيل**.
- [ ] `opening_balance` غير قابل للتعديل ولا يُرسل في أي طلب.
- [ ] `branch_user` لا يرى بند "الجرد اليومي" القديم ولا يقدر يفتح `/inventory` (يُحوَّل أو يُمنع).
- [ ] `branch_manager` لا يرى أزرار إعادة الفتح ولا الإغلاق الاستثنائي.
- [ ] صفر نص عربي مكتوب مباشرة في JSX — كله عبر `i18n`، والمفاتيح موجودة في `ar.json` و `en.json`.
- [ ] `npm run build` ينجح بلا أخطاء ولا تحذيرات جديدة.
- [ ] لقطات شاشة للثلاث شاشات بعرض موبايل (390px) مرفقة في التقرير.
- [ ] **إثبات إخفاء الجرد القديم — شرط إطلاق، لا رفاهية:**
      - لقطة بحساب `branch_user` تُظهر القائمة الجانبية **بلا** بند "الجرد اليومي" القديم.
      - لقطة لمحاولة فتح `/inventory` بحساب `branch_user` تُظهر المنع أو إعادة التوجيه.
- [ ] `/branch-stock` و `/reports/inventory` تحقق بصريًا أنهما **عرض فقط** بلا أي زر
      اعتماد أو ترحيل أو إنشاء — ولم تُلمسا في الـdiff.
- [ ] التقرير مكتوب مع أي حقل ناقص في استجابات الباك إند وقسم `Deviations`.

# خارج النطاق

أي تعديل باك إند · تعبئة قوائم الأصناف أو إعدادات الشفتات · إنشاء حسابات الفروع أو كلمات مرورها ·
`git commit` · `git push` · النشر · الدمج في `main` · migration على الإنتاج · تعديل الجرد القديم
بخلاف تضييق الأدوار.

# شرط الإيقاف

أي مطلوب لا يمكن تنفيذه دون لمس ملف ممنوع أو دون تعديل الباك إند ⇒ **قف**، اكتب
`Status: BLOCKED` مع السبب، ولا تغيّر شيئًا.
