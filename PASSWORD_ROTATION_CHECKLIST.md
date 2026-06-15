# Password Rotation Checklist — Mandatory Before LAN Trial

**Phase 9 audits passwords. Phase 9 does NOT rotate passwords.**

Password rotation is a **Mandatory Operator Action** before LAN Trial begins.

---

## Known default / demo credentials (from phase reports)

| Credential | Source | Location |
|------------|--------|----------|
| `Raed@Demo2026` | Phase 2 official users default | `seed_phase2_official_users.py` (`PHASE2_DEMO_PASSWORD`) |
| `Raed@2025` | Supply chain demo seed | `seed_supply_chain_demo.py` |
| `Admin@2025` | Base seed + deployment admin bootstrap | `seed.py`, `deployment_admin_service.py` |
| `Raed@2025` | Internal auditor bootstrap | `deployment_internal_auditor_service.py` |

---

## Pre-LAN Trial checklist

Complete every item. Record date, operator initials, and evidence in your runbook.

### A. Environment secrets

- [ ] **`PHASE2_DEMO_PASSWORD`** set to a strong operator-chosen value (not `Raed@Demo2026`)
- [ ] **`ADMIN_PASSWORD`** env set if deployment bootstrap is used (not default `Admin@2025`)
- [ ] **`INTERNAL_AUDITOR_PASSWORD`** env set if auditor bootstrap is used
- [ ] LAN `.env` file **not** committed to git
- [ ] LAN `.env` file permissions restricted to service account only

### B. Database user passwords

- [ ] PostgreSQL `lan_user` (or equivalent) uses strong password
- [ ] `DATABASE_URL` password rotated from any dev/shared value
- [ ] No shared dev database credentials reused on LAN host

### C. Application user passwords (post-seed)

After running seeds on **fresh LAN trial DB**:

- [ ] Run `seed_phase2_official_users.py` with new `PHASE2_DEMO_PASSWORD`
- [ ] Start API once; note if deployment bootstrap resets `admin`
- [ ] Re-run `seed_phase2_official_users.py` **after** API startup if bootstrap ran (`USER_SCOPE_MATRIX_REPORT.md`)
- [ ] Verify login with **new** password for sample users (branch, area, kitchen, warehouse, delivery)
- [ ] Confirm `admin` / `super.admin` passwords are known only to operators (not demo defaults)

### D. Demo / bootstrap accounts

- [ ] **`admin`** — password changed from `Admin@2025` or bootstrap default
- [ ] **`super.admin`** — uses Phase 2 demo password env, not factory default
- [ ] **`audit.officer`** — auditor bootstrap password rotated if account is enabled
- [ ] Legacy demo users (`branch.user1`, `am_riyadh`, etc.) — **disabled or not seeded** on LAN trial DB

### E. Frontend / client exposure

- [ ] No demo password hints in production/LAN frontend builds
- [ ] `LoginPage.jsx` dev-only password hint acceptable for local demo only (`USER_SCOPE_MATRIX_REPORT.md`)
- [ ] No credentials in browser localStorage except JWT after login (C-01 accepted risk for LAN)

### F. Operational verification

- [ ] Password list stored in operator secure vault (not chat, not repo)
- [ ] Trial operators briefed: do not share accounts
- [ ] Rate limiting policy decided for multi-user LAN sessions (`RATE_LIMIT_ENABLED` local shell only for bulk tests)

---

## Verification commands (operator)

After rotation, from LAN host:

```powershell
# Must fail with old demo password
curl -X POST http://localhost:8010/api/v1/auth/login `
  -H "Content-Type: application/json" `
  -d '{"username":"branch_onda_1_arkan","password":"Raed@Demo2026"}'

# Must succeed with new password
curl -X POST http://localhost:8010/api/v1/auth/login `
  -H "Content-Type: application/json" `
  -d '{"username":"branch_onda_1_arkan","password":"<NEW_PASSWORD>"}'
```

Repeat spot-check for one user per role class.

---

## Production additional requirements (not LAN)

Production requires all LAN items **plus**:

- [ ] C-01 JWT storage remediation (httpOnly cookies or equivalent) — **production blocker**
- [ ] Remove all hardcoded bootstrap password resets on startup
- [ ] Secrets manager / vault integration for all service credentials
- [ ] Password rotation policy and audit trail

---

## Phase 9 audit status

| Check | Audit result |
|-------|--------------|
| Demo passwords documented | **PASS** — sources identified in reports |
| Bootstrap passwords documented | **PASS** — `USER_SCOPE_MATRIX`, `RBAC_SECURITY`, `ENVIRONMENT_READY` |
| Passwords rotated for LAN | **NOT VERIFIED** — operator action pending |
| Known credentials eliminated | **FAIL until operator completes checklist** |

---

*Mandatory operator action before LAN Trial. Phase 9 does not rotate passwords automatically.*
