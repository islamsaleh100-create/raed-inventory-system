# Permission Matrix Implementation Report

**Date:** 2026-04-26  
**Source file:** `C:\Users\islam\Downloads\raed_user_matrix_permissions.xlsx`  
**Runtime:** PostgreSQL local demo/runtime

## 1. Overall result

The permission matrix workbook was successfully converted into live seeded users and scopes inside the current PostgreSQL environment.

What is now true:
- Official branches are active and visible in operational selectors.
- Old demo branches are inactive and hidden from normal operational selectors.
- Matrix users were created/updated from the workbook.
- Branch users were linked to official branches.
- Area managers were linked through `AreaManagerAssignment`.
- Kitchen section managers were linked through `KitchenSectionAssignment`.
- Warehouse users/managers were activated on the current warehouse runtime.
- Delivery users were activated as operational accounts.

## 2. Workbook import result

From the workbook:
- `matrix_users_total = 42`
- `users_created = 37`
- `users_updated = 5`
- `warnings_count = 0`

Current total users in database after merge with existing demo/canonical accounts:
- `total_users = 63`
- `active_users = 61`
- `inactive_users = 2`

The two inactive users match the workbook's future roles:
- `kitchen_dammam_manager_future`
- `kitchen_riyadh_manager_future`

## 3. Files used / added

Seed and transition files now involved in the final environment:
- [seed_official_branches.py](C:/raed_inventory_system/raed_inventory/backend/seed_official_branches.py)
- [finalize_demo_branch_transition.py](C:/raed_inventory_system/raed_inventory/backend/finalize_demo_branch_transition.py)
- [activate_demo_readiness.py](C:/raed_inventory_system/raed_inventory/backend/activate_demo_readiness.py)
- [seed_users_from_permission_matrix.py](C:/raed_inventory_system/raed_inventory/backend/seed_users_from_permission_matrix.py)

### Staging / CI environment variables

| Variable | Purpose |
|----------|---------|
| `PERMISSION_MATRIX_WORKBOOK` | Absolute path to the workbook on the runner. **Required** when the built-in default path does not exist; the seed script **exits with code 1** if the file is missing. |
| `PERMISSION_MATRIX_PASSWORD` | Optional; defaults to `Raed@2025`. Must match `VERIFY_API_PASSWORD` when running `scripts/verify_matrix_roles_api.py` after seed. |

## 4. Branch transition status

Official branch transition is complete for operational use.

Current state:
- `active official branches = 23`
- `inactive demo branches = 8`

Inactive demo branches were kept in the database with:
- `active = False`
- `is_deleted = False`

This preserves history and foreign-key safety while hiding them from normal operational lists.

## 5. User scope implementation

### Super Admin
- `super.admin`
- Full runtime account exists and remains active.

### Admin
- `admin`
- Active and present.

### Area Managers
Implemented from workbook:
- `area_dammam_onda`
- `area_dammam_restaurants`
- `area_riyadh_all`

Verified scope behavior in data:
- `area_dammam_restaurants` has `3` active brand assignments
- `area_riyadh_all` has `4` active brand assignments

### Branch Users
Branch users from workbook were seeded and linked to official branches.

Examples verified:
- `branch_onda_1_arkan` -> `BR-DM-ON-ARKAN`
- `branch_onda_13_al_malqa` -> `BR-RY-ON-MALQA`
- `branch_pizza_4_riyadh_takhasosy` -> `BR-RY-RN-TAKHS`
- `branch_shawarma_olaya` -> `BR-RY-SH-OLAYA`

Implementation note:
- Branch users were seeded with both:
  - `branch_user`
  - `branch_manager`

Reason:
- Current operational UX and branch employee management depend on branch-manager level capability in the existing app behavior.

### Kitchen Section Managers
Seeded and linked through `KitchenSectionAssignment`.

Verified examples:
- `kitchen_dammam_meat_and_chicken_mgr` -> 1 active section assignment
- `kitchen_riyadh_pizza_mgr` -> 1 active section assignment

### Warehouse Users / Managers
Seeded and activated:
- `warehouse_dammam_manager`
- `warehouse_dammam_user`
- `warehouse_riyadh_manager`
- `warehouse_riyadh_user`

Current system limitation:
- The current PostgreSQL runtime has one active warehouse entity.
- Therefore city-specific warehouse users currently point to the same warehouse runtime object.

### Delivery Users
Seeded and activated:
- `delivery_dammam`
- `delivery_riyadh`

Current system limitation:
- Delivery scope exists as active accounts, but city-specific assignment in the current runtime is lighter than the workbook model and should still be treated as an operational policy layer rather than a fully separated delivery-city model.

## 6. Griddle handling

`branch_griddle` was normalized into the official runtime by attaching it to:
- `BR-RY-SH-OLAYA`
- `Shawarma Olaya`

That branch now carries both brands:
- `Shawarma`
- `Griddle`

Verified counts on that branch:
- `Griddle_requestable_items = 41`
- `Shawarma_requestable_items = 42`

This removes the previous inactive-demo-branch blocker for Griddle.

## 7. Verification performed

Verified directly in PostgreSQL/runtime:
- Official branches seeded
- Demo branches deactivated
- `branch_griddle` remapped to active official branch
- Operational branch selector shows only active official branches (`23`)
- Matrix accounts exist in the database
- Sample branch users are linked to official branches
- Sample area managers have active assignments
- Sample kitchen section managers have active section assignments

## 8. What is fully implemented

Fully implemented now:
- Branch officialization for operational use
- Matrix-based user seeding
- Branch scope seeding
- Area manager brand/city assignment seeding
- Kitchen section assignment seeding
- Warehouse and delivery account activation

## 9. What is partially implemented

These are not missing users. They are model/runtime limitations still present:

### A. Warehouse by city
- Improved.
- Runtime now has city warehouses:
  - `WH-RY-1`
  - `WH-DM-1`
- Active official branches are mapped by city to those warehouses.
- Warehouse users are mapped by city to those warehouses.
- A legacy `DEMO-WH-1` row still exists for compatibility/history, but operational branch mappings now use the city warehouses.

### B. Kitchen entity by city
- Workbook distinguishes:
  - Kitchen Dammam
  - Kitchen Riyadh
- Current runtime is stronger on:
  - section-based access (`Meat & Chicken`, `Bakery & Sweets`, `Pizza`)
- and weaker on:
  - fully separated kitchen entities per city

### C. Delivery city enforcement
- Improved, but still not perfect.
- Delivery users now carry `warehouse_id` by city in runtime:
  - `delivery_dammam -> WH-DM-1`
  - `delivery_riyadh -> WH-RY-1`
- Delivery backend was tightened to honor `warehouse_id` when present.
- This is a practical warehouse-scoped city proxy, not a full territory/assignment engine.

### D. Live smoke verification after backend restart
- Backend restarted successfully on `127.0.0.1:8010`
- `health` returned `200`
- Verified live:
  - `delivery_dammam` sees `warehouse_id = 3`
  - `delivery_riyadh` sees `warehouse_id = 2`
  - `warehouse_dammam_user` sees `warehouse_id = 3`
  - `warehouse_riyadh_user` sees `warehouse_id = 2`
- Post-restart delivery lists for those scoped users returned city/warehouse-filtered results and no longer leaked the old legacy delivery order from the inactive demo branch.

## 10. Final status

The permission matrix has now been operationalized to a useful degree inside the live PostgreSQL demo/runtime.

Practical conclusion:
- Users from the workbook are in the system.
- Branch-linked users are on official branches.
- Main scopes are seeded.
- The remaining gaps are architectural/runtime refinement items, not missing seed data.

## 11. Recommended next step

If we continue from here, the correct next step is:

1. Keep this user/branch seed as the new baseline
2. Stop adding more demo-style duplicate accounts
3. If needed, refine:
   - warehouse-by-city modeling
   - kitchen-by-city modeling
   - delivery-city assignment policy

At this point, the user matrix is no longer just a document. It is materially reflected in the running system.
