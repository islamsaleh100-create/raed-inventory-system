# Raed Inventory System - Implementation Blueprint

## Goal
Build a complete Supply Chain operating flow covering:
- Branches
- Central kitchen
- Warehouse
- Delivery
- Dashboards

## Core users

### Admin
- `super.admin`
- `admin`

### Area Managers
- `area_dammam_onda`
- `area_dammam_restaurants`
- `area_riyadh_all`

### Branch Users
- `branch_onda`
- `branch_ronaldos`
- `branch_shawarma`
- `branch_griddle`

### Kitchen
- `kitchen_manager`
- `meat_manager`
- `bakery_sweets_manager`
- `pizza_manager`

### Warehouse
- `warehouse_user`

### Delivery
- `delivery_user`

## Roles
- `SUPER_ADMIN`
- `ADMIN`
- `AREA_MANAGER`
- `BRANCH_USER`
- `KITCHEN_SECTION_MANAGER`
- `WAREHOUSE_MANAGER`
- `WAREHOUSE_USER`
- `DELIVERY_USER`

## Item master
Each item should keep:
- `name`
- `brand`
- `category`
- `source_type`
- `default_source`
- `kitchen_section_id`
- `can_branch_request`

## Workflow
`Branch -> Request -> Area Approval -> Auto Split -> Kitchen Production -> Warehouse Fulfillment -> Delivery`

### Auto split
- `KITCHEN -> Production Orders`
- `WAREHOUSE -> Warehouse Lines`
- `BOTH -> default_source`

## Rules
- Kitchen is independent from branch
- Kitchen output must pass through warehouse before branch delivery
- `NOT_REQUESTABLE` must never appear in request UIs
- Auto split is mandatory after approval
- Stock deduction happens on issue, not on request creation

## Execution order
1. Users
2. Master data
3. Permissions
4. Workflow
5. Testing
6. Dashboards

## Current implementation note
This blueprint is the canonical target. The current local demo runtime does not yet contain every branch, kitchen, and warehouse listed in the larger business plan, so implementation proceeds in phases while preserving the working demo environment.
