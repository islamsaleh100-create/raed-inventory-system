# Branch Request Catalog UI Fix — LAN Trial

## Problem

Branch users on the Branch Request create screen saw an admin-style form: editable brand dropdown, per-row item dropdown, source dropdown (Warehouse/Kitchen/Both), and empty line rows. Branch staff must only pick quantities from allowed items; source is decided by item master and Auto Split after area manager approval.

## UI Before

- Editable brand `<select>`
- Per-row item `<select>` with empty default rows
- Source `<select>` on every line
- «حفظ مسودة» / «حفظ وإرسال» actions
- Unclear full item visibility (dropdown-only)

## UI After

For `branch_user` / `branch_manager` (not admin/auditor):

- Read-only header: **الفرع:** and **البراند:**
- Full allowed-item catalog table with columns: الصنف، التصنيف، الوحدة، الكمية المطلوبة، ملاحظة
- Search: **بحث باسم الصنف** and category filter: **فلتر التصنيف**
- Single primary action: **إرسال الطلب** (disabled until at least one quantity &gt; 0)
- Item labels: `{name} — {short code}` (e.g. `7UP سفن أب — 31319B`)
- Request history list unchanged on the left

Admin / internal auditor branch-selection form is unchanged.

## Source Dropdown Removal

- Frontend catalog path (`BranchRequestCatalogForm`) has no source field; `handleCatalogSubmit` sends lines without `source_type`.
- Backend `_lines_without_branch_source_override()` strips `source_type` from branch role create/update payloads before validation.

## Item Catalog Rules

Allowed items come from existing `/api/v1/branch-requests/allowed-items`:

- `active = true`
- `branch_requestable = true`
- `visible_in_branch_ui = true`
- Not RAW (`item_type != raw_material`)
- Not `NOT_REQUESTABLE`
- In branch brand scope via `ItemBrand`
- Excludes `DEMO-%` codes

## Allowed Items Validation

PostgreSQL test against `raed_lan_trial` for `branch_onda_1_arkan` / Onda brand confirms API list excludes RAW, inactive, other-brand, and NOT_REQUESTABLE items; all returned rows are active and branch-requestable.

## Submit Flow Validation

- Only lines with `qty_requested > 0` are submitted from the catalog UI.
- Empty lines array and zero quantity rejected by API (422).
- Warehouse item: create → submit → area approve → Auto Split creates `WarehouseLine`.
- Kitchen item: create → submit → area approve → Auto Split creates production/warehouse child as per item master.
- Branch user sending `source_type: KITCHEN` on a warehouse-only item is ignored; resolved line source remains WAREHOUSE.

## Test Results

```
tests/test_branch_request_catalog_ui_lan.py — 8 passed
```

Database: PostgreSQL `raed_lan_trial`  
Simulation: not run

## Screenshot Path

`outputs/branch_request_catalog_lan.png`

Shows read-only branch/brand, catalog table with quantity inputs, search/filter, **إرسال الطلب**, no source or brand dropdowns.

## Final Verdict

**BRANCH_REQUEST_CATALOG_READY**
