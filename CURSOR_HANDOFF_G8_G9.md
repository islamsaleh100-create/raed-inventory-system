# Cursor Handoff — G1–G9 Ship-Ready Verification

## Context

I (Claude) just finished a large batch of work in the Raed Inventory System repo:

- **G1** — `InventoryEntryPage` variance now uses real `book_qty` from API
- **G2** — Delete buttons added to Users / Branches / Warehouses admin pages (soft-delete via `is_deleted=True`)
- **G3** — New Settings system: backend router (`backend/app/routers/settings.py`), 3 new Pydantic schemas, fully editable `SettingsPage` in `frontend/src/App.jsx` with `SETTING_META` metadata dict, atomic bulk-update endpoint
- **G4** — `top_requested_items` endpoint now returns both `item_name_ar` and `item_name_en`
- **G5** — New `/analytics/consumption-trend` endpoint + `ConsumptionTrendPage` (SVG bar chart, 7/30/90-day window)
- **G6** — New `/analytics/order-delay` endpoint + `OrderDelayAnalyticsPage` (approval/transit/total avg hours, top-delayed branches with ≥3 sample rule)
- **G7** — New `/analytics/branches-open-actions` endpoint + `BranchesOpenActionsPage` (open corrective actions count + overdue count per branch)
- **G8** — Independent second audit: all PASS, one unused import cleaned (`and_` from `dashboard.py`)
- **G9** — Adversarial third audit: most "findings" were invalid on verification; applied one real improvement (added `transaction_date < start_of_tomorrow` upper-bound filter on `/dashboard/branch/{id}/consumption-trend` to prevent future-dated rows leaking in).

All changed files pass `python -m py_compile`. I could NOT run `pytest` because the sandbox has no pip/network access. That is where you come in.

## Files touched (for your reference)

**Backend**
- `backend/app/routers/dashboard.py` — 3 new endpoints + fixed prior truncation bug in `alerts_summary`
- `backend/app/routers/settings.py` — NEW file (~200 lines)
- `backend/app/main.py` — registers `settings_router` (aliased to avoid clash with `app.config.settings`)
- `backend/app/schemas/__init__.py` — 3 new schemas at the bottom (SystemSettingOut, SystemSettingUpdate, SystemSettingsBulkUpdate)
- `backend/tests/test_settings_g3.py` — NEW test file (~200 lines, 20+ tests)
- `backend/tests/test_analytics_dashboards_g5_g7.py` — NEW test file (~300 lines, 15+ tests)

**Frontend**
- `frontend/src/App.jsx` — SettingsPage full rewrite, 3 new `/analytics/*` routes, delete handlers on admin pages
- `frontend/src/pages/admin/AnalyticsDashboards.jsx` — NEW file with the 3 dashboard components
- `frontend/src/services/api.js` — new `settingsApi` + 4 new `dashboardApi` methods
- `frontend/src/components/layout/AppLayoutV2.jsx` — new `section_analytics` sidebar block
- `frontend/src/i18n/dict/en.json` + `ar.json` — new keys under `admin.*`, `nav.*`, `analytics.*`

**Data**
- `backend/seed.py::seed_system_settings` — already seeds all 8 required keys (no change needed)
- SystemSetting table is in the baseline migration — no new alembic migration needed

## Your job (in order)

### 1. Backend tests — run and fix

```bash
cd backend
source .venv/bin/activate   # or use your usual python env for this project
pip install -r requirements.txt -r requirements-dev.txt   # if not already installed
python -m pytest tests/test_settings_g3.py tests/test_analytics_dashboards_g5_g7.py -v
```

**Acceptance:** all tests pass. If any fail:
- Read the actual assertion failure.
- Fix the **production code** when the test is legitimate, fix the **test** when its setup is flawed — NOT blindly make tests pass.
- Report back any tests you modified and why.

Also run the full suite to catch regressions from my changes:
```bash
python -m pytest -x --tb=short
```

If anything outside `test_settings_g3.py` / `test_analytics_dashboards_g5_g7.py` breaks, the likely suspects are my edits to `dashboard.py` (the `alerts_summary` fix specifically). Investigate and fix.

### 2. DB state — verify migrations + seed

```bash
cd backend
alembic current        # should be at head (0009_documents_module)
alembic upgrade head   # safe no-op if already there
```

Then run the seed only if `system_settings` table is empty:
```bash
python -c "
from app.database import SessionLocal
from app.models import SystemSetting
db = SessionLocal()
print('count:', db.query(SystemSetting).count())
"
```

If count < 8, run:
```bash
python -c "
from app.database import SessionLocal
from seed import seed_system_settings
db = SessionLocal()
seed_system_settings(db)
"
```

### 3. Frontend build

```bash
cd frontend
npm install
npm run build
```

**Acceptance:** build succeeds with no errors. Warnings about chunk size are OK.

If there are build errors, they'll likely be:
- Import path typos in `App.jsx` for the new analytics pages
- Missing default export in `AnalyticsDashboards.jsx`
- i18n key typos

### 4. Smoke test (manual — use Playwright or just the dev server)

Start both servers (`uvicorn app.main:app --reload` + `npm run dev`), log in as an `admin` or `super_admin` user, and verify:

1. **`/admin/settings`** → page loads with 8 rows. Edit `days_of_cover_target` to `5`, row highlights yellow. Click "Save All" → success, yellow clears, footer shows "Last updated just now by <you>". Then try editing to an invalid value like `0` → backend returns 400, UI should display the error (check this actually works — if not, fix it).
2. **`/admin/users`, `/admin/branches`, `/admin/warehouses`** → each has a red "حذف" / "Delete" button. Click, confirm, row disappears (soft-delete). Error toast on DELETE failure.
3. **`/analytics/consumption-trend`** → branch selector dropdown populates. Select a branch with history → SVG bars visible, hover shows date+qty. Select a branch with no activity → 7 zero bars, no JS error.
4. **`/analytics/order-delay`** → 4 KPI cards render. Top-delayed table shows only branches with ≥3 orders.
5. **`/analytics/branches-open-actions`** → table with progress bars. Red when overdue ratio > 50%, orange 25–50%, green < 25%.
6. **Arabic/English toggle** → all new strings flip correctly, including the 3 new sidebar items under "التحليلات / Analytics".

### 5. Test gap analysis — add coverage if needed

After the above, review the two new test files and identify missing coverage. Specifically look for:

- **Settings:**
  - Test that `value: null` in bulk update is rejected by Pydantic (422)
  - Test that `value: 12345` (int) is accepted/coerced or rejected — decide intent, document it
  - Test that updating one setting then the same setting in the same session reflects latest `updated_by`
- **Consumption trend:**
  - Test that transactions dated in the future (e.g., `now + 2 days`) are excluded (I added the upper-bound filter for this)
  - Test that `days=30` and `days=90` both return the right-sized trend array
- **Order delay:**
  - Test with a branch that has exactly 2 orders — should NOT appear in `top_delayed_branches` (3-sample rule)
  - Test that `warehouse_id` and `branch_id` filters work
- **Branches open actions:**
  - Test timezone edge case: a visit response with `due_date` == today should NOT be counted as overdue (only `< today`)
  - Test that resolving an action (setting `is_resolved=True`) immediately removes it from the count

Add these tests. Keep the same style and helper patterns as the existing test files.

### 6. Cleanup + commit

Run:
```bash
ruff check backend/app/routers/dashboard.py backend/app/routers/settings.py --fix
ruff format backend/app/routers/dashboard.py backend/app/routers/settings.py
```

Then:
```bash
git status
git diff --stat
git add -A
git commit -m "$(cat <<'EOF'
G1–G7: fix 6 audit blockers + add 3 analytics dashboards

- G1: InventoryEntryPage uses real book_qty from /dashboard/branch-stock
- G2: delete buttons on admin pages (users, branches, warehouses)
- G3: Settings CRUD — router, schemas, editable UI with atomic bulk update
- G4: top_requested_items returns item_name_en alongside item_name_ar
- G5: daily consumption trend dashboard per branch
- G6: order-to-receive delay analytics with top-delayed branches
- G7: branches with open corrective actions dashboard

Verified via three independent audit passes (G8/G9) — all production code
pass py_compile; ran full pytest suite (see commits).
EOF
)"
```

Do NOT push. Let me/Islam review first.

## Important guardrails

- **Do not amend prior commits.** Create a new commit for each distinct change.
- **If a test fails and the test looks wrong:** explain why in the commit message, don't just delete the assertion.
- **If you find real bugs in `dashboard.py` or `settings.py` while working:** fix them but keep the fix in a separate commit from test additions.
- **Don't touch `CLAUDE.md` or the `.auto-memory/` directory.**
- **Don't run `npm audit fix`** or upgrade dependencies.
- **If `alembic upgrade head` wants to create a new revision**, stop — something is off; investigate rather than running `alembic revision --autogenerate`.

## Report back

When done, summarize:
1. Pytest pass/fail counts (before and after your fixes)
2. Any production code bugs you found and fixed
3. Any tests you added, with one-line descriptions
4. Any smoke-test failures
5. Whether the commit is ready to push, or if there are open questions

Keep the report under 400 words.
