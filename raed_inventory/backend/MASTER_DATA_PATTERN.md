# Master Data Pattern

This document records the current standard used for `master` module work in `Epic 2`.

## Scope Covered
- `items`
- `categories`
- `units`
- `branches`
- `warehouses`

## Rules
1. Routers stay thin and delegate to `master_service`.
2. Create and update endpoints return typed response models.
3. Business validation and lookup failures use `AppError`.
4. Reference validation happens before writes.
5. Soft-deleted records are excluded from normal reads.

## Item Master Rules
- `item_type` and `storage_type` are explicit fields.
- `purchase_unit_id` and `supply_unit_id` must be provided together.
- `conversion_ratio` must be greater than zero.
- If purchase/supply units are not used, `conversion_ratio` must remain `1`.
- `category_id`, `unit_id`, `purchase_unit_id`, and `supply_unit_id` must point to existing records.

## Error Model
Current error codes include:
- `master.item_code_exists`
- `master.item_not_found`
- `master.category_not_found`
- `master.unit_not_found`
- `master.category_code_exists`
- `master.unit_code_exists`
- `master.warehouse_code_exists`
- `master.warehouse_not_found`
- `master.branch_code_exists`
- `master.branch_not_found`

## Testing Expectations
- success path for create/update/get/list
- duplicate-key path
- not-found path
- reference-validation path
- schema validation path for item unit/conversion rules

## Next Use
Any new master-data slice should reuse this pattern before adding deeper business features.
