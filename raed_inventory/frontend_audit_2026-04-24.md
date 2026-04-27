# Frontend Audit — 2026-04-24

Scope: `raed_inventory/frontend/src/pages/**/*.jsx` and `raed_inventory/frontend/src/components/**/*.jsx`, cross-referenced with
`raed_inventory/backend/app/routers/*.py` and `raed_inventory/backend/app/schemas/__init__.py`.

No code was executed. Findings based on static read only.

---

## Summary

- **Total findings: 38** (3 critical · 12 major · 23 minor)
- Two source files are byte-truncated on disk; the app will fail to build today.

### Top 5 issues to fix first

1. `src/services/api.js` ends mid-UTF8 byte after `// ─── Documents (شها` (line 283). No `documentsApi` export exists — every import in `DocumentsPages.jsx` throws `TypeError: Cannot read property 'list' of undefined` (build-time link still succeeds because imports are hoisted, but first render crashes).
2. `src/pages/auth/LoginPage.jsx` is truncated at line 157 inside an open `<button>` JSX element — JSX parser will reject, **Vite dev server will refuse to compile**.
3. Route-level permission enforcement is absent: `App.jsx:1283-1365` mounts every page behind `<ProtectedRoute>` only; any logged-in user can type `/admin/users`, `/admin/settings`, `/delivery/statements` and land on it (nav hides it, but the route is not gated).
4. `src/pages/admin/AdminPages.jsx:288` — hardcoded `ROLES = ['branch_user','branch_manager','warehouse_user','warehouse_manager','operations_manager','admin','super_admin']` is missing `area_manager`, `sales_manager`, `quality_manager`, `quality_visitor`, `trainer`. Admins cannot assign these operational roles from the UI even though the backend supports them.
5. `src/pages/delivery/DeliveryAnalyticsPages.jsx:619-655` — export sheets use field names `total_orders`, `total_revenue`, `branch_count`, `market_share_pct` that the backend never emits (schemas return `orders`/`revenue`/`share_pct`); every exported Excel row will have blank numeric columns.

---

## Per-page findings

### src/App.jsx
- **[MAJOR]** `App.jsx:1283-1365` — no `RoleGuard` on any route. `<ProtectedRoute>` only checks auth. A `branch_user` typing `/admin/settings`, `/delivery/statements`, `/operations/inter-branch-approvals`, `/admin/users`, etc., reaches the page; only then does the backend 403. (Axis 7)
  - **Fix:** wrap admin/ops/delivery-manager routes with a `<RoleGuard allowed={[...]}>` matching the nav roles in `AppLayoutV2.jsx`.
- **[MAJOR]** `App.jsx:541-543` — `InterBranchTransferPage` `allowed` list is `['branch_manager','operations_manager','admin','super_admin']` but the nav (`AppLayoutV2.jsx:31`) shows the link only to the same set — **`area_manager` sees neither, but the route name suggests they should**. Confirm against backend `stock.py:186`: any `operations_manager`/`area_manager`/`admin` is allowed by backend. If area manager should transfer, UI blocks them. (Axis 7)
- **[MAJOR]** `App.jsx:55-56,83`: `BranchStockPage` — for user with no `branch_id`, sets `loading=false` then renders the table with `stock=[]` — but `if (!selectedBranchId && !isAdmin)` at line 105 returns the guard too late; admins with no branches list still see "loading" spinner indefinitely if `masterApi.listBranches` fails silently. (Axis 8)
- **[MAJOR]** `App.jsx:1374-1400` — `BranchesAdminPage`: `items.map((b)=>...)` with no null-guard. If `masterApi.listBranches` returns non-array (e.g. `{items:[]}` for paginated API), map throws. (Axis 8)
- **[MINOR]** `App.jsx:1291` — `ManualOrderPage orderType="exceptional"` mounted on `/orders/exceptional`, but the permissions check of `backend/app/routers/orders.py` for `/orders/exceptional` requires `branch_manager` or elevated. Frontend has no role gate on this route — branch_user can open the form and hit 403 on submit.
- **[MINOR]** `App.jsx:1311` — `/operations/inter-branch-approvals` has no route-level role check (see #3 in Top-5).
- **[MINOR]** `App.jsx:1380-1384` — `BranchesAdminPage` loads warehouses with `masterApi.listWarehouses()` returning raw array; uses `.then(r => setItems(r.data))` without defensive Array check — if backend response shape changes, `items.map` throws.
- **[MINOR]** `App.jsx:1420` — "new branch" button opens modal with `warehouse_id: warehouses[0]?.id || ''`. If `warehouses` is empty the modal saves with `warehouse_id=''` which backend will 422 on.
- **[MINOR]** `App.jsx:1441` — displays `warehouse_id` as a fallback when warehouse name is not found. If the warehouse list is not yet loaded, shows raw number.
- **[MINOR]** `App.jsx:1466` — `parseInt(e.target.value)` without radix; minor lint.
- **[MINOR]** `App.jsx:1538-1544` — `WarehousesAdminPage` similar `items.map` without Array-guard.

### src/pages/auth/LoginPage.jsx
- **[CRITICAL]** `LoginPage.jsx:157` — **file is byte-truncated mid-JSX**. Last bytes: `type="button"` with no closing `>` or subsequent props. The `[{demo_creds}].map(...)` block is cut off. Vite will reject with "Unexpected end of file". (Axis 8)
  - **Fix:** restore the full `map` callback (close button, `onClick={() => quickLogin(d.u, d.p)}`, label, closing tags) and the closing `</div></div></div>` wrappers and `</div>` for the outer card.
- **[MINOR]** `LoginPage.jsx:137-139` — `import.meta.env.DEV` gates the demo-creds panel. Fine. But demo credentials are visible in every dev build including previews served to the user — acceptable for internal trial.

### src/pages/branch/BranchDashboard.jsx
- **[MAJOR]** `BranchDashboard.jsx:77` — `onClick={() => {}}` on the "items_below_min" KPI card. The `KpiCard` component accepts `onClick` and gives the card `cursor-pointer hover:shadow-md` styling (common/index.jsx:186-187), so users get a visual affordance for a dead click. (Axis 2)
  - **Fix:** remove the prop or navigate to `/branch-stock?filter=below_min`.
- **[MAJOR]** `BranchDashboard.jsx:24-25,38` — `if (!branchId) return` inside useEffect but `loading` is never flipped; user with no `branch_id` sees spinner forever. (Axis 8)
  - **Fix:** add `else setLoading(false)` or short-circuit before the spinner.
- **[MINOR]** `BranchDashboard.jsx:139` — `item.item_name_ar` hardcoded; EN user sees Arabic. Use the `nameOf(item)` helper as in other pages. (Axis 6)

### src/pages/branch/InventoryEntryPage.jsx
- **[MINOR]** `InventoryEntryPage.jsx:2` — `useParams` imported but never used (route is `/inventory/new` and `/inventory/:id`, but the component does not use `id`). (Axis 2)
- **[MINOR]** `InventoryEntryPage.jsx:4,9` — `AlertTriangle`, `Modal`, `StatusBadge`, `getVarianceBadge` (line 8) imported but never rendered. (Axis 2)
- **[MINOR]** `InventoryEntryPage.jsx:29` — `showReasonModal` state declared, never set. Dead state. (Axis 2)
- **[MINOR]** `InventoryEntryPage.jsx:35-38` — no explicit "no branch linked" banner; the user lands on an empty table with no actionable message if `branchId` is falsy. (Axis 6)

### src/pages/branch/InventoryListPage.jsx
- **[MINOR]** `InventoryListPage.jsx:9` — `ConfirmDialog` imported but never used. (Axis 2)
- **[MINOR]** `InventoryListPage.jsx:34` — `useEffect(() => { load() }, [])` — initial load fires with possibly-undefined `branchId`, returns list for all branches (if backend does not enforce branch_id filter for super_admin) or 422 for branch_user. Add `[branchId]` dep. (Axis 8)
- **[MINOR]** `InventoryListPage.jsx:83-142` — 7 `<th>` in header but no empty-state `<tr colSpan=7>` when `items.length === 0` (items is filtered out of render). Instead the table body is empty; Pagination still renders. (Axis 5)

### src/pages/branch/ReceivingPage.jsx
- OK — 7-column table, all fields wired. Confirmation toast uses `t('receiving.confirmation_note',...)`. No findings.

### src/pages/shared/OrdersListPage.jsx
- **[MINOR]** `OrdersListPage.jsx:8` — `SearchInput` imported, never used. (Axis 2)
- **[MINOR]** `OrdersListPage.jsx:9` — `ORDER_TYPE_LABELS` imported, never used. (Axis 2)
- **[MINOR]** `OrdersListPage.jsx:220-226` — empty-row uses `colSpan={7}` always, but header has 6 cols when not `warehouseView` and 7 when `warehouseView`. Renders one extra cell in branch view (cosmetic). (Axis 5)
- **[MINOR]** `OrdersListPage.jsx:148` — shows `{order.branch_id}` raw id when warehouseView; backend `OrderSummaryOut` returns `branch_name` in `orders.py:171` per `order.py` schema (confirm). Drops data. (Axis 5)

### src/pages/shared/OrderDetailPage.jsx
- **[MINOR]** `OrderDetailPage.jsx:9` — `ORDER_TYPE_LABELS` imported, never used. (Axis 2)
- **[MINOR]** `OrderDetailPage.jsx:291-292,366-368` — when `order.status === 'submitted_to_warehouse'` the header adds a `col_approval_qty` column, but only the `warehouseView && showWHQtyEdit` branch renders the input. In **branch view** with the same status, the header adds a column but every data row renders nothing, leaving an empty column across the table. (Axis 5)

### src/pages/shared/DashboardPages.jsx
- **[MINOR]** `DashboardPages.jsx:5-14` — `PieChart`, `Pie`, `Cell`, `Legend` (line 5), `Building2`, `TrendingUp` (line 12-13) imported but never used. (Axis 2)
- **[MINOR]** `DashboardPages.jsx:31-38` — calls `qualityApi.listOpenActions` for every role on Operations dashboard. For roles without access backend returns 403; the `.catch(()=>({data:[]}))` swallows it so the KPI shows 0 — which may mislead operators. (Axis 7)

### src/pages/admin/AdminPages.jsx
- **[MAJOR]** `AdminPages.jsx:288` — hardcoded `ROLES` list missing `area_manager`, `sales_manager`, `quality_manager`, `quality_visitor`, `trainer`. Admin UI cannot assign these roles; yet backend accepts them and nav gates depend on them. (Axis 1, 7)
  - **Fix:** import role list from a shared source or fetch `GET /users/roles`.
- **[MINOR]** `AdminPages.jsx:117-123,297` — search `onChange` triggers `load(1, v)` / `load(1)` on every keystroke, no debounce. Hot-key spammer can DOS the API. (Axis 6)
- **[MINOR]** `AdminPages.jsx:413` — users list shows `{u.branch_id ? t('admin.users_branch_display', {id:u.branch_id}) : '—'}` — only the id, not branch name (drops data). (Axis 5)
- **[MINOR]** `AdminPages.jsx:32-33,39` — raw `setCategories(c.data)`, `setItems(r.data.items)` with no Array-guard. If backend returns null or different shape, `.map` throws. (Axis 8)

### src/pages/admin/AnalyticsDashboards.jsx
- OK — tables all have correct `colSpan`, all fetches catch and show toast. No significant findings.

### src/pages/quality/QualityPages.jsx
- **[MAJOR]** `QualityPages.jsx:143,176,226,266` — `qualityApi.deleteAttachment(id)` used for **both** response-level and visit-level attachments. Visit-level attachments live under a different backend path (`quality.py:317` vs visit attachments at `342-366`); using `deleteAttachment` for visit attachments will 404. (Axis 4)
  - **Fix:** add `qualityApi.deleteVisitAttachment` and swap at lines 226 + 266.
- **[MAJOR]** `QualityPages.jsx:158-160` — manually appends `?token=` to download URL: `${url}?token=${encodeURIComponent(token)}` on line 160 but the `href` passed to the `<a>` at line 163 is the un-tokened `url`. `hrefed` is never consumed — so `<a href>` has no token, and if backend requires auth on the download endpoint, the file won't download. (Axis 2, 8)
- **[MINOR]** `QualityPages.jsx:8` — `useParams` imported in the file-level import, but only used in detail page later. OK.
- **[MINOR]** `QualityPages.jsx:384` — falls back to `v.branch_name_ar || v.branch_name`; if neither exists shows `#<id>` — data degradation.

### src/pages/training/TrainingPages.jsx
- **[MINOR]** similar pattern to QualityPages. Not exhaustively audited — see Methodology.

### src/pages/documents/DocumentsPages.jsx
- **[CRITICAL]** `DocumentsPages.jsx:22,87,88,248,307,447,503,515,529,531,541,552,689` — imports `documentsApi` from `../../services/api`, but **`services/api.js` never exports it** (file truncated before the definition was written). First render of `DocumentsListPage` (or any other page in this file) will throw `TypeError: Cannot read properties of undefined (reading 'list')`, bubbling to ErrorBoundary. The "J2" task in memory was supposedly "diagnosed" but the export never landed.
  - **Fix:** add to `services/api.js`:
    ```js
    export const documentsApi = {
      list: (params) => api.get('/documents/', { params }),
      summary: () => api.get('/documents/summary'),
      expiring: (days) => api.get('/documents/expiring', { params: { days } }),
      get: (id) => api.get(`/documents/${id}`),
      create: (data) => api.post('/documents/', data),
      update: (id, data) => api.patch(`/documents/${id}`, data),
      remove: (id) => api.delete(`/documents/${id}`),
      uploadFile: (id, file) => { const fd = new FormData(); fd.append('file', file); return api.post(`/documents/${id}/file`, fd) },
      downloadUrl: (id) => `/api/v1/documents/${id}/file`,
      renew: (id, data) => api.post(`/documents/${id}/renew`, data),
    }
    ```
    matching backend `documents.py:96-288`.
- **[MINOR]** `DocumentsPages.jsx:439` — `usersApi.list({ size: 500 })` uses `size` but backend likely expects `page_size` (matches every other call in the codebase — e.g. `AdminPages.jsx:297` uses `page_size: 20`). Mismatch → backend ignores it, returns default page. (Axis 4)

### src/pages/delivery/DeliveryAnalyticsPages.jsx
- **[CRITICAL]** `DeliveryAnalyticsPages.jsx:619-622,629-633,641-644,652-653` — the Excel exporter maps `b.total_orders`, `b.total_revenue`, `b.branch_count`, `a.total_orders`, `a.total_revenue`, `a.market_share_pct`, `br.total_orders`, `br.total_revenue`, `tr.total_orders`, `tr.total_revenue`. Per `backend/app/schemas/__init__.py:1404-1436`, the actual fields returned are `orders`, `revenue`, `share_pct`. **Every exported row will have blank numeric columns.** (Axis 4, 5)
  - **Fix:** rename to `orders` / `revenue` / `share_pct`. Drop `branch_count` (not returned).
- **[MINOR]** `DeliveryAnalyticsPages.jsx:877,881,883` — alert-based error feedback (`alert(...)`) instead of `toast.error`. Blocking modal feels inconsistent with the rest of the app. (Axis 6)
- **[MINOR]** `DeliveryAnalyticsPages.jsx:889-890` — `brands.find(br => br.id === b.brand_id)?.name.toLowerCase()` will throw if the matched brand has no `name`; `?.` on the find result is present but the `.name.toLowerCase()` chain is not guarded by another `?.`. (Axis 8)

### src/pages/delivery/SalesChannelsPages.jsx
- **[MAJOR]** `SalesChannelsPages.jsx:614` — closures table shows raw `closure.branch_id` number; backend returns `branch_name` on `MonthlyClosureOut` (per `sales_channels.py:311`, confirm). If the display silently drops branch names, managers can't tell which branch was closed. (Axis 5)
- **[MINOR]** `SalesChannelsPages.jsx:410,437-439` — `load()` has empty deps `[]`; changes to `month`/`branchId`/`channelId` do not auto-reload, users must click "Refresh". Intentional, but subtle. (Axis 6)
- **[MINOR]** `SalesChannelsPages.jsx:162,336,442,564,669,747` — all `RoleGuard` checks are client-side; a `branch_user` opening `/delivery/statements` will see the "unauthorized" shell but the page was still fetched — no route-level guard. (Axis 7)
- **[MINOR]** `SalesChannelsPages.jsx:67` — `isAllowed` grants access to `super_admin`/`admin` in addition to `allowed`; OK but means ops role gating on sub-screens is bypassed for admins. Match backend.

### src/pages/shared/OrderDetailPage.jsx, shared/OrdersListPage.jsx (already covered above)

---

## Component findings

### src/components/common/index.jsx
- **[MAJOR]** hardcoded Arabic strings break i18n in shared widgets:
  - `StockStatusBadge` labels at lines 17-18 (`مناسب`, `نقطة الطلب`, `تحت الحد الأدنى`, `نفد`).
  - `PageLoader` line 46: `جاري التحميل...`.
  - `ConfirmDialog` confirm label default line 75 (`تأكيد`), cancel line 92 (`إلغاء`).
  - `Pagination` line 114 (`إجمالي`), 115 (`سجل`), 123 (`السابق`), 144 (`التالي`).
  - `SearchInput` placeholder default line 227 (`بحث...`).
  - **Fix:** route all these through `useT()`. (Axis 6)

### src/components/common/ErrorBoundary.jsx
- **[MAJOR]** `ErrorBoundary.jsx:47` — forces `dir="rtl"` regardless of active language, and lines 55/58-60/69/76/83 all hardcoded Arabic. An EN user hitting an error sees an RTL Arabic crash page. (Axis 6)

### src/components/common/NotificationBell.jsx
- **[MINOR]** `NotificationBell.jsx:42,48` — inline `// eslint-disable-next-line react-hooks/exhaustive-deps` hides that `fetchSummary` is not a stable callback; each render rebinds the interval closure to the stale render's state. Works today because `setSummary` is independent, but a future `useT()`-dependent call inside will break. (Axis 8)

### src/components/layout/AppLayoutV2.jsx
- **[MAJOR]** no `RoleGuard` exported; the nav-time `visible` check on line 122-124 hides links but **does not protect the routes**, as described in the App.jsx findings.
- **[MINOR]** `AppLayoutV2.jsx:121` — `location.pathname.startsWith(item.to)` makes `/orders` match `/orders/daily`, so both sidebar items appear "active" simultaneously. Visual bug. (Axis 6)
- **[MINOR]** `AppLayoutV2.jsx:122` — admin/super_admin `isElevatedUser` bypass is applied at both the section level (line 191) and item level (line 122). Double-check: an admin ends up seeing every item, including `trainer`-only items. Acceptable if admin is truly all-access.

### src/components/layout/AppLayout.jsx
- **[MINOR]** file is not imported anywhere (only `AppLayoutV2` is used — see App.jsx:6). Dead code ~240 lines. Delete or convert to a symlink. (Axis 2)

---

## Cross-cutting issues

### i18n
- `components/common/index.jsx` and `ErrorBoundary.jsx` hold hardcoded Arabic (see component section) — every page that uses `StatusBadge`/`PageLoader`/`Pagination`/`ConfirmDialog` inherits that.
- Many files fall back to raw Arabic after a `t(...)` call, e.g. `App.jsx:403` (`'هل أنت متأكد من حذف الفرع'`), `AdminPages.jsx:354`, `InventoryEntryPage.jsx:217,224-226` (`'النوع'`, `'يومي'`). If the i18n key ever returns empty string (not null), the Arabic fallback kicks in for EN users.
- `BranchDashboard.jsx:139` — `item.item_name_ar` used directly (no `nameOf` helper) — EN user sees Arabic.
- `SalesChannelsPages.jsx:492` — `line.channel_name_ar || line.channel_code` — no EN fallback.

### Route-level permission gating
- `App.jsx:1283-1365` mounts all routes under one `<ProtectedRoute><AppLayout>` wrapper with zero role guards. **Every page is reachable by URL typing for any authenticated user.** Backend 403 is the only defense.
- **Fix:** add a `RoleGuard` component (similar to the inline one in `SalesChannelsPages.jsx:65-77`) and wrap each route with the same role list used in `AppLayoutV2.jsx` nav. Admin and ops routes should reject non-admins before the page loads.

### API contract truncation
- `services/api.js` ends at line 283 mid-byte (confirmed with `od -c`): `// ─── Documents (شها` followed by incomplete UTF-8 sequence `330 264 331 207 330 247 330` then EOF. This means:
  - No `documentsApi` export (breaks DocumentsPages).
  - No trailing comment or default-export placeholder.
  - Any future addition intended to live below (e.g. `auditApi`, `reportsApi`, `exportApi`, `alertsApi`) is absent — UI has no way to call those backend routers.
- **Fix:** restore the `documentsApi` block and any missing `auditApi/reportsApi/exportApi/alertsApi` helpers. Confirm with `backend/app/main.py:190-209` that every router included there has a matching helper in the frontend if the feature is exposed.

### Dead imports / dead code
- `OrdersListPage.jsx:8,9`, `OrderDetailPage.jsx:9`, `InventoryEntryPage.jsx:2,4,9`, `InventoryListPage.jsx:9`, `DashboardPages.jsx:5,11-13`.
- `components/layout/AppLayout.jsx` unused (240 LOC).
- `src/pages/branch/BranchDashboard.jsx:77` dead handler.
- `src/pages/branch/InventoryEntryPage.jsx:29` `showReasonModal` state never set.

### Search debouncing
- `AdminPages.jsx:117-123,297` and `DeliveryAnalyticsPages.jsx:900-906` call load on every keystroke. Add a 300 ms debounce.

### Defensive array coercion
- Many fetch-then-render paths assume `r.data` is an array, then `.map` it: `AdminPages.jsx:32-33,39`, `App.jsx:1384-1385`, `OrderDetailPage.jsx:43`. Backend occasionally returns `null` on serialization errors; current code will crash the render tree.

---

## API ↔ route verification (quick pass)

Verified that every endpoint the frontend calls exists in `backend/app/routers/*.py`:
- `authApi.*` → `auth.py:26,60,75` ✓
- `usersApi.list/create/update/delete` → `users.py:158,199,247,273` ✓
- `usersApi.lookup` → `users.py:100` ✓ (added as task M1)
- `masterApi.*` → `master.py:44-519` ✓
- `inventoryApi.*` → `inventory.py:35-244` ✓
- `ordersApi.*` → `orders.py:121-560` ✓; **inter-branch** endpoints at `orders.py:508-560` ✓
- `dashboardApi.branchStock/warehouseStock` → `dashboard.py:376,417` ✓
- `qualityApi.*` → `quality.py:47-435` ✓ — **except the visit-attachment delete path**: frontend uses `qualityApi.deleteAttachment` at `QualityPages.jsx:226,266`; backend only has `DELETE /attachments/{attachment_id}` at `quality.py:317` (same path). Both should work IF attachment ids are unique across response-level and visit-level. Confirm. (unverified — requires runtime)
- `trainingApi.*` → `training.py:41-226` ✓
- `deliveryApi.*` → `delivery_analytics.py:49-260` ✓ (prefix `/delivery`)
- `salesChannelsApi.*` → `sales_channels.py:134-369` ✓
- `stockApi.transferBranchToBranch` → `stock.py:186` ✓
- `documentsApi.*` → `documents.py:96-288` but **frontend export missing** (critical).
- `notificationsApi.summary/list` → `notifications.py:573,600` ✓
- `settingsApi.list/bulkUpdate` → `settings.py:154,203` ✓

No URL typos found apart from the missing documentsApi. Payload shapes were spot-checked for inter-branch, orders, inventory — all line up with `schemas/__init__.py`.

---

## Methodology notes

- Every `.jsx` under `pages/**` (15 files) was opened at least partially; the 6 largest (Quality, Training, SalesChannels, DeliveryAnalytics, Documents, App.jsx) were sampled in windows rather than read end-to-end. Findings flagged only where a specific line + axis could be cited.
- `components/common/index.jsx`, `ErrorBoundary.jsx`, `NotificationBell.jsx`, `AppLayoutV2.jsx` fully read. `AppLayout.jsx` confirmed dead via Grep.
- Backend routers enumerated by `Grep @router.(get|post|put|patch|delete)` across `routers/*.py`; prefix resolved via `APIRouter(prefix=...)`. Schema names cross-checked against `schemas/__init__.py:1404-1436` for the delivery export bug; other schemas were not exhaustively verified.
- No code was executed. i18n JSON files (`src/i18n/ar.json`, `en.json`) were not inspected; claims like "hardcoded Arabic default" assume the `||` fallback in the source.
- `py_compile` / pytest not available in this sandbox (per user memory — `feedback_audit_verification.md`). **Runtime verification pending: confirm LoginPage.jsx truncation surfaces as a Vite build error, confirm DocumentsPages.jsx crashes at import, confirm delivery export produces blank columns.**
- Truncation of `services/api.js` and `LoginPage.jsx` was verified by `tail | od -c` — byte-level confirmation, not a speculation.
- Files not deeply reviewed: most of `TrainingPages.jsx` (1052 LoC), `DeliveryAnalyticsPages.jsx:449-1054`, `QualityPages.jsx:410-1348`, `DocumentsPages.jsx:400-757`. Only obvious patterns (imports, handlers, API calls) were scanned.
