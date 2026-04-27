# Raed Supply Chain System — Implementation Gap Report

**Date:** 2026-04-26  
**Baseline (closed current program):** `CURRENT_VERSION_CLOSEOUT_REPORT.md`  
**Official users/scopes reference:** `PERMISSION_MATRIX_IMPLEMENTATION_REPORT.md`  
**Target:** User-provided production blueprint (alignment phases, not a single drop).

**Execution closeout (DB + UI + Step 2 start):** see `STEP1_STEP2_EXECUTION_CLOSEOUT.md` (2026-04-26).  
**Phase program final (Step 2 finished):** see `PHASE_PROGRAM_FINAL_CLOSEOUT.md` (2026-04-26).

---

## 1. Overall verdict

The current system is **no longer demo-only**. It is a **stabilized operational baseline** suitable for **staging handoff**. It is **not identical** to the blueprint: the correct reading is **stable / seeded / scoped / testable** today vs a **cleaner, more productized** target tomorrow. The next phase is **alignment work**, not rescue work.

---

## 2. Current architecture vs blueprint (summary)

| Theme | Status |
|-------|--------|
| PostgreSQL, official branches, matrix users, area/kitchen section assignments | Strong |
| Warehouse by city, delivery by `warehouse_id` proxy | Strong in practice |
| Branch request → approve → auto split → kitchen → warehouse → delivery | Strong |
| Branch employees, partial delivery, kitchen material requests | Strong |
| Kitchen-by-city, delivery-by-city (territory), unified smart dashboard | Partial vs blueprint |
| First-class **Kitchen** entity (blueprint) | Was partial — **Step 1 (this document) adds `Kitchen` + links** |
| Full production ops (monitoring, backups, deployment posture) | Out of scope for application alignment |

---

## 3. ERD / API / UI gaps (condensed)

- **Users / branches / items / branch requests / production / warehouse lines / delivery:** Richer than or aligned with the blueprint; see prior gap narrative in program chat.
- **Kitchens:** Blueprint wants `Kitchen(name, city, active)` + sections under kitchen. **Runtime was section-first** with `KitchenSectionAssignment.service_city`. **Step 1 adds** `kitchens` + `kitchen_kitchen_sections` M2M so sections remain shared for **items**, while **kitchen sites** exist for reporting and future tightening.
- **Warehouse receive:** Blueprint expects an explicit receive step. **Step 1 adds** `POST /api/v1/warehouse-lines/{id}/receive` for **BRANCH_REQUEST** lines (`PENDING` → `AVAILABLE`); **`issue` remains valid from `PENDING`** (backward compatible). Kitchen-output lines treat `receive` as **idempotent** where already in fulfillable states.
- **Dashboard / procurement:** Still fragmented vs blueprint; **Step 2** work — not started here.

---

## 4. Step 1 execution record (2026-04-26) — Core system alignment

### 4.1 Kitchen model clarification

- **Added** ORM model **`Kitchen`** (`kitchens`: id, name, city, active, created_at).
- **Added** association table **`kitchen_kitchen_sections`** (M2M between kitchens and existing `KitchenSection` rows).
- **Reason:** Items and production orders still reference **`kitchen_section_id`** globally; duplicating sections per city would break the item master. M2M matches **“shared sections, multiple kitchen sites”**.
- **API:** `GET /api/v1/master/kitchens` returns kitchens with `section_ids`. `GET /api/v1/master/kitchen-sections` now includes **`kitchen_ids`** on each section (empty until backfill).
- **Data:** Script **`backend/backfill_official_kitchens.py`** creates **Official Kitchen — Dammam** / **Riyadh** and links **all active sections** to both (idempotent). Run after migration.
- **Migration:** `alembic` revision **`z6a7b8c9d0e1`** (`20260426_0032_..._kitchens_and_kitchen_section_links.py`).

### 4.2 Warehouse receive contract

- **`POST /api/v1/warehouse-lines/{line_id}/receive`** with idempotency key support (same helper as other supply-chain mutations when key present).
- **Semantics:** Documented in router docstring; tests cover **receive → receive (idempotent) → issue → receive fails**.

### 4.3 Legacy vs current operational surfaces

- **Document:** `raed_inventory/docs/STEP1_OPERATIONAL_SURFACE_MAP.md` lists **primary V1 routes** vs **legacy/parallel** areas (replenishment orders, inventory, old dashboards, procurement).

---

## 5. Verification

- `pytest` `tests/test_supply_chain_phase1_branch_requests.py` + `tests/test_branch_employees.py`: **71 passed** (includes 2 new tests).

---

## 6. Files touched (Step 1 slice)

- `raed_inventory/backend/app/models/__init__.py` — `Kitchen`, M2M, `kitchen_ids` / `section_ids` helpers.
- `raed_inventory/backend/alembic/versions/20260426_0032_z6a7b8c9d0e1_kitchens_and_kitchen_section_links.py`
- `raed_inventory/backend/backfill_official_kitchens.py`
- `raed_inventory/backend/app/schemas/__init__.py` — `KitchenOut`, `KitchenSectionOut.kitchen_ids`
- `raed_inventory/backend/app/routers/master.py` — `GET /kitchens`, joined loads.
- `raed_inventory/backend/app/routers/warehouse_lines.py` — `POST .../receive`
- `raed_inventory/backend/tests/test_supply_chain_phase1_branch_requests.py` — new tests.
- `raed_inventory/docs/STEP1_OPERATIONAL_SURFACE_MAP.md`
- `IMPLEMENTATION_GAP_REPORT.md` (this file)

---

## 7. What remains inside Step 1 (next slices)

1. **Wire `kitchen_id` (optional)** into production-order scoping or admin UX — only after product confirms whether visibility is **site** vs **section+city** (avoid double rules).
2. **`POST /master/kitchens`** (admin) if kitchen rows must be editable without SQL/script.
3. **Require `receive` before `issue`** (breaking change) — only if stakeholders agree; today **optional** receive step.
4. **Rename / soft-hide** legacy menu entries in the frontend using the operational map (bounded UI pass).

---

## 8. تقرير تنفيذي (عربي) — ماذا وجدنا، ماذا غيّرنا، ماذا بقي، والخطوة التالية

### ماذا وجدنا

- الفجوة الجوهرية مقارنة بالـ blueprint: لا يوجد كيان **`Kitchen`** واضح في الـ ERD، بينما **`KitchenSection` + التعيينات + `service_city`** يشغّل التشغيل فعلياً.
- فجوة العقد في الـ API: مسار **استلام/إقرار** سطر المستودع (`receive`) غير معرّف كخطوة أولى للـ **branch-request warehouse lines** رغم وجود `issue` / `partial-issue`.
- فجوة وضوح المنتج: لوحات **قديمة** (طلبات التوريد، الجرد، dashboards عامة) ما زالت بجانب مسار **Supply Chain V1** دون خريطة رسمية للمستهلك.

### ماذا غيّرنا (تنفيذ محدود Step 1)

- أضفنا جداول **`kitchens`** و **`kitchen_kitchen_sections`** وربط M2M مع **`kitchen_sections`** مع الإبقاء على **`kitchen_section_id`** في الأصناف وأوامر الإنتاج لتجنّب كسر البيانات.
- أضفنا **`GET /api/v1/master/kitchens`** و **`kitchen_ids`** في استجابة **`kitchen-sections`**.
- أضفنا **`POST /api/v1/warehouse-lines/{id}/receive`** لخط سير **BRANCH_REQUEST** مع بقاء **`issue` يعمل من `PENDING`** كما كان.
- أضفنا سكربت **`backfill_official_kitchens.py`** ووثيقة **`STEP1_OPERATIONAL_SURFACE_MAP.md`** لتمييز المسارات الرسمية عن الموروث.

### ماذا بقي

- دمج **اختياري** لـ `kitchen` في فلاتر أو واجهات الإنتاج (قرار منتج لتجنب ازدواج مع `service_city`).
- CRUD مطبخ في الـ master API إذا لزم الإدارة من الواجهة.
- جعل **`receive` إلزامياً قبل `issue`** إن رُفع ذلك كقرار تشغيل (Breaking).
- تحسينات UI لترتيب القوائم (خارج نطاق هذا الـ slice الخلفي).

### الخطوة التالية داخل Step 1

1. تشغيل **`alembic upgrade head`** ثم **`python backfill_official_kitchens.py`** على بيئة staging/محلية.  
2. مراجعة منتجية: هل **Kitchen site** يكفي كمرجع تقارير، أم نريد ربط صريح بأوامر الإنتاج؟  
3. تنفيذ **واحد** من بنود القسم 7 أعلاه حسب الأولوية — دون فتح Step 2 (dashboard موحّد).
