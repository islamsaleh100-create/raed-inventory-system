# Ledger Pattern

This document defines the current ledger pattern for the backend before the
full Inventory Ledger Engine epic expands the schema.

## Scope

The current scope covers:

- writing stock-impacting transactions through `stock_ledger_service`
- reading item transaction history through `stock card`
- reusing the existing `stock_transactions` table without schema expansion

## Write Rule

Any workflow that changes stock and also needs a transaction trail should call:

- `app.services.stock_ledger_service.post_transaction(...)`

Current writers using this pattern:

- inventory approval adjustments
- order dispatch
- order receive

Seed scripts may still instantiate `StockTransaction` directly for demo data.
That is acceptable for now and should be revisited only when seed refactoring
is worth the time.

## Read Rule

Item ledger history is exposed through:

- `GET /api/master/items/{item_id}/stock-card`

The response returns:

- item identity fields
- ordered transaction rows

It does not attempt balance snapshots yet. That belongs to a later ledger
slice when schema evolution is introduced deliberately.

## Error Model

The stock card read flow uses the standard error envelope:

- `error_code`
- `message`
- `detail`

Current ledger-specific error code:

- `ledger.item_not_found`

## Next Safe Expansion

When Epic 3 continues, the next safe slices are:

1. additional stock-card filters and pagination
2. stronger service coverage for any new stock mutation
3. schema evolution for before/after balances only when migration work starts
