# Sprint 2 Follow-ups

## 1. Material Issue Idempotency
- Add `X-Idempotency-Key` support to kitchen material issue endpoints
- Goal: prevent parallel or repeated issue requests from double-decrementing stock

## 2. Partial Delivery Policy Tightening
- Require `shortage_reason` whenever `qty_received < qty_dispatched`
- Goal: make partial delivery records operationally clearer

## 3. Clarify Internal Warehouse Status Naming
- Review whether kitchen material issue should continue using `WarehouseLineStatus.DELIVERED`
- If retained, document it clearly in UI/help text

## 4. Branch Employee Transfer History
- Add lightweight transfer history later if needed
- Suggested future fields:
  - from_branch_id
  - to_branch_id
  - transferred_at
  - transferred_by
- Not required for current sprint
