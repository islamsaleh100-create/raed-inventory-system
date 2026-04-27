# Raed Food System - Full Production Audit Report

Audit date: 2026-04-25  
Scope reviewed: backend architecture, data model, Supply Chain V1 workflow, Quality/Evaluation module, legacy replenishment flow, authentication/RBAC, frontend routing/API integration, file uploads, exports, startup behavior, and consistency risks.

This report is intentionally direct. Several parts of the system work functionally, but the production architecture is fragile because business logic, authorization, persistence, seeding, migrations, and UI behavior are scattered across large files and routers.

---

## 1) 🔴 CRITICAL ISSUES (must fix immediately)

### C1. Runtime schema mutation outside Alembic can corrupt production schema history
**What is wrong:** `backend/app/startup_schema.py` creates tables and alters columns at application startup using `Base.metadata.create_all()` and raw `ALTER TABLE`. It is called from `backend/app/main.py`.  
**Why it is wrong:** Schema changes become dependent on application boot order rather than controlled migrations. Alembic history can say one thing while the live DB contains another structure.  
**Real impact:** Production upgrades can diverge between environments, fail silently, or create tables missing constraints/indexes. PostgreSQL migration becomes risky. Rollback is not reliable.  
**Exact fix suggestion:** Move every table/column in `NEW_MODULE_TABLES` and `SQLITE_COMPAT_ALTERS` into Alembic revisions. Remove schema mutation from startup. Startup may validate schema version, but must not mutate it.

### C2. Stock mutations are not consistently locked or idempotent
**What is wrong:** `warehouse_lines.py`, `production_orders.py`, and `delivery_orders.py` mutate `WarehouseStock` and `BranchStock` without row locking or idempotency keys.  
**Why it is wrong:** Two concurrent requests can read the same quantity and both update stock. Delivery can double-increment branch stock if two workers pass the status check before either commits.  
**Real impact:** Incorrect stock balances, duplicate ledger entries, and impossible reconciliation. This is a financial/operational correctness issue.  
**Exact fix suggestion:** Add `SELECT ... FOR UPDATE` helpers for stock and workflow rows, use idempotency keys on stock-changing endpoints, and add database-level uniqueness for ledger references where operations must be one-time.

### C3. Delivery order lines can be duplicated under concurrency
**What is wrong:** `delivery_orders.py` checks for existing `DeliveryOrderLine` by `warehouse_line_id`, but `delivery_order_lines` has no unique constraint on `warehouse_line_id`.  
**Why it is wrong:** Application-level duplicate checks are not safe under concurrent requests.  
**Real impact:** Same warehouse line can enter two delivery orders and be delivered twice, causing duplicate branch receipt.  
**Exact fix suggestion:** Add a unique constraint/index on `delivery_order_lines.warehouse_line_id`, catch integrity errors, and wrap delivery creation in a transaction with row locks on selected `WarehouseLine` rows.

### C4. File upload is unsafe and not production-ready
**What is wrong:** `evaluation_storage_service.py` stores uploaded files under `uploads/evaluations` with no size enforcement, no extension allowlist, no MIME validation, no antivirus hook, and writes file before DB commit.  
**Why it is wrong:** Attackers can upload oversized files, unsupported content, or many files to exhaust disk. If DB commit fails, orphan files remain.  
**Real impact:** Disk exhaustion, operational outage, malware storage, orphan data, and compliance risk.  
**Exact fix suggestion:** Enforce `settings.MAX_UPLOAD_SIZE_MB`, allowlist MIME/extensions, store under configured absolute upload root, write after validation, commit DB and file via compensating cleanup on failure, and add background cleanup for orphan files.

### C5. JWT stored in `localStorage` is vulnerable to token theft
**What is wrong:** `frontend/src/store/index.js` and `frontend/src/services/api.js` store and read `access_token` from `localStorage`.  
**Why it is wrong:** Any XSS bug gives full bearer token access. The system also has long-lived access tokens by default.  
**Real impact:** Account takeover until token expiry. Admin token theft is catastrophic.  
**Exact fix suggestion:** Move auth to secure `HttpOnly`, `Secure`, `SameSite` cookies or reduce access-token TTL sharply with refresh-token rotation and CSP hardening.

### C6. RBAC is fragmented and cannot be audited reliably
**What is wrong:** Role checks are spread across routers (`require_roles`, `_broad`, `_is_admin`, `_require_*`) with separate rules per module. `ROLE_PERMISSIONS` is not the true authority.  
**Why it is wrong:** Authorization behavior cannot be reasoned about centrally. New modules can accidentally bypass scope rules.  
**Real impact:** Privilege escalation, cross-branch access leaks, inconsistent admin/manager behavior.  
**Exact fix suggestion:** Introduce a policy layer: `PermissionService.can(user, action, resource)` with unit tests per role/resource/action. Keep router role checks only as coarse entry gates.

### C7. Supply Chain stock ledger lacks durable operation identity
**What is wrong:** Production receipt uses reference strings like `PO-{id}-{qty_sent_to_warehouse}` and delivery uses `DO-{id}` without uniqueness.  
**Why it is wrong:** References are not enforced as unique operation IDs. Retries/concurrent calls can produce multiple ledger rows.  
**Real impact:** Ledger cannot be trusted as an audit-grade source of truth.  
**Exact fix suggestion:** Add `operation_id` or unique `(module, entity_type, entity_id, action, sequence)` columns for stock transactions, with unique constraints.

### C8. Frontend does not expose or validate several accepted backend modules
**What is wrong:** Supply Chain V1 and the new Evaluation module are mostly backend-only. `AppLayoutV2.jsx` navigation still exposes old quality pages and no `/api/evaluations` UI.  
**Why it is wrong:** Users cannot operate accepted workflows through the UI, or they continue using old quality logic.  
**Real impact:** Production users operate incomplete flows manually or via API, causing data inconsistency and adoption failure.  
**Exact fix suggestion:** Add isolated frontend modules for Supply Chain V1 and Evaluations with route guards matching backend roles. Keep legacy quality screens clearly separated.

---

## 2) 🟠 HIGH PRIORITY ISSUES

### H1. `models/__init__.py` is a domain dump
**What is wrong:** One file contains auth, inventory, replenishment, quality, training, supply chain, delivery, documents, analytics, and evaluation models.  
**Why it is wrong:** Any model import loads the entire domain graph. Merge conflicts and accidental coupling become likely.  
**Real impact:** Slower development, higher regression risk, poor ownership boundaries.  
**Exact fix suggestion:** Split into `models/auth.py`, `models/master.py`, `models/inventory.py`, `models/replenishment.py`, `models/supply_chain.py`, `models/evaluations.py`, etc. Re-export from `models/__init__.py` during transition.

### H2. `schemas/__init__.py` is too large and couples all API contracts
**What is wrong:** Pydantic schemas for unrelated modules live in one file.  
**Why it is wrong:** A schema change in evaluations imports enums/models from inventory and supply chain.  
**Real impact:** Import fragility and high review risk.  
**Exact fix suggestion:** Split schemas by module and update routers to import only their module schema.

### H3. Routers contain business logic that belongs in services
**What is wrong:** `branch_requests.py`, `production_orders.py`, `delivery_orders.py`, and `evaluations.py` perform state transitions, stock mutations, validation, audit, and persistence directly.  
**Why it is wrong:** Router logic is difficult to test independently and tends to duplicate validation.  
**Real impact:** Business workflows become scattered and hard to audit.  
**Exact fix suggestion:** Move workflow operations to services: `BranchRequestWorkflowService`, `ProductionService`, `WarehouseExecutionService`, `DeliveryService`, `EvaluationWorkflowService`.

### H4. Supply Chain parent status is incomplete
**What is wrong:** `BranchRequestStatus` has `IN_EXECUTION` and `DELIVERED`, but split sets parent to `SPLIT`; execution steps update line statuses without consistently rolling up parent status until delivery.  
**Why it is wrong:** Parent status should represent the aggregate state of all lines.  
**Real impact:** Dashboards and operators can see stale or misleading request status.  
**Exact fix suggestion:** Add a single status rollup function called after split, production send, warehouse issue, delivery create, and delivery complete.

### H5. Partial production model is improved but still semantically weak
**What is wrong:** `ProductionOrder.status` remains `PARTIAL_READY` after partial send, while the remaining work is not represented as a separate pending execution state.  
**Why it is wrong:** The status mixes "some ready to send" with "remaining work still in production".  
**Real impact:** Kitchen operators cannot distinguish partially sent but still active orders from ready-but-not-sent orders.  
**Exact fix suggestion:** Add explicit statuses such as `PARTIAL_SENT_PENDING_PRODUCTION` or introduce production batches/outputs while keeping the order as the total obligation.

### H6. Evaluation dashboard endpoint is heavy and unpaginated
**What is wrong:** `evaluations.py` dashboard builds many queries and full trend arrays in one request.  
**Why it is wrong:** As evaluations grow, response size and query cost grow without bound.  
**Real impact:** Slow dashboard and DB pressure.  
**Exact fix suggestion:** Add date range defaults, pagination/limits for trend arrays, pre-aggregated reporting tables if volume grows, and indexes on `(evaluation_date, brand_id, branch_id, employee_id, status)`.

### H7. Area-manager scoping has expensive and inconsistent implementations
**What is wrong:** Some modules scope area managers by `AreaManagerAssignment`; `core/auth.py` scopes by user's home branch city/area; evaluations loop through all branches and call `can_access_branch`.  
**Why it is wrong:** The same role gets different access rules by module.  
**Real impact:** Cross-branch visibility bugs and slow queries.  
**Exact fix suggestion:** Define one area-manager scope model and query helper using joins, not Python loops.

### H8. Delivery users can view all delivery orders
**What is wrong:** `_require_order_access` allows any `delivery_user` to view any delivery order.  
**Why it is wrong:** There is no assignment or warehouse/branch restriction.  
**Real impact:** Delivery staff can see operational data for every branch.  
**Exact fix suggestion:** Add `delivery_order_assignments` or `delivery_user.branch_id/area_id` rules. Until then, restrict delivery users to READY/OUT_FOR_DELIVERY orders assigned to them or explicitly unassigned.

### H9. User password validation is inconsistent
**What is wrong:** `UserCreate` schema accepts password length >= 6, while `_validate_password` requires >= 8, uppercase, digit.  
**Why it is wrong:** API validation and service validation disagree.  
**Real impact:** Some endpoints accept weaker passwords or return inconsistent errors.  
**Exact fix suggestion:** Move password policy to one reusable validator and use it in all create/reset/change endpoints.

### H10. Excel export is vulnerable to formula injection
**What is wrong:** Evaluation Excel export writes user-controlled strings (names, template names) directly to cells.  
**Why it is wrong:** Values beginning with `=`, `+`, `-`, or `@` can execute formulas when opened in Excel.  
**Real impact:** Spreadsheet-based data exfiltration or command attempts depending on client configuration.  
**Exact fix suggestion:** Escape exported strings that start with formula characters by prefixing `'`.

### H11. "PDF" endpoint is not a PDF
**What is wrong:** `GET /api/evaluations/{id}/export/pdf` returns printable HTML.  
**Why it is wrong:** Endpoint naming and expected content type are misleading.  
**Real impact:** Integrations expecting PDF will fail. Users may distribute HTML thinking it is a PDF.  
**Exact fix suggestion:** Either generate a real PDF using a supported library or rename endpoint to `/export/printable` and add a separate real PDF endpoint later.

---

## 3) 🟡 MEDIUM ISSUES

### M1. API prefixes are inconsistent
**What is wrong:** Most endpoints use `/api/v1`, but evaluations use `/api/evaluations`.  
**Why it is wrong:** API versioning and routing conventions become inconsistent.  
**Real impact:** Client code needs special handling; version migration is harder.  
**Exact fix suggestion:** Standardize on `/api/v1/evaluations` or explicitly document evaluations as unversioned and add compatibility redirects.

### M2. Frontend API fallback can hide routing bugs
**What is wrong:** `api.js` retries `/api/v1` failures against `/api`.  
**Why it is wrong:** 404s can be masked and hit a different API namespace.  
**Real impact:** Debugging endpoint mismatches becomes harder; incorrect endpoint may appear to work.  
**Exact fix suggestion:** Remove fallback in production; keep it dev-only with a visible warning.

### M3. Error response shapes are mixed
**What is wrong:** Some endpoints raise `AppError`, others raise `HTTPException`, and frontend reads `detail`, `message`, or `error`.  
**Why it is wrong:** Clients cannot rely on one error contract.  
**Real impact:** Generic toasts and missing validation feedback.  
**Exact fix suggestion:** Standardize all application errors through `AppError` and a single error schema.

### M4. Startup seeding is embedded in `main.py`
**What is wrong:** Training, evaluation, and quality seeds are invoked from application startup.  
**Why it is wrong:** App boot has side effects and can mutate production data.  
**Real impact:** Unexpected seed rows, boot delays, and hidden failures.  
**Exact fix suggestion:** Move seeds to explicit management commands or migrations with idempotent seed revisions.

### M5. Missing module-level frontend for new Evaluation system
**What is wrong:** Existing `QualityPages.jsx` uses old quality visits and hardcoded brand inference. New dynamic evaluation APIs are not represented.  
**Why it is wrong:** It contradicts the new architecture: dynamic templates and brand-specific versions.  
**Real impact:** Users continue using old static quality flows.  
**Exact fix suggestion:** Build a new Evaluation UI and label the old Quality Visit module as legacy or migrate it.

### M6. Quality frontend hardcodes brand inference
**What is wrong:** `QualityPages.jsx` infers brand from branch name strings like `pizza`, `shawarma`, `griddle`, `onda`.  
**Why it is wrong:** Brand membership should come from database relationships, not text matching.  
**Real impact:** Wrong forms/checklists for branches with unexpected names.  
**Exact fix suggestion:** Use `BranchBrand`/template metadata from backend.

### M7. Action plan state machine is incomplete
**What is wrong:** Status includes `IN_PROGRESS`, but there is no dedicated transition endpoint. Generic update rejects status changes.  
**Why it is wrong:** The model exposes a state that API cannot reach cleanly.  
**Real impact:** UI cannot represent started action plans without admin DB edits.  
**Exact fix suggestion:** Add `/action-plans/{id}/start` or remove `IN_PROGRESS` until needed.

### M8. File deletion swallows permission failures
**What is wrong:** `evaluation_storage_service.delete_attachment()` ignores repeated `PermissionError`.  
**Why it is wrong:** DB row can be deleted while file remains on disk.  
**Real impact:** Orphan files and compliance issue.  
**Exact fix suggestion:** Log failed deletions and mark attachment as pending deletion, then retry asynchronously.

### M9. Report endpoints lack consistent pagination
**What is wrong:** Evaluation reports, delivery lists, production lists, and some dashboard queries return unbounded lists.  
**Why it is wrong:** Data grows faster than expected in operational systems.  
**Real impact:** Slow UI, memory pressure, timeout risk.  
**Exact fix suggestion:** Add `page`, `page_size`, and sane maximum limits to every list/report endpoint.

### M10. Testing is backend-heavy and UI-light
**What is wrong:** Backend tests cover many workflows, but frontend route/interaction tests are minimal or absent.  
**Why it is wrong:** The user's earlier pain was UI behavior; backend tests do not catch hidden buttons, wrong API calls, or state bugs.  
**Real impact:** UI regressions reach users.  
**Exact fix suggestion:** Add Playwright smoke tests for login, inventory, orders, quality, supply chain, evaluation, and delivery workflows.

---

## 4) 🟢 LOW IMPROVEMENTS

### L1. Large inline React pages reduce maintainability
**What is wrong:** `App.jsx` and page files include large inline page implementations.  
**Why it is wrong:** Hard to test and review.  
**Real impact:** Slower feature work.  
**Exact fix suggestion:** Split pages into route containers, service hooks, forms, tables, and dialogs.

### L2. Role labels and navigation are incomplete
**What is wrong:** New roles such as `evaluator`, `hr_manager`, `delivery_user`, and `kitchen_section_manager` are not consistently represented in frontend navigation/role display.  
**Why it is wrong:** Users may have backend access but no visible navigation.  
**Real impact:** Operational confusion.  
**Exact fix suggestion:** Update role translation keys, nav sections, and route guards.

### L3. Some imports and compatibility comments show accumulated technical debt
**What is wrong:** Comments like "legacy value only", startup compatibility warnings, and alias exports indicate transitional code.  
**Why it is wrong:** Transitional code becomes permanent without ownership.  
**Real impact:** Future developers copy old patterns.  
**Exact fix suggestion:** Track all compatibility shims in a debt register with removal dates.

### L4. Audit logs are split between generic audit and evaluation-specific audit
**What is wrong:** Some modules use `audit_service`; evaluations use `evaluation_audit_logs`.  
**Why it is wrong:** Auditors need multiple sources for one timeline.  
**Real impact:** Investigation friction.  
**Exact fix suggestion:** Either centralize audit events or create a unified audit view over all audit tables.

### L5. Dashboard query functions are not service-layer reusable
**What is wrong:** Reporting logic is embedded in routers.  
**Why it is wrong:** Hard to reuse in exports or scheduled reports.  
**Real impact:** Duplication later.  
**Exact fix suggestion:** Move analytics query builders into services.

### L6. `localStorage` JSON parsing can crash app startup
**What is wrong:** `JSON.parse(stored_user)` is not wrapped.  
**Why it is wrong:** Corrupt localStorage breaks the frontend before login.  
**Real impact:** User gets blank app until storage is cleared.  
**Exact fix suggestion:** Safe-parse with fallback and clear invalid stored user.

### L7. API client is monolithic
**What is wrong:** `frontend/src/services/api.js` contains all module API clients.  
**Why it is wrong:** Changes in one domain risk merge conflicts across all domains.  
**Real impact:** Poor maintainability.  
**Exact fix suggestion:** Split into `authApi.js`, `masterApi.js`, `evaluationsApi.js`, etc.

### L8. Local dev random secret invalidates tokens on restart
**What is wrong:** If default `SECRET_KEY` is used outside production, config replaces it with a random in-memory secret.  
**Why it is wrong:** Good security warning, but bad developer experience.  
**Real impact:** Unexpected logouts after restart.  
**Exact fix suggestion:** Generate a persistent local `.env` secret on first run or require developers to set one.

---

## 5) 🧠 ARCHITECTURE RISKS

### A1. The system is moving toward a "modular monolith" but is implemented as a "large coupled monolith"
The functional domains are recognizable, but the code structure does not enforce boundaries. Models, schemas, routers, startup seeding, and policy checks are centralized or scattered in ways that defeat modular ownership.

**Fix:** Introduce domain packages:
- `domains/auth`
- `domains/master_data`
- `domains/inventory`
- `domains/replenishment`
- `domains/supply_chain`
- `domains/quality_evaluations`
- `domains/documents`
- `domains/delivery_analytics`

Each domain should own models, schemas, services, router, policy, tests, and migrations.

### A2. Workflow state machines are implicit
State transitions are coded inside route handlers. There is no state machine definition per workflow.

**Fix:** Define explicit transition maps and guard functions for:
- ReplenishmentOrder
- BranchRequest
- ProductionOrder
- WarehouseLine
- DeliveryOrder
- Evaluation
- EvaluationActionPlan

### A3. Authorization is not a first-class architecture component
RBAC exists, but scoping rules are duplicated in every domain.

**Fix:** Build a central policy layer with resource scopes:
- branch scope
- warehouse scope
- brand/city area manager scope
- evaluator ownership
- delivery assignment scope

### A4. Runtime compatibility logic is hiding migration debt
The system still relies on SQLite compatibility behavior and startup table creation.

**Fix:** Freeze schema mutation at runtime. All structural changes must be Alembic-only.

### A5. New modules are backend-first but not operationally complete
Supply Chain V1 and Evaluations have strong backend APIs but limited frontend exposure.

**Fix:** Treat "module done" as backend + frontend + permissions + seed data + smoke tests.

---

## 6) 📊 SCALABILITY RISKS

### S1. Reports and dashboards will not scale with data volume
Many endpoints aggregate live operational tables without date bounds or materialized summaries.

**Fix:** Add date filters by default, indexes, and summary tables for heavy dashboards.

### S2. SQLite-first assumptions leak into production design
Row locking comments assume SQLite behavior is sufficient, but production-grade concurrency needs real locking and transaction discipline.

**Fix:** Standardize PostgreSQL behavior, integration-test concurrency, and avoid SQLite-only compatibility paths.

### S3. File storage will become unmanageable
Local uploads have no lifecycle policy, no checksum, no dedupe, no cleanup job, and no secure download abstraction for evaluations.

**Fix:** Add storage metadata, checksum, size/mime validation, cleanup job, and signed download endpoints.

### S4. Single giant model/schema files will slow every future feature
Merge conflicts and accidental imports will increase as the system grows.

**Fix:** Domain split before adding more modules.

### S5. Lack of frontend E2E tests will scale defects linearly with features
As backend modules grow, UI mismatches become more likely.

**Fix:** Add Playwright smoke tests for the top workflows and require them before release.

---

## Top 10 Most Dangerous Issues

1. Runtime schema mutation outside Alembic.
2. Stock mutations without consistent locking/idempotency.
3. Delivery duplicate race due to missing unique constraint.
4. Unsafe local file upload handling.
5. JWT in localStorage.
6. Fragmented RBAC and scope rules.
7. Ledger operations lack durable unique operation identity.
8. Supply Chain parent/request status rollup is incomplete.
9. Frontend does not expose accepted backend workflows.
10. Evaluation/Excel exports are vulnerable to formula injection and misleading "PDF" behavior.

---

## Architectural Redesign Suggestion

Do not rewrite the product. Refactor into a disciplined modular monolith.

### Target Structure
```text
app/
  domains/
    auth/
      models.py
      schemas.py
      router.py
      service.py
      policy.py
    supply_chain/
      models.py
      schemas.py
      branch_request_service.py
      production_service.py
      warehouse_service.py
      delivery_service.py
      policy.py
      router.py
    quality_evaluations/
      models.py
      schemas.py
      template_service.py
      evaluation_service.py
      scoring_service.py
      action_plan_service.py
      storage_service.py
      reports_service.py
      policy.py
      router.py
```

### Redesign Rules
1. Routers only parse input, call service, return schema.
2. Services own transactions and state transitions.
3. Policies own authorization and scoping.
4. Models are split by domain but can be re-exported during migration.
5. Every stock mutation has row locks, idempotency, and a ledger operation ID.
6. Every report endpoint has filters and limits.
7. Every new backend workflow gets a minimal frontend and E2E smoke test.

---

## Final Audit Verdict

The system has useful business coverage and many recent tests, but it is not yet production-grade. The most dangerous risks are not missing features; they are schema drift, stock consistency under concurrency, fragmented authorization, and frontend/backend workflow mismatch.

Fix those before adding more modules.
