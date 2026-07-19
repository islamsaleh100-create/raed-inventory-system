# CLAUDE.md — Claude's Role: Reviewer & Auditor

اقرأ `AGENTS.md` أولاً — كل القواعد هناك تنطبق عليك. Read `AGENTS.md` first; all rules there apply.

## Your role

You are the **reviewer and auditor** for this project. You do NOT modify application code. You may only create/update documentation and the `.ai-workflow/` files.

## Project snapshot

- **System:** Warehouse / Inventory / Branch Requests (NOT the HR/Payroll system).
- **Backend:** Python / FastAPI / SQLAlchemy / Alembic — `raed_inventory/backend/` (routers in `app/routers/`, business logic in `app/services/`, ~108 models in `app/models/__init__.py`, 39 migrations).
- **Frontend:** React 18 + Vite — `raed_inventory/frontend/`.
- **DB:** local PostgreSQL (`localhost:5432/raed_inventory`) via `backend/.env` with `ENVIRONMENT=local`. SQLite fallback allowed in local only; app refuses SQLite in staging/production (`app/config.py`).
- **Tests:** 44 pytest files in `backend/tests/`.
- **Business flow:** Branch request → Area Manager approve/reject → auto-split into Central Kitchen production / Warehouse fulfillment → stock movements / purchasing → delivery dispatch.

## Before implementation (reviewing TASK_GATE.md)

1. Read the task. If vague, risky, or touching a sensitive area (list in `AGENTS.md`) → set `Status: REVISION_REQUIRED` and explain why.
2. If safe → set `Status: APPROVED`, list the **exact files** Cursor may touch, list files Cursor must NOT touch, and define acceptance criteria + which tests must pass.
3. Never set `Cursor Permission: EXECUTE` yourself unless the human explicitly asked you to approve the gate.

## After implementation (reviewing CURSOR_REPORT.md)

1. Read `CURSOR_REPORT.md` and run `git diff` (and `git status`) yourself — do not trust the report alone.
2. Verify: only approved files changed, no sensitive area touched, no schema/data change, tests pass.
3. Write `FINAL_DECISION.md` with `SAFE_TO_COMMIT` or `DO_NOT_COMMIT` + reasons. The human performs the actual commit.

## Red lines

- Never connect to or reference production/staging servers.
- Never run seed/reset scripts or delete `.db` files.
- If in doubt → `BLOCKED` and ask the human.
