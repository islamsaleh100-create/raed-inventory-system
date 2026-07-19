# PAGE 02 — Create Supply Request

| Field | Value |
|---|---|
| Page ID | PAGE 02 |
| Current route | `/supply-chain/branch-requests` (inline — **no dedicated create route**) |
| Target candidate route | `/supply-chain/branch-requests/new` (menu design — **not implemented**) |
| Review date | 2026-07-13 |
| Mode | READ-ONLY REVIEW |
| Database verified | `localhost:5432/raed_inventory` |
| Git branch | `release/lan-trial-2026-06-16` @ `8a971a0` |
| **Final status** | **DISCUSSION_REQUIRED** |
| **Recommendation** | **REBUILD as dedicated 3-step wizard page** — unify branch + admin flows; remove legacy source picker from target UI |

Evidence: `PAGE_SPEC_EVIDENCE/PAGE_02/` (`_capture_meta.json`, `api_probe_meta.json`, `_test_data_manifest.json`, 22 PNG)

```text
PAGE 02 REVIEW: COMPLETE
PAGE 02 DESIGN: DISCUSSION_REQUIRED
PAGE 02 IMPLEMENTATION: NOT AUTHORIZED
PAGE 03: NOT AUTHORIZED
```

---

## 1. Page purpose and primary role

**Purpose:** Allow authorized branch roles (and elevated admins) to compose a new branch supply request — select branch context (where applicable), choose requestable items with quantities, optionally save as **DRAFT**, and **submit for Area Manager approval** (PD-02). No Kitchen/Warehouse path selection by the requester (PD-01).

**Primary actors today:**

| Actor | Current UI | Backend POST |
|---|---|---|
| `branch_user` / `branch_manager` | Inline **catalog form** on PAGE 01 | ✅ Allowed (own branch) |
| `admin` / `super_admin` | **No create UI** (code gate) | ✅ Allowed (any branch via API) |
| All others | No create UI / route denied | ❌ 403 on POST |

**Conflict with PAGE 01 assumption:** PAGE 01 documented admin legacy inline form; runtime code sets `canCreateRequest` only for `branch_user` \| `branch_manager` — **admin/super_admin legacy form is dead code** in current frontend.

---

## 2. Preflight

| Check | Result |
|---|---|
| Git branch | `release/lan-trial-2026-06-16` ✅ |
| HEAD | `8a971a0` (PAGE 01 commit) ✅ |
| Frontend `:3000` | HTTP 200 ✅ |
| Backend `:8010` | HTTP 200 ✅ |
| `DATABASE_URL` | `localhost:5432/raed_inventory` ✅ |
| `raed_lan_trial` / remote DB | **Not detected** ✅ |
| PAGE 01 in index | **APPROVED** ✅ |
| PAGE 02 prior status | NOT_STARTED → **IN_REVIEW** (index updated, not committed) |
| Application code modified | **No** — review artifacts only |

```bash
git branch --show-current   # release/lan-trial-2026-06-16
git rev-parse HEAD          # 8a971a0407fce56b2cd909063a8d7910bd0500e4
```

Working tree contains many unrelated tracked modifications — **preserved, not touched**.

---

## 3. Allowed and denied roles

### 3.1 Role / action matrix

| Role | Browser create UI | Route `/branch-requests` | Route `/branch-requests/new` | POST create | POST submit |
|---|---|---|---|---|---|
| `branch_user` | Catalog inline ✅ | ✅ | ❌ no route | ✅ own branch | ✅ own DRAFT |
| `branch_manager` | Catalog inline ✅ (CODE VERIFIED — dual-role account `branch_onda_1_arkan`; no dedicated-only account) | ✅ | ❌ | ✅ own branch | ✅ |
| `admin` | **❌ hidden** | ✅ list only | ❌ | ✅ any branch (API) | ✅ |
| `super_admin` | **❌ hidden** | ✅ list only | ❌ | ✅ (API) | ✅ |
| `area_manager` | ❌ | ✅ read list | ❌ | **403** `branch_write_denied` | **403** |
| `internal_auditor` | ❌ + ReadOnlyBanner | ✅ read | ❌ | **403** read-only | **403** |
| `operations_manager` | ❌ | — | — | **Not tested** — no account (OP-BR-01) | — |
| `kitchen_section_manager` | ❌ | Nav excluded | ❌ | **403** role tuple | — |
| `warehouse_user` | ❌ | Nav excluded | ❌ | **403** role tuple | — |
| `delivery_user` | ❌ | Nav excluded | ❌ | **403** role tuple | — |

### 3.2 Object-level scope

- **Branch roles:** `branch_id` fixed to `user.branch_id`; spoofing other branch → **403** `branch_requests.branch_write_denied` (verified).
- **Admin:** `_require_branch_write` bypasses branch ownership; must pass `_branch_brand_allowed` + active branch/item checks.
- **Creator:** `created_by = current_user.id` from auth — not from payload ✅

---

## 4. Current vs target navigation / entry

### Current

| Step | Branch user (`branch_pizza_1_al_khobar`) |
|---|---|
| Login | `/login` |
| Nav | سلسلة الإمداد → **طلبات الفروع** (1 click) |
| Form | Same URL — catalog panel left of list (**no scroll-to-create CTA**) |
| Clicks to form | **2** (login → nav item) |
| Back/cancel | Browser back only — **no unsaved-change warning** |
| List filters | Not preserved in URL — **lost on full navigation** |

**Create action label (branch):** **إرسال الطلب** — single button; **no حفظ مسودة** in catalog form.

**Admin:** No visible create entry — must use API or future PAGE 02 page.

### Target (candidate — for discussion)

| Element | Proposal |
|---|---|
| Route | `/supply-chain/branch-requests/new` |
| PAGE 01 CTA | **+ إنشاء طلب توريد** → navigates to PAGE 02 |
| Back | Returns to PAGE 01 preserving list filter state (query params) |
| Cancel | Confirm dialog if form dirty |

---

## 5. Current fields vs target fields

### 5.1 Field matrix

| Field | Catalog form (branch) | Legacy form (unreachable for admin) | Target (PD-01/02) |
|---|---|---|---|
| Branch | Read-only display | Select (admin path) | Branch fixed / admin picker |
| Brand | Tab if multi-brand | Select dropdown | Derived or explicit |
| Request type REGULAR/URGENT | ❌ | ❌ | ✅ Required |
| `urgent_reason` | ❌ | ❌ | ✅ Required if URGENT |
| `needed_by` | ❌ | ❌ | ✅ Required if URGENT |
| General notes (header) | ❌ | ❌ | ✅ Optional |
| `priority` (legacy text) | ❌ | Input placeholder «اختياري» | ❌ Replace with `request_type` (DATA-01) |
| Per-line qty | ✅ number step 0.01 | ✅ | ✅ |
| Per-line note | ✅ | ✅ | ✅ |
| **Source (Kitchen/Warehouse)** | ❌ (correct) | **✅ dropdown** — **product defect** | ❌ **Must not exist** |
| Item picker | Full catalog table | Per-line dropdown | Catalog table/cards |
| Stock on hand | ❌ | ❌ | Optional — **NOT AVAILABLE** without verified API |
| Category | Filter + column | optgroup | Filter + column |

### 5.2 Two implementations (verified)

1. **`BranchRequestCatalogForm.jsx`** — branch-only (`useCatalogForm = canCreateRequest && !canSelectBranch`).
2. **Legacy inline block** in `SupplyChainPages.jsx` — intended for admin branch picker + source selector; **gated by same `canCreateRequest` flag → unreachable for admin**.

---

## 6. Catalog completeness and item visibility

### 6.1 Reconciliation — `branch_pizza_1_al_khobar` (branch_id **19**, Ronaldos Al Khobar)

| Layer | Count | Source |
|---|---:|---|
| Active items (master) | **635** | SQL `items.active AND NOT is_deleted` |
| Branch-requestable (master flag) | **135** | SQL `branch_requestable=true` |
| **`GET /branch-requests/allowed-items`** | **69** | API + browser qty inputs |
| Visible after search «بيب» | Subset in catalog tbody | Client filter only |
| Brands on branch | **1** (Ronaldos, brand_id=8) | `branch_brands` |

**Why 135 → 69:** Endpoint filters (see `list_allowed_items`):

- Item must belong to branch’s brand via `item_brands` + `branch_brands`
- `active`, `branch_requestable`, `visible_in_branch_ui`
- `source_type != NOT_REQUESTABLE`
- `item_type != raw_material`
- `item_code NOT LIKE 'DEMO-%'`

**Why 635 → 135:** Most master items are not branch-requestable (raw materials, not-requestable, inactive, other brands).

**Branch-item assignment table:** Not the primary gate for catalog endpoint — **brand linkage + item flags** dominate. Items without `item_brands` for Ronaldos never appear.

### 6.2 Reconciliation — `branch_onda_1_arkan` (branch_id **9**)

| Layer | Count |
|---|---:|
| Allowed-items endpoint | **47** |
| Global requestable items **not** in allowed set | **88** (other brands / visibility / type rules) |

### 6.3 Mandatory Q&A

| # | Question | Answer |
|---|---|---|
| 1 | Why are some catalog items not visible? | **Filtered by brand assignment, `visible_in_branch_ui`, `branch_requestable`, item type, source_type, DEMO prefix** — not a frontend truncation bug. |
| 2 | Which items should a branch request? | **Exactly the allowed-items set** per PD-01; unavailable items should be **hidden** (current) or **disabled with reason** (target — discuss). |
| 3 | UI Kitchen/Warehouse picker? | **Legacy admin form only** — branch catalog correctly omits it. Legacy exists for historical demo/admin override. |
| 4 | Backend rejects source override? | **Branch roles:** client `source_type` **stripped** (`_lines_without_branch_source_override`). Item master resolves source. Admin can set source in legacy payload — **product defect for target**. |
| 5 | Two workflows? | **Yes** — catalog (branch) vs legacy (admin-intended); admin UI **broken** by `canCreateRequest` gate. |
| 6 | Branch spoof / unassigned item? | Spoof branch **403**; invalid item **400** `item_not_requestable`; wrong brand **400** `item_not_allowed_for_brand`. |
| 7 | Unit/decimal server rules? | Pydantic `qty_requested: Decimal, gt=0`; zero/negative **422**; duplicate line **400**; no per-unit integer enforcement in schema (**gap**). |
| 8 | Draft vs submit side effects? | **Draft:** `request_created` audit only. **Submit:** status→SUBMITTED, line→SUBMITTED, audit — **no auto-split, no stock, no kitchen/warehouse orders**. |
| 9 | Submit only to approval? | **Yes** — split runs on **approve** only (`approve_branch_request` L647–649). |
| 10 | Best target structure? | **Dedicated 3-step wizard page** (see §12) — score highest for validation + tablet + admin parity. |
| 11 | Missing Regular/Urgent fields? | **`request_type`, `urgent_reason`, `needed_by`** — none in UI or create schema today. |
| 12 | Tablet usable? | **Partial** — catalog scrolls in 834px; sticky header OK; no horizontal break observed; **no draft/review step** hurts usability. |

---

## 7. Search, filters and catalog performance

### Current (catalog form)

| Feature | Behavior |
|---|---|
| Arabic name search | ✅ client-side substring on name + code |
| Item code search | ✅ same blob |
| Category filter | ✅ `<select>` all categories from loaded items |
| Empty result | Empty tbody — **no dedicated empty-search message** |
| Clear filters | Manual only |
| Qty retention on filter | ✅ stored in `quantities` state map by item id |
| Duplicate selection | N/A — single row per item |
| Performance | 69 rows DOM — acceptable; 200+ may need virtual scroll (**PERF-P02-01**) |

**Note:** Playwright `rows_after_search` counted **list table rows below** — not catalog-only; search itself works on catalog tbody.

---

## 8. Actions and ownership

| Action | Owner (current) | Behavior |
|---|---|---|
| إرسال الطلب (catalog) | branch | Creates DRAFT then **immediately POST submit** — **no separate draft button** |
| حفظ مسودة | legacy (unreachable) | Would create DRAFT only |
| حفظ وإرسال | legacy (unreachable) | Create + submit |
| إرسال (list row) | branch | Submit existing DRAFT from list |
| Confirmation before submit | ❌ | **Gap** — required by PD-02 / OQ-01 baseline |
| Double-submit protection | Partial | `saving` disables button; backend idempotency header supported, **frontend does not send `X-Idempotency-Key`** |

---

## 9. Draft / submit statuses and transitions

```text
[Create POST]  → DRAFT (request + lines DRAFT)
[Submit POST]  → SUBMITTED (submitted_at set, lines SUBMITTED)
[Approve]      → AREA_APPROVED → auto-split (OUT OF PAGE 02 SCOPE)
```

**Catalog path:** Always create+submit in one user action (`handleCatalogSubmit`).

**Test evidence:** `BR-005374` created DRAFT then submitted → **SUBMITTED** (marker `UXP02-20260713-branch_pizza-001`). `BR-005375` admin DRAFT remains **DRAFT**.

---

## 10. Quantity and unit handling

| Check | Frontend | Backend |
|---|---|---|
| Blank qty | Ignored (not in lines) | — |
| Zero | Toast «أدخل كمية واحدة…» | **422** if sent |
| Negative | Toast | **422** |
| Large value | Accepted if finite | Accepted (no upper cap — **DATA-P02-01**) |
| Decimal | `step="0.01"` all items | Decimal field — **no unit-specific integer rule** |
| Duplicate item | N/A catalog | **400** duplicate_item |
| Cross-unit totals | N/A | Must not aggregate in target review summary |

Unit displayed from `item.unit` in catalog — **server-sourced** ✅

---

## 11. Confirmations and unsaved-change protection

| Scenario | Current | Target |
|---|---|---|
| Pre-submit review | ❌ | Step 3 summary (branch, type, items, notes) |
| Confirm dialog | ❌ | Required before submit |
| Unsaved exit | ❌ | `beforeunload` or modal |
| Success navigation | Stays on PAGE 01 list | → PAGE 03 detail or PAGE 01 with toast |

**Messages (current):**

- Success catalog: «تم إرسال الطلب لمدير المنطقة»
- Success legacy draft: «تم حفظ الطلب كمسودة»
- Validation: toast Arabic (see catalog form)

---

## 12. Target-design alternatives (DISCUSSION_REQUIRED)

### A. Page structure

| Option | Branch speed | Admin | Tablet | Validation | Risk | Score |
|---|---|---|---|---|---|---|
| **Dedicated single page** | Medium | Good | Medium | Medium | Low | 7/10 |
| **3-step wizard (recommended)** | Good | Good | **Best** | **Best** | Medium | **9/10** |
| **Inline on PAGE 01 (status quo)** | Poor discoverability | Broken admin | Crowded | Poor | Low change cost | 3/10 |
| **Drawer/modal** | Fast | OK | Cramped | Medium | State loss | 5/10 |

**Recommendation:** **3-step wizard** on `/supply-chain/branch-requests/new`:

1. Request info (type, urgent fields, notes, branch for admin)
2. Catalog (search, qty, line notes)
3. Review + confirm → Save Draft \| Submit for Approval

### B. Catalog presentation

| Option | Desktop | Tablet |
|---|---|---|
| Searchable table (recommended desktop) | ✅ sticky header, qty column | Acceptable with scroll |
| Item cards | Slower scan | **Better touch targets** |
| Category-grouped | Good for large catalogs | Good |

**Recommendation:** Same data model — **table desktop, compact cards tablet** (optional responsive switch).

### C. Actions placement

- Sticky footer: **حفظ مسودة** (secondary) + **إرسال للاعتماد** (primary, disabled until step 3 valid)
- **إلغاء** → back with dirty check
- No «clear form» unless user confirms

### D. Review summary (pre-submit)

Show: branch, request type, needed_by + urgent_reason if urgent, line count, each item (Arabic name, code, unit, qty), header notes.

**Do not show** cross-unit quantity total.

---

## 13. UI states (current vs target)

| # | State | Current | Target (Arabic proposal) |
|---|---|---|---|
| 1 | Initial loading | Page-level spinner on list | «جارٍ تحميل نموذج الطلب…» |
| 2 | Catalog loading | Items load with page init | Skeleton rows |
| 3 | Empty catalog | Amber «لا توجد أصناف قابلة للطلب…» | Same + link to support |
| 4 | Search no results | Empty table | «لا توجد أصناف مطابقة — جرّب كلمة أخرى» |
| 5 | Validation | toast.error | Inline field errors + summary banner |
| 6 | 403 | RouteRoleGuard card | «غير مصرّح بإنشاء طلبات التوريد» |
| 7 | Network error | toast | Retry banner |
| 8 | Saving draft | N/A catalog | «جارٍ حفظ المسودة…» |
| 9 | Submitting | «جارٍ الإرسال…» | «جارٍ إرسال الطلب للاعتماد…» |
| 10 | Success | toast success | toast + navigate |
| 11 | Already submitted | — | «تم إرسال هذا الطلب مسبقاً» |
| 12 | Unsaved exit | None | «لديك تغييرات غير محفوظة — هل تريد المغادرة؟» |

---

## 14. Arabic, RTL, terminology, accessibility

- RTL layout ✅ via app shell
- Labels hardcoded Arabic in catalog — not i18n keys (**UX-P02-05**)
- Dates N/A on create form
- Catalog inputs have `aria-label` on qty/note ✅
- Keyboard: table scroll OK; **no skip to submit**; focus order row-by-row
- Terminology clash: **إرسال الطلب** (create) vs list **إرسال** (submit draft) — **UX-P02-06**

---

## 15. Desktop and Tablet behavior

| Viewport | Finding |
|---|---|
| Desktop 1920×1080 | Two-column PAGE 01: catalog + list side-by-side — form discoverable without scroll |
| Tablet 834×1112 | Catalog table scrolls (`max-h-[28rem]`); touch targets ≥44px on buttons; **no dedicated review panel** |

Screenshots: `desktop_*_form.png`, `tablet_*_form.png`, `*_search.png` in evidence folder.

---

## 16. Frontend / Backend / API / security gaps

### 16.1 Problem register

| ID | Sev | Cat | Issue |
|---|---|---|---|
| UX-P02-01 | High | UX | No dedicated PAGE 02 route or CTA from PAGE 01 |
| UX-P02-02 | High | UX | Catalog **no Save Draft** — always submit |
| UX-P02-03 | High | UX | **No pre-submit confirmation / review step** |
| UX-P02-04 | High | Product | **Missing REGULAR/URGENT**, `urgent_reason`, `needed_by` (PD-01/02) |
| UX-P02-05 | High | UX | **Admin/super_admin create UI missing** — backend works, frontend `canCreateRequest` too narrow |
| UX-P02-06 | Med | UX | Duplicate verb «إرسال» for create vs submit draft |
| UX-P02-07 | Med | UX | No unsaved-change guard |
| UX-P02-08 | Med | A11y | List+catalog same page — long tablet scroll |
| PRD-P02-01 | High | Product | Legacy **المصدر** picker violates PD-01 (Kitchen/Warehouse not request types) |
| SEC-P02-01 | Med | Security | Admin can POST `source_type` override via API — branch cannot |
| SEC-P02-02 | Low | Security | `area_manager` in POST role tuple — blocked later by `_require_branch_write` (SEC-02) |
| SEC-P02-03 | Info | Security | Branch spoof **403** ✅; auditor **403** ✅ |
| DATA-P02-01 | Low | Data | No max qty; no integer enforcement per unit type |
| PERF-P02-01 | Low | Perf | Full catalog DOM for 100+ items — plan virtual scroll |
| ACC-P02-01 | Med | A11y | No idempotency key on double-click submit |

### 16.2 API contract (create)

```http
POST /api/v1/branch-requests
Body: { branch_id, brand_id, priority?, lines: [{ item_id, qty_requested, source_type?, notes? }] }
→ 201 DRAFT

POST /api/v1/branch-requests/{id}/submit
→ 200 SUBMITTED

GET /api/v1/branch-requests/allowed-items?branch_id=&brand_id=
→ 200 Item[]
```

**Idempotency:** `X-Idempotency-Key` supported on create/submit — frontend unused.

### 16.3 Dependencies from PAGE 01

- PAGE 01 CTA must link to PAGE 02 when built (PAGE01-D04)
- `request_type` migration DATA-01
- SEC-02 split read/create roles
- OP-BR-01 operations_manager read-only elsewhere

---

## 17. Final alternatives and recommendation

| Dimension | Judgment |
|---|---|
| **Current create UX** | **REBUILD** — split from list; unify branch/admin |
| **Backend create endpoint** | **KEEP + EXTEND** — add PD-01 fields; tighten admin source override policy |
| **Catalog endpoint** | **KEEP** — filters align with business rules |
| **Legacy inline form** | **REMOVE** from target (admin uses same wizard + branch picker) |
| **PAGE 02 DESIGN** | **DISCUSSION_REQUIRED** |
| **PAGE 02 IMPLEMENTATION** | **NOT AUTHORIZED** |

**Recommended target:** `/supply-chain/branch-requests/new` — **3-step wizard**, searchable catalog table (desktop) / cards (tablet), **no source picker**, REGULAR/URGENT with conditional urgent fields, **Save Draft + Submit with confirmation**, idempotency keys on submit.

---

## 18. Open decisions for user

| ID | Decision |
|---|---|
| OQ-P02-01 | Wizard vs single-page vs drawer? |
| OQ-P02-02 | Hide vs disable unavailable catalog items? |
| OQ-P02-03 | After success: stay on list vs open PAGE 03 detail? |
| OQ-P02-04 | Should admin source override remain in API for break-glass, or strip like branch? |
| OQ-01 | Global request-type change rule — pending PAGE 02–05 (baseline in PAGE 01 §16.ب) |

---

## 19. Controlled test data

See `PAGE_SPEC_EVIDENCE/PAGE_02/_test_data_manifest.json`:

| Request | Role | Status | Marker |
|---|---|---|---|
| BR-005374 | branch_pizza | **SUBMITTED** | UXP02-20260713-branch_pizza-001 |
| BR-005375 | admin | **DRAFT** | UXP02-20260713-admin-001 |

**Not performed:** approve, split, stock movement, delete.

---

## 20. Files inspected

**Frontend:** `App.jsx`, `AppLayoutV2.jsx`, `SupplyChainPages.jsx`, `BranchRequestCatalogForm.jsx`, `services/api.js`, `BranchRequestDetailPage.jsx` (submit only)

**Backend:** `routers/branch_requests.py`, `schemas/__init__.py` (BranchRequestCreate), `models/__init__.py` (BranchRequest, Item), `branch_request_split_service.py` (read-only trace)

**Docs:** `RAED_INVENTORY_MASTER_PLAN.md`, `PRODUCT_DECISIONS_FINAL.md`, `ROLE_MENU_MATRIX.md`, `PAGE_SPEC_01_*`, `FINAL_DECISION_PAGE_01.md`, `PAGE_SPEC_INDEX.md`

**Evidence created (untracked):** `PAGE_SPEC_EVIDENCE/PAGE_02/*`, `tools/page_spec_02_probes.py`, `tools/page_spec_02_capture.py`

**Index updated (uncommitted):** `PAGE_SPEC_INDEX.md` — PAGE 02 IN_REVIEW, counts APPROVED=1 IN_REVIEW=1 NOT_STARTED=78

---

*Review performed read-only. No application code, schema, routes, RBAC, or data model modified. Test creates only as authorized.*
