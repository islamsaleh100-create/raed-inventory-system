# DEMO_LAUNCH_CHECKLIST

## Official baseline (matrix + Control Center)

For the **current program** (official branches, matrix users, demo branches inactive), use:

- **Staging / handoff:** `STAGING_HANDOFF_REPORT.md` (ordered DB steps, env expectations).
- **Operational map:** `raed_inventory/docs/STEP1_OPERATIONAL_SURFACE_MAP.md` — Control Center **`/supply-chain/control`**, warehouse receive, **`/admin/kitchens`**.
- **Accounts:** Prefer **permission-matrix** users (workbook-driven); password in matrix seed defaults to `Raed@2025` unless changed. Legacy demo usernames below may not exist after **`finalize_demo_branch_transition.py`**.

## Official demo URL

- Use only: `http://127.0.0.1:8010/login`
- Do **not** rely on `3000` for the current demo run

## Demo accounts

- Password for all: `Raed@2025`

- `branch_ronaldos`
- `area_riyadh_all`
- `pizza_manager`
- `warehouse_user`
- `delivery_user`
- `super.admin`
- `admin`

## Fast start

1. Open `http://127.0.0.1:8010/login`
2. Hard refresh once if needed: `Ctrl + F5`
3. Login with the required demo user

## End-to-end demo flow

1. Login as `branch_ronaldos`
2. Open `/supply-chain/branch-requests`
3. Create and submit a request
4. Login as `area_riyadh_all`
5. Open `/supply-chain/approvals`
6. Approve the request
7. Confirm auto-split
8. Login as `pizza_manager`
9. Open `/supply-chain/kitchen`
10. Start production
11. Mark ready
12. Send to warehouse
13. Login as `warehouse_user`
14. Open `/supply-chain/warehouse`
15. Issue warehouse lines
16. Create delivery order
17. Login as `delivery_user`
18. Open `/supply-chain/delivery`
19. Move order to `OUT_FOR_DELIVERY`
20. Complete `DELIVERED`

## Expected result

- Branch request reaches `DELIVERED`
- Kitchen flow completes
- Warehouse flow completes
- Delivery flow completes

## Notes

- Backend is running on PostgreSQL for this demo path
- The verified report is:
  - `C:\raed_inventory_system\POSTGRES_DEMO_READY_REPORT.md`
