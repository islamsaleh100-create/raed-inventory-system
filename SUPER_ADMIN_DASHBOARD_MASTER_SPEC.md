# Super Admin Dashboard Master Spec

## Purpose

Build a true command-center dashboard for `super.admin` that combines:

- executive visibility
- operational monitoring
- performance analytics
- data health
- admin audit

The dashboard should answer two questions at all times:

1. What is happening now across the supply chain?
2. Where does the super admin need to intervene?

---

## Scope

This spec covers the `super.admin` dashboard only.

It is intentionally broader than the current `Control Center`, and should become the top-level management surface for:

- Branch
- Area Approval
- Kitchen
- Warehouse
- Delivery
- Inventory / Items
- Users / Permissions
- Data Health / Audit

---

## Users

Primary:

- `super.admin`

Secondary later if explicitly approved:

- `admin` with a reduced version
- `operations_manager` with a reduced operational version

This spec is written for the full `super.admin` view first.

---

## Success Criteria

The dashboard is successful when a super admin can:

- understand current system status within 10-15 seconds
- identify delayed or blocked operations immediately
- compare city / brand / branch performance quickly
- drill down into problematic queues without leaving context blindly
- detect data-quality or permission anomalies
- review recent sensitive actions and operational exceptions

---

## Global Filters

These filters must exist at the top of the dashboard and apply consistently where relevant:

- Date range
- City
- Brand
- Branch
- Kitchen
- Warehouse
- Status

Behavior rules:

- default date range: `Today`
- filters should support `All` as the default except date
- filters should update KPI cards, charts, and tables consistently
- drill-down links should preserve active filters when possible

---

## Information Architecture

The dashboard should be structured into 4 top-level tabs or sections:

1. Overview
2. Operations
3. Analytics
4. Governance

Recommended route:

- `/dashboard/super-admin`

If route strategy needs to preserve current conventions:

- `/dashboard/super-admin`
- or `/admin/dashboard/super-admin`

---

## Section 1: Overview

### 1.1 Hero Summary

Top KPI cards:

- Total Requests Today
- Pending Approval
- In Production
- Warehouse Pending
- Out for Delivery
- Delivered
- Delayed
- Partial
- Active Branches
- Active Users

Each card should show:

- current value
- delta vs yesterday
- optional delta vs last 7 days
- click action to drill down

### 1.2 Critical Alerts

Alert types:

- delayed orders
- stuck orders
- partial chains
- repeated delay reasons
- city/brand pressure spikes
- inactive entities still referenced
- users with broken or missing scope

Each alert row should show:

- severity
- concise title
- affected entity
- count
- direct action link

Severity levels:

- Critical
- Warning
- Info

### 1.3 End-to-End Pipeline

Pipeline blocks:

- Branch Requests
- Pending Approval
- Production
- Warehouse
- Delivery
- Delivered

For each block:

- current count
- delayed count
- partial count if relevant
- click to open detail queue

Preferred visuals:

- horizontal pipeline
- or stacked operational columns

---

## Section 2: Operations

### 2.1 Branch Operations

Widgets:

- Top requesting branches
- Branches with delayed requests
- Branches with high rejection counts
- Branches with frequent partial deliveries
- Requests by branch

Views:

- top 10 table
- status distribution by branch
- city / brand split

### 2.2 Area Manager Operations

Widgets:

- requests processed by area manager
- average approval time
- modify-before-approve count
- reject count
- approval backlog by city/brand

Views:

- leaderboard
- average time chart
- backlog table

### 2.3 Kitchen Operations

Widgets:

- production orders by section
- production orders by city
- delayed production orders
- average start time
- average ready time
- partial ready rate
- top manufactured items
- kitchen pressure by section

Views:

- section heatmap
- city split chart
- delayed production table
- top items table

### 2.4 Warehouse Operations

Widgets:

- warehouse lines by status
- receive count
- full issue count
- partial issue count
- delay reasons
- average issue time
- top issued items
- warehouse pressure by city

Views:

- warehouse summary cards
- delay reasons chart
- issue backlog table
- pressure comparison chart

### 2.5 Delivery Operations

Widgets:

- delivery orders by status
- out for delivery count
- delivered count
- delayed deliveries
- average delivery time
- city performance
- delivery user performance
- top destination branches

Views:

- city comparison chart
- user leaderboard
- delayed delivery table

---

## Section 3: Analytics

### 3.1 Supply Chain Performance

Widgets:

- average approval time
- average production time
- average warehouse processing time
- average delivery time
- complete vs partial fulfillment rate
- delay rate trend

Views:

- trend lines by day/week
- city comparison
- brand comparison

### 3.2 Branch Consumption Analytics

Widgets:

- branch consumption by period
- branch consumption by brand
- branch consumption by item
- top consuming branches
- low-activity branches

Views:

- branch ranking table
- brand split chart
- item trend chart

### 3.3 Inventory & Item Intelligence

Widgets:

- top requested items
- least requested items
- delayed items
- unavailable items
- items by brand
- items by source type
- inactive items
- not-requestable items

Views:

- top/bottom item tables
- brand distribution chart
- source-type distribution chart
- delayed items exception table

---

## Section 4: Governance

### 4.1 Data Health

Widgets:

- users without valid scope
- users linked to inactive entities
- branches with missing brand links
- kitchen sections without kitchen links
- items without valid source rules
- not-requestable items visible in wrong context
- inactive entities still operationally referenced

Views:

- health checklist
- anomaly table
- counts by issue type

### 4.2 User / Permission Oversight

Widgets:

- users by role
- active vs inactive users
- users by city / branch / warehouse
- duplicated or legacy accounts
- recent failed login attempts if available
- users missing assignments

Views:

- distribution cards
- role table
- anomaly table

### 4.3 Admin Audit

Widgets:

- recent approvals
- recent quantity modifications
- recent rejections
- recent warehouse receive / issue actions
- recent delivery state changes
- recent admin/master-data changes

Views:

- recent action log
- sensitive action table
- actor + timestamp + entity + before/after summary

---

## Drill-Down Rules

Every major card or chart should support drill-down to a meaningful destination.

Examples:

- Pending Approval KPI -> approvals queue
- Delayed Production -> kitchen delayed queue
- Partial Warehouse -> warehouse partial lines
- Delivered count -> filtered delivery orders list
- Users without scope -> users/admin filtered list

Drill-downs should:

- preserve active filters when feasible
- land on filtered operational pages
- not require the user to rebuild context manually

---

## Required Coverage Matrix

Each dashboard module must be tracked through this checklist before being marked complete.

| Module | KPI | Chart | Table/List | Filters | Drill-down | API | Status |
|---|---|---|---|---|---|---|---|
| Hero Summary | Yes | No | No | Yes | Yes | Required | Pending |
| Critical Alerts | Yes | Optional | Yes | Yes | Yes | Required | Pending |
| Pipeline Overview | Yes | Yes | Optional | Yes | Yes | Required | Pending |
| Branch Operations | Yes | Yes | Yes | Yes | Yes | Required | Pending |
| Area Manager Operations | Yes | Yes | Yes | Yes | Yes | Required | Pending |
| Kitchen Operations | Yes | Yes | Yes | Yes | Yes | Required | Pending |
| Warehouse Operations | Yes | Yes | Yes | Yes | Yes | Required | Pending |
| Delivery Operations | Yes | Yes | Yes | Yes | Yes | Required | Pending |
| Performance Analytics | Yes | Yes | Optional | Yes | Optional | Required | Pending |
| Branch Consumption | Yes | Yes | Yes | Yes | Optional | Required | Pending |
| Item Intelligence | Yes | Yes | Yes | Yes | Optional | Required | Pending |
| Data Health | Yes | Optional | Yes | Yes | Yes | Required | Pending |
| User / Permission Oversight | Yes | Yes | Yes | Yes | Yes | Required | Pending |
| Admin Audit | Yes | Optional | Yes | Yes | Yes | Required | Pending |

---

## API Expectations

The dashboard should not depend on dozens of unrelated page-level calls if a consolidated API layer is feasible.

Recommended API grouping:

- `GET /api/v1/dashboard/super-admin/summary`
- `GET /api/v1/dashboard/super-admin/alerts`
- `GET /api/v1/dashboard/super-admin/pipeline`
- `GET /api/v1/dashboard/super-admin/branches`
- `GET /api/v1/dashboard/super-admin/area-managers`
- `GET /api/v1/dashboard/super-admin/kitchen`
- `GET /api/v1/dashboard/super-admin/warehouse`
- `GET /api/v1/dashboard/super-admin/delivery`
- `GET /api/v1/dashboard/super-admin/inventory`
- `GET /api/v1/dashboard/super-admin/data-health`
- `GET /api/v1/dashboard/super-admin/audit`

These can internally reuse current reporting services where possible.

---

## UI Rules

### Layout

- Top: global filters
- Then: Hero Summary
- Then: Critical Alerts
- Then: tabbed content

### Visual Priorities

- urgent alerts should be visually loud
- KPI cards should be readable in one glance
- charts should favor clarity over decorative complexity
- tables should support sorting where useful

### States

Every section must support:

- loading
- empty
- error
- populated

### Responsiveness

- desktop-first dashboard is acceptable initially
- tablet support should remain usable
- mobile may collapse into stacked cards/tables but should not break

---

## MVP Delivery Order

The safest MVP for this dashboard is:

1. Hero Summary
2. Critical Alerts
3. End-to-End Pipeline
4. Branch Operations
5. Kitchen Operations
6. Warehouse Operations
7. Delivery Operations
8. Data Health
9. Admin Audit

This gives immediate management value without waiting for every analytic detail.

---

## Implementation Phases

### Phase A — Core Command Center

Includes:

- Hero Summary
- Critical Alerts
- End-to-End Pipeline
- basic drill-down behavior

Definition of done:

- super admin can understand current operational state in under 15 seconds

### Phase B — Operations Visibility

Includes:

- Branch Operations
- Area Manager Operations
- Kitchen Operations
- Warehouse Operations
- Delivery Operations

Definition of done:

- super admin can identify bottlenecks by function and city

### Phase C — Analytics & Governance

Includes:

- Performance Analytics
- Branch Consumption
- Item Intelligence
- Data Health
- User / Permission Oversight
- Admin Audit

Definition of done:

- super admin can use the dashboard for oversight, anomaly detection, and follow-up

---

## Non-Goals For This Spec

This spec does not require:

- predictive analytics
- AI forecasting
- auto-replenishment
- advanced optimization models
- external BI replacement

Those can be a later phase after this dashboard is stable.

---

## Open Decisions

These should be resolved before or during implementation:

- Will `admin` see a reduced version of the same dashboard?
- Will the route live under `dashboard` or `admin`?
- Which existing report endpoints can be reused vs replaced?
- Which charts should be server-aggregated vs client-composed?
- How much audit detail should be exposed directly on the dashboard?

---

## Final Note

This dashboard should be treated as a management product surface, not just a visual summary page.

If implemented correctly, it becomes:

- the super admin's first page after login
- the fastest place to detect operational risk
- the central bridge between operations, governance, and reporting
