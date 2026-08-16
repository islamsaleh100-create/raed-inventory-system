# CURSOR_REPORT — TG-SHIFT-OPS-POLISH

## Task ID
TG-SHIFT-OPS-POLISH

## Status
IMPLEMENTED

## Executor
Cursor

## Date
2026-08-16

---

## Summary

Added sidebar shortcuts **جرد الشفت** / **كاش الشفت** via redirect routes that resolve today's shift (or send the user to open-shift form). No auto-open of shifts. Verified Claude's seven i18n keys present; added two nav keys only.

---

## Changes

### 1. `ShiftTodayRedirect.jsx` (new)

- Calls `listShifts({ date_from: today, date_to: today })`.
- Shift exists ⇒ `navigate(/shift-ops/${id}/${target}, { replace: true })`.
- None ⇒ `navigate('/shift-ops?open=1', { replace: true })`.
- Loading ⇒ `<PageLoader />`.
- Error ⇒ `toast.error(t('common.load_failed'))` then `/shift-ops`.
- **Does not call `openShift`** (verified: zero occurrences in file).

### 2. `ShiftListPage.jsx`

- Reads `?open=1` via `useSearchParams`; `openForm` starts `true` when set (same pattern as `?manage=1` on cash page).

### 3. `App.jsx` — route order (lines 1947–1950)

```
1947: /shift-ops/today/count  → ShiftTodayRedirect target="count"
1948: /shift-ops/today/cash   → ShiftTodayRedirect target="cash"
1949: /shift-ops/:shiftId/count
1950: /shift-ops/:shiftId/cash
```

Static `today` paths **before** `:shiftId` — avoids 422 from `/shifts/today`.

### 4. `AppLayoutV2.jsx`

Two nav items after `/shift-ops`, **same roles** literally:

`branch_user` · `branch_manager` · `area_manager` · `operations_manager` · `admin` · `super_admin`

| Path | Icon | labelKey |
|------|------|----------|
| `/shift-ops/today/count` | `ClipboardList` | `nav.shift_count` |
| `/shift-ops/today/cash` | `Wallet` | `nav.shift_cash` |

`Wallet` from `lucide-react` — already used in `ShiftListPage.jsx`; build confirms import OK.

### 5. i18n — additions by this gate

| Key | ar | en |
|-----|----|----|
| `nav.shift_count` | جرد الشفت | Shift count |
| `nav.shift_cash` | كاش الشفت | Shift cash |

---

## Claude keys — verify only (not re-done)

All seven present in both `ar.json` and `en.json`, JSON valid:

- `common.date_from` · `common.date_to` · `common.load_failed` · `common.save_failed` · `common.saved`
- `shift_ops.error.MOVEMENT_EXCEPTION_REASON_REQUIRED` · `shift_ops.error.NEGATIVE_VALUE`

Note: `git diff` vs HEAD also shows the five `common.*` keys and two `shift_ops.error.*` lines — they were already on the working tree from Claude's prior fix, uncommitted. This gate **did not re-edit** those entries; only `nav.shift_count` / `nav.shift_cash` were added by Cursor.

---

## Automated checks

| Check | Result |
|-------|--------|
| `npm run build` | ✓ zero errors |
| `pytest test_shift_ops_*` | ✓ **43 passed** |
| Arabic in `pages/shift_ops/*.jsx` (non-comment) | ✓ **zero** |
| `AppLayoutV2.jsx` new lines | ✓ no new Arabic literals (pre-existing lines 61/102/193+ unchanged pattern) |
| JSON valid + nav keys | ✓ |
| `openShift` absent in `ShiftTodayRedirect` | ✓ |

---

## git diff — this gate's files

```
 raed_inventory/frontend/src/App.jsx
 raed_inventory/frontend/src/components/layout/AppLayoutV2.jsx
 raed_inventory/frontend/src/i18n/dict/ar.json
 raed_inventory/frontend/src/i18n/dict/en.json
 raed_inventory/frontend/src/pages/shift_ops/ShiftListPage.jsx
 raed_inventory/frontend/src/pages/shift_ops/ShiftTodayRedirect.jsx  (new, untracked)
 .ai-workflow/CURSOR_REPORT_TG-SHIFT-OPS-POLISH.md
```

No backend · no production · no commit · no push · no deploy.

---

## Owner next steps

1. **Single commit + deploy** bundling: trial-guard · config exposure · translation keys · this polish (all pending frontend/backend shift-ops fixes on disk).
2. Smoke: sidebar **جرد الشفت** with no shift today ⇒ list opens with form visible; with today's shift ⇒ lands on count page.
3. Then **seed gate** (`seed_shift_ops_config.py --production`).

---

## Explicit statement

**لم يُلمَس الإنتاج، ولم يُدفَع شيء.**
