# CURSOR_REPORT.md

## Task ID
TG-PHASE2-DEPLOY-PREP

## Gate check performed?
Yes — `Status: APPROVED` + `Cursor Permission: EXECUTE` (owner supplied gate file).

## Files Modified
- `apps_script/Migration.gs` — **NEW**: `migratePhase2SalesColumns()`, `rollbackPhase2SalesColumns()` (header-only, LockService, idempotent).
- `apps_script/Config.gs` — `INVENTORY_ENFORCEMENT_START_DATE: '2026-07-22'`.
- `apps_script/Inventory.gs` — `resolveOpeningBalances_` ignores pre-cutoff earlier shifts via `storedBusinessDate_`.
- `tools/phase0_hotfix/inventory_opening_engine.mjs` — cutoff parameter + three deploy-prep scenarios.
- `tools/phase0_hotfix/run_tests.mjs` — cutoff tests + migration/cutoff source checks.
- `.ai-workflow/TASK_GATE.md`

## Summary

### Migration (Codex runs manually in maintenance window)
Append-only Sales columns 24–25 after 23-col base verified. Rollback deletes trailing columns only if empty.

### Inventory cutoff (no backfill)
Prior-inventory rule applies only to shifts on/after `INVENTORY_ENFORCEMENT_START_DATE`. First inventory on go-live day opens at 0; chain enforced from next shift onward.

### Unchanged
`ADMIN` remains in `MANAGER_ACTION_ROLES`.

## Tests Run & Results
```
node tools/phase0_hotfix/run_tests.mjs
Phase 0 hotfix tests: 40/40 passed
```

## Deviations
NONE.

## Codex handoff (after Claude SAFE_TO_COMMIT)
1. Set `INVENTORY_ENFORCEMENT_START_DATE` to **actual go-live date** before `clasp push`.
2. §4 sequence: backup → push → `migratePhase2SalesColumns()` → new deployment version → 12 scenarios.
3. See `RAED_Phase2_Deploy_Review_for_Codex.md`.
