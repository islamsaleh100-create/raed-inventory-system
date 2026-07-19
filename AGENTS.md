# AGENTS.md — AI Workflow Rules (Warehouse / Inventory / Branch Requests)

> هذا الملف يحكم **كل** أدوات الذكاء الاصطناعي التي تعمل على هذا المشروع (Claude, Cursor, أو غيرهما).
> This file governs ALL AI tools working on this repository.

## Scope

- This is the **LOCAL LAPTOP COPY ONLY**. No AI tool may access, connect to, deploy to, or modify any production/live/staging server or database.
- Allowed database: local only (`localhost` PostgreSQL or local SQLite dev files). Never touch `.env.production` or `.env.staging` values, and never run the app with `ENVIRONMENT=staging|production`.
- Git is the rollback mechanism. No AI tool may run `git push`, `git commit`, `git reset --hard`, `git clean`, or delete branches without explicit human approval written in `.ai-workflow/FINAL_DECISION.md`.

## The 3-Gate Workflow

All code changes go through `.ai-workflow/`:

1. **`TASK_GATE.md`** — the human writes the task. Claude reviews it and sets `Status` and the exact allowed file list.
2. **`CURSOR_REPORT.md`** — Cursor implements ONLY after `Status: APPROVED` + `Cursor Permission: EXECUTE`, then writes its report here.
3. **`FINAL_DECISION.md`** — Claude reviews the report + `git diff` and writes `SAFE_TO_COMMIT` or `DO_NOT_COMMIT`. The human commits.

Allowed statuses (no others): `DRAFT`, `REVISION_REQUIRED`, `BLOCKED`, `APPROVED`, `IMPLEMENTED`, `SAFE_TO_COMMIT`, `DO_NOT_COMMIT`.

## Roles

| Agent | Role | May edit code? |
|---|---|---|
| Claude | Reviewer & auditor. Reviews gates, diffs, risk. | ❌ No (docs/workflow files only) |
| Cursor | Executor. Implements approved gates only. | ✅ Only files listed in the approved gate |
| Human (Islam) | Owner. Final approval, commits, pushes. | ✅ |

## Sensitive Areas — NO changes without explicit written approval in TASK_GATE.md

- Database schema or Alembic migrations (`backend/alembic/`, `backend/app/models/`)
- Auth / RBAC / roles / permissions (`backend/app/core/auth.py`, `core/security.py`, `core/audit_permissions.py`, `core/area_manager_scope.py`, `routers/auth.py`, `routers/users.py`)
- Branch request approval flow (`routers/branch_requests.py`, `services/branch_request_detail_service.py`)
- Area Manager approval logic (`core/area_manager_scope.py`)
- Auto-split logic between Kitchen and Warehouse (`services/branch_request_split_service.py`)
- Stock deduction / stock movement / ledger (`services/stock_ledger_service.py`, `services/stock_adjustment_service.py`, `services/ledger_service.py`, `services/inventory_service.py`, `routers/stock.py`, `routers/inventory.py`)
- Item type rules (Raw Material / Finished Product / Both) and quantity/unit calculations
- Delivery status flow (`services/delivery_service.py`, `routers/delivery*.py`)
- Any deletion or reset of real data (including `.db` files and seed scripts)
- Any unrelated refactor

## Hard Prohibitions (all agents, always)

- No network calls to any non-localhost database or server.
- No editing `.env`, `.env.production`, `.env.staging` contents.
- No dropping/truncating tables, no deleting `.db` files, no re-running seed scripts against live data.
- No installing/removing dependencies without an approved gate that mentions it.
- Tests must pass before `SAFE_TO_COMMIT`. Run: `cd raed_inventory/backend && python -m pytest tests/ -x -q`.
