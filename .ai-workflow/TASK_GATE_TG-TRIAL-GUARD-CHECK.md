# TASK_GATE_TG-TRIAL-GUARD-CHECK

## Task ID
TG-TRIAL-GUARD-CHECK

## Status
IMPLEMENTED

## Cursor Permission
**EXECUTE** — المرحلة ١ دائمًا · المرحلة ٢ **فقط إذا** كانت نتيجة المرحلة ١ سلبية.
**DO_NOT_EXECUTE:** `git commit` · `git push` · نشر · أي كتابة على الإنتاج.

## Owner
Islam. Executor: Cursor. Reviewer: Claude. Deploy: Islam.

---

# الخلفية

دمج `feature/shift-ops` في `main` (كوميت `7929cdc`) جلب 28 كوميتًا متراكمة، لا shift-ops
وحده. أُجري فحص لميكانيكا الدمج (fast-forward · صفر تعارضات) **ولم يُفحَص أثر بقية
الكوميتات على سلوك الإنتاج**. هذا خطأ في مراجعة جيت النشر، مسجَّل هنا صراحةً.

**ما نُشر:** `components/common/TrialLegacyRouteGuard.jsx` — بُني لتجربة الـLAN، **وبلا أي
شرط بيئة**. مطبَّق على ~20 مسارًا في `App.jsx`، ويحجب هذه الأدوار:

```
branch_user · branch_manager · area_manager · kitchen_section_manager
warehouse_user · warehouse_manager · delivery_user
```

عن `/orders` · `/receiving` · `/warehouse/*` · `/delivery/*` — تظهر لهم صفحة حظر بدل
الشاشة. `admin` و`super_admin` وحدهما غير متأثرين (`utils/trialLegacy.js:isTrialLegacyBlocked`).

**تم فحصه وهو سليم — لا تُعِد فحصه:** `app/startup_schema.py` يرجع فورًا على PostgreSQL،
فلا DDL على الإنتاج · كروت دخول التجربة مغلَّفة بـ`import.meta.env.DEV` فلا تُعرض ·
كلمات المرور الافتراضية **غير موجودة** في حزمة الإنتاج المبنية (فُحصت نصيًا).

---

# المرحلة ١ · الفحص (دائمًا)

الرابط عبر Railway CLI، كما في `TG-PROD-READINESS-REPORT`:

```powershell
railway status
railway link            # إن لزم — اختر المشروع ثم خدمة Postgres
railway variables       # خذ DATABASE_PUBLIC_URL — لا DATABASE_URL
$env:PROD_DATABASE_URL = "<القيمة>"
```

**متغيّر جلسة فقط. لا يُكتب في أي ملف.**

```powershell
cd C:\raed_inventory_system\raed_inventory\backend\seed_shift_ops
python check_blocked_roles.py
```

انسخ الجدول كاملًا في التقرير (الرابط يُطبع مقنَّعًا).

- **`✓ صفر مستخدمين نشطين`** ⇒ **قف هنا.** اكتب التقرير ولا تلمس أي كود. المرحلة ٢ ملغاة.
- **`❌ N مستخدمًا نشطًا`** ⇒ انتقل للمرحلة ٢، واذكر في التقرير الأدوار وأعدادها بالاسم.

---

# المرحلة ٢ · الإصلاح (فقط عند وجود متأثرين)

**لا تتراجع عن الدمج.** 189 ملفًا لا تُرمى بسبب مكوّن واحد. الإصلاح في دالة واحدة.

في `raed_inventory/frontend/src/utils/trialLegacy.js`:

```diff
 export function isTrialLegacyBlocked(roles = []) {
+  // حُجِبت هذه الشاشات لتجربة الـLAN، ثم وصل المكوّن إلى الإنتاج ضمن دمج 7929cdc
+  // بلا شرط بيئة، فحجب مستخدمين حقيقيين. الحظر الآن اختياري وصريح: مطفأ ما لم
+  // تُضبط VITE_TRIAL_LEGACY_BLOCK=true في بيئة التجربة وحدها.
+  if (import.meta.env.VITE_TRIAL_LEGACY_BLOCK !== 'true') return false
   if (roles.includes('admin') || roles.includes('super_admin')) return false
   return TRIAL_SUPPLY_CHAIN_ROLES.some((r) => roles.includes(r))
 }
```

**هذا التغيير الوحيد المسموح به في الملف.** لا تحذف `TrialLegacyRouteGuard` ولا تعدّل
`App.jsx` ولا تلمس `LEGACY_TRIAL_BLOCKED_PATHS` — إبقاء الآلية قائمة ومطفأة أرخص من إعادة
بنائها لاحقًا للتجربة.

> `isLegacyPathBlockedForTrial` تستدعي `isTrialLegacyBlocked` أولًا، فتُطفأ معها. تحقّق من ذلك
> ولا تعدّلها بشكل منفصل.

ثم:

```powershell
cd C:\raed_inventory_system\raed_inventory\frontend
npm run build
```

⇒ صفر أخطاء.

**وابحث عن أي اختبار يعتمد على الحجب:**

```powershell
cd C:\raed_inventory_system\raed_inventory\backend
python -m pytest tests/test_lan_trial_blockers.py tests/test_final_lan_ui_fixes.py -q
```

أي اختبار يفشل بسبب هذا التغيير ⇒ **اكتبه في التقرير ولا تعدّله.** قد يكون كاشفًا عن نيّة
تصميمية لم ننتبه لها، والقرار للمالك.

**لا `git commit` ولا `git push` ولا نشر.** سلّم الفرق (diff) والقرار للمالك.

---

# الملفات المسموح بها

1. `raed_inventory/frontend/src/utils/trialLegacy.js` — دالة `isTrialLegacyBlocked` فقط (المرحلة ٢ فقط)
2. `.ai-workflow/CURSOR_REPORT_TG-TRIAL-GUARD-CHECK.md` — جديد

**لا شيء غيرهما.**

# معايير القبول

- [ ] جدول الأدوار كاملًا في التقرير، وسطر الخلاصة منقولًا حرفيًا.
- [ ] صفر كتابة على الإنتاج.
- [ ] (٢) `git diff` ⇒ ملف واحد، دالة واحدة، سطر شرط + تعليق. لا شيء غيره.
- [ ] (٢) `npm run build` ⇒ صفر أخطاء.
- [ ] (٢) نتيجة اختبارَي LAN مذكورة، وأي فشل مكتوب لا مُعدَّل.
- [ ] `grep -ri "rlwy.net\|proxy.rlwy" .` ⇒ **صفر**.
- [ ] التقرير يذكر صراحةً: **لم يُدمَج ولم يُدفَع ولم يُنشَر شيء.**

# ملاحظة للمالك

المايجريشن (`alembic upgrade head`) على الإنتاج **مؤجَّل حتى تُغلَق هذه المسألة**. هو نفسه
غير متعلق بها — يضيف 8 جداول جديدة فقط — لكن لا تُضاف خطوة كتابة على الإنتاج ومسألة انقطاع
محتملة مفتوحة.
