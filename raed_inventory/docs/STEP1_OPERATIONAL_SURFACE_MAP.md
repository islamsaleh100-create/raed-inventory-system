# Step 1 — Operational surface map (legacy vs supply-chain V1)

**Baseline:** `CURRENT_VERSION_CLOSEOUT_REPORT.md` (staging-closed current program).  
**Purpose:** Clarify which HTTP/API areas are **primary for the official supply-chain program** vs **legacy / parallel** surfaces, without redesigning navigation.

## Primary (supply-chain V1 — official operational path)

| Area | Router prefix (examples) | Role |
|------|---------------------------|------|
| Branch requests | `/api/v1/branch-requests` | Branch → area approval, split |
| Production (kitchen execution) | `/api/v1/production-orders` | Section-scoped kitchen work |
| Warehouse lines (V1) | `/api/v1/warehouse-lines` | Pick/issue/delay; **`POST .../receive`** acknowledges branch-request lines (`PENDING` → `AVAILABLE`); **`issue`** still allowed from `PENDING` (optional receive) |
| Control center (UI) | `/supply-chain`, `/supply-chain/control` | **`/supply-chain` → redirect to control**; KPIs, **60s auto-refresh**, **queue previews** (≤5 rows), ops **alerts breakdown**; legacy shortcuts labeled below |
| Kitchen admin (UI) | `/admin/kitchens` | **Admin only**: create `Kitchen` + link sections (`POST /api/v1/master/kitchens`) |
| Delivery (V1) | `/api/v1/delivery-orders` | Out-for-delivery / deliver / partial |
| Master — supply-chain master | `/api/v1/master/kitchen-sections`, **`/api/v1/master/kitchens`**, brands, branches, items | Reference data; kitchens are first-class **sites** (city) linked to sections via M2M |

## Secondary / legacy (still in runtime — not the V1 handoff contract)

| Area | Router prefix (examples) | Notes |
|------|---------------------------|-------|
| Replenishment orders | `/api/v1/orders` (and related) | Classic warehouse ↔ branch replenishment model |
| Inventory sessions | `/api/v1/inventory` | Daily inventory / branch counting flows |
| Dashboards | `/api/v1/dashboard/*` | Branch / warehouse / operations KPIs — fragmented vs a future single SC dashboard |
| Procurement (light) | `/api/v1/procurement` | Exists; not the same contract as V1 branch-request fulfillment |
| Sales / delivery analytics | `/api/v1/delivery-analytics`, sales channels | Commercial analytics, not V1 line-level delivery execution |

## Neutral naming

- Prefer **“supply chain V1”** / **“warehouse line”** in new docs and scripts over **“demo”** when describing the official path.
- **`DEMO-WH-1`** remains a legacy warehouse **row** in data; operational branches use city warehouses per closeout report.

## Runtime / health probes

| Endpoint | Use |
|----------|-----|
| `GET /health` | Lightweight liveness (no DB). |
| `GET /api/v1/health` | App metadata + `environment` (no DB). |
| `GET /api/v1/ready` | **Readiness** — runs `SELECT 1` against the configured database; **503** if DB unreachable. Prefer for LB “ready” gates after deploy/migrate. |

## Next Step 1 items (not done in this pass)

- Optional **POST /master/kitchens** (admin CRUD) if product needs UI-managed kitchen sites beyond the backfill script.
- Tighten **production-order ↔ kitchen** filters using `kitchen_id` (today: sections + `service_city` on assignments remain the enforcement layer).
- UX: mark legacy menu entries as secondary (frontend pass — out of scope for this backend Step 1 slice).
