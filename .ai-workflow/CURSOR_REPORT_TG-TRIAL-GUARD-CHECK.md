# CURSOR_REPORT — TG-TRIAL-GUARD-CHECK

## Task ID
TG-TRIAL-GUARD-CHECK

## Status
IMPLEMENTED

## Executor
Cursor

## Date
2026-08-16

---

## Phase 1 — Production role check (read-only)

**Connection:** Railway CLI → Postgres service → `DATABASE_PUBLIC_URL` (session env `PROD_DATABASE_URL` only; not written to any file).

```
القاعدة: postgresql://postgres:***@switchback.proxy.rlwy.net:50440/railway
الوضع : قراءة فقط

──────────────────────────────────────────────────────────
الدور                        الحالة         عدد
──────────────────────────────────────────────────────────
branch_user                  active          25  ← محظور
branch_manager               active          25  ← محظور
kitchen_section_manager      active           6  ← محظور
area_manager                 active           3  ← محظور
warehouse_user               active           3  ← محظور
warehouse_manager            active           3  ← محظور
super_admin                  active           2
kitchen_manager              inactive         2
delivery_user                active           2  ← محظور
internal_auditor             active           1
operations_manager           active           1
admin                        active           1
══════════════════════════════════════════════════════════
❌ 67 مستخدمًا نشطًا على أدوار محظورة.
  هؤلاء مقفول عليهم شاشات الطلبات/المستودع/التوصيل الآن.
  الإصلاح قبل أي خطوة أخرى.
══════════════════════════════════════════════════════════
لم تُكتب أي بيانات.
```

**Decision:** Phase 2 required — 67 active users on blocked roles.

### Active blocked roles (summary)

| Role | Active count |
|------|-------------|
| branch_user | 25 |
| branch_manager | 25 |
| kitchen_section_manager | 6 |
| area_manager | 3 |
| warehouse_user | 3 |
| warehouse_manager | 3 |
| delivery_user | 2 |
| **Total** | **67** |

---

## Phase 2 — Env-guard fix (applied)

**File changed:** `raed_inventory/frontend/src/utils/trialLegacy.js` — `isTrialLegacyBlocked` only.

Added at function start:

```js
if (import.meta.env.VITE_TRIAL_LEGACY_BLOCK !== 'true') return false
```

Plus the three-line Arabic comment block from the gate.

**Not modified:** `TrialLegacyRouteGuard.jsx`, `App.jsx`, `LEGACY_TRIAL_BLOCKED_PATHS`, `isLegacyPathBlockedForTrial` (calls `isTrialLegacyBlocked` first — disabled with it).

### git diff (single file)

```
diff --git a/raed_inventory/frontend/src/utils/trialLegacy.js b/raed_inventory/frontend/src/utils/trialLegacy.js
index 6fb28c2..baa837d 100644
--- a/raed_inventory/frontend/src/utils/trialLegacy.js
+++ b/raed_inventory/frontend/src/utils/trialLegacy.js
@@ -33,6 +33,10 @@ export const LEGACY_TRIAL_BLOCKED_PATHS = new Set([
 ])
 
 export function isTrialLegacyBlocked(roles = []) {
+  // حُجِبت هذه الشاشات لتجربة الـLAN، ثم وصل المكوّن إلى الإنتاج ضمن دمج 7929cdc
+  // بلا شرط بيئة، فحجب مستخدمين حقيقيين. الحظر الآن اختياري وصريح: مطفأ ما لم
+  // تُضبط VITE_TRIAL_LEGACY_BLOCK=true في بيئة التجربة وحدها.
+  if (import.meta.env.VITE_TRIAL_LEGACY_BLOCK !== 'true') return false
   if (roles.includes('admin') || roles.includes('super_admin')) return false
   return TRIAL_SUPPLY_CHAIN_ROLES.some((r) => roles.includes(r))
 }
```

### npm run build

**Result:** ✓ success (zero errors). Bundle ~1,781 kB JS.

### LAN-related pytest

```powershell
python -m pytest tests/test_lan_trial_blockers.py tests/test_final_lan_ui_fixes.py -q
```

**Result:** 27 collected, **27 skipped**, 0 failed, 0 passed.

No test failures attributable to this change. Tests were not modified.

---

## Acceptance criteria

| Criterion | Result |
|-----------|--------|
| Full role table + summary line in report | ✓ |
| Zero production writes | ✓ (SELECT only) |
| git diff ⇒ one file, one function | ✓ |
| npm run build zero errors | ✓ |
| LAN test results documented | ✓ (all skipped) |
| No commit / push / deploy | ✓ **Nothing merged, pushed, or deployed.** |

---

## Owner next steps

1. Review diff and this report.
2. Commit + deploy frontend fix **before** resuming prod `alembic upgrade head` (shift-ops).
3. For LAN trial only: set `VITE_TRIAL_LEGACY_BLOCK=true` in that environment's build vars.
4. Production default (env unset or not `'true'`): guard is **off** — operational roles regain access to blocked routes.

---

## Files touched

1. `raed_inventory/frontend/src/utils/trialLegacy.js` (modified)
2. `.ai-workflow/CURSOR_REPORT_TG-TRIAL-GUARD-CHECK.md` (this file)
