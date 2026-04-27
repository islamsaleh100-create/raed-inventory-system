# Production hardening plan (next phase)

**Date:** 2026-04-26  
**Last updated:** 2026-04-26  
**Status:** **Backlog / plan** — full operationalization is a **separate project** after staging sign-off. This file groups work by **layer** so infra vs app vs process owners can split tickets without scope creep.

**Baseline context:** `PHASE_PROGRAM_FINAL_CLOSEOUT.md`, `IMPLEMENTATION_GAP_REPORT.md`, `STAGING_HANDOFF_REPORT.md`, `FINAL_PHASE_CLOSEOUT_HANDOFF.md`

---

## 0. What is already in the codebase (not “full hardening”)

- **Logging:** `app/core/logging_config.py` — JSON-oriented logs in staging/production when supported; local human-readable.  
- **Sentry:** `app/core/sentry_init.py` + `SENTRY_DSN` — optional; requires `sentry-sdk` and external project.  
- **Config guards:** `Settings.validate_security()` — blocks weak `SECRET_KEY` pattern in production, `DEBUG` in staging/prod, SQLite URL in staging/prod, default `ADMIN_PASSWORD` in staging/prod.  
- **Rate limits:** slowapi + `RATE_LIMIT_*` env vars.  
- **Health:** `GET /health`, `GET /api/v1/health` (no DB).  
- **Readiness:** `GET /api/v1/ready` — DB `SELECT 1`; **503** if DB down (suitable for LB readiness; **not** a full dependency graph).

---

## 1. Objectives (production phase)

Move from **staging-ready application** to **operated production**: observable, recoverable, rate-safe under real load, with runbooks—**without** mixing large product changes into the same phase.

---

## 2. Backlog by layer

### A. Code / application (repo)

| Item | Status / notes |
|------|----------------|
| Structured log fields | Partially addressed via `logging_config`; optional `pythonjsonlogger` for richer JSON. |
| `/api/v1/ready` | Implemented; extend only if you add critical deps (Redis, queues, etc.). |
| Sentry PII scrubbing / sampling | Review `sentry_init.py` vs your compliance bar. |
| Rate limit tuning | Needs **load test** evidence; code paths exist. |
| Security headers (HSTS, CSP, etc.) | **Not** implemented at app edge — usually reverse proxy / CDN. |

### B. Infrastructure / platform

| Item | Notes |
|------|------|
| Postgres HA, disk, connection limits | Platform choice; not in repo. |
| Automated **backups** + **restore drills** | **No backup scripts in repo** — document RPO/RTO and use managed-DB snapshots or `pg_dump` automation **outside** this codebase (see §5). |
| Object storage for uploads | `UPLOAD_DIR` etc. — migrate to S3-compatible store if multi-instance. |
| TLS termination | LB / ingress. |
| Secrets store | Vault / platform secrets — no secrets in images. |

### C. Operational / process

| Item | Notes |
|------|------|
| Deployment runbook | Build → migrate → optional data scripts (`STAGING_HANDOFF_REPORT.md` order) → `/api/v1/ready` → smoke script. |
| On-call + alerts | Define SLOs; wire to Pager/Opsgenie after metrics exist. |
| Pen test / audit | Schedule against `STEP1_OPERATIONAL_SURFACE_MAP.md` surface. |
| Dependency patch SLAs | `pip audit`, `npm audit`, upgrade windows. |

---

## 3. Monitoring, logging, and errors

| Item | Hardening work |
|------|----------------|
| **Dashboards** | Error rate, latency p95/p99, DB pool saturation. |
| **Alerts** | 5xx spikes, readiness failures, disk. |
| **Sentry** | Set `SENTRY_DSN` in prod; release = git SHA; tune traces. |

---

## 4. Backups and restore

| Item | Hardening work |
|------|----------------|
| **Postgres** | Managed snapshots + PITR or scheduled logical dumps; **quarterly restore test**. |
| **Uploads** | Include in backup scope or replicate object store. |
| **Gap** | **No in-repo backup automation** — treat as **infra deliverable**; do not pretend backups exist without runbooks. |

---

## 5. Health and readiness (staging vs production)

| Endpoint | Role |
|----------|------|
| `/health`, `/api/v1/health` | Liveness / shallow health (no DB). |
| `/api/v1/ready` | Readiness — DB connectivity only. |

**Remaining (optional later):** split “deep” checks (migrations version, disk space) if the platform requires them; keep liveness cheap.

---

## 6. Rate limits under load

Load-test login and hot APIs; tune `RATE_LIMIT_DEFAULT` / `RATE_LIMIT_AUTH`; consider authenticated per-user caps for abuse scenarios.

---

## 7. Security tightening

Rotate secrets; production-only CORS; dependency audits; auth policy review (lockout, password rules); edge security headers at proxy.

---

## 8. Deployment runbook (outline)

1. Prereqs: Python/Node versions, `ENV_FILE` / secrets.  
2. Build backend artifact + frontend `dist/`.  
3. `alembic upgrade head`.  
4. Data scripts per `STAGING_HANDOFF_REPORT.md` (first cut vs delta).  
5. Start app; gate traffic on **`/api/v1/ready` = 200**.  
6. `verify_matrix_roles_api.py` (point `VERIFY_API_BASE` at new URL).  
7. Mark Sentry release if enabled.

---

## 9. Operational recovery

| Scenario | Expectation |
|----------|-------------|
| Bad deploy | Roll back image; forward-fix migrations with DBA. |
| Migration failure | Stop traffic; restore DB snapshot; fix migration. |
| Key compromise | Rotate `SECRET_KEY` (invalidates JWTs); rotate DB password. |

---

## 10. Required before *real* production (checklist)

- [ ] Strong `SECRET_KEY`, non-default admin password, Postgres-only `DATABASE_URL`.  
- [ ] Backups + **documented and tested** restore path.  
- [ ] Monitoring/alerts on errors and readiness.  
- [ ] Load-tested rate limits and connection pool sizing.  
- [ ] Security review / pen test per risk appetite.  
- [ ] Runbook signed off by on-call owner.
