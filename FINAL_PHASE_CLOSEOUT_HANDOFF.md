# Final phase closeout — master handoff index

**Date:** 2026-04-26  
**Audience:** Staging operators, then the **production-hardening** phase owner.

**→ Start here:** read **§1** below, then open **`STAGING_HANDOFF_REPORT.md`** for ordered bring-up and **`PRODUCTION_HARDENING_PLAN.md`** for what must still happen before real production.

This file **indexes** other reports; it does not duplicate step-by-step DB commands.

---

## 1. Reading order (recommended)

| Order | Document | Why |
|-------|----------|-----|
| 1 | **`STAGING_HANDOFF_REPORT.md`** | Env vars, **required vs optional** scripts, order, failures, health/ready, verification checklist. |
| 2 | **`raed_inventory/backend/.env.example`** | Copy/paste env names + numbered DB commands (same order as staging report). |
| 3 | **`raed_inventory/docs/STEP1_OPERATIONAL_SURFACE_MAP.md`** | Which URLs/APIs are the official supply-chain path (control center, receive, kitchens admin). |
| 4 | **`CURRENT_VERSION_CLOSEOUT_REPORT.md`** | What was verified in the last program pass (pytest counts, role probes). |
| 5 | **`PRODUCTION_HARDENING_PLAN.md`** | **Next phase only** — monitoring, backups, security, runbooks; split **code / infra / ops**. |
| 6 | **`IMPLEMENTATION_GAP_REPORT.md`** | Blueprint deltas / future product work — **not** blocking staging if out of scope. |

**Historical / evidence (read if auditing past work):**  
`PHASE_PROGRAM_FINAL_CLOSEOUT.md`, `STEP1_STEP2_EXECUTION_CLOSEOUT.md`, `PERMISSION_MATRIX_IMPLEMENTATION_REPORT.md`, `DEMO_LAUNCH_CHECKLIST.md` (legacy demo users — see disclaimer there).

---

## 2. Codebase pointers (quick)

| Need | Location |
|------|----------|
| Matrix user seed | `seed_users_from_permission_matrix.py` — `PERMISSION_MATRIX_WORKBOOK` (**required** on staging), `PERMISSION_MATRIX_PASSWORD` (optional). |
| API smoke | `raed_inventory/backend/scripts/verify_matrix_roles_api.py` — `VERIFY_API_BASE`, `VERIFY_API_PASSWORD`, `VERIFY_LOGIN_DELAY_S`. |
| Readiness | `GET /api/v1/ready` — DB check; use after migrate/deploy. |
| Sample staging env | `raed_inventory/backend/.env.staging` (template only; no real secrets). |

---

## 3. What is complete vs deferred

| Status | Scope |
|--------|--------|
| **Complete (program)** | PostgreSQL path, official branches, demo deactivation path, matrix seed + backfills, control center / warehouse receive / kitchens admin, automated tests + build + API smoke patterns, **staging handoff docs**, **readiness endpoint**, matrix workbook/password env handling. |
| **Ready for staging workflow** | App + scripts + docs; operators still run **real** staging DB steps and **browser** smoke on deployed URL. |
| **Not production-certified** | Backups, full observability, load tuning, pen test, multi-instance uploads — see **`PRODUCTION_HARDENING_PLAN.md` §10**. |

---

## 4. Recommended next actions

1. Run **`STAGING_HANDOFF_REPORT.md`** §7 checklist on the **real** staging database and host.  
2. Confirm **`/api/v1/ready`** returns **200** before sending user traffic.  
3. One **manual browser** smoke on staging (control center, receive, kitchens admin).  
4. Open the **production-hardening** project from **`PRODUCTION_HARDENING_PLAN.md`**; keep product roadmap items in **`IMPLEMENTATION_GAP_REPORT.md`** separate.
