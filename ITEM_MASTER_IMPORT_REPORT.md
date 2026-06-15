# Phase 3 — Item Master Import & Validation Report

**Date:** 2026-06-14  
**Branch:** `phase3/item-master-validation-2026-06-14` (local only)  
**Alembic head:** `c1d2e3f4a5b6` (no new migration)  
**Input workbook:** `C:\raed_inventory_system\classified_supply_items.xlsx` (not committed)

---

## Summary

Phase 3 validated the official item master model, hardened import validation, branch visibility filters, split-service error handling (C-04), and automated PostgreSQL tests.

| Area | Result |
|------|--------|
| Item model fields | Present (see mappings below) |
| Alembic migration | **None required** |
| Import from classified workbook | 136 imported / 138 rejected / 274 rows read |
| C-04 split silent skip | **Fixed** → `split.unresolvable_source_type` |
| Branch RAW / NOT_REQUESTABLE visibility | **Hardened** |
| Automated tests | **15/15 passed** (PostgreSQL) |

---

## Existing Item Model

Table: `items` (`app/models/__init__.py`)

| Spec field | DB field | Notes |
|------------|----------|-------|
| name | `item_name_ar`, `item_name_en` | Both set from workbook Item Name |
| brand | `item_brands` → `brand_id` | M2M via `ItemBrand`; no direct `brand_id` column |
| category | `category_id` | FK → `item_categories` (from POS Category) |
| item_type | `item_type` | Enum `ItemType` — see mapping below |
| source_type | `source_type` | `SupplySourceType` |
| default_source | `default_source` | `SupplyDefaultSource` |
| kitchen_section_id | `kitchen_section_id` | FK → global `kitchen_sections` |
| can_branch_request | `branch_requestable` | Boolean |
| active | `active` | Boolean |
| (visibility) | `visible_in_branch_ui` | Used for branch UI filtering |

### Item type mapping (workbook → DB)

| Workbook | DB `ItemType` |
|----------|---------------|
| `RAW` | `raw_material` |
| `FINISHED` | `finished_good` |
| `BOTH` | `finished_good` |

Legacy DB values also include `packaging`, `consumable` (unchanged).

### Source types

`WAREHOUSE`, `KITCHEN`, `BOTH`, `NOT_REQUESTABLE` — all present in `SupplySourceType`.

---

## Migration Changes

**None.** All required columns exist under Alembic head `c1d2e3f4a5b6`. No runtime schema patching added for Phase 3.

---

## Import Script

**Entry point:** `raed_inventory/backend/import_classified_supply_items.py`  
**Service:** `raed_inventory/backend/app/services/supply_item_master_import_service.py`

- Reads **`C:\raed_inventory_system\classified_supply_items.xlsx`** by default (override with CLI path).
- Sheet: `Classified_Items`
- Upserts by deterministic `item_code` (no duplicate rows for same brand + name).
- Rejected rows written to **`outputs/item_master_rejected_rows.csv`** (not committed).
- Invalid rows are **not** silently corrected.

**Run:**

```text
cd raed_inventory/backend
python import_classified_supply_items.py
```

---

## Rows Read

| Metric | Count |
|--------|------:|
| Data rows in workbook | 274 |
| Rows passing validation | 136 |
| Rows rejected | 138 |

---

## Imported / Updated

| Metric | Count |
|--------|------:|
| Imported (created + updated) | 136 |
| Created (first run) | 0 |
| Updated (re-import) | 136 |
| Hidden (unlisted official-brand items) | 0 |

Second run updated existing `SUP-*` item codes in place.

---

## Rejected

| Metric | Count |
|--------|------:|
| Total rejected | 138 |

### Rejection reasons (top)

| Count | Reason |
|------:|--------|
| 95 | Invalid item_type `POS_ONLY` |
| 43 | RAW items cannot be branch-requestable |

POS-only / promotional rows are correctly rejected per NOT_REQUESTABLE policy. RAW rows marked requestable in the workbook are rejected (not auto-fixed).

---

## Brand Mapping

Workbook brand labels map to DB `Brand.name`:

| Workbook label | DB brand(s) |
|----------------|-------------|
| `Onda` | Onda |
| `Ronaldos` | Ronaldos |
| `Shawarma` | Shawarma |
| `Griddle` | Griddle |
| `General` | Onda, Ronaldos, Shawarma, Griddle |
| `Shared` | Ronaldos, Shawarma, Griddle |

Official branch codes for pizza restaurants use **`Ronaldos`** brand on branches (e.g. `BR-DM-RN-*`, `BR-RY-RN-*`).

---

## Pizza vs Ronaldos Finding

**Verified in PostgreSQL — do not assume a separate Pizza brand.**

| Brand record | id | Used by pizza branches? |
|--------------|---:|-------------------------|
| **Ronaldos** | 8 | **Yes** — all `BR-*-RN-*` branch users |
| **Ronaldos Pizza** | 9 | Legacy/extra record; **not** used by official branch seeds |
| **Pizza** (name) | — | **Does not exist** |

Visibility and import rules use **`brand_id` from `ItemBrand`**, not display names. Branch users named `branch_pizza_*` authenticate against branches whose **`brand_id` resolves to Ronaldos (id=8)**.

Spec wording “Pizza” = operational label; system brand entity is **`Ronaldos`**.

---

## Kitchen Mapping

**Model:** Global `kitchen_sections` table (not per-kitchen section rows). Kitchen sites (`kitchens` table) link to sections via M2M; item master references **`kitchen_section_id`** only.

| Section | Valid for import |
|---------|------------------|
| Meat & Chicken | Yes |
| Bakery & Sweets | Yes |
| Pizza | Yes |

Import **rejects** unknown section names (no auto-create during Phase 3 import).

KITCHEN / BOTH+KITCHEN default items must have a valid section. WAREHOUSE items must have `kitchen_section_id = NULL`.

---

## Visibility Tests

HTTP + DB tests confirm branch `/branch-requests/allowed-items` and `/master/items?requestable_only=true` exclude:

- `item_type = raw_material` (RAW)
- `source_type = NOT_REQUESTABLE`
- inactive / non-requestable items
- other brands (via `ItemBrand` + `brand_id`)

Verified for **Onda**, **Ronaldos**, and **Shawarma** branch contexts (by actual `brand_id`).

Area managers inherit the same item rules when listing through scoped endpoints; no RAW/NOT_REQUESTABLE bypass.

---

## Split Tests

| Case | Result |
|------|--------|
| KITCHEN → Production Order | Pass |
| WAREHOUSE → Warehouse Line | Pass |
| BOTH (KITCHEN default) → Production Order | Pass |
| Unresolvable `resolved_source_type` | Raises `AppError` `split.unresolvable_source_type` with `item_id`, `source_type`, `request_id` |

**C-04 fix:** `branch_request_split_service.py` no longer silently skips lines with unknown resolution.

---

## Remaining Risks

1. **138 workbook rows rejected** — mostly `POS_ONLY` and RAW+requestable; business may need workbook cleanup or explicit NOT_REQUESTABLE classification for POS rows.
2. **`Ronaldos Pizza` brand (id=9)** — duplicate legacy brand; official matrix uses `Ronaldos` (id=8) only.
3. **Item type enum drift** — spec uses RAW/FINISHED/BOTH; DB retains legacy `packaging`/`consumable` values on older rows.
4. **Hidden-items pass** — importer can hide unlisted official-brand items; second run reported `hidden_items=0` because prior import already aligned catalog.
5. **PostgreSQL required for Phase 3 tests** — run with `DATABASE_URL` from `.env` (SQLite conftest default is bypassed via env for this suite).

---

## Demo Readiness

**Ready for local item-master demo** after:

1. Place workbook at `C:\raed_inventory_system\classified_supply_items.xlsx`
2. Run `python import_classified_supply_items.py`
3. Review `outputs/item_master_rejected_rows.csv` for any business-needed rows

Branch request dropdowns will show FINISHED/requestable, brand-scoped items only.

---

## LAN Trial Readiness

**Conditionally ready** — import script and visibility rules are stable. For LAN trial:

- Run import against trial PostgreSQL
- Confirm Ronaldos pizza branches use `brand_id=8`
- Review rejected POS_ONLY rows with business owners

---

## Production Readiness

**Not fully production-ready** until:

- Workbook rejection backlog reviewed (POS_ONLY / RAW rows)
- Legacy `Ronaldos Pizza` brand clarified or merged
- Full import executed on staging DB with sign-off on rejected-row CSV

Core validation, visibility enforcement, and split error handling are in place for production cutover after data sign-off.

---

## Test Results

```text
pytest tests/test_phase3_item_master.py tests/test_supply_item_master_import.py
15 passed (PostgreSQL, DATABASE_URL from .env)
```

---

## Phase Boundaries (not started)

Workflow E2E, dashboards, kitchen tracking, warehouse/delivery recovery, analytics, AI, and forecasting were **not** touched.
