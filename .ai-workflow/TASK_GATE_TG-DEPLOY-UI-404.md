# TASK_GATE_TG-DEPLOY-UI-404.md

## Task ID
TG-DEPLOY-UI-404

## Origin
Production diagnosis 2026-08-14: `https://raed-inventory-system-production.up.railway.app`
returns the JSON banner on `/` and **404** on every UI route (`/login`).

## Owner
Islam. Executor: Cursor. Deploy/dashboard change: Islam (human only).

## Status
APPROVED

## Cursor Permission
EXECUTE

---

## ⚠️ READ FIRST — Cursor CANNOT fix the actual outage

The root cause is a **Railway dashboard setting**, not code:

| | Root Directory | Dockerfile used | Result |
|---|---|---|---|
| Current (broken) | `raed_inventory/backend` | `backend/Dockerfile` | API only — `npm run build` never runs |
| Correct | `raed_inventory` | `raed_inventory/Dockerfile` | Vite build → `/app/frontend_dist` + `FRONTEND_DIST_DIR` → API **and** UI |

A code-only workaround is **impossible**. With Root Directory = `raed_inventory/backend`,
Docker's build context is that folder, so `backend/Dockerfile` cannot `COPY ../frontend`
— Docker forbids paths outside the build context.

**Cursor must NOT attempt to make `backend/Dockerfile` build the frontend.**
Any such attempt = immediate `DO_NOT_COMMIT`.

Islam performs the one-time dashboard change:
`Settings → Source → Root Directory` = `raed_inventory` → Save → Deploy.

**This gate covers only the code-side work that stops this from recurring.**

---

## Evidence (verified 2026-08-14, do not re-verify against production)

- `GET /health` → `200 {"status":"healthy"}` — container is alive, not crashed, not sleeping.
- `GET /api/docs` → Swagger UI renders. Backend fully functional.
- `GET /` → `200` JSON banner `{"app":...,"status":"running"}`.
- `GET /login` → `404`.
- `backend/app/main.py` `serve_frontend_app()` returns `error_code: "frontend_not_built"`
  when `FRONTEND_DIST_DIR/index.html` is absent.

**The misleading part:** `root()` returns a cheerful `"status":"running"` banner while the
UI is entirely missing. That banner is what made this look like a working deployment for
weeks. Fixing that signal is the point of this gate.

---

## Allowed Files — Cursor may touch ONLY these

1. `raed_inventory/backend/app/main.py` — **only the `root()` function**, lines ~392–400.
2. `raed_inventory/backend/railway.toml` — **comment header only**, zero config-value changes.
3. `raed_inventory/DEPLOYMENT.md` — **NEW file**.
4. `raed_inventory/backend/tests/test_deploy_root_contract.py` — **NEW file**.
5. `.ai-workflow/CURSOR_REPORT_TG-DEPLOY-UI-404.md` — **NEW file**, the report.

## Forbidden Files — touching any of these = DO_NOT_COMMIT

- `raed_inventory/Dockerfile` and `raed_inventory/railway.toml` — **these are correct. Do not "improve" them.**
- `raed_inventory/backend/Dockerfile` — do not add frontend build stages (see above).
- `raed_inventory/frontend/**` — no frontend source changes in this gate.
- All Sensitive Areas in `AGENTS.md`: `backend/alembic/**`, `backend/app/models/**`,
  `core/auth.py`, `core/security.py`, `core/audit_permissions.py`, `core/area_manager_scope.py`,
  `routers/auth.py`, `routers/users.py`, `routers/branch_requests.py`,
  `services/branch_request_split_service.py`, `services/stock_*`, `services/ledger_service.py`,
  `services/inventory_service.py`, `services/delivery_service.py`, `routers/delivery*.py`.
- Any `.env*` file.
- `.ai-workflow/TASK_GATE.md` and `.ai-workflow/CURSOR_REPORT.md` — **an unrelated task
  (TG-PHASE2-DEPLOY-PREP) is still open at `IMPLEMENTED` awaiting review. Do not overwrite.**
- Any dependency add/remove. `requirements.txt` and `package.json` stay untouched.

---

## Required changes

### 1. `root()` must report frontend build state

Replace the JSON fallback branch in `root()` so the response distinguishes a UI-serving
deployment from an API-only one. Keep existing keys; **add** two:

```python
return {
    "app": settings.APP_NAME,
    "version": settings.APP_VERSION,
    "status": "running",
    "frontend": "not_built",
    "frontend_dist_dir": str(FRONTEND_DIST_DIR),
    ...keep any other existing keys unchanged...
}
```

Do not change the `index_file.exists()` → `FileResponse(index_file)` branch.
Do not change `serve_frontend_app()`.

### 2. `backend/railway.toml` warning header

Prepend a comment block stating: this config is **API-only**; using it means no UI will be
served; for API + UI on one domain set Railway Root Directory to `raed_inventory` and use
`raed_inventory/railway.toml`. Change **no** actual config values.

### 3. `raed_inventory/DEPLOYMENT.md` (NEW)

Single source of truth, must contain:
- The two-mode table above (Root Directory → Dockerfile → outcome).
- The rule: **Root Directory is a Railway dashboard setting; it cannot be set from the repo.**
- Diagnostic: `GET /` returning JSON instead of HTML ⇒ frontend not in the image.
  Do not chase DNS, CORS, sleeping containers, or crashed deploys.
- Note: unified mode bakes `VITE_API_BASE_PATH=/api/v1` at build time, so the UI calls the
  same origin and `ALLOWED_ORIGINS`/CORS/nginx `proxy_set_header Host` stop applying.
- Note: migrations do **not** run on container start by design — run
  `alembic upgrade head` against `DATABASE_PUBLIC_URL` as an explicit step after schema PRs.

### 4. `tests/test_deploy_root_contract.py` (NEW)

Using FastAPI `TestClient`, assert:
- When `FRONTEND_DIST_DIR` points at a directory with **no** `index.html`:
  `GET /` returns `200` and the body contains `"frontend": "not_built"`.
- When it points at a temp directory **containing** `index.html`:
  `GET /` returns `200` with `content-type: text/html`.
- `GET /api/v1/definitely-not-a-real-route` still returns `404` with `error_code: "not_found"`
  (regression guard — the catch-all must not swallow API 404s).

Use `monkeypatch` / `tmp_path`. **No network calls. No database. No production hostnames.**

---

## Acceptance Criteria

- [ ] Exactly the 5 allowed files appear in `git status`. Nothing else.
- [ ] `git diff raed_inventory/backend/app/main.py` touches only the `root()` function.
- [ ] `git diff raed_inventory/backend/railway.toml` is comment lines only.
- [ ] No schema change, no migration, no dependency change, no `.env` change.
- [ ] Full suite green: `cd raed_inventory/backend && python -m pytest tests/ -x -q`
- [ ] New test file passes on its own and is included in that run.
- [ ] `CURSOR_REPORT_TG-DEPLOY-UI-404.md` written with: files modified, full pytest output
      pasted verbatim (not summarized), and a `Deviations` section.

## Out of scope

Git commit, git push, Railway dashboard changes, deleting the `humorous-optimism` frontend
service, running alembic, touching production or staging, any refactor of `main.py` beyond
`root()`.

## Blocking condition

If any required change cannot be made without touching a Forbidden File, **stop**, write
`Status: BLOCKED` in the report with the reason, and change nothing.
