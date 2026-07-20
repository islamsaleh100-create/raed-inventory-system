# Google Sheets Data Model V1

## Purpose and Boundaries

This document defines the approved Phase 1 Google Sheets data layer for master data and access scopes. It is a design and normalized-source package only: no online Google Sheet, Apps Script, authentication, deployment, or transaction data is created.

Canonical brands are `ONDA`, `RONALDOS`, and `SHAWARMA`. `PIZZA` is not a canonical brand. Area Manager access is one row per user + city + brand.

## ID Standards

- IDs are stable text values using uppercase English characters, digits, and underscores only.
- IDs contain no spaces and do not depend on spreadsheet row position.
- Brand IDs: `BRAND_<BRAND_CODE>`.
- Branch IDs: `BR_<CITY_CODE>_<BRAND_CODE>_<NN>`.
- User IDs: `USR_<ROLE_CODE>_<IDENTIFIER>`.
- Scope IDs: immutable `SCOPE_<NNN>` values.
- Pending shift configuration IDs: `SCFG_<BRANCH_ID>_PENDING`; approved rows use `SCFG_<BRANCH_ID>_<SHIFT_NO>`.

## Phase 1 Fully Defined Tabs

### 1. Brands

Primary key: `brand_id`. Alternate unique key: `brand_code`.

| Column | Required | Validation |
|---|---|---|
| brand_id | Yes | Unique stable ID |
| brand_code | Yes | One of ONDA, RONALDOS, SHAWARMA; unique |
| brand_name_ar | Yes | Display name |
| brand_name_en | Yes | Confirmed English display name |
| is_active | Yes | TRUE/FALSE |
| notes | No | Free text |

### 2. Branches

Primary key: `branch_id`. Foreign key: `brand_code` → `Brands.brand_code`.

| Column | Required | Validation |
|---|---|---|
| branch_id | Yes | Unique stable ID |
| branch_name_ar | No | Blank when source does not confirm Arabic name |
| branch_name_en | No | Source-faithful name; never invented |
| brand_code | Yes | Existing active brand |
| city_code | Yes | Normalized uppercase city code |
| city_name_ar | Yes | Confirmed Arabic city label |
| region_code | Yes | Normalized uppercase region code |
| is_active | Yes | TRUE/FALSE |
| shifts_per_day | No | Positive integer only when source-confirmed |
| source_name | Yes | Source workbook name |
| source_sheet | Yes | Source worksheet name |
| source_row | Yes | Positive source row number |
| source_brand_value | Yes | Original source brand token |
| notes | No | Normalization/review notes |

Uniqueness rule: one row per active branch; reject duplicate `branch_id` or duplicate normalized branch identity.

### 3. Users

Primary key: `user_id`. Alternate unique key: nonblank `username`.

| Column | Required | Validation |
|---|---|---|
| user_id | Yes | Unique stable ID |
| username | No in template | Unique when populated |
| display_name | No for placeholders | Confirmed name only |
| role_code | Yes | BRANCH_USER, BRAND_MANAGER, OPERATIONS_MANAGER, or ADMIN |
| branch_id | Conditional | Required only for BRANCH_USER; blank otherwise |
| is_active | Yes | TRUE/FALSE |
| login_pin | No in template | Exactly six numeric digits when provisioned |
| must_change_password | Yes | TRUE/FALSE |
| created_at | No in template | ISO timestamp when provisioned |
| updated_at | No in template | ISO timestamp when changed |
| notes | No | Provisioning status |

Phase 1 creates confirmed Brand Manager seed rows plus unassigned Operations Manager and Admin placeholders. It creates no branch users.

### 4. User_Scopes

Primary key: `scope_id`. Foreign keys: `user_id` → `Users.user_id`; `brand_code` → `Brands.brand_code`.

| Column | Required | Validation |
|---|---|---|
| scope_id | Yes | Unique immutable ID |
| user_id | Yes | Existing BRAND_MANAGER user |
| manager_source_name | Yes | Exact source spelling |
| display_name | Yes | Normalized only when unambiguous |
| city_code | Yes | One city per row |
| brand_code | Yes | One canonical brand per row |
| is_active | Yes | TRUE/FALSE |
| effective_from | No | ISO date |
| effective_to | No | ISO date; blank or not before effective_from |
| source_name | Yes | Source workbook name |
| source_sheet | Yes | Source worksheet name |
| source_row | Yes | Representative confirming row |
| notes | No | Audit note |

Unique business key: `user_id + city_code + brand_code`. Comma-separated brands are forbidden. Branch Users do not inherit these scopes.

### 5. Shift_Config

Primary key: `shift_config_id`. Foreign key: `branch_id` → `Branches.branch_id`.

| Column | Required | Validation |
|---|---|---|
| shift_config_id | Yes | Unique stable ID |
| branch_id | Yes | Existing active branch |
| shift_number | Conditional | Positive integer after business approval |
| shift_name_ar | Conditional | Required for approved shift |
| is_active | Yes | TRUE only for approved configuration |
| start_time | Conditional | Time; never invented |
| end_time | Conditional | Time; never invented |
| submission_deadline | Conditional | Time; never invented |
| source_confirmed | Yes | TRUE/FALSE |
| notes | No | Review requirement |

Until shift details are approved, one inactive `PENDING` row per branch keeps all shift fields blank and sets `source_confirmed = FALSE`.

## Proposed Transaction and Supporting Tabs

These tabs are column and relationship proposals only. Phase 1 does not populate them.

### 6. Brand_Items

Columns: `brand_item_id`, `brand_code`, `item_name`, `unit`, `is_shift_count_item`, `sort_order`, `is_active`, `source_reference`, `notes`.

- Primary key: `brand_item_id`.
- Foreign key: `brand_code` → `Brands.brand_code`.
- Inventory loads the current brand only and includes only `is_shift_count_item = TRUE`.
- ONDA, RONALDOS, and SHAWARMA item lists remain isolated.

### 7. Shifts

Columns: `shift_id`, `branch_id`, `shift_date`, `shift_number`, `status`, `opened_by`, `opened_at`, `submitted_by`, `submitted_at`, `reopened_by`, `reopened_at`, `locked_at`, `notes`.

- Primary key: `shift_id`.
- Foreign keys: `branch_id` → Branches; user fields → Users.
- Statuses: `DRAFT`, `SUBMITTED`, `REOPENED`, `LOCKED`.
- Valid transitions: DRAFT → SUBMITTED → LOCKED; SUBMITTED or LOCKED → REOPENED only through authorized review with an audited reason; REOPENED → SUBMITTED → LOCKED.
- A locked shift is immutable to Branch Users.

### 8. Sales

Columns, in canonical order: `sales_id`, `shift_id`, `status`, `total_sale`, `bill_count`, `mada_sales`, `cash_sales`, `app_sales`, `refund_bill`, `exchange_amount`, `expiry_amount`, `cash_expense`, `cash_float_carried_forward`, `cash_deposited`, `expense_type`, `expense_details`, `shift_notes`, `created_by`, `updated_by`, `submitted_by`, `created_at`, `updated_at`, `submitted_at`.

- Primary key: `sales_id`.
- Unique foreign key: `shift_id` → `Shifts.shift_id`; one Sales row is allowed per Shift.
- Actor foreign keys: `created_by`, `updated_by`, and nullable `submitted_by` → `Users.user_id`.
- Allowed statuses: `DRAFT`, `SUBMITTED`, `LOCKED`.
- Required for every persisted row: `sales_id`, `shift_id`, `status`, `created_by`, `updated_by`, `created_at`, and `updated_at`.
- `submitted_by` and `submitted_at` remain blank until submission and become required when status is `SUBMITTED` or `LOCKED`.
- Draft business fields may remain blank; blank is distinct from an explicit zero.
- Financial fields are `total_sale`, `mada_sales`, `cash_sales`, `app_sales`, `refund_bill`, `exchange_amount`, `expiry_amount`, `cash_expense`, `cash_float_carried_forward`, and `cash_deposited`; populated values are nonnegative and normalized to two decimals by the application layer.
- `exchange_amount` records the shift exchange amount; `expiry_amount` records the shift expiry amount. These are the canonical field names.
- On submit: `mada_sales + cash_sales + app_sales = total_sale`.
- `cash_float_carried_forward` is the amount intentionally retained in the branch cash drawer for the next selling period. It may be blank in a draft, but is required on submission; zero and decimal values are valid.
- On submit: `cash_float_carried_forward <= cash_sales - cash_expense`.
- On submit: expected cash deposited is `cash_sales - cash_expense - cash_float_carried_forward`.
- On submit: `cash_deposited = cash_sales - cash_expense - cash_float_carried_forward`.
- On submit: `bill_count >= 1` and all required business validation must pass.
- Expense type and details are required when `cash_expense > 0`.
- Submitted and locked Sales rows are immutable to Branch Users.

### 9. Inventory

Columns, in canonical order: `inventory_id`, `shift_id`, `status`, `general_notes`, `created_by`, `updated_by`,
`submitted_by`, `created_at`, `updated_at`, `submitted_at`.

- Primary key: `inventory_id`; unique foreign key: `shift_id` → Shifts.

- Exactly one Inventory header row is allowed per Shift.
- Actor fields are `created_by`, `updated_by`, and nullable `submitted_by`; all reference `Users.user_id`.
- Allowed statuses are `DRAFT`, `SUBMITTED`, and `LOCKED`.
- `submitted_by` and `submitted_at` remain blank before submission and become required upon submission.
- Submitted and locked Inventory headers and their lines are immutable to Branch Users.

### 10. Inventory_Lines

Columns: `inventory_line_id`, `inventory_id`, `brand_item_id`, `opening_balance`, `received_qty`, `returned_qty`, `damaged_qty`, `closing_balance`, `consumption_qty`, `item_notes`, `row_status`, `created_at`, `updated_at`.

- Primary key: `inventory_line_id`.
- Foreign keys: `inventory_id` → Inventory; `brand_item_id` → Brand_Items.
- `brand_item_id` is retained on every line and must reference an approved shift-count item for the Inventory brand.
- Allowed row statuses: `INCOMPLETE`, `VALID`, `INVALID`, `LOCKED`.
- `row_status` is server-controlled: draft lines may be `INCOMPLETE`, `VALID`, or `INVALID`; submitted lines must be `VALID`; locked lines use `LOCKED`.
- Opening balance is derived by the server from the applicable prior submitted/locked shift and is read-only.
- Received, returned, damaged, and closing are manual values.
- Blank is different from zero; zero is a valid reviewed value.
- Consumption is calculated by the server per completed row only: `opening_balance + received_qty - returned_qty - damaged_qty - closing_balance`.
- Negative inputs and negative consumption are invalid.
- Submitted or locked Inventory lines use `row_status = LOCKED` and are immutable to Branch Users.
- Mixed-unit consumption totals are forbidden.

### 11. Audit_Log

Columns: `audit_id`, `event_timestamp`, `actor_user_id`, `action`, `entity_type`, `entity_id`, `before_json`, `after_json`, `reason`, `branch_id`, `notes`.

- Primary key: `audit_id`.
- Foreign keys: `actor_user_id` → Users; optional `branch_id` → Branches.
- Reopen actions require a reason and must record actor, timestamp, target entity, and before/after state.

## Cross-Tab Integrity Rules

- Every Branch brand exists in Brands.
- Every User Scope user exists in Users and its brand exists in Brands.
- Every Shift Config branch exists in Branches.
- No canonical PIZZA row is allowed.
- One scope row represents exactly one City + Brand pair.
- No plain-text password is stored.
- Transaction rows cannot reference missing master records.

## Implementation Sequence for the Next Phase

1. Create protected master tabs and validations.
2. Import these normalized UTF-8 CSV values.
3. Complete business review of branch Arabic names, usernames, and shift configurations.
4. Add transaction tabs without seed transaction data.
5. Implement Apps Script only under a separate approved Task Gate.
