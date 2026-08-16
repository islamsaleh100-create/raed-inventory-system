# CURSOR_REPORT — TG-SHIFT-CONFIG-EXPOSURE

## Task ID
TG-SHIFT-CONFIG-EXPOSURE

## Status
IMPLEMENTED

## Executor
Cursor

## Date
2026-08-16

---

## Problem fixed

`available_shift_numbers` was only reachable inside shift summary items. Empty `items` left the UI at `null`, disabling “Open shift” for all 23 branches on launch. Admin views could also inherit numbers from the first unrelated shift row.

---

## Changes

### 1. Backend — `list_shifts` (`shift_ops.py`)

Added top-level `available_shift_numbers` computed from `scope_branch = branch_id or current_user.branch_id` and `date_to or date.today()`. Empty scope ⇒ `[]`.

`_serialize_shift_summary` unchanged (field remains on items for backward compatibility).

### 2. Frontend — `ShiftListPage.jsx`

- Reads `r.data.available_shift_numbers` first; falls back to item-level field for old backends.
- `[]` vs `null` distinguished: empty config shows `shift_ops.no_shift_config`; missing response shows `shift_ops.shift_config_unavailable`.
- Open button: `disabled={saving || !availableShiftNumbers?.length}`

### 3. i18n

| Key | ar | en |
|-----|----|----|
| `shift_ops.no_shift_config` | لا يوجد إعداد شفتات لهذا الفرع — راجع الإدارة | No shift configuration for this branch — contact admin |

### 4. Tests — `test_shift_ops_gaps.py` (3 new, existing untouched)

| Test | Asserts |
|------|---------|
| `test_list_shifts_exposes_config_with_zero_shifts` | Config + zero shifts ⇒ `items == []`, `available_shift_numbers == [1]` |
| `test_list_shifts_empty_config_returns_empty_array` | No config ⇒ `available_shift_numbers == []` |
| `test_list_shifts_admin_scope_uses_requested_branch` | Admin + `branch_id` for 1-shift branch ⇒ `[1]` not `[1,2]` when another branch has open 2-shift shift |

---

## Regression proof (reverted router)

Temporarily restored old `list_shifts` return `{"total", "items"}` only, ran:

```powershell
python -m pytest tests/test_shift_ops_gaps.py::test_list_shifts_exposes_config_with_zero_shifts -q
```

**Failure (expected):**

```
KeyError: 'available_shift_numbers'
FAILED tests/test_shift_ops_gaps.py::test_list_shifts_exposes_config_with_zero_shifts
```

Fix re-applied; full suite green.

---

## Test & build

```powershell
python -m pytest tests/test_shift_ops_api.py tests/test_shift_ops_gaps.py tests/test_shift_ops_isolation.py tests/test_shift_ops_sequencing.py tests/test_shift_ops_validation.py -q
```

**Result:** **43 passed** (40 prior + 3 new).

```powershell
npm run build
```

**Result:** ✓ zero errors.

---

## git diff — allowed files

```
 raed_inventory/backend/app/routers/shift_ops.py           | 14 +++++++++++++-
 raed_inventory/backend/tests/test_shift_ops_gaps.py       | 48 ++++++++++++++++++++++++++++++++++++++++++++++++
 raed_inventory/frontend/src/i18n/dict/ar.json             |  1 +
 raed_inventory/frontend/src/i18n/dict/en.json             |  1 +
 raed_inventory/frontend/src/pages/shift_ops/ShiftListPage.jsx | 19 ++++++++++++++-----
```

Note: `.gitignore` (`*.dump`) is an uncommitted carryover from TG-PROD-MIGRATE, not part of this gate.

---

## Acceptance

| Criterion | Result |
|-----------|--------|
| shift_ops tests pass | ✓ 43 passed |
| Regression test fails on old router | ✓ KeyError documented |
| npm run build | ✓ |
| No Arabic literal in JSX | ✓ (i18n keys only) |
| Five allowed files only (this change) | ✓ |
| Production untouched | ✓ |
| No commit / push / deploy | ✓ |

---

## Owner next steps

1. Commit + deploy backend **and** frontend together (response shape + UI reader).
2. Smoke test: branch with config, **zero shifts opened** ⇒ Open button **enabled**, shift dropdown shows one option.
3. Then proceed to seed gate (`seed_shift_ops_config.py --production`).

---

## Explicit statement

**لم يُلمَس الإنتاج، ولم يُدفَع شيء.**
