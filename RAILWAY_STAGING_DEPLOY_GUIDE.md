# Railway staging deploy guide

**Project shape:** split the repo into **three Railway services**:

1. **Postgres**
2. **Backend API**
3. **Frontend SPA**

This guide is specific to the current Raed Inventory repo layout.

---

## 1. Services

### 1.1 Postgres service

Create a Railway PostgreSQL service first.

Use the Railway Postgres template, then let Railway provide:

- `DATABASE_URL`
- `PGHOST`
- `PGPORT`
- `PGUSER`
- `PGPASSWORD`
- `PGDATABASE`

### 1.2 Backend service

Connect the same GitHub repo and configure:

- **Root Directory:** `raed_inventory/backend`
- **Dockerfile path:** `Dockerfile`

The backend container already:

- installs requirements
- runs `alembic upgrade head`
- starts `uvicorn`
- exposes a readiness endpoint at `/api/v1/ready`

### 1.3 Frontend service

Connect the same GitHub repo and configure:

- **Root Directory:** `raed_inventory/frontend`
- **Dockerfile path:** `Dockerfile`

The frontend container now:

- builds with Vite
- serves with nginx
- listens on Railway's runtime `PORT`
- proxies `/api/` to `BACKEND_ORIGIN`

---

## 2. Backend variables

Set these on the **backend** Railway service:

- `ENVIRONMENT=staging`
- `DEBUG=false`
- `SECRET_KEY=<strong-secret>`
- `ALLOWED_ORIGINS=https://<frontend-domain>`
- `ADMIN_PASSWORD=<non-default-admin-password>`
- `PERMISSION_MATRIX_WORKBOOK=/app/raed_user_matrix_permissions.xlsx` only if you place the workbook inside the service image or a mounted path
- `PERMISSION_MATRIX_PASSWORD=Raed@2025` if you want to keep current matrix passwords

For database:

- `DATABASE_URL=${{Postgres.DATABASE_URL}}`

Recommended optional vars:

- `SENTRY_DSN=<value-if-used>`
- `RATE_LIMIT_ENABLED=true`
- `RATE_LIMIT_DEFAULT=200/minute`
- `RATE_LIMIT_AUTH=20/minute`

---

## 3. Frontend variables

Set these on the **frontend** Railway service:

- `PORT=${{PORT}}` (Railway injects this automatically at runtime; setting explicitly is optional)
- `BACKEND_ORIGIN=https://<backend-domain>`

Notes:

- The frontend code uses relative `/api/v1` by default.
- nginx proxies `/api/` to `BACKEND_ORIGIN`.
- The backend domain must be the public Railway backend URL, for example:
  - `https://raed-backend-production.up.railway.app`

---

## 4. Ordered bring-up

After services exist and variables are staged:

1. Deploy **Postgres**
2. Deploy **Backend**
3. Wait for:
   - `GET /api/v1/ready` = `200`
4. Run data/setup commands against the backend service environment in this order:
   - `alembic upgrade head`
   - `python seed_supply_chain_demo.py` only if brands baseline is missing
   - `python seed_official_branches.py`
   - `python finalize_demo_branch_transition.py`
   - `python seed_users_from_permission_matrix.py`
   - `python backfill_kitchen_assignment_service_city.py`
   - `python backfill_official_kitchens.py`
5. Run:
   - `python scripts/verify_matrix_roles_api.py`
6. Deploy **Frontend**
7. Smoke test:
   - `/supply-chain/control`
   - `/supply-chain/warehouse`
   - `/admin/kitchens`

---

## 5. Workbook handling

The one staging-sensitive item is:

- `raed_user_matrix_permissions.xlsx`

Options:

1. Upload/place it where the backend service can read it, then set:
   - `PERMISSION_MATRIX_WORKBOOK=<absolute-path-inside-runtime>`
2. Seed users once from another trusted environment against the Railway database, then skip re-seeding on every deploy

If the workbook path is wrong, the seed script exits with code `1`.

---

## 6. Readiness checks

Use these after backend deploy:

- `GET /health`
- `GET /api/v1/health`
- `GET /api/v1/ready`

The one to trust before frontend traffic is:

- `GET /api/v1/ready`

---

## 7. Manual smoke after deploy

Use these users:

- `super.admin`
- `warehouse_dammam_user`
- `delivery_dammam`

Check:

- `super.admin -> /supply-chain/control`
- `super.admin -> /admin/kitchens`
- `warehouse_dammam_user -> /supply-chain/warehouse`
- `delivery_dammam -> /supply-chain/delivery`

---

## 8. Current repo changes already prepared for Railway

Prepared in code:

- Backend Docker healthcheck now uses:
  - `/api/v1/ready`
- Frontend nginx now supports:
  - Railway dynamic `PORT`
  - backend proxy via `BACKEND_ORIGIN`

Files:

- `raed_inventory/backend/Dockerfile`
- `raed_inventory/frontend/Dockerfile`
- `raed_inventory/frontend/nginx.conf.template`

