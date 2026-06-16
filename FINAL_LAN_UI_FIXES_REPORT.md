# Final LAN UI Fixes Report

**Date:** 2026-06-16  
**Branch:** `lan-readiness/final-ui-fixes-2026-06-16`

---

## Fixes Applied

| # | Fix | Summary |
|---|-----|---------|
| 1 | Legacy orders blocked | `TrialLegacyRouteGuard` + shared `trialLegacy.js` block direct access to `/orders`, legacy warehouse, and legacy delivery routes for LAN trial operational roles with Arabic message |
| 2 | Notification translations | Added supply-chain notification keys and uppercase workflow status labels to `ar.json` / `en.json`; `operationalLabels.js` resolves labels without exposing raw i18n keys |
| 3 | Internal auditor read-only | Confirmed backend GET access for kitchen/warehouse/delivery; write actions blocked (403); UI already hides action buttons and shows `ReadOnlyBanner` |
| 4 | LAN kitchen hygiene | Added `validate_lan_kitchen_hygiene.py` and LAN trial DB reset checklist section |

---

## Legacy Route Results

| Role | `/orders` UI | Nav hidden | Message |
|------|--------------|------------|---------|
| branch_user | Blocked | Yes | هذه الشاشة غير مستخدمة في تجربة LAN… |
| area_manager | Blocked | Yes | Same |
| kitchen_section_manager | Blocked | Yes | Same |
| warehouse_manager / warehouse_user | Blocked (legacy warehouse routes) | Yes | Same |
| delivery_user | Blocked (legacy delivery analytics) | Yes | Same |
| admin / super_admin | Allowed | Legacy nav visible | — |

Implementation: `TrialLegacyRouteGuard` wraps legacy routes in `App.jsx`. Sidebar hiding uses shared `LEGACY_TRIAL_BLOCKED_PATHS` from `utils/trialLegacy.js`.

---

## Notification Translation Results

Added Arabic labels for supply-chain sections including:

- `sc_request_approved` → تم اعتماد الطلب
- `sc_request_rejected` → تم رفض الطلب
- `sc_production_started` → بدأ الإنتاج

Added branch-request / workflow status labels under `order_status.*`:

- `SPLIT` → تم تقسيم الطلب
- `IN_EXECUTION` → قيد التنفيذ
- `AREA_REJECTED` → مرفوض من مدير المنطقة

Notifications page and bell use `notificationSectionLabel()` / `operationalStatusLabel()` helpers.

---

## Internal Auditor Read-only Results

| Screen | GET API | Write blocked | UI actions hidden |
|--------|---------|---------------|-------------------|
| Kitchen Production | 200 | 403 on POST | Yes + ReadOnlyBanner |
| Warehouse Execution | 200 | 403 on POST receive | Yes + ReadOnlyBanner |
| Delivery Orders | 200 | 403 on POST | Yes + ReadOnlyBanner |

Backend middleware `block_writes_for_internal_auditor` unchanged; supply-chain list endpoints already include `internal_auditor` in view roles.

---

## LAN DB Hygiene Findings

**Dev database (`raed_inventory`):** `GO WITH WARNINGS`

- Official kitchens found: 2 (`Official Kitchen – Dammam`, `Official Kitchen – Riyadh`)
- Forbidden test kitchens: 18 (`Flow Kitchen *`, `PW Kitchen *`) — acceptable in dev, **must not exist on LAN trial DB**

Validation:

```powershell
python validate_lan_kitchen_hygiene.py --strict-lan-trial --write-report
```

Documented in `LAN_TRIAL_DB_RESET.md` §8.

---

## Test Results

```text
pytest tests/test_final_lan_ui_fixes.py -v
→ 12 passed

pytest tests/test_lan_trial_blockers.py::TestLegacyNavigationHiding -v
→ 2 passed
```

---

## Final LAN Trial Verdict

**GO WITH CONDITIONS**

UI blockers from screenshot review are addressed. Before LAN trial:

1. Reset LAN trial DB and run `validate_lan_kitchen_hygiene.py --strict-lan-trial` (must be **GO**)
2. Remove or exclude Flow/PW test kitchens from trial database
3. Re-capture role UI screenshots after frontend reload to confirm legacy `/orders` shows LAN trial message
