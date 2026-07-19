# RAED INVENTORY SYSTEM — MASTER PLAN

## Document Control

| Field | Value |
|---|---|
| Project | Raed Inventory and Supply Chain System |
| Document | Master Product, UX, Technical and Implementation Plan |
| Version | 1.0 — Approved Baseline |
| Date | 2026-07-13 |
| Status | **APPROVED** |
| Current authorization | Planning and read-only page review only |
| Code implementation | **NOT AUTHORIZED** until all page specifications and technical design are approved |
| Next deliverables | `PAGE_SPEC_INDEX.md` then `PAGE_SPEC_01_supply_chain_branch_requests.md` |

---

# 1. Purpose

This document is the single master plan for completing the Raed Inventory System from the current design stage through:

1. Product decisions.
2. Page-by-page UX and code review.
3. Technical design.
4. Implementation planning.
5. Security closure.
6. Navigation and application implementation.
7. End-to-end verification.
8. LAN Trial.
9. Production readiness.

The objective is to prevent rework by approving the menu structure, workflows and every page specification before changing application code.

---

# 2. Non-Negotiable Working Rules

1. The mandatory order is:

   ```text
   Product Decisions
   → Page Specifications
   → Technical Design
   → Implementation Plan
   → P0 Closure
   → Code Implementation
   → Testing
   → LAN Trial
   → Production
   ```

2. No application code may be modified before all current-page specifications are approved.

3. Every current page is reviewed from two perspectives:

   - Browser: Desktop and Tablet/Responsive.
   - Code: Frontend, Backend, RBAC and Object-Level Scope.

4. Frontend hiding is a UX measure only. Authorization and scope enforcement must exist in the Backend.

5. No new module may be built before approving:

   - Data Model.
   - API contract.
   - State machine.
   - Roles and scope.
   - Audit Trail.
   - Idempotency and concurrency rules.
   - Acceptance tests.

6. Admin and Super Admin must see and operate both the current and previous systems.

7. Full administrative access does not bypass:

   - Inventory integrity.
   - Append-only Audit Trail.
   - Required reasons for exceptional actions.
   - Valid state transitions.
   - Idempotency protections.

8. The previous system remains in a separate `النظام السابق` section and is not mixed with the current supply-chain workflow.

9. Page-creation routes such as `/new` are normally actions inside list pages, not separate sidebar items.

10. Test data may be created only in the confirmed test database when a page scenario requires it. Every created record must be documented. No migration or seed script may run during page-specification review.

---

# 3. Approved Source Documents

The following documents are the current planning sources of truth:

- `ROLE_MENU_MATRIX.md`
- `PRODUCT_DECISIONS_FINAL.md`
- Approved ten-section Admin/Super Admin menu tree.
- Complete Fix Register.
- Consolidated UX and technical audit reports.
- Runtime evidence and prior E2E reports.

If a later document conflicts with an approved decision, the conflict must be recorded and resolved explicitly. It must not be silently implemented.

---

# 4. Approved Product Decisions

## PD-01 — Supply Request Types

The current system has two business request types:

### Regular Request

- Default request type.
- Requires Area Manager approval.
- Continues through the standard supply-chain workflow.

### Urgent Request

- `urgent_reason` is mandatory.
- `needed_by` is mandatory.
- Requires Area Manager approval.
- Does not auto-approve.
- Does not bypass directly to Kitchen or Warehouse.
- Receives higher execution priority after approval.
- Generates escalation when SLA is exceeded.

Kitchen and Warehouse are fulfillment paths selected by Auto Split. They are not user-selected request types.

## PD-02 — Mandatory Area Approval

Both regular and urgent Branch Supply Requests follow:

```text
Branch Request
→ Area Manager Approval
→ Auto Split
→ Kitchen and/or Warehouse
→ Warehouse Issue
→ Delivery
→ Branch
```

Operational urgency must not bypass the Area Manager approval stage.

## PD-03 — Initial LAN SLA

SLA values must be configurable and must not be hardcoded.

| Stage | Regular | Urgent |
|---|---:|---:|
| Area approval target | 2 hours | 15 minutes |
| Start processing after approval | According to operating cycle | 15 minutes |
| First escalation | After 1 hour | After 10 minutes |
| Overdue | After 2 hours | After 15 minutes |

Production, picking and delivery SLA values will be measured during LAN Trial before final production values are approved.

## PD-04 — Delivery Claim

The target delivery lifecycle is:

```text
READY
→ CLAIMED by delivery user
→ OUT_FOR_DELIVERY
→ DELIVERED or PARTIALLY_DELIVERED
```

- A Delivery User may claim an unclaimed eligible order.
- The claimed order becomes locked to that user.
- Another Delivery User cannot execute it.
- Claiming must be transaction-safe and idempotent.

## PD-05 — Claim Release and Reassignment

- `warehouse_manager`, `admin` and `super_admin` may release or reassign a claim.
- A mandatory reason is required.
- `operations_manager` remains read-only and cannot reassign delivery work.
- Before `OUT_FOR_DELIVERY`, release returns the order to `READY`.
- After `OUT_FOR_DELIVERY`, reassignment requires a documented handover.
- After partial delivery, only the remaining quantities may be reassigned.
- Previous delivery execution must never be erased.

## PD-06 — Delivery Assignment History

A durable assignment history is required, preferably through a dedicated model such as:

```text
delivery_assignment_history
```

Required audit data includes:

- `claimed_by`
- `claimed_at`
- `released_by`
- `released_at`
- `release_reason`
- previous driver
- new driver
- status at reassignment
- delivered quantities before reassignment
- remaining quantities

## PD-07 — Quality Inspector Branch Scope

Quality Inspectors must operate only on assigned branches.

A new data model is required:

```text
quality_inspector_branch_assignments
├── id
├── inspector_user_id
├── branch_id
├── active
├── effective_from
├── effective_to
├── assigned_by
├── created_at
└── updated_at
```

Rules:

- Quality Visitor cannot create a visit for an unassigned branch.
- Quality Visitor cannot create a visit using another visitor's identity.
- Historical access to the visitor's earlier visits remains available after an assignment expires.
- Quality Manager, Admin and Super Admin manage assignments.

## PD-08 — Admin and Super Admin

- Both roles have the same target functional capability across the current and previous systems.
- Exceptional administrative action requires a reason and Audit Trail.
- No silent inventory or audit-finding modification is permitted.
- Audit Trail records remain append-only.

---

# 5. Approved Open Questions

These questions do not reopen the approved product baseline. They must be resolved at the specified page or technical-design stage.

## OQ-01 — Changing Request Type After Submission

Question:

> Can a submitted Regular Request be changed to Urgent, and which roles can perform this change?

Resolution location:

- PAGE 02 — Create Supply Request.
- PAGE 03 — Request Details and Timeline.
- PAGE 04/05 — Area Approval.

The decision must define notifications, timeline events, required reason and whether an already-approved request can change type.

## OQ-02 — Escalation Channels

Question:

> Is escalation an in-app notification, push notification, visual list flag, or a combination?

Resolution location:

- Phase 3 — Notifications and Escalation Technical Design.

## OQ-03 — Exceptional Admin Approval UI

Question:

> Does Admin use the normal approval button with a mandatory reason modal, or a visually distinct exceptional-approval action?

Resolution location:

- PAGE 04/05 — Approval Page Specification.

---

# 6. Phase 0 — Freeze the Planning Baseline

## Work

- Confirm the approved menu tree and Role Menu Matrix.
- Confirm `PRODUCT_DECISIONS_FINAL.md` is closed.
- Record the active Fix Register.
- Record that code implementation is not authorized.

## Prohibited Actions

- Application-code modification.
- Migration or seed execution.
- RBAC change.
- Route deletion.
- Legacy/current data merge.
- Deployment.

## Exit Gate

```text
MENU DESIGN: CLOSED
ROLE MATRIX: APPROVED CONCEPTUALLY
PRODUCT DECISIONS: CLOSED
MASTER PLAN: APPROVED
CODE IMPLEMENTATION: NOT AUTHORIZED
```

---

# 7. Phase 1 — Create the Live Page Index

`PAGE_SPEC_INDEX.md` must be created on the first day of page review, before PAGE 01.

It is not an end-of-phase report. It is a live control document updated after every page review.

## Initial Content

- Prepopulate all 80 planned page rows.
- Give every row the initial status `NOT_STARTED`.
- Do not leave the file literally blank.

## Required Columns

| Column |
|---|
| Page ID |
| Page Name |
| Route |
| Group |
| Current Status |
| Browser Review |
| Code Review |
| Security Review |
| Target Design |
| Open Questions |
| Decision |
| Dependencies |
| Specification File |
| Approval Date |

## Status Lifecycle

```text
NOT_STARTED
→ IN_REVIEW
→ DISCUSSION_REQUIRED
→ APPROVED
→ TECHNICAL_DEPENDENCY
→ READY_FOR_IMPLEMENTATION_PLANNING
```

---

# 8. Phase 2 — Page-by-Page Review and Specification

This phase is read-only for application code.

## Review Method

Every current page is reviewed through:

1. Desktop browser at 1920×1080.
2. Tablet/Responsive browser viewport.
3. Frontend component and routing code.
4. Backend router, service, authorization and object-level scope.
5. Role-specific direct URL tests.
6. Existing-data and state review.

## Group A — Core Supply Chain

| ID | Page | Primary Route | Initial Status |
|---:|---|---|---|
| 01 | Branch Supply Request List | `/supply-chain/branch-requests` | NOT_STARTED |
| 02 | Create Supply Request | `/supply-chain/branch-requests/new` or approved in-page action | NOT_STARTED |
| 03 | Supply Request Details and Timeline | Detail route to be confirmed | NOT_STARTED |
| 04 | Area Approval List | `/supply-chain/approvals` | NOT_STARTED |
| 05 | Approval Details, Approve and Reject | Detail/action route to be confirmed | NOT_STARTED |
| 06 | Kitchen Production Orders List | `/supply-chain/kitchen` | NOT_STARTED |
| 07 | Kitchen Production Order Details | Detail route to be confirmed | NOT_STARTED |
| 08 | Warehouse Execution List | `/supply-chain/warehouse` | NOT_STARTED |
| 09 | Warehouse Execution Details | Detail route to be confirmed | NOT_STARTED |
| 10 | Delivery Orders List | `/supply-chain/delivery` | NOT_STARTED |
| 11 | Delivery Claim and Delivery Details | Detail route to be confirmed | NOT_STARTED |
| 12 | Supply Chain Control | `/supply-chain/control` | NOT_STARTED |
| 13 | Operations Dashboard | `/operations` | NOT_STARTED |
| 14 | Main Dashboard | `/dashboard` | NOT_STARTED |
| 15 | Notifications | `/notifications` | NOT_STARTED |

Core success flow:

```text
Request
→ Area Approval
→ Auto Split
→ Kitchen Production and/or Warehouse
→ Warehouse Issue
→ Delivery Claim
→ Delivery
→ Branch Stock Update
```

## Group B — Inventory and Transfers

| ID | Page | Primary Route | Initial Status |
|---:|---|---|---|
| 16 | Daily Inventory Records | `/inventory` | NOT_STARTED |
| 17 | Enter Today's Inventory | `/inventory/new` | NOT_STARTED |
| 18 | Inventory Record Details/Edit | `/inventory/:id` | NOT_STARTED |
| 19 | Daily Inventory Review | `/reports/inventory` — component rebuild required | NOT_STARTED |
| 20 | Branch Balances | `/branch-stock` | NOT_STARTED |
| 21 | Warehouse Balances | `/warehouse/stock` | NOT_STARTED |
| 22 | Stock Movements | New module/route | NOT_STARTED |
| 23 | Physical Inventory Sessions | New module/route | NOT_STARTED |
| 24 | Create and Execute Physical Count | New action/route | NOT_STARTED |
| 25 | Review Differences and Approve Adjustment | New workflow/route | NOT_STARTED |
| 26 | Inter-Branch Transfer List | `/stock/inter-branch-transfer` | NOT_STARTED |
| 27 | Create Transfer Request | In-page action/route to be confirmed | NOT_STARTED |
| 28 | Transfer Approval | `/operations/inter-branch-approvals` | NOT_STARTED |
| 29 | Transfer Execution and Receipt | Workflow/route to be confirmed | NOT_STARTED |

## Group C — Internal Audit

| ID | Page | Primary Route | Initial Status |
|---:|---|---|---|
| 30 | Internal Audit Dashboard | `/audit/dashboard` | NOT_STARTED |
| 31 | Order Review — Today and History Tabs | `/audit/orders?tab=today|history` target | NOT_STARTED |
| 32 | Warehouse Stock Review | `/audit/warehouse-stock` | NOT_STARTED |
| 33 | Item Change Requests | `/audit/item-change-requests` | NOT_STARTED |
| 34 | Audit Findings | `/audit/findings` | NOT_STARTED |
| 35 | Audit Trail | `/audit/trail` | NOT_STARTED |
| 36 | Stock Movement Review | New with Stock Movements module | NOT_STARTED |
| 37 | Physical Inventory and Adjustment Review | New with Physical Inventory module | NOT_STARTED |

## Group D — Sales Channels

| ID | Page | Primary Route | Initial Status |
|---:|---|---|---|
| 38 | Sales Channels Dashboard | `/delivery` | NOT_STARTED |
| 39 | Daily Entries | `/delivery/daily-entry` | NOT_STARTED |
| 40 | Statements | `/delivery/statements` | NOT_STARTED |
| 41 | Reconciliation | `/delivery/reconciliation` | NOT_STARTED |
| 42 | Unmatched Transactions | `/delivery/unmatched` | NOT_STARTED |
| 43 | Closures | `/delivery/closures` | NOT_STARTED |
| 44 | Compliance | `/delivery/compliance` | NOT_STARTED |
| 45 | Branch Performance | `/delivery/branch-stats` | NOT_STARTED |
| 46 | Brand Performance | `/delivery/brands` | NOT_STARTED |
| 47 | Data Import | `/delivery/import` | NOT_STARTED |
| 48 | Delivery Branch Management | `/delivery/branches` | NOT_STARTED |
| 49 | Sales Channel and Commission Settings | `/admin/sales-channels` | NOT_STARTED |

## Group E — Quality and Training

| ID | Page | Primary Route | Initial Status |
|---:|---|---|---|
| 50 | Quality Visit List | `/quality` | NOT_STARTED |
| 51 | Create Quality Visit | `/quality/new` | NOT_STARTED |
| 52 | Quality Visit Details and Review | `/quality/:id` | NOT_STARTED |
| 53 | Open Corrective Actions | `/quality/open-actions` | NOT_STARTED |
| 54 | Quality Analytics | `/quality/analytics` | NOT_STARTED |
| 55 | Training Evaluations and Create Action | `/training`, `/training/new` | NOT_STARTED |
| 56 | Training Analytics | `/training/analytics` | NOT_STARTED |

## Group F — Documents and Analytics

| ID | Page | Primary Route | Initial Status |
|---:|---|---|---|
| 57 | Document List | `/documents` | NOT_STARTED |
| 58 | Create and View Document | `/documents/new` and detail route | NOT_STARTED |
| 59 | Expiring Documents | `/documents/expiring` | NOT_STARTED |
| 60 | Order Reports | `/reports/orders` | NOT_STARTED |
| 61 | Consumption Trend | `/analytics/consumption-trend` | NOT_STARTED |
| 62 | Order Delay | `/analytics/order-delay` | NOT_STARTED |
| 63 | Branch Corrective Actions | `/analytics/branches-open-actions` | NOT_STARTED |

## Group G — Administration

| ID | Page | Primary Route | Initial Status |
|---:|---|---|---|
| 64 | Users and Permissions | `/admin/users` | NOT_STARTED |
| 65 | Branches | `/admin/branches` | NOT_STARTED |
| 66 | Branch Employees | `/branch-employees` | NOT_STARTED |
| 67 | Warehouses | `/admin/warehouses` | NOT_STARTED |
| 68 | Kitchens and Production Sections | `/admin/kitchens` | NOT_STARTED |
| 69 | Items | `/admin/items` | NOT_STARTED |
| 70 | Branch Item Mapping | `/operations/branch-items` | NOT_STARTED |
| 71 | Assistant Suggestions | `/admin/suggestions` | NOT_STARTED |
| 72 | System Settings | `/admin/settings` | NOT_STARTED |

## Group H — Previous System

These pages are frozen for Admin and Super Admin only. They receive a functional verification rather than a full visual redesign unless a blocking defect is found.

| ID | Page | Primary Route | Initial Status |
|---:|---|---|---|
| 73 | Previous Branch Orders | `/orders` | NOT_STARTED |
| 74 | Previous Daily Order | `/orders/daily` | NOT_STARTED |
| 75 | Previous Exceptional Order | `/orders/exceptional` | NOT_STARTED |
| 76 | Previous Branch Receiving | `/receiving` | NOT_STARTED |
| 77 | Previous Warehouse Orders | `/warehouse/orders` | NOT_STARTED |
| 78 | Previous Warehouse Picking | `/warehouse/picking` | NOT_STARTED |
| 79 | Previous Warehouse Dispatch | `/warehouse/dispatch` | NOT_STARTED |
| 80 | Previous Warehouse Reports | `/warehouse/reports` | NOT_STARTED |

---

# 9. Page Specification Standard

Every current page from PAGE 01 through PAGE 72 must include:

1. Page purpose.
2. Primary role.
3. All allowed roles.
4. Object-level scope per role.
5. Current Nav and Target Nav.
6. Fields and table columns.
7. Search, filters and pagination.
8. Actions and action ownership.
9. Statuses and state transitions.
10. Requested, approved, produced, issued, delivered and remaining quantities where applicable.
11. Confirmation for dangerous actions.
12. Success, validation and error messages.
13. Loading, empty, error and 403 states.
14. Arabic, RTL and terminology consistency.
15. Desktop and Tablet behavior.
16. Backend, API, security and scope gaps.
17. Final decision: Keep, Improve, Rebuild or New Page.

Each output is named:

```text
PAGE_SPEC_XX_page_name.md
```

## Previous-System Review Standard

Each PAGE 73 through PAGE 80 review checks:

1. Does the page open?
2. Does data load?
3. Does the primary action work?
4. Can only Admin and Super Admin access it in the target design?
5. Is it visible under `النظام السابق`?
6. Does it affect current-system data?
7. Is there duplication or inventory-integrity risk?
8. Screenshot and final functional result.

## Phase 2 Exit Gate

```text
PAGE_SPEC_INDEX: CURRENT
ALL CURRENT PAGE SPECS: APPROVED
LEGACY FUNCTIONAL CHECKS: COMPLETE
NO APPLICATION CODE CHANGES MADE
```

---

# 10. Phase 3 — Final Technical Design

This phase begins only after Phase 2 exit approval.

## Data Models

Design or confirm:

- Request type: Regular/Urgent.
- `urgent_reason`.
- `needed_by`.
- SLA configuration.
- Escalation events.
- Delivery Claim.
- Delivery assignment history.
- Quality Inspector branch assignments.
- Stock movements.
- Physical inventory sessions.
- Physical inventory lines.
- Inventory adjustments.
- Transfer requests and approvals.
- Audit history for sensitive administrative actions.

## State Machines

Freeze the state machines for:

- Supply Request.
- Area Approval.
- Kitchen Production.
- Warehouse Execution.
- Delivery.
- Inter-Branch Transfer.
- Physical Inventory.
- Inventory Adjustment.
- Audit Finding.
- Corrective Action.

## API Contracts

For every endpoint define:

- Request and response schemas.
- Validation.
- Role and object scope.
- Error codes.
- Idempotency.
- Concurrency control.
- Audit event.
- Pagination and filtering.

## Notifications and Escalation

Resolve OQ-02 and define:

- In-app notifications.
- Visual urgency flags.
- Push capability if selected.
- Escalation recipients.
- SLA timers and retry behavior.
- Notification deduplication.

## Outputs

```text
TECHNICAL_DESIGN_FINAL.md
DATA_MODEL_CHANGES.md
API_CONTRACTS_FINAL.md
STATE_MACHINES_FINAL.md
NOTIFICATIONS_AND_ESCALATION_DESIGN.md
```

## Exit Gate

```text
TECHNICAL DESIGN: APPROVED
OPEN PRODUCT QUESTIONS: CLOSED
DATABASE CHANGES: DOCUMENTED
API CONTRACTS: FROZEN
```

---

# 11. Phase 4 — Implementation Plan

After technical-design approval, create:

```text
IMPLEMENTATION_PLAN.md
```

Every task must specify:

- Objective.
- Allowed files.
- Prohibited files.
- Backend changes.
- Frontend changes.
- Migration requirements.
- Tests.
- Test data.
- Acceptance criteria.
- Rollback method.
- Required evidence/report.
- Commit boundary.

Large instructions such as `implement the whole system` are prohibited. Tasks must be small, reviewable and reversible.

---

# 12. Phase 5 — Implementation Preflight

Before the first code modification:

- Confirm branch and HEAD.
- Confirm and record working-tree state.
- Create an intentional baseline commit.
- Confirm the exact database.
- Create and test a backup.
- Confirm migration head.
- Confirm no Production connection exists.
- Confirm Backend and Frontend processes match current source.
- Confirm test accounts and credentials.
- Define the Evidence directory.

Output:

```text
IMPLEMENTATION_PREFLIGHT_REPORT.md
```

---

# 13. Phase 6 — P0 and Security Closure

Confirmed and potential P0 items are handled before major operational development.

## Known Security and Integrity Items

- `FIX-WH-01`: Internal Auditor must receive 403 on Warehouse write actions.
- `FIX-QV-02`: Quality Visitor draft-delete IDOR.
- `WH-SEC-01`: Warehouse/Branch object-level scope investigation; P0 if confirmed.
- `FIX-QV-03/04`: Quality visit ownership, impersonation and branch assignment.
- Admin/Super Admin custom-role-check parity.
- Stock and export scope enforcement.
- Direct stock-adjustment restrictions.
- Approved-transfer workflow enforcement.
- Credential Bootstrap conflict if still open.
- 401/403 and cross-scope negative tests.

## KITCHEN-RUNTIME-01 — Core Flow / LAN Trial Blocker

### Evidence

Previous E2E scenarios `PIZZA_KITCHEN` and `SHAWARMA_MIXED` were blocked around the send-to-warehouse stage.

### Current Certainty

The workflow blockage is established, but the exact failing endpoint and root cause were not conclusively proven by the earlier records.

### Required Retest

Reproduce on current source and a clean test environment:

```text
start
→ partial/ready
→ send-to-warehouse
→ WarehouseLine creation
```

Also verify the previously observed notification enum/schema drift separately.

### Priority

```text
P0 — CORE FLOW / LAN TRIAL BLOCKER
```

### Exit Criteria

- Both Kitchen scenarios complete.
- WarehouseLine is created exactly once.
- Correct quantities transfer.
- No duplicate stock movement.
- No frontend crash.
- No 5xx response.
- Browser screenshots, API logs and DB evidence are attached.

## SEC-C-01 — Authentication Token Storage

```text
P0 — RELEASE GATE BEFORE PRODUCTION
```

It may remain deferred during the current design and LAN-preparation phase, but it must be resolved and verified before any Production release.

Target direction:

- HttpOnly cookie.
- Secure in HTTPS environments.
- SameSite policy.
- CSRF design where required.
- Removal of long-lived authentication token storage from localStorage.

## Outputs

```text
SECURITY_CLOSURE_REPORT.md
RBAC_NEGATIVE_TEST_REPORT.md
OBJECT_SCOPE_TEST_REPORT.md
KITCHEN_RUNTIME_RETEST_REPORT.md
```

## Exit Gate for Operational Implementation

```text
CONFIRMED OPERATIONAL P0 OPEN: 0
SECURITY NEGATIVE TESTS: PASS
KITCHEN-RUNTIME-01: CLOSED
```

`SEC-C-01` remains a mandatory Production gate even if not required for design work.

---

# 14. Phase 7 — Navigation Implementation

Implement the approved ten-section structure:

1. الرئيسية
2. التشغيل الحالي
3. المخزون والتحويلات
4. المراجعة الداخلية
5. قنوات المبيعات
6. الجودة والتدريب
7. الوثائق والرخص
8. التحليلات
9. الإدارة
10. النظام السابق

Work includes:

- Move approved items to their target sections.
- Add missing Nav items.
- Create `section_legacy` for Admin and Super Admin.
- Promote `/warehouse/stock` to current Warehouse Balances.
- Keep create actions inside their parent list pages.
- Apply approved Arabic names.
- Align Nav, frontend route guards and Backend authorization.
- Remove incorrect Trial Guard conflicts affecting current Sales Channels.
- Preserve direct-route security.

Outputs:

```text
NAV_IMPLEMENTATION_REPORT.md
ROLE_MENU_BROWSER_VERIFICATION.md
```

Exit criteria:

- Every role sees its approved menu.
- Direct URLs are protected.
- Admin and Super Admin see current and previous systems.
- No dead links.
- No Nav/Route/Backend mismatch.

---

# 15. Phase 8 — Core Supply-Chain Implementation

Implement in this order:

1. Supply Request List.
2. Regular/Urgent Request Creation.
3. Request Details and Timeline.
4. Approval and Rejection.
5. Auto Split.
6. Kitchen Production.
7. Kitchen-to-Warehouse output.
8. Warehouse Picking and Issue.
9. Delivery Claim.
10. Claim Release/Reassignment.
11. Full and Partial Delivery.
12. Branch Stock Update.
13. Notifications and Escalation.
14. Supply Chain Control.

After every page/task:

- Backend tests.
- Desktop browser test.
- Tablet browser test.
- Correct-role test.
- Negative 403 test.
- Evidence screenshots.
- Implementation report.
- Approval before the next task.

---

# 16. Phase 9 — Inventory and Transfers Implementation

Implement:

- Daily Inventory Review.
- Branch Balances.
- Warehouse Balances.
- Stock Movements.
- Physical Inventory.
- Count Differences.
- Adjustment Approval.
- Approved Inter-Branch Transfers.
- Transfer Execution and Receipt.
- Audit Trail for every movement.

Inventory reconciliation must satisfy:

```text
Opening Balance
+ Receipts
- Issues
± Approved Adjustments
= Current Balance
```

Outputs:

```text
INVENTORY_INTEGRITY_REPORT.md
PHYSICAL_INVENTORY_IMPLEMENTATION_REPORT.md
TRANSFER_WORKFLOW_REPORT.md
```

---

# 17. Phase 10 — Supporting Modules

Only after the core supply chain and inventory are stable:

1. Internal Audit.
2. Sales Channels.
3. Quality and Training.
4. Documents.
5. Analytics.
6. Administration.
7. Previous System navigation and functional containment.

---

# 18. Phase 11 — Comprehensive Verification

## Backend Tests

- RBAC.
- Object-level scope.
- State transitions.
- Partial quantities.
- Idempotency.
- Concurrency.
- Negative-stock prevention.
- Audit Trail.
- SLA and escalation.
- Claim and reassignment.
- Duplicate submission.

## Browser Tests

- Every role.
- Every menu.
- Every page.
- Desktop and Tablet.
- Arabic and RTL.
- Loading, Empty, Error and 403.
- Refresh and Back.
- Direct URLs.
- Hidden and rejected actions.

## Required E2E Scenarios

1. Warehouse-only request.
2. Kitchen-only request.
3. Mixed request.
4. Urgent request.
5. Partial production.
6. Partial warehouse issue.
7. Partial delivery.
8. Delivery release and reassignment.
9. Inter-branch transfer.
10. Physical inventory and adjustment.
11. Cross-scope access attempt.
12. Internal Auditor write attempt.
13. Admin current-system operation.
14. Admin previous-system operation.

Outputs:

```text
FINAL_E2E_REPORT.md
FINAL_UX_VALIDATION.md
FINAL_SECURITY_REPORT.md
FINAL_INVENTORY_RECONCILIATION.md
```

---

# 19. Phase 12 — LAN Trial Gate

LAN Trial may start only when:

- All confirmed operational P0 items are closed.
- Core E2E is complete.
- `KITCHEN-RUNTIME-01` is closed.
- Inventory balances reconcile.
- Role menus and scopes are correct.
- Test accounts and credentials are stable.
- Backup and Restore are tested.
- Migrations are at the expected head.
- Evidence is complete.
- Rollback Plan exists.
- No Production data or connection is used.

Verdict values:

```text
GO
GO WITH CONDITIONS
NO-GO
```

Output:

```text
LAN_TRIAL_READINESS_REPORT.md
```

---

# 20. Phase 13 — Production Release Gate

Before Production:

- Close `SEC-C-01`.
- Use HttpOnly/Secure/SameSite authentication cookies.
- Configure Production secrets.
- Enforce HTTPS.
- Configure logging and monitoring.
- Configure backup schedule.
- Complete a Restore drill.
- Configure rate limiting.
- Configure error monitoring.
- Review migrations.
- Remove Demo credentials.
- Review bootstrap credential services.
- Perform final security review.

Output:

```text
PRODUCTION_RELEASE_GATE.md
```

Production is prohibited if any mandatory gate fails.

---

# 21. Final Gate Summary

| Gate | Requirement |
|---|---|
| A — Planning Baseline | Menu, Role Matrix, Product Decisions and Master Plan approved |
| B — Page Design | All current page specs approved; Legacy functional checks complete |
| C — Technical Design | Models, APIs, state machines and open questions approved |
| D — Implementation Plan | Small, bounded, testable tasks approved |
| E — Security | Confirmed operational P0 count equals zero |
| F — Navigation | Role menus, routes and Backend authorization aligned |
| G — Core Flow | Supply request through branch delivery completes |
| H — Inventory | Reconciliation and integrity tests pass |
| I — LAN Trial | Runtime, accounts, backup and evidence gates pass |
| J — Production | `SEC-C-01` and all Production security gates pass |

---

# 22. Current Official Status

```text
MENU DESIGN: CLOSED
ROLE MATRIX: APPROVED CONCEPTUALLY
PRODUCT DECISIONS: CLOSED
MASTER PLAN: APPROVED
CODE IMPLEMENTATION: NOT AUTHORIZED
```

## Immediate Next Steps

```text
1. Create PAGE_SPEC_INDEX.md with PAGE 01–80 = NOT_STARTED.
2. Change PAGE 01 to IN_REVIEW.
3. Review `/supply-chain/branch-requests` in Desktop and Tablet browsers.
4. Review its Frontend and Backend code.
5. Create PAGE_SPEC_01_supply_chain_branch_requests.md.
6. Discuss and approve PAGE 01.
7. Do not start PAGE 02 until PAGE 01 is approved.
8. Do not modify application code.
```

---

# 23. Approval Statement

This Master Plan is approved as the controlling execution sequence for the Raed Inventory System.

Any change to the following requires an explicit documented decision:

- Menu structure.
- Role Matrix.
- Supply-chain flow.
- Inventory posting point.
- Admin/Super Admin access.
- Request types.
- Delivery Claim model.
- Quality Inspector scope.
- P0 gates.
- Page-specification-before-code rule.

No implementation activity may treat an unresolved question, assumption or current-code behavior as an approved product decision.
