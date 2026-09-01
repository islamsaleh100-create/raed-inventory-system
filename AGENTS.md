# AGENTS.md — AI Workflow Rules (Warehouse / Inventory / Branch Requests)

> هذا الملف يحكم **كل** أدوات الذكاء الاصطناعي التي تعمل على هذا المشروع (Claude, Cursor, أو غيرهما).
> This file governs ALL AI tools working on this repository.

## Scope

- Default database is **local only** (`localhost` PostgreSQL or local SQLite dev files). Never edit `.env.production` or `.env.staging` contents, and never run the app with `ENVIRONMENT=staging|production`.
- **Production access is governed by the Production Access Protocol below — not by a blanket ban.** With no explicit grant in the gate, production remains off limits exactly as before.
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

## Production Access Protocol (added 2026-08-16 by the owner)

**Why this replaced the blanket ban.** The old rule said no agent may connect to production at
all. In practice that was neither followed nor followable: on 2026-08-16 production had to be
read to answer questions no local copy could answer — which branch codes exist, which item codes
are real, whether a migration was applied. One agent did that work; another refused the same task
citing this file. **A rule that one agent honours and another ignores is worse than either
outcome**, because nobody can tell from the rule what actually happened.

So the ban is replaced by something checkable. Reading production is legitimate and often the
only way to be correct. Writing to it is a different act with different consequences, and the two
are now separated.

### The grant lives in the gate, never in the agent

Every gate carries one line. **Absent that line, the answer is NONE** — the old ban still applies:

```
Production Access: NONE | READ_ONLY | WRITE
```

- **NONE** — default. No connection to any non-local host. This is most gates.
- **READ_ONLY** — `SELECT` and HTTP `GET` only.
- **WRITE** — only for migrations and seeding, and only under the conditions below.

An agent that finds no such line **must treat it as NONE and say so** rather than infer intent
from the task. A gate that needs production access and does not say so is a defective gate:
report it, do not work around it.

### READ_ONLY — required technique, not just intent

1. **Enforce it at the database, not in your head.** First statement on every connection:
   `SET default_transaction_read_only = on`. PostgreSQL then rejects writes even if the code is
   wrong. Intent is not a control; this is.
2. **HTTP: `GET` only.** No `POST` / `PATCH` / `PUT` / `DELETE` against a production host.
3. **Never open a shift, create a record, or trigger any side effect** as a way of "testing".
   A record created for a test occupies a real unique key and blocks the real one later.
4. **Report what you read**, including row counts. A read that leaves no trace in the report did
   not happen as far as the next reader is concerned.

### WRITE — narrower than it sounds

Permitted **only** for: Alembic migrations, and seed scripts run through their own confirmation
path. Everything else stays forbidden.

1. **Owner confirmation in the session, at the time.** Ask, and wait for a clear yes. A yes in an
   earlier gate is not a yes now. Record the answer verbatim — including a refusal.
2. **Read the migration first.** If any pending revision does anything beyond `create_table`,
   `create_index`, `create_*_constraint`, or `CREATE EXTENSION` — in particular `drop_*`,
   `alter_column`, or `op.execute` carrying `UPDATE`/`DELETE`/`INSERT` — **stop and report.**
   Additive work is one risk class; touching live rows is another, and it needs its own decision.
3. **Never** `DROP`, `TRUNCATE`, or `DELETE` on production. No exception, no gate, ever.
4. **Never `alembic downgrade` on production.** A failed migration is reported, not reversed by
   the executor.
5. **One transaction.** All of it or none of it.
6. **Expectation guard.** A seed or bulk write states the count it expects (e.g.
   `--expect-branches 23`) and aborts before writing if reality differs. This is what catches the
   wrong database; the connection string alone will not.

### Credentials — the same rules for every level

- The connection string comes from a **session environment variable**, obtained from
  `railway variables` or handed over by the owner.
- **Never written to any file** — not `.env`, not a script, not a report, not a scratch note.
- **Never printed unmasked.** Strip the password before any output.
- **Never asked for.** If a task needs a password, the owner performs that step himself and hands
  over the resulting token.
- Before finishing: clear the variable, and confirm
  `grep -ri "rlwy.net\|proxy.rlwy\|amazonaws" .` finds nothing but guard lists and documentation
  placeholders. **Match the finding, not the pattern** — the guard that blocks these hosts
  contains their names by necessity, and flagging it as a leak is a false positive.

### What the report must say

Every gate that touched production states, explicitly:

- the access level used, and the gate line that granted it;
- every write performed — or **"صفر كتابة على الإنتاج"** where there were none;
- row counts before and after any write;
- confirmation that the environment variables were cleared.

## Hard Prohibitions (all agents, always)

- No connection to a non-local host unless the gate grants `Production Access: READ_ONLY` or `WRITE`.
- No editing `.env`, `.env.production`, `.env.staging` contents.
- No `DROP` / `TRUNCATE` / `DELETE` on production — at any access level, in any gate.
- No dropping/truncating tables locally, no deleting `.db` files, no re-running seed scripts against live data outside the WRITE protocol above.
- No installing/removing dependencies without an approved gate that mentions it.
- Tests must pass before `SAFE_TO_COMMIT`. Run: `cd raed_inventory/backend && python -m pytest tests/ -x -q`.
