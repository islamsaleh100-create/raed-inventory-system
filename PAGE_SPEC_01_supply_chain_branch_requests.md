# PAGE 01 — Branch Supply Requests List

| Field | Value |
|---|---|
| Page ID | PAGE 01 |
| Route | `/supply-chain/branch-requests` |
| Review date | 2026-07-13 |
| Mode | READ-ONLY REVIEW |
| Database verified | `localhost:5432/raed_inventory` |
| Git branch | `release/lan-trial-2026-06-16` @ `cd0739f` |
| **Final status** | **APPROVED** |
| **Recommendation** | **REBUILD Frontend List / KEEP + EXTEND Backend Endpoint** |

Evidence: `PAGE_SPEC_EVIDENCE/PAGE_01/` (28+ PNG, `_capture_meta.json`, `_steps_3_5_meta.json`)

---

## 1. Page purpose

Operational landing page for **branch supply requests** (طلبات توريد الفروع): branch roles create/submit requests; area/admin/auditor roles monitor scoped lists; all authorized roles open detail via request number.

Per `PRODUCT_DECISIONS_FINAL.md` (PD-01–PD-03), the **target** list page should surface request type (regular/urgent), pipeline stage, responsible party, quantity progress, SLA/overdue signals, and role-scoped actions. **Current implementation partially fulfills branch monitoring only**; creation is embedded on the same page (PAGE 02 not separated).

---

## 2. Preflight

| Check | Result |
|---|---|
| Git branch | `release/lan-trial-2026-06-16` |
| HEAD | `cd0739f` |
| Working tree | Modified/untracked docs & audit artifacts only — **no app source changes in this review** |
| Frontend `:3000` | HTTP 200 |
| Backend `:8010` | HTTP 200 (`/api/v1/health`) |
| Effective `DATABASE_URL` | `localhost:5432/raed_inventory` ✅ |
| `raed_lan_trial` detected | **No** — review proceeded |
| `RAED_INVENTORY_MASTER_PLAN.md` | ✅ |
| `ROLE_MENU_MATRIX.md` | ✅ |
| `PRODUCT_DECISIONS_FINAL.md` | ✅ |
| `PAGE_SPEC_INDEX.md` | ✅ — PAGE 01 = **APPROVED** — 2026-07-13 |

---

## 2. Browser UX findings (Step 3)

Review: Desktop **1920×1080**, Tablet **834×1112**. No create/approve/reject performed.
Evidence: `ux_desktop_<role>.png`, `ux_tablet_<role>.png`, `ux_filter_active.png`, `ux_empty_state.png`, `ux_pagination.png`, `ux_403_<role>.png`, `_steps_3_5_meta.json`.

### 2.1 Nav and menu (3.1)

| Role | Nav visible | Section | Arabic label (exact) |
|---|---|---|---|
| branch_user / branch_manager | ✅ | `nav.section_supply_chain` (سلسلة الإمداد) | **طلبات الفروع** (`nav.supply_chain_branch_requests`) |
| area_manager | ✅ | Same | **طلبات الفروع** |
| internal_auditor | ✅ | Same | **طلبات الفروع** |
| admin / super_admin | ✅ | Same | **طلبات الفروع** |
| operations_manager | ❌ | — | Item not in nav `roles` array |
| delivery_user / kitchen / warehouse | ❌ | Supply-chain section partial | No branch-requests link |

### 2.2 Page header (3.2)

| Role context | Title (exact) | Subtitle (exact) |
|---|---|---|
| Branch (`canCreateRequest`) | **طلبات الفروع** | **إنشاء ومتابعة طلبات التوريد للفروع** |
| Scoped list (`usesScopedList`) | **طلبات الفروع** | **متابعة طلبات التوريد ضمن نطاقك** |
| internal_auditor | Same as scoped | Same + amber **ReadOnlyBanner** above content |

### 2.3 Create button (3.3)

| Role | Present? | Label (exact) | Behavior |
|---|---|---|---|
| branch_user / branch_manager | ✅ (not a top-level CTA) | **إرسال الطلب** (`BranchRequestCatalogForm`) | Submits catalog inline — **no navigation**, no modal, no scroll |
| admin / super_admin | ✅ (legacy panel) | **حفظ مسودة** / **حفظ وإرسال** | Inline POST + optional submit |
| area_manager / internal_auditor | ❌ | — | — |

There is **no** dedicated «إنشاء طلب توريد» button and **no** route to `/supply-chain/branch-requests/new`.

### 2.4 Summary counters (3.4)

**None** on this page. No pending/overdue/urgent/KPI widgets. (KPIs exist on `/supply-chain/control` and `/dashboard` only.)

### 2.5 Search and filters (3.5)

| Control | Present | Details |
|---|---|---|
| Search | ✅ | Label **بحث**; placeholder **اسم الفرع، الصنف، أو رقم الطلب** |
| Branch filter (list) | ❌ | Branch fixed by role or selected only in admin **create** form |
| Request type Regular/Urgent | ❌ | — |
| Status filter | ✅ | **الحالة** — values: كل الحالات، مسودة، مرسل، موافق عليه، مرفوض، تم التقسيم، قيد التنفيذ، تم التسليم |
| Date range | ✅ | **من / إلى** date inputs |
| Overdue / urgent quick-filter | ❌ | — |

**Filters → API:** Server-side query params via `buildFilterParams` → `reloadRequests()` on change.
Observed URL when status set to SUBMITTED (admin):
`GET /api/v1/branch-requests?status=SUBMITTED&page_size=100&branch_id=<selected>` (via Vite proxy).
Default list call from code: `page_size=100`, optional `branch_id`, `status`, `search`, `date_from`, `date_to`. **No separate counter API.**

### 2.6 Table columns (3.6)

**Headers (exact Arabic):**

| Column | branch_user | area_manager / auditor / admin |
|---|---|---|
| **رقم الطلب** | ✅ | ✅ |
| **الفرع** | ❌ | ✅ (`usesScopedList`) |
| **البراند** | ✅ | ✅ |
| **الحالة** | ✅ | ✅ |
| **الإنشاء** | ✅ | ✅ |
| **الإجراء** | ✅ | ✅ |

- **Current stage / responsible party:** ❌ not on list
- **Quantity progress** (requested/approved/produced/issued/delivered/remaining): ❌ list only; detail page (`BranchRequestDetailPage`)
- **Urgent indicator:** ❌ no badge/icon/color

### 2.7 Row actions (3.7)

| Action | Roles | Condition |
|---|---|---|
| **تفاصيل** (link button) | All authorized | Always |
| Request # link | All | Navigates to `/supply-chain/branch-requests/{id}` |
| **إرسال** (submit draft) | branch_user / branch_manager / admin | `canCreateRequest && status === 'DRAFT'` |

Row click (non-link) does **not** navigate — only explicit links/buttons.

### 2.8 Pagination (3.8)

| Item | Finding |
|---|---|
| UI pagination | **None** — no page controls, no page-size selector |
| Frontend default | `page_size: 100`, `page` omitted (=1) in `reloadRequests()` |
| Backend max | `page_size` le=100 |
| Global totals | admin/auditor `total=5,351` but **only 100 rows rendered** |
| Network (admin reload) | Response **~183 KB**, **100 items** in body, `total: 5351`, ~2.0s (V.4) |

**PERF-01:** Users cannot reach records 101–5351 without API pagination UI (not a single 5,351-row payload, but **effective data loss** in UI).

### 2.9 Sorting (3.9)

- **Sortable columns:** none in UI
- **Default:** backend `ORDER BY created_at DESC` only

### 2.10 States (3.10)

| State | Observation |
|---|---|
| Loading | Table row: **جارٍ التحميل…** (colspan) |
| Empty | **لا توجد طلبات بعد** (no-match search also shows this — `ux_empty_state.png`) |
| Error | `toast.error(...)` on load failure — no inline error panel |
| 403 | **Verified** for `delivery_user`, `kitchen_section_manager`, `warehouse_user`: card **غير مصرّح** / **ليس لديك صلاحية لعرض هذه الصفحة.** (`ux_403_*.png`) |

### 2.11 Arabic and RTL (3.11)

- Layout: **RTL** throughout (`dir` from app shell)
- Labels: mostly Arabic hardcoded; nav label from i18n **طلبات الفروع**
- English leaks: header **English** language toggle; dates via `formatDate()` → **`en-GB`** locale (e.g. `13/07/2026, 10:15:00`)
- Mixed catalog strings: category names may include English (`drinks / مشروبات`)

### 2.12 Desktop vs Tablet (3.12)

| Viewport | Behavior |
|---|---|
| Desktop | Two-column grid when `canCreateRequest`: catalog (~1.2fr) + list (~1fr) |
| Tablet | Columns stack; catalog table scrolls (`max-h-[28rem]`); filter toolbar wraps; horizontal table scroll |
| Issues | Heavy vertical scroll on tablet; filter fields usable but cramped |

### 2.13 UX problems observed (3.13)

- Two clicks minimum to detail (open page → تفاصيل or request #) — acceptable
- List + create combined — confusing for area/auditor landing on same URL
- **إرسال الطلب** vs list **إرسال** (draft) — similar verbs, different actions
- No dead-end links observed; unauthorized roles get clear 403 card

---

## 3. Role and scope matrix (+ Verification V.1–V.6)

### 3.1 Access matrix

| Role | Route guard | Nav | GET list | List total | Scope enforcement |
|---|---|---|---:|---:|---|
| branch_user | ✅ | ✅ | 200 | 1,024 | `branch_id = 9` |
| branch_manager | ✅¹ | ✅ | 200 | 1,024 | Same |
| area_manager | ✅ | ✅ | 200 | 2,824 | `_area_scope_filter` (Dammam + Onda); **no DRAFT** |
| internal_auditor | ✅ | ✅ | 200 | 5,351 | **Unfiltered (global read)** |
| admin | ✅ | ✅ | 200 | 5,351 | Unfiltered |
| super_admin | ✅ | ✅ | 200 | 5,351 | Unfiltered |
| operations_manager | ❌ | ❌ | **401**² | — | Not in `SCOPED_ROLES` |
| warehouse_user / manager | ❌ | ❌ | **403** | — | Role gate |
| kitchen_section_manager | ❌ | ❌ | **403** | — | Role gate |
| delivery_user | ❌ | ❌ | **403** | — | Role gate |
| sales_manager / quality_manager | — | — | **Not tested**³ | — | No LAN trial accounts in DB |

¹ `branch_manager` runtime: **CODE VERIFIED** (RouteRoleGuard + backend scope). حساب مخصص لم يُختبر — الاختبار على حساب dual-role (`PAGE01-BRANCH-MGR`). ² No `operations_manager` user in `raed_inventory`. ³ Deferred — no seeded accounts.

### 3.2 POST authorization (code + probe)

| Role | POST create (empty body) | POST approve | Notes |
|---|---:|---:|---|
| branch_user | 422 | 403 | Create allowed with valid lines; approve denied |
| area_manager | 422 | 400 | In `SCOPED_ROLES` for POST but `_require_branch_write` blocks create with valid payload → **403** |
| internal_auditor | **403** | **403** | In router roles; write blocked in handler |
| admin | 422 | 400 | Platform admin can create for any branch via legacy form |

### 3.3 Verification samples

**V.1 — branch_user (PASS):** 5/5 sample rows `branch_id = 9` (Onda Arkan).

**V.2 — area_manager (PASS):** Account `area_dammam_onda`; assignment **Dammam + brand Onda** (9 branches in scope). Page-1 sample: 4 distinct `branch_id`s (9×97, 12×1, 13×1, 18×1). **0 DRAFT** in 100-row sample.

**V.3 — count plausibility (PASS):** branch 1,024 ⊆ area 2,824 ⊆ global 5,351. Area scope covers **9 branches** vs single branch — ratio plausible.

**V.4 — global response size:** admin page-1: **100 records**, **183,504 bytes**, `total=5351`, **2.055s**. Flag **PERF-01** (UI cannot paginate beyond 100).

**V.5 — admin vs super_admin:** Both **total=5351**, **items_len=100** — identical list contract.

**V.6 — untested / denied roles:**

| Role | HTTP | Notes |
|---|---|---|
| operations_manager | 401 login | No account |
| warehouse_manager / user | 403 | `require_roles` rejection |
| kitchen_section_manager | 403 | Same |
| delivery_user | 403 | Same |

---

## 4. Frontend code structure (Step 4)

### 4.1 Page component

| Item | Value |
|---|---|
| File | `raed_inventory/frontend/src/pages/supply_chain/SupplyChainPages.jsx` |
| Component | `SupplyChainBranchRequestsPage` (lines ~301–695) |
| Dedicated? | **Yes** for list route; shares file with other supply-chain pages (approvals, warehouse, etc.) |

Child: `BranchRequestCatalogForm.jsx` (branch create catalog).

### 4.2 Route definition

```2050:2051:raed_inventory/frontend/src/App.jsx
<Route path="/supply-chain/branch-requests/:id" element={<RouteRoleGuard allowed={['branch_user', 'branch_manager', 'area_manager', 'internal_auditor', 'admin', 'super_admin']}><BranchRequestDetailPage /></RouteRoleGuard>} />
<Route path="/supply-chain/branch-requests" element={<RouteRoleGuard allowed={['branch_user', 'branch_manager', 'area_manager', 'internal_auditor', 'admin', 'super_admin']}><SupplyChainBranchRequestsPage /></RouteRoleGuard>} />
```

`RouteRoleGuard`: `super_admin` bypass; `admin` must be listed (`RouteRoleGuard.jsx`).

### 4.3 Nav definition

`AppLayoutV2.jsx` → section **سلسلة الإمداد** (`nav.section_supply_chain`):

```66:66:raed_inventory/frontend/src/components/layout/AppLayoutV2.jsx
{ to: '/supply-chain/branch-requests', icon: ClipboardList, labelKey: 'nav.supply_chain_branch_requests', roles: ['branch_user', 'branch_manager', 'area_manager', 'internal_auditor', 'admin', 'super_admin'] },
```

**operations_manager** is in section roles but **excluded** from this item.

### 4.4 API calls

| Call | Trigger | URL / params |
|---|---|---|
| List | `reloadRequests()` | `GET /branch-requests` + `{ page_size: 100, branch_id?, status?, search?, date_from?, date_to? }` |
| Brands/branches | `useEffect` mount | `listBrands`, `masterApi.listBranches` (admin/auditor) |
| Allowed items | branch change | `listAllowedItems` (create only) |
| Counters | — | **None on this page** |

Filters sent as **query params** (server-side). No client-side list filtering beyond React state refresh.

### 4.5 Pagination (code)

- **Server-side params supported** by API but frontend sends **`page_size: 100` only**, never increments `page`
- **Not client-side sliced** — displays API `items` array as returned
- Default page size in code: **100**

### 4.6 Filters (code)

`EMPTY_FILTERS`: `{ search, status, branch_id, item_id, date_from, date_to }`
List uses `SupplyChainFilterBar` with `showBranch={false}`, `showItem={false}`.
**No `request_type` / urgent / overdue filters in code.**

### 4.7 Table columns (code)

| UI column | Data field |
|---|---|
| رقم الطلب | `request.request_no` → Link `/supply-chain/branch-requests/${request.id}` |
| الفرع | `request.branch_name` (if `usesScopedList`) |
| البراند | `request.brand_name_snapshot` or brand lookup |
| الحالة | `StatusBadge` ← `STATUS_LABEL[request.status]` |
| الإنشاء | `formatDate(request.created_at)` |
| الإجراء | Link + conditional submit button |

**Urgency:** `priority` field exists on model but **not shown** in list. No urgent UI.

### 4.8 Actions per role (code)

```306:308:raed_inventory/frontend/src/pages/supply_chain/SupplyChainPages.jsx
  const canCreateRequest = (roles.includes('branch_user') || roles.includes('branch_manager')) && !isAuditor
  const canSelectBranch = roles.includes('admin') || roles.includes('super_admin') || isAuditor
  const useCatalogForm = canCreateRequest && !canSelectBranch
```

- **Catalog form:** branch roles without admin/auditor branch picker
- **Legacy form:** admin/super_admin (and auditor sees disabled fields)
- **Submit draft:** `canCreateRequest && request.status === 'DRAFT'`

### 4.9 Loading / empty / error

| State | Implementation |
|---|---|
| Loading | `loading` state → table «جارٍ التحميل…» |
| Empty | `requests.length === 0` → «لا توجد طلبات بعد» |
| Error | `catch` in mount → `toast.error('تعذر تحميل...')` |
| 403 route | `RouteRoleGuard` — not handled inside page component |

### 4.10 Hardcoded content / placeholders

- Page title/subtitle: hardcoded Arabic in `PageShell`
- Status labels: hardcoded `STATUS_LABEL` map (not i18n keys)
- `priority` input placeholder **اختياري** — not PD-01 enum
- No TODO/FIXME in list component block

### 4.11 Frontend gaps

- Missing pagination UI despite API support
- Missing PD-01 filters and columns
- `page` param never sent — stuck on page 1
- Admin vs branch create UX split on same route
- Auditor global list with no branch filter in list toolbar
- Date localization wrong locale

---

## 5. Backend code structure (Step 5)

### 5.1 List endpoint

| Item | Value |
|---|---|
| File | `raed_inventory/backend/app/routers/branch_requests.py` |
| Function | `list_branch_requests` |
| Method / path | `GET /api/v1/branch-requests` |
| Auth | `require_roles(*SCOPED_ROLES)` |
| SCOPED_ROLES | `branch_user`, `branch_manager`, `area_manager`, `internal_auditor`, `admin`, `super_admin` |
| super_admin bypass | **Yes** — automatic in `require_roles()` (`auth.py:153`) |

### 5.2 Object-level scope (router — no separate service)

| Role | Implementation | Location |
|---|---|---|
| branch_user / branch_manager | `q.filter(BranchRequest.branch_id == current_user.branch_id)` | `list_branch_requests` L520–521 |
| area_manager | `_area_scope_filter()` — join `AreaManagerAssignment` on brand+city+user; **`status != DRAFT`** | L151–165, L522–523 |
| internal_auditor | **No branch** — query unfiltered | Falls through after L518–523 |
| admin | **No filter** | L518–519 |
| super_admin | Same as admin (via role check) | L518–519 |
| operations_manager | **Not in SCOPED_ROLES** → 403 at dependency | — |

### 5.3 Draft visibility

| Role | DRAFT visible? |
|---|---|
| branch_user / branch_manager | ✅ own branch drafts |
| area_manager | ❌ excluded by `_area_scope_filter` |
| admin / auditor / super_admin | ✅ all branches |

### 5.4 Pagination

- Params: `page` (default 1), `page_size` (default 20, **max 100**)
- Total: separate **`q.count()`** before offset/limit
- Default in practice (frontend): page=1, page_size=100

### 5.5 Filters (backend)

Accepted query params: `status`, `brand_id`, `branch_id`, `search`, `date_from`, `date_to`
All applied in DB query in `list_branch_requests`.
**Not implemented:** `request_type`, `urgent`, `overdue`, `stage`.

### 5.6 Sorting

- Fixed: `order_by(BranchRequest.created_at.desc())`
- **No** sort param

### 5.7 Response fields (`BranchRequestOut`)

**Present:** `id`, `request_no`, `branch_id`, `branch_name`, `brand_id`, `brand_name_snapshot`, `status`, `priority`, timestamps, approval/rejection metadata, **`lines[]`** (full line objects with qty_requested, qty_approved, etc.)

**Missing on list DTO for PAGE 01 target:**

- `request_type` (regular/urgent)
- `urgent_reason`, `needed_by`
- `stage`, `current_owner_role`
- Aggregated qty progress fields
- `overdue` / SLA flags

Line-level qty fields exist but list UI does not aggregate them.

### 5.8 Performance

**Indexes** (`20260425_0016` migration): `branch_id`, `brand_id`, `status`, `request_no` — **no index on `created_at`**.

**N+1:** Mitigated via `joinedload` on branch and lines+item; however embedding **full lines[] for 100 requests** inflates payload (~183 KB/page).

**Risk:** `count()` + wide join on 5,351 rows acceptable; missing pagination UI is the primary UX/perf issue (PERF-01).

### 5.9 Create endpoint authorization (code review)

| Item | Value |
|---|---|
| Function | `create_branch_request` — `POST /api/v1/branch-requests` |
| Router roles | `require_roles(*SCOPED_ROLES)` — **same tuple as list** |
| **area_manager in POST roles** | **⚠️ YES** — but `_require_branch_write()` rejects (403) unless admin/branch |
| **internal_auditor in POST roles** | **⚠️ YES** — blocked by `_require_branch_write` |
| warehouse / delivery / kitchen | **Not listed** ✅ |

Object-level write gate: `_require_branch_write()` L191–200.

### 5.10 Backend gaps

- Auditor list scope undefined vs policy
- area_manager listed on POST though business rules forbid create
- Missing PD-01 columns/filters
- No `created_at` index for sort/filter at scale
- Fat list response includes nested lines

---

## 6. Problems found (UX + Security + Performance)

### 6.1 UX

| ID | Sev | Issue |
|---|---|---|
| UX-01 | High | List + inline create — conflicts with PAGE 02; tablet overload |
| UX-02 | High | No pagination UI — 5,351 total, 100 visible |
| UX-03 | High | No summary KPI counters on page |
| UX-04 | High | PD-01 regular/urgent not implemented |
| UX-05 | Medium | No stage / responsible-party columns |
| UX-06 | Medium | No quantity progress on list |
| UX-07 | Medium | Dates use `en-GB` instead of target `ar-SA-u-ca-gregory` locale |
| UX-08 | Medium | Admin legacy form vs branch catalog on same route |
| UX-09 | Medium | No dedicated create CTA / PAGE 02 route |
| UX-10 | Low | No branch filter for global roles on list |
| UX-11 | Low | No sorting / overdue quick-filter |
| UX-12 | Low | Tablet: excessive scroll |

### 6.2 Security / scope

| ID | Sev | Issue |
|---|---|---|
| SEC-01 | Info | `internal_auditor` قراءة عالمية — **EXPECTED BY DESIGN** (PAGE01-D01). لا filter مطلوب. |
| SEC-02 | Low | `area_manager` + `internal_auditor` in POST `require_roles` tuple though writes blocked later — confusing contract |
| SEC-03 | Info | Branch isolation server-side **PASS** (V.1) |
| SEC-04 | Info | Area DRAFT exclusion **PASS** (V.2) |
| SEC-05 | Info | Unauthorized roles: API 403 + RouteRoleGuard UI **PASS** (delivery/kitchen/warehouse) |
| SEC-06 | Info | operations_manager excluded; no trial user to test end-to-end |

### 6.3 Performance

| ID | Sev | Issue |
|---|---|---|
| PERF-01 | High | Frontend fixed at page 1 × 100 rows — 5,251 records unreachable in UI |
| PERF-02 | Medium | List response includes nested `lines[]` — ~183 KB per page |
| PERF-03 | Low | No DB index on `created_at` for default sort |

---

## 9. الحكم على الصفحة

| البُعد | الحكم |
|---|---|
| **Frontend List Page** | **REBUILD** — نقص التصميم والفلاتر والـPagination وحقول المنتج الجديدة |
| **Backend List Endpoint** | **KEEP + EXTEND** — الـscope مُحقق؛ يلزم توسيع الـDTO والفلاتر والـmigration |
| **List DTO** | **SLIM + LINE-BASED PROGRESS** — حذف `lines[]` وإضافة تقدم الأصناف |
| **Pagination / Filtering** | **SERVER-SIDE** — default 25؛ لا تحميل كامل في الذاكرة |
| **Security Scope** | **PASS** للأدوار المختبرة |
| **PAGE 01 DESIGN** | **APPROVED** |
| **PAGE 01 IMPLEMENTATION** | **TECHNICAL_DEPENDENCIES** — انظر عناصر المتابعة في §16.د |
| **PAGE 01 CODE CHANGES** | **NOT AUTHORIZED** |
| **PAGE 02** | **NOT STARTED** |

---

## 10. التصميم المستهدف للصفحة

### رأس الصفحة

```
طلبات التوريد
تابع طلبات الفروع من الإنشاء حتى التسليم
                              [+ إنشاء طلب توريد]  ← branch_user / branch_manager / admin / super_admin فقط
```

### العرض الافتراضي

- **الافتراضي:** الطلبات النشطة والجارية فقط (لا تاريخية).
- الطلبات المكتملة والملغاة تظهر عند تفعيل زر/فلتر «السجل».
- يظهر للمستخدم بوضوح أن فلتر «الطلبات النشطة» مطبق (شريط / chip مرئي).

### الترتيب الافتراضي

```
1. عاجل + متأخر
2. عاجل (ضمن SLA)
3. متأخر (غير عاجل)
4. الأحدث (created_at DESC)
```

### Layout Wire

```
┌──────────────────────────────────────────────────────────────────┐
│ طلبات التوريد                       [+ إنشاء طلب توريد]         │
│ تابع طلبات الفروع من الإنشاء حتى التسليم                         │
├──────────────────────────────────────────────────────────────────┤
│  [الطلبات النشطة: N]  [بانتظار الاعتماد: N]  [عاجل: N]  [متأخر: N]│
├──────────────────────────────────────────────────────────────────┤
│ بحث | الفرع▼ | نوع الطلب▼ | المرحلة▼ | الحالة▼ | التاريخ | ☐ عاجل | ☐ متأخر | [مسح] │
│                                                    [الطلبات النشطة ✕] │
├──────────────────────────────────────────────────────────────────┤
│ #  │ الفرع │ النوع │ تاريخ الطلب │ الموعد المطلوب │ المرحلة │   │
│    │ الحالة │ تقدم الأصناف │ المسؤولون │ SLA │ آخر تحديث │ تفاصيل│
├──────────────────────────────────────────────────────────────────┤
│ ← 1 من 215  [25▼]  < 1 2 3 … 215 >                              │
└──────────────────────────────────────────────────────────────────┘
```

- **Desktop ≥1280px:** صف KPI + شريط فلاتر كامل + جدول 12 عموداً + تذييل pagination.
- **Tablet 768–1279px:** KPI chips تُطوى، درج فلاتر قابل للطي، قائمة بطاقات مع الحقول الأساسية + «تفاصيل».
- **Mobile:** خارج نطاق PAGE 01.

---

## 11. الفلاتر والأعمدة المستهدفة

### الفلاتر

| الفلتر | branch | area_manager | ops / auditor | admin / super_admin |
|---|---|---|---|---|
| بحث (رقم الطلب، الفرع، الصنف) | ✅ | ✅ | ✅ | ✅ |
| الفرع | مخفي (مثبت) | ✅ multi (نطاقه) | ✅ | ✅ |
| نوع الطلب (اعتيادي / عاجل) | ✅ | ✅ | ✅ | ✅ |
| المرحلة الحالية | ✅ | ✅ | ✅ | ✅ |
| الحالة | ✅ | ✅ | ✅ | ✅ |
| التاريخ من/إلى | ✅ | ✅ | ✅ | ✅ |
| عاجل فقط | ✅ | ✅ | ✅ | ✅ |
| متأخر فقط | ✅ | ✅ | ✅ | ✅ |
| السجل (مكتمل / ملغى) | ✅ | ✅ | ✅ | ✅ |
| مسح الفلاتر | ✅ | ✅ | ✅ | ✅ |

جميع الفلاتر **server-side** — لا تحميل كامل في الذاكرة.

### أعمدة الجدول

| العمود | ملاحظة |
|---|---|
| رقم الطلب | رابط إلى PAGE 03 (التفاصيل) |
| الفرع | مخفي لمستخدمي الفرع الواحد |
| النوع | شارة: اعتيادي / **عاجل** (نص + أيقونة — لا لون فقط) |
| تاريخ الطلب | `ar-SA-u-ca-gregory` locale (تقويم ميلادي بأرقام عربية — يمنع عرض أم القرى في بعض البيئات) |
| الموعد المطلوب | إلزامي للعاجل؛ اختياري/قابل للإعداد للاعتيادي (PD-02) |
| المراحل النشطة | `active_stages[]` — قد يكون متعدداً (مطبخ + مستودع بالتوازي) |
| الحالة | DRAFT / SUBMITTED / APPROVED / … |
| تقدم الأصناف | إجمالي الأصناف: مكتملة / جزئية / لم تبدأ + شريط تقدم بالنسبة المئوية. **لا يُجمع qty بين وحدات مختلفة على مستوى الطلب.** |
| المسؤولون الحاليون | `current_owner_roles[]` — يعكس المراحل النشطة الفعلية |
| SLA | `sla_stage` + `sla_due_at` + `sla_status` (ON_TIME / APPROACHING / OVERDUE) — للـLAN Trial يخص مرحلة الاعتماد فقط |
| آخر تحديث | `ar-SA-u-ca-gregory` locale (تقويم ميلادي بأرقام عربية — يمنع عرض أم القرى في بعض البيئات) |
| عرض التفاصيل | زر ← PAGE 03 |

> عند اكتمال مرحلة واحدة (مثلاً المطبخ) يُحذف دورها من القائمة ويبقى المسؤول الفعلي المتبقي.
> عرض المثال: «إنتاج المطبخ + تنفيذ المستودع» أو «المستودع» عند اكتمال المطبخ.

> الكميات التفصيلية لكل صنف بوحدته تظهر في PAGE 03 فقط.
> لا يُحسب SUM عبر وحدات مختلفة (كجم، كرتون، حبة) على مستوى الطلب.

التفاصيل الكاملة (المعتمد / المنتج / المصروف) في PAGE 03 فقط.

### Pagination

```
Default page size : 25
Options           : 25 / 50 / 100
Maximum enforced  : 100 (server-side)
API response      : { items, total, page, page_size, total_pages }
```

---

## 12. الصلاحيات والإجراءات المستهدفة

| الدور | النطاق | إنشاء | إجراءات في القائمة |
|---|---|---|---|
| `branch_user` | فرعه فقط | ✅ → PAGE 02 | عرض، إرسال مسودة |
| `branch_manager` | فرعه فقط | ✅ → PAGE 02 | عرض، إرسال مسودة |
| `area_manager` | City + Brand (لا DRAFT) | ❌ | عرض فقط |
| `operations_manager` | Global read-only (بعد OP-BR-01) | ❌ | عرض فقط |
| `internal_auditor` | Global read-only | ❌ | عرض فقط + ReadOnlyBanner |
| `admin` | Global | ✅ مع اختيار الفرع → PAGE 02 | عرض فقط في القائمة |
| `super_admin` | Global | ✅ مع اختيار الفرع → PAGE 02 | عرض فقط في القائمة |
| Kitchen / Warehouse / Delivery | ❌ | ❌ | 403 |

**قواعد ثابتة في القائمة:**
- زر «إنشاء طلب توريد» يظهر فقط لمن يملك صلاحية الإنشاء.
- لا اعتماد سريع / رفض سريع / حذف / تعديل حالة مباشرة.
- الضغط على الصف يفتح PAGE 03 (التفاصيل) — **رقم الطلب** و**تفاصيل** يجب أن يكونا `<a>` أو `<button>` قابلين للوصول بـTab وEnter؛ لا يُعتمد على `onClick` للصف وحده (انظر §13).
- الاعتماد والرفض حصراً في PAGE 04 (صفحة الاعتماد).

---

## 13. حالات الواجهة المستهدفة

| الحالة | السلوك المستهدف |
|---|---|
| Loading | Skeleton rows + فلاتر معطلة |
| Empty — scope | «لا توجد طلبات لهذا الفرع» + CTA إنشاء (branch roles) |
| Empty — filters | «لا توجد نتائج مطابقة لهذه الفلاتر» + زر مسح الفلاتر |
| API Error | بانر مضمّن + زر إعادة المحاولة؛ الفلاتر محفوظة |
| 403 | بطاقة RouteRoleGuard + رابط للداشبورد |
| Missing scope / configuration | رسالة توضيحية + رابط للدعم |
| فلتر غير صالح بعد مسحه | صفحة فارغة مؤقتة ← تعود للعرض الافتراضي |
| 401 انتهاء الجلسة | إعادة توجيه لصفحة تسجيل الدخول |
| Auditor read-only | ReadOnlyBanner أعلى الصفحة |

> **إمكانية الوصول بالكيبورد:** رقم الطلب وزر «تفاصيل» يجب أن يكونا روابط `<a>` أو `<button>` فعلية قابلة للوصول بـTab وEnter.
> لا يُعتمد على `onClick` للصف وحده.

---

## 14. التغييرات المطلوبة في Backend / API

### Schema Migration (PD-01)

```sql
-- حقول request_type الجديدة على جدول branch_requests
request_type   ENUM('REGULAR', 'URGENT')  NOT NULL DEFAULT 'REGULAR'
urgent_reason  TEXT                        NULL  -- إلزامي عند URGENT
needed_by      TIMESTAMPTZ                 NULL  -- إلزامي عند URGENT؛ اختياري/قابل للإعداد عند REGULAR
```

حقل `priority` الحالي:
**DATA PROFILING + MIGRATION DECISION REQUIRED** — لا يُستبدل قبل:
- فحص القيم الموجودة في 5,351 طلباً (HIGH / NORMAL / نص حر؟).
- حصر الصفحات والخدمات التي تقرأ `priority` أو تكتبه.
- تحديد استراتيجية الترحيل.
يُسجل كـ DATA-01 في `DATA_MODEL_CHANGES.md`.

### List DTO — إضافة حقول

| الحقل | المصدر |
|---|---|
| `request_type` | `branch_requests.request_type` |
| `urgent_reason` | `branch_requests.urgent_reason` |
| `needed_by` | `branch_requests.needed_by` |
| `active_stages[]` | مصفوفة المراحل النشطة حالياً — قد تحتوي أكثر من مرحلة عند التوازي |
| `current_owner_roles[]` | مصفوفة الأدوار المسؤولة حالياً — تتزامن مع `active_stages[]` |
| `total_lines` | عدد أصناف الطلب الإجمالي |
| `completed_lines` | أصناف مكتملة (qty_delivered >= qty_requested) |
| `partial_lines` | أصناف سُلِّم منها جزء |
| `pending_lines` | أصناف لم يبدأ تنفيذها |
| `completion_percent` | (completed_lines / total_lines) × 100 — «نسبة الأصناف المكتملة»؛ للشريط فقط. يُرجع 0 إذا total_lines = 0. لا يدخل الجزئي في الحساب لتجنب الالتباس. |
| `sla_stage` | `"area_manager_approval"` (الوحيدة المُعرَّفة الآن) |
| `sla_due_at` | `submitted_at + SLA threshold` (من system_settings) |
| `sla_status` | `ON_TIME` / `APPROACHING` / `OVERDUE` |

> الكميات التفصيلية لكل صنف بوحدته تظهر في PAGE 03 فقط.
> لا يُحسب SUM عبر وحدات مختلفة (كجم، كرتون، حبة) على مستوى الطلب.

حذف `lines[]` المتداخلة من الـlist response — تظهر في PAGE 03 فقط.

### فلاتر جديدة في List Endpoint

`request_type`, `stage`, `overdue_only`, `urgent_only`, `include_historical` (default=false), `sort` (field + direction)

### الأدوار

- إضافة `operations_manager` إلى `SCOPED_ROLES` لـGET (بعد OP-BR-01).
- إزالة `area_manager` و`internal_auditor` من POST `require_roles` ← code cleanup (يُتابع في PAGE 02 Backend review).

### SLA / Overdue (مؤقت للـLAN Trial)

**SLA مرحلة الاعتماد (مؤقت للـLAN Trial):**

الحقول المُضافة إلى List DTO:
```
sla_stage     : "area_manager_approval"  (الوحيدة المُعرَّفة الآن)
sla_due_at    : submitted_at + SLA threshold (من system_settings)
sla_status    : ON_TIME | APPROACHING | OVERDUE
```

منطق `sla_status` (مطابق لـPD-03):
```
إذا status ∈ {SUBMITTED} (الحالات المعلقة فعلياً في الـEnum الحالي):
  OVERDUE     إذا now() >= sla_due_at
  APPROACHING إذا now() >= sla_escalation_at AND now() < sla_due_at
  ON_TIME     إذا now() < sla_escalation_at
```

كلا الحقلين يأتيان من `system_settings` حسب `request_type`:
```
REGULAR: sla_escalation_at = submitted_at + 1hr   | sla_due_at = submitted_at + 2hr
URGENT:  sla_escalation_at = submitted_at + 10min | sla_due_at = submitted_at + 15min
```

حقول `sla_*` تُرجع null لأي طلب خارج مرحلة الاعتماد.

**SLA مراحل الإنتاج / المستودع / التوصيل:**
لا تُحدَّد الآن — تُقاس خلال LAN Trial وتُضاف في Phase 3 التصميم التقني.

**ملاحظة:** لا تُستخدم `PENDING_APPROVAL` إذا لم تكن حالة فعلية في الـEnum الحالي.
استخدم الحالات الموجودة في `BranchRequestStatus`.

### المؤشرات (Summary Endpoint)

```
GET /api/v1/branch-requests/summary
Response: { active, awaiting_approval, urgent, overdue }
نطاق: نفس نطاق الدور الحالي
```

### الأداء

**الأداء — فهارس (تُقيَّم في Phase 3):**

لا تُضاف فهارس جديدة قبل تشغيل `EXPLAIN ANALYZE` على الاستعلامات الفعلية.
المرشحات للتقييم:
```
(branch_id, created_at)
(status, created_at)
(request_type, needed_by)
```
نطاق area_manager قد يحتاج فهرساً مختلفاً حسب خطة الاستعلام.
يُسجل كـ PERF-03 في عناصر المتابعة.

- Default page_size في الـFrontend يتحول إلى 25 (من 100).
- الـBackend يُعيد `total_pages` في الـresponse.

---

## 15. معايير القبول

للتحقق قبيل إغلاق التنفيذ:

- [ ] صفحة القائمة قراءة/متابعة فقط؛ الإنشاء ينتقل إلى PAGE 02.
- [ ] الأدوار السبعة المصرح لها تعمل حسب §12؛ الأدوار غير المصرح لها تحصل على 403 API + بطاقة RouteRoleGuard.
- [ ] `branch_user` يرى فرعه فقط — عيّنة V.1 مُجتازة ✅.
- [ ] `area_manager` يرى City + Brand المخصصة له، لا DRAFT — V.2 + V.3 مُجتازة ✅.
- [ ] `internal_auditor` قراءة عالمية بلا فلتر — مُؤكَّد (by design) ✅.
- [ ] `operations_manager` قراءة عالمية فقط بعد OP-BR-01.
- [ ] `request_type` (اعتيادي / عاجل) مرئي وقابل للفلترة (PD-01).
- [ ] الطلبات العاجلة تُظهر `urgent_reason` و`needed_by` (PD-02).
- [ ] عمود المراحل النشطة + المسؤولون الحاليون بدون فتح التفاصيل.
- [ ] تقدم الأصناف (مكتمل / جزئي / لم يبدأ + شريط %) مرئي في صف القائمة. لا SUM عبر وحدات مختلفة.
- [ ] Pagination: 25 صفاً افتراضياً، خيارات 25/50/100، `total_pages` مرجع.
- [ ] KPI الأربعة تعكس نطاق المستخدم ± صفر على بيانات العيّنة.
- [ ] تسمية عربية RTL؛ التواريخ بـ`ar-SA-u-ca-gregory` locale (تقويم ميلادي بأرقام عربية — يمنع عرض أم القرى في بعض البيئات).
- [ ] Tablet: لا تمرير أفقي معطوب؛ درج فلاتر يعمل.
- [ ] جميع حالات الواجهة الثماني مُطبقة (§13).
- [ ] لا اعتماد / رفض / حذف في القائمة.
- [ ] `lines[]` لا يُضمَّن في list response.
- [ ] خطة الاستعلام (EXPLAIN ANALYZE) مراجَعة والفهارس المركبة المطلوبة مُضافة قبل الـdeploy (PERF-03).

---

## 16. الأسئلة المفتوحة والقرارات المُغلقة

### أ. قرارات PRODUCT_DECISIONS_FINAL.md (أسئلة عالمية)

| المعرف | القرار | الحالة |
|---|---|---|
| OQ-01 | قاعدة التغيير مسجلة مبدئيًا في PAGE 01 — انظر §16.ب | **DECISION RECORDED — FINAL RATIFICATION IN PAGE 02–05** |
| OQ-02 | قنوات التصعيد: إشعار داخل التطبيق / Push / علامة بصرية | **OPEN — يُحسم في Phase 3** |
| OQ-03 | Admin Exceptional Approval UI: نفس الزر أم مستقل؟ | **OPEN — يُحسم في PAGE 04 / PAGE 05** |

قواعد المرجعية:
- أرقام `OQ-*` محجوزة لـ`PRODUCT_DECISIONS_FINAL.md` فقط.
- القرارات المحلية لـPAGE 01 تستخدم معرف `PAGE01-D*`.

### ب. قاعدة OQ-01 المسجلة مبدئيًا — تغيير «اعتيادي → عاجل»

**الحالة: BASELINE APPROVED FOR PAGE 01 — GLOBAL CLOSURE PENDING PAGE 02–05**

| المرحلة | من يملك التغيير | الشروط |
|---|---|---|
| DRAFT | branch_user / branch_manager / admin / super_admin | بلا قيود |
| بعد SUBMIT وقبل الاعتماد | area_manager / admin / super_admin | سبب إلزامي + إشعار للفرع + Timeline entry |
| الفرع نفسه بعد SUBMIT | ❌ | لا يغير النوع مباشرة |
| بعد APPROVED | ❌ | النوع مقفول |
| عاجل جديد بعد الاعتماد | طلب عاجل منفصل | لا تعديل على الدورة الجارية |

**قواعد إضافية:**
- تغيير النوع وفعل الاعتماد سجلّان مستقلّان في Audit Trail — حتى لو حدثا في نفس الجلسة.
- إذا تحوّل الطلب إلى عاجل وهو متأخر أصلاً، لا يُعاد تصفير التأخير.
- SLA الجديد = `min(original_sla_due_at, urgency_changed_at + urgent_sla_threshold)`
- Timeline يسجل: النوع القديم، النوع الجديد، منفذ التغيير، السبب، الوقت.

### ج. قرارات محلية لـPAGE 01

| المعرف | القرار | الحالة |
|---|---|---|
| PAGE01-D01 | `internal_auditor` = قراءة عالمية بلا فلتر — by design | **CLOSED** |
| PAGE01-D02 | العرض الافتراضي = الطلبات النشطة فقط؛ السجل بزر منفصل | **CLOSED** |
| PAGE01-D03 | SLA في القائمة = مرحلة الاعتماد فقط للـLAN Trial؛ باقي المراحل تُحدد في Phase 3 | **CLOSED** |
| PAGE01-D04 | Admin create ينتقل إلى PAGE 02 بعد بنائه؛ النموذج القديم يُزال | **CLOSED** (dependency على PAGE 02) |

### د. عناصر متابعة (لا تمنع APPROVED)

| ID | البند | يُتابع في |
|---|---|---|
| OP-BR-01 | `operations_manager`: تمكين قراءة عالمية + إنشاء حساب اختباري رسمي | قبل E2E |
| PAGE01-TD01 | تحديد مصدر `active_stages[]` و`current_owner_roles[]` من حالات أوامر المطبخ والمستودع والتوصيل، وليس من `BranchRequest.status` وحده — الحالة الواحدة لا تمثل التوازي | Phase 3 |
| SEC-02 | فصل `BRANCH_REQUEST_READ_ROLES` عن `BRANCH_REQUEST_CREATE_ROLES` في الكود بدل استخدام `SCOPED_ROLES` مشتركاً | PAGE 02 Backend review |
| PERF-02 | حذف `lines[]` من list response → line-progress summary counts (completed/partial/pending) بدون جمع كميات عبر وحدات مختلفة | تصميم List DTO |
| PERF-03 | مراجعة خطة الاستعلام وإضافة الفهارس المركبة المناسبة — لا قرار قبل `EXPLAIN ANALYZE` | Phase 3 |
| DATA-01 | فحص قيم `priority` الحالية (5,351 طلب) وتحديد استراتيجية الترحيل قبل إضافة `request_type` | DATA_MODEL_CHANGES.md |
| PAGE01-BRANCH-MGR | `branch_manager` runtime: CODE VERIFIED / حساب مخصص لم يُختبر بعد | قبل E2E |

---

## 17. التوصية النهائية

| الخيار | الحكم |
|---|---|
| إبقاء الصفحة كما هي | ❌ — نقص PD-01/03 وKPI وPagination |
| **إعادة بناء Frontend** | ✅ **مُعتمَد** — نفس الـRoute؛ نقل الإنشاء لـPAGE 02؛ توسيع DTO والفلاتر والـpagination والـKPI |
| إعادة بناء Backend | ❌ غير لازم — الـscope والصلاحيات مُحققة |
| صفحة جديدة | ❌ نفس الوظيفة |

**الحالة النهائية: APPROVED — 2026-07-13**
Implementation status: TECHNICAL_DEPENDENCIES — pending DATA-01, OP-BR-01, Phase 3 indexes, PAGE 02.

---

## Appendix A — Evidence index

| File | Description |
|---|---|
| `_capture_meta.json` | Step 1–2 API + browser probe |
| `_steps_3_5_meta.json` | Step 3–5 verification + UX metadata |
| `ux_desktop_<role>.png` / `ux_tablet_<role>.png` | Step 3 per-role screenshots |
| `ux_filter_active.png` | Status filter SUBMITTED applied |
| `ux_empty_state.png` | No-match search empty table |
| `ux_pagination.png` | Admin list — no pagination controls |
| `ux_403_delivery_user.png` etc. | RouteRoleGuard forbidden state |
| `branch_user_desktop.png` / `tablet` | Step 1–2 catalog + list |
| `area_manager_*`, `internal_auditor_*`, `admin_*`, `super_admin_*` | Role views |

## Appendix B — Code references

```301:336:raed_inventory/frontend/src/pages/supply_chain/SupplyChainPages.jsx
export function SupplyChainBranchRequestsPage() {
  // ... role gates, reloadRequests(page_size: 100), list + inline create
```

```465:532:raed_inventory/backend/app/routers/branch_requests.py
@router.get("", response_model=BranchRequestListResponse)
def list_branch_requests(...):
    # scope: admin | branch | area_manager; auditor unfiltered
```

```2050:2051:raed_inventory/frontend/src/App.jsx
<Route path="/supply-chain/branch-requests" element={<RouteRoleGuard allowed={[...]}><SupplyChainBranchRequestsPage /></RouteRoleGuard>} />
```

---

*Review performed read-only. No application code, schema, routes, RBAC, or data modified.*
