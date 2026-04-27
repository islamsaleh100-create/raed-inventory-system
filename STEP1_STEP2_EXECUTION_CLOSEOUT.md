# Step 1 closure + Step 2 start — execution closeout

**Date:** 2026-04-26  
**Baseline:** `CURRENT_VERSION_CLOSEOUT_REPORT.md`  
**Matrix reference:** `PERMISSION_MATRIX_IMPLEMENTATION_REPORT.md`  
**Gap / alignment doc:** `IMPLEMENTATION_GAP_REPORT.md`  
**Operational map:** `raed_inventory/docs/STEP1_OPERATIONAL_SURFACE_MAP.md`

---

## 1) What was closed in Step 1 (this execution)

| Item | Evidence |
|------|-----------|
| **Alembic to head** on local PostgreSQL (`.env`) | Ran `alembic upgrade head`; applied `y5z6a7b8c9d0` (service_city) and `z6a7b8c9d0e1` (kitchens + M2M). |
| **`backfill_official_kitchens.py`** | Ran successfully: `kitchens_upserted=2`, `section_links_added_this_run=6`, `sections_total=3`. |
| **DB verification** | `SELECT count(*)`: `kitchens = 2`, `kitchen_kitchen_sections = 6`. |
| **UI / runtime alignment (light)** | Supply Chain sidebar: **Control center** first; `operations_manager` can open Supply Chain section to reach control + ops alerts; nav active state fixed so `/supply-chain/control` does not highlight other SC routes. |
| **Operational surfaces doc** | `STEP1_OPERATIONAL_SURFACE_MAP.md` updated with `/supply-chain/control` and receive semantics. |

Step 1 **code** (Kitchen + receive + tests) was already merged earlier; this pass **closed the operational loop** on a real Postgres DB and shipped the **navigation / surface** alignment.

---

## 2) What was started in Step 2 (bounded, no wide redesign)

| Item | What shipped |
|------|----------------|
| **Dashboard layer** | New route **`/supply-chain/control`** — `SupplyChainControlDashboard`: role-aware **KPI cards** fed from existing APIs (`branch-requests`, `production-orders`, `warehouse-lines`, `delivery-orders/ready`, `dashboard/alerts-summary`, `master/kitchens`). |
| **KPI layer** | Counts only (totals / list lengths); links to existing queue pages (`approvals`, `kitchen`, `warehouse`, `delivery`, `operations`). |
| **Alerts layer** | Reuses **`GET /api/v1/dashboard/alerts-summary`** for `operations_manager` / admin (legacy ops aggregate — explicitly labeled on the page). |
| **Queue widgets** | Implemented as **summary cards + deep links**, not duplicate tables (avoids redesign and drift). |

**Not started (explicitly out of scope for this slice):** production hardening, Railway, unified replacement of `/dashboard`, procurement depth, requiring `receive` before `issue`.

---

## 3) What remains

### Step 1 follow-ups (optional)

- **`POST /master/kitchens`** CRUD if kitchens must be edited from UI.  
- **Require `receive` before `issue`** if stakeholders want a strict workflow (breaking).  
- **Production scoping by `kitchen_id`** after product rules (avoid double rules with `service_city`).

### Step 2 follow-ups

- **Real-time / polling** on control center (optional).  
- **Dedicated queue tables** on the same page (would duplicate warehouse/kitchen UIs — defer).  
- **Role-specific layout presets** (area vs warehouse) — cosmetic.  
- **Wire `receiveWarehouseLine` in warehouse UI** when product wants the button (API client already has `receiveWarehouseLine`).

---

## 4) Files changed (this execution)

| Path |
|------|
| `raed_inventory/frontend/src/services/api.js` — `listKitchens`, `receiveWarehouseLine` |
| `raed_inventory/frontend/src/pages/supply_chain/SupplyChainPages.jsx` — `SupplyChainControlDashboard`, `KpiCard` |
| `raed_inventory/frontend/src/App.jsx` — route `/supply-chain/control` |
| `raed_inventory/frontend/src/components/layout/AppLayoutV2.jsx` — nav item + `operations_manager` on supply chain section + nav active fix |
| `raed_inventory/frontend/src/i18n/dict/en.json` — `nav.supply_chain_control`, `supply_chain_control_page.*` |
| `raed_inventory/frontend/src/i18n/dict/ar.json` — same |
| `raed_inventory/docs/STEP1_OPERATIONAL_SURFACE_MAP.md` — control center row |
| `STEP1_STEP2_EXECUTION_CLOSEOUT.md` — this report |

*(Step 1 schema/code from the prior slice: models, alembic `20260426_0032_*`, `warehouse_lines.receive`, `backfill_official_kitchens.py`, tests — unchanged in this diff batch except docs/i18n/API client.)*

---

## 5) Verification commands (for staging repeat)

```text
set ENV_FILE=.env
python -m alembic upgrade head
python backfill_official_kitchens.py
pytest tests/test_supply_chain_phase1_branch_requests.py tests/test_branch_employees.py -q
npm run build   # in raed_inventory/frontend
```

---

## 6) Short Arabic summary

- **أُقفل Step 1 تشغيلياً:** ترحيل قاعدة البيانات، تشغيل سكربت المطابخ، والتحقق من أعداد الجداول، وتمريرة تنقل خفيفة في الواجهة.  
- **بدأ Step 2 بحدود آمنة:** صفحة **`/supply-chain/control`** تعرض بطاقات مؤشرات وطوابير مرتبطة بمسار V1 مع روابط للصفحات الحالية، وتنبيهات العمليات للأدوار المخولة، مع صندوق يوضح المسارات الموروثة.  
- **المتبقي:** تعميق Step 2 (تحديث تلقائي، جداول طوابير مدمجة)، واختيارات Step 1 الاختيارية أعلاه، **دون** فتح production hardening الآن.
