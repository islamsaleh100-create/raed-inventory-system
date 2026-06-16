# LAN Login Single Source Report

**Date:** 2026-06-16  
**Branch:** `release/lan-trial-2026-06-16`  
**Database:** `raed_lan_trial`

---

## Problem Found

The login screen showed **two confusing sections**:

1. «تجربة LAN — حسابات رسمية»
2. «بيانات تجريبية (تطوير فقط)»

The legacy demo section exposed wrong users (`am_riyadh`, `branch.mgr1`, …). The LAN section included **non-trial branches** (`branch_pizza_3_arkan`, `branch_shawarma_4_arkan`, …) instead of the agreed trial branches (Khobar).

---

## Required Accounts Verified

All **14** required accounts exist in `raed_lan_trial`, are **active**, and **login successfully**:

| Username | Role(s) | Scope |
|----------|---------|-------|
| super.admin | super_admin | — |
| admin | admin | — (password: Admin@2025) |
| audit.officer | internal_auditor | — (password: seed default) |
| area_dammam_onda | area_manager | Dammam / Onda |
| area_dammam_restaurants | area_manager | Dammam restaurants |
| branch_onda_1_arkan | branch_user, branch_manager | BR-DM-ON-ARKAN |
| branch_pizza_1_al_khobar | branch_user, branch_manager | BR-DM-RN-KHOBR |
| branch_shawarma_1_khobar | branch_user, branch_manager | BR-DM-SH-KHOBR |
| kitchen_dammam_meat_and_chicken_mgr | kitchen_section_manager | Meat & Chicken |
| kitchen_dammam_bakery_and_sweets_mgr | kitchen_section_manager | Bakery & Sweets |
| kitchen_dammam_pizza_mgr | kitchen_section_manager | Pizza |
| warehouse_dammam_manager | warehouse_manager | WH-DM-1 |
| warehouse_dammam_user | warehouse_user | WH-DM-1 |
| delivery_dammam | delivery_user | WH-DM-1 |

---

## Missing Accounts

**None.** All required accounts present.

Note: `admin` uses `Admin@2025` (not the generic LAN trial password). Quick-login handles this internally without displaying passwords.

---

## UI Changes

- Single config module: `frontend/src/config/lanTrialLoginCards.js` (single source of truth)
- Login page shows **one section only:** «**حسابات تجربة LAN**»
- Notice banner: «استخدم هذه الحسابات فقط في تجربة LAN. لا تستخدم حسابات التطوير القديمة.»
- Cards grouped: إدارة النظام، مدير المنطقة، الفروع التجريبية، المطبخ، المستودع، التوصيل
- Passwords auto-filled on card click but **never displayed**
- Manual login form unchanged

---

## Removed Wrong Cards

Removed legacy demo section and wrong usernames:

- `am_riyadh`, `branch.mgr1`, `wh.mgr1`, `branch.user1`, `qa.mgr`, `ops.mgr`
- `branch_pizza_3_arkan`, `branch_shawarma_4_arkan`
- `area_riyadh_all`, `branch_onda_5_muowasat`, `branch_onda_4_sefarat`
- Entire «بيانات تجريبية (تطوير فقط)» block

---

## Screenshot Path

`outputs/lan_login_clean.png`

Verified: shows «حسابات تجربة LAN»; does **not** show «بيانات تجريبية» or «تطوير فقط».

---

## Test Results

```text
pytest tests/test_lan_login_cards.py — 20 passed
```

Covers: UI source, required usernames, forbidden usernames, login + `/me`, branch/warehouse/kitchen scope.

---

## Final Verdict

### **LAN_LOGIN_READY**

---

*Development-only quick-login cards. Production build hides them via `import.meta.env.DEV`.*
