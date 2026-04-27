# Railway Deployment — Raed Inventory System

Complete walkthrough for deploying the FastAPI backend to Railway.
Frontend deployment is covered at the bottom (separate service).

---

## Prerequisites

- Railway account (you said you already have one)
- The project pushed to a GitHub repo (Railway pulls from GitHub)
- About 15–20 minutes

---

## Step 1 — Push the project to GitHub

If the project isn't on GitHub yet, do this from your local machine:

```bash
cd C:\raed_inventory_system\raed_inventory
git init
git add .
git commit -m "Initial commit for Railway deployment"
# Create a new EMPTY repo on github.com first, then:
git remote add origin https://github.com/<your-username>/raed-inventory.git
git branch -M main
git push -u origin main
```

If it's already on GitHub, skip this step.

---

## Step 2 — Create a Railway project

1. Open https://railway.app/dashboard
2. Click **New Project** → **Deploy from GitHub repo**
3. Pick the `raed-inventory` repo
4. Railway will auto-detect the Dockerfile

**IMPORTANT:** Right after creating, click on the service → **Settings** →
**Root Directory** → set it to `backend`. This tells Railway to look at
`backend/Dockerfile` instead of the project root.

---

## Step 3 — Add a Postgres database (recommended)

Why: SQLite breaks on Railway because containers restart and wipe local
files. Use Postgres for a stable demo.

1. In your Railway project, click **+ New** → **Database** → **PostgreSQL**
2. Wait ~30 seconds for it to provision
3. Click on your **backend service** (not the database)
4. Go to **Variables** tab
5. Click **+ New Variable** → **Add Reference** → select the Postgres
   service → pick `DATABASE_URL`. This automatically wires the backend
   to the database.

---

## Step 4 — Set required environment variables

In the backend service → **Variables** tab, add these:

| Variable | Value | Notes |
|----------|-------|-------|
| `SECRET_KEY` | (any random 32+ char string) | Used to sign JWT tokens. Generate one with `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `ENVIRONMENT` | `production` | Disables some dev-only behaviors |
| `ALLOWED_ORIGINS` | `https://<your-frontend-url>.up.railway.app` | Update after deploying the frontend |
| `ADMIN_PASSWORD` | `Raed@2025` (or your choice) | Initial admin password — change it after first login |
| `DEBUG` | `false` | Don't leak stack traces |

You don't need to set `PORT` — Railway injects it automatically.
You don't need to set `DATABASE_URL` if you used the reference button in Step 3.

---

## Step 5 — Deploy

Railway should auto-deploy when you push to `main`. The first build takes
3–5 minutes. Watch logs in the **Deployments** tab.

If the deploy fails:
- Check that the **Root Directory** is `backend`
- Check that `DATABASE_URL` resolves (it should auto-populate from the
  Postgres reference)
- Check the build log for missing dependencies

---

## Step 6 — Get your URL

1. Once deployed, go to **Settings** → **Networking** → **Generate Domain**
2. Railway will give you something like
   `https://raed-inventory-production-XXXX.up.railway.app`
3. Test it: visit `https://your-url.up.railway.app/health` — should return
   `{"status":"healthy"}`

---

## Step 7 — Seed the demo data

Open the Railway service → **Logs** tab (or use the Railway CLI). Run:

```bash
# Via Railway CLI (one-time):
railway run python seed_supply_chain_demo.py
```

Or use the Railway dashboard's **shell** feature if available.

You should see all 4 brands, 3 kitchen sections, demo users, branches,
items, and stock get created.

---

## Step 8 — Frontend (separate service)

The Vite frontend is a separate static site. Two options:

### Option A — Deploy frontend to Railway as a second service

1. **+ New** → **GitHub repo** → same repo
2. **Root Directory:** `frontend`
3. Add env var:
   - `VITE_API_BASE_URL` = `https://<your-backend-url>.up.railway.app/api/v1`
4. Add a start command (if Railway can't auto-detect Vite):
   - **Build:** `npm install && npm run build`
   - **Start:** `npx serve dist -l ${PORT:-3000}`
5. Generate a domain. Update `ALLOWED_ORIGINS` on the backend to include this URL.

### Option B — Deploy frontend to Vercel/Netlify (easier for Vite)

Vercel auto-detects Vite. Just connect the repo, set Root Directory to
`frontend`, and add `VITE_API_BASE_URL` env var pointing to your Railway
backend.

---

## Common issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| Build fails with "no such file Dockerfile" | Wrong Root Directory | Settings → Root Directory = `backend` |
| `psycopg2` import error | Postgres binary not installed | Already handled — `requirements.txt` has `psycopg2-binary` |
| `alembic upgrade head` fails | DB connection refused | Check `DATABASE_URL` reference in Variables |
| 500 on every endpoint | Missing `SECRET_KEY` | Set `SECRET_KEY` env var (32+ chars) |
| CORS error in browser | Frontend URL not whitelisted | Add frontend URL to `ALLOWED_ORIGINS` |
| Health check fails | App not responding on $PORT | Check logs; `start_command` must use `$PORT` |

---

## Security checklist before shipping

- [ ] `SECRET_KEY` is set to a strong random value (NOT the default)
- [ ] `ADMIN_PASSWORD` is set; change it on first login
- [ ] `ENVIRONMENT=production`
- [ ] `DEBUG=false`
- [ ] `ALLOWED_ORIGINS` only lists your real frontend URL(s)
- [ ] Postgres has a non-default password (Railway handles this)
- [ ] After first login, rotate the admin password via the Users page

---

## What to do AFTER deployment

The system audit (system_audit_2026-04-25.md) flagged ~5 critical issues
that you should address before letting real users (>1 concurrent) use
production. The most urgent:

1. Stock locking races (warehouse_lines.py:88-115)
2. Reserved-qty release on issue/partial-issue
3. Approve/auto-split race condition handling
4. Frontend route-level RBAC hardening
5. Idempotency on key endpoints (X-Idempotency-Key)

For a demo or single-user trial, you can ship now. For multi-user
production, finish Sprint 2 first.
