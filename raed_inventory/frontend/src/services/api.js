import axios from 'axios'

const normalizeBasePath = (value, fallback) => {
  const raw = String(value || fallback || '').trim()
  if (!raw) return fallback
  return raw.endsWith('/') ? raw.slice(0, -1) : raw
}

export const stockApi = {
  adjustBranch: (branchId, data) => api.post(`/stock/branches/${branchId}/adjust`, data),
  adjustWarehouse: (warehouseId, data) => api.post(`/stock/warehouses/${warehouseId}/adjust`, data),
  bulkAdjustWarehouse: (warehouseId, data) => api.post(`/stock/warehouses/${warehouseId}/bulk-adjust`, data),
  exportWarehouseStock: (warehouseId, format = 'xlsx') =>
    api.get(`/export/stock/warehouses/${warehouseId}`, { params: { format }, responseType: 'blob' }),
  transferWarehouseToBranch: (warehouseId, branchId, data) =>
    api.post(`/stock/transfer/warehouse-to-branch?warehouse_id=${warehouseId}&branch_id=${branchId}`, data),
  transferBranchToWarehouse: (branchId, warehouseId, data) =>
    api.post(`/stock/transfer/branch-to-warehouse?branch_id=${branchId}&warehouse_id=${warehouseId}`, data),
  transferBranchToBranch: (data) => api.post('/stock/transfer/branch-to-branch', data),
}

export const replenishmentApi = {
  runNow: (daysOfCover = 3) =>
    api.post(`/orders/auto-replenishment/run?days_of_cover=${daysOfCover}`),
}

export const notificationsApi = {
  summary: () => api.get('/notifications/summary'),
  list: (params) => api.get('/notifications/list', { params }),
}

export const documentsApi = {
  list: (params) => api.get('/documents/', { params }),
  get: (id) => api.get(`/documents/${id}`),
  create: (data) => api.post('/documents/', data),
  update: (id, data) => api.patch(`/documents/${id}`, data),
  remove: (id) => api.delete(`/documents/${id}`),
  renew: (id, data) => api.post(`/documents/${id}/renew`, data),
  summary: () => api.get('/documents/summary'),
  expiring: (days = 30) => api.get('/documents/expiring', { params: { days } }),
  uploadFile: (id, file) => {
    const fd = new FormData()
    fd.append('file', file)
    return api.post(`/documents/${id}/file`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  downloadUrl: (id) => `/api/v1/documents/${id}/file`,
}

export const settingsApi = {
  list: () => api.get('/settings'),
  get: (key) => api.get(`/settings/${key}`),
  update: (key, value) => api.put(`/settings/${key}`, { value }),
  bulkUpdate: (settings) => api.put('/settings', { settings }),
}

const PRIMARY_API_BASE = normalizeBasePath(import.meta.env.VITE_API_BASE_PATH, '/api/v1')
const FALLBACK_API_BASE = PRIMARY_API_BASE === '/api/v1' ? '/api' : null

const shouldRetryWithFallbackBase = (error) => {
  if (!FALLBACK_API_BASE) return false
  const status = error?.response?.status
  return (
    error?.code === 'ERR_NETWORK' ||
    status === 404 ||
    status === 502 ||
    status === 503 ||
    status === 504
  )
}

const api = axios.create({
  baseURL: PRIMARY_API_BASE,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (res) => res,
  (error) => {
    const config = error.config
    if (
      config &&
      !config._baseFallbackTried &&
      shouldRetryWithFallbackBase(error) &&
      String(config.baseURL || PRIMARY_API_BASE) === PRIMARY_API_BASE
    ) {
      config._baseFallbackTried = true
      config.baseURL = FALLBACK_API_BASE
      return api.request(config)
    }

    if (error.response?.status === 401) {
      const url = String(config?.url || '')
      // Failed login returns 401 — do not hard-redirect (user is already on /login) or clear flow mid-toast.
      const isLoginAttempt = url.includes('/auth/login')
      if (!isLoginAttempt) {
        localStorage.removeItem('access_token')
        localStorage.removeItem('user')
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export { shiftOpsApi } from './shiftOpsApi'

export default api

export const authApi = {
  login: (username, password) => api.post('/auth/login', { username, password }),
  me: () => api.get('/auth/me'),
  changePassword: (old_password, new_password) =>
    api.post('/auth/change-password', { old_password, new_password }),
}

export const usersApi = {
  list: (params) => api.get('/users/', { params }),
  roles: () => api.get('/users/roles'),
  lookup: (params) => api.get('/users/lookup', { params }),
  get: (id) => api.get(`/users/${id}`),
  create: (data) => api.post('/users/', data),
  update: (id, data) => api.put(`/users/${id}`, data),
  delete: (id) => api.delete(`/users/${id}`),
  resetPassword: (id, new_password) => api.post(`/users/${id}/reset-password`, { new_password }),
}

export const branchEmployeesApi = {
  list: (params) => api.get('/branch-employees/', { params }),
  create: (data) => api.post('/branch-employees/', data),
  update: (id, data) => api.patch(`/branch-employees/${id}`, data),
  deactivate: (id, active = false) => api.post(`/branch-employees/${id}/deactivate`, { active }),
}

export const masterApi = {
  listWarehouses: (params) => api.get('/master/warehouses', { params }),
  createWarehouse: (data) => api.post('/master/warehouses', data),
  updateWarehouse: (id, data) => api.put(`/master/warehouses/${id}`, data),
  deleteWarehouse: (id) => api.delete(`/master/warehouses/${id}`),
  listBranches: (params) => api.get('/master/branches', { params }),
  createBranch: (data) => api.post('/master/branches', data),
  updateBranch: (id, data) => api.put(`/master/branches/${id}`, data),
  deleteBranch: (id) => api.delete(`/master/branches/${id}`),
  listKitchens: (params) => api.get('/master/kitchens', { params }),
  createKitchen: (data) => api.post('/master/kitchens', data),
  listKitchenSections: (params) => api.get('/master/kitchen-sections', { params }),
  listCategories: () => api.get('/master/categories'),
  createCategory: (data) => api.post('/master/categories', data),
  listUnits: () => api.get('/master/units'),
  createUnit: (data) => api.post('/master/units', data),
  listItems: (params) => api.get('/master/items', { params }),
  getItem: (id) => api.get(`/master/items/${id}`),
  createItem: (data) => api.post('/master/items', data),
  updateItem: (id, data) => api.put(`/master/items/${id}`, data),
  deleteItem: (id) => api.delete(`/master/items/${id}`),
  listVarianceReasons: () => api.get('/master/variance-reasons'),
  listReceivingVarianceReasons: () => api.get('/master/receiving-variance-reasons'),
}

export const inventoryApi = {
  list: (params) => api.get('/inventory/', { params }),
  get: (id) => api.get(`/inventory/${id}`),
  create: (data) => api.post('/inventory/', data),
  submit: (id) => api.post(`/inventory/${id}/submit`),
  approve: (id) => api.post(`/inventory/${id}/approve`),
  reject: (id, reason) => api.post(`/inventory/${id}/reject`, { reason }),
}

export const ordersApi = {
  list: (params) => api.get('/orders/', { params }),
  get: (id) => api.get(`/orders/${id}`),
  createExceptional: (data) => api.post('/orders/exceptional', data),
  createDaily: (data) => api.post('/orders/daily', data),
  areaReview: (id, data) => api.post(`/orders/${id}/area-review`, data),
  branchReview: (id, data) => api.post(`/orders/${id}/branch-review`, data),
  submitToWarehouse: (id) => api.post(`/orders/${id}/submit-to-warehouse`),
  warehouseReview: (id, data) => api.post(`/orders/${id}/warehouse-review`, data),
  approve: (id) => api.post(`/orders/${id}/approve`),
  reject: (id, reason) => api.post(`/orders/${id}/reject`, { reason }),
  startPicking: (id) => api.post(`/orders/${id}/start-picking`),
  dispatch: (id, data) => api.post(`/orders/${id}/dispatch`, data),
  receive: (id, data) => api.post(`/orders/${id}/receive`, data),
  getPickList: (id) => api.get(`/orders/${id}/pick-list`),
  close: (id, client_request_id) =>
    api.post(`/orders/${id}/close`, null, {
      headers: client_request_id ? { 'X-Idempotency-Key': client_request_id } : {},
    }),
  timeline: (id) => api.get(`/orders/${id}/timeline`),
  cancel: (id, reason) => api.post(`/orders/${id}/cancel`, { reason }),

  // Inter-branch transfer workflow (approval required)
  createInterBranch: (data) => api.post('/orders/inter-branch', data),
  listPendingInterBranch: () => api.get('/orders/inter-branch/pending'),
  approveInterBranch: (id, data = {}) => api.post(`/orders/${id}/inter-branch-approve`, data),
  rejectInterBranch: (id, reason) => api.post(`/orders/${id}/inter-branch-reject`, { reason }),
}

export const dashboardApi = {
  branch: (id) => api.get(`/dashboard/branch/${id}`),
  /** لوحة وتقارير المستودع — نفس مسار الـ backend */
  warehouse: (id) => api.get(`/dashboard/warehouse/${id}`),
  warehouseReports: (id) => api.get(`/dashboard/warehouse/${id}`),
  operations: () => api.get('/dashboard/operations'),
  branchStock: (id) => api.get(`/dashboard/stock/branch/${id}`),
  warehouseStock: (id) => api.get(`/dashboard/stock/warehouse/${id}`),
  alertsSummary: () => api.get('/dashboard/alerts-summary'),
  // G5 — daily consumption trend per branch
  branchConsumptionTrend: (id, days = 30) =>
    api.get(`/dashboard/branch/${id}/consumption-trend`, { params: { days } }),
  // G6 — order-to-receive delay analytics
  orderDelayAnalytics: (params) => api.get('/dashboard/order-delay-analytics', { params }),
  // G7 — branches with most open corrective actions
  branchesOpenActions: (limit = 10) =>
    api.get('/dashboard/branches-open-actions', { params: { limit } }),
  superAdminOverview: () => api.get('/supply-chain/super-admin-overview'),
}

export const auditApi = {
  dashboard: () => api.get('/audit/findings/dashboard/summary'),
  listFindings: (params) => api.get('/audit/findings', { params }),
  getFinding: (id) => api.get(`/audit/findings/${id}`),
  createFinding: (data) => api.post('/audit/findings', data),
  updateFinding: (id, data) => api.patch(`/audit/findings/${id}`, data),
  acknowledgeFinding: (id, data) => api.post(`/audit/findings/${id}/acknowledge`, data),
  findingsByEntity: (entityType, entityId) => api.get(`/audit/findings/by-entity/${entityType}/${entityId}`),
  exportFindingsUrl: (params = {}) => {
    const filtered = Object.fromEntries(Object.entries(params || {}).filter(([, value]) => value !== '' && value !== null && value !== undefined))
    const query = new URLSearchParams(filtered).toString()
    return `/api/v1/audit/findings/export.csv${query ? `?${query}` : ''}`
  },
  listLogs: (params) => api.get('/audit/logs', { params }),
  listModules: () => api.get('/audit/modules'),
  listActions: (params) => api.get('/audit/actions', { params }),
  entityHistory: (entityType, entityId) => api.get(`/audit/entity/${entityType}/${entityId}`),
  exportLogsUrl: (params = {}) => {
    const filtered = Object.fromEntries(Object.entries(params || {}).filter(([, value]) => value !== '' && value !== null && value !== undefined))
    const query = new URLSearchParams(filtered).toString()
    return `/api/v1/audit/logs/export.csv${query ? `?${query}` : ''}`
  },
}

export const itemChangeRequestsApi = {
  list: (params) => api.get('/item-change-requests', { params }),
  requestWarehouseRemove: (data) => api.post('/item-change-requests/warehouse-remove', data),
  addBranchItem: (data) => api.post('/item-change-requests/branch-add', data),
  requestBranchRemove: (data) => api.post('/item-change-requests/branch-remove', data),
  requestNewItem: (data) => api.post('/item-change-requests/new-item', data),
  renameItem: (data) => api.post('/item-change-requests/rename-item', data),
  approve: (id, data = {}) => api.post(`/item-change-requests/${id}/approve`, data),
  reject: (id, data = {}) => api.post(`/item-change-requests/${id}/reject`, data),
}

export const getApiErrorMessage = (error, fallback = 'Request failed') => {
  const data = error?.response?.data
  const detail = data?.detail ?? data?.message ?? error?.message
  if (!detail) return fallback
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === 'string') return item
        if (!item || typeof item !== 'object') return String(item)
        const loc = Array.isArray(item.loc) ? item.loc.join('.') : item.loc
        const msg = item.msg || item.message || JSON.stringify(item)
        return loc ? `${loc}: ${msg}` : msg
      })
      .join('\n')
  }
  if (typeof detail === 'object') {
    return detail.message || detail.msg || JSON.stringify(detail)
  }
  return String(detail)
}

export const qualityApi = {
  getChecklist: (params) => api.get('/quality/checklist', { params }),
  list: (params) => api.get('/quality/', { params }),
  get: (id) => api.get(`/quality/${id}`),
  create: (data) => api.post('/quality/', data),
  delete: (id) => api.delete(`/quality/${id}`),
  submit: (id) => api.post(`/quality/${id}/submit`),
  review: (id, data) => api.post(`/quality/${id}/review`, data),
  close: (id) => api.post(`/quality/${id}/close`),
  updateResponse: (visitId, responseId, data) =>
    api.patch(`/quality/${visitId}/responses/${responseId}`, data),
  // E7 — إجراءات تصحيحية + تحليلات
  listOpenActions: (params) => api.get('/quality/open-actions', { params }),
  listActionOwners: (params) => api.get('/quality/open-actions/owners', { params }),
  resolveOpenAction: (responseId, notes) =>
    api.post(`/quality/open-actions/${responseId}/resolve`, null, {
      params: notes ? { notes } : {},
    }),
  bulkResolveActions: (data) => api.post('/quality/open-actions/bulk-resolve', data),
  complianceTrend: (params) => api.get('/quality/analytics/compliance-trend', { params }),
  sectionCompliance: (params) => api.get('/quality/analytics/section-compliance', { params }),
  // E8 — توقيعات ومرفقات
  signVisit: (visitId, data) => api.post(`/quality/${visitId}/sign`, data),
  listAttachments: (responseId) =>
    api.get(`/quality/responses/${responseId}/attachments`),
  uploadAttachment: (responseId, file, kind = 'photo') => {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('kind', kind)
    return api.post(`/quality/responses/${responseId}/attachments`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  deleteAttachment: (attachmentId) => api.delete(`/quality/attachments/${attachmentId}`),
  downloadAttachmentUrl: (attachmentId) =>
    `/api/v1/quality/attachments/${attachmentId}/download`,
  // I3 — visit-level attachments (on the visit itself, not a specific response)
  listVisitAttachments: (visitId) =>
    api.get(`/quality/${visitId}/attachments`),
  uploadVisitAttachment: (visitId, file, kind = 'photo') => {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('kind', kind)
    return api.post(`/quality/${visitId}/attachments`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
}

export const trainingApi = {
  listTemplates: (params) => api.get('/training/templates', { params }),
  getTemplate: (id) => api.get(`/training/templates/${id}`),
  list: (params) => api.get('/training/', { params }),
  get: (id) => api.get(`/training/${id}`),
  create: (data) => api.post('/training/', data),
  submit: (id) => api.post(`/training/${id}/submit`),
  approve: (id, data) => api.post(`/training/${id}/approve`, data),
  reject: (id, reason) => api.post(`/training/${id}/reject`, { reason }),
  upsertDevPlan: (id, data) => api.post(`/training/${id}/dev-plan`, data),
  // E7 — تحليلات
  verdictDistribution: (params) => api.get('/training/analytics/verdict-distribution', { params }),
  // E8 — توقيعات
  sign: (assessmentId, data) => api.post(`/training/${assessmentId}/sign`, data),
}

export const deliveryApi = {
  getBrands: () => api.get('/delivery/brands'),
  getApps: () => api.get('/delivery/apps'),
  getBranches: (params) => api.get('/delivery/branches', { params }),
  createBranch: (data) => api.post('/delivery/branches', data),
  updateBranch: (id, data) => api.put(`/delivery/branches/${id}`, data),
  addAlias: (branchId, alias) => api.post(`/delivery/branches/${branchId}/aliases`, { alias }),
  deleteAlias: (branchId, aliasId) => api.delete(`/delivery/branches/${branchId}/aliases/${aliasId}`),
  getPeriods: () => api.get('/delivery/periods'),
  importData: (data) => api.post('/delivery/import', data),
  getKPIs: (params) => api.get('/delivery/kpis', { params }),
  getAppStats: (params) => api.get('/delivery/stats/apps', { params }),
  getBrandStats: (params) => api.get('/delivery/stats/brands', { params }),
  getBranchStats: (params) => api.get('/delivery/stats/branches', { params }),
  getTrend: (params) => api.get('/delivery/stats/trend', { params }),
  getUnmatched: (params) => api.get('/delivery/unmatched', { params }),
}

export const salesChannelsApi = {
  listChannels: () => api.get('/sales-channels/channels'),
  updateCommissionRate: (id, commission_rate) =>
    api.patch(`/sales-channels/channels/${id}/commission-rate`, { commission_rate }),
  createDailySalesBatch: (data) => api.post('/sales-channels/daily-sales/batch', data),
  updateDailySale: (id, data) => api.patch(`/sales-channels/daily-sales/${id}`, data),
  listDailySales: (params) => api.get('/sales-channels/daily-sales', { params }),
  createStatement: (data) => api.post('/sales-channels/statements', data),
  getReconciliation: (params) => api.get('/sales-channels/reconciliation', { params }),
  listClosures: (params) => api.get('/sales-channels/closures', { params }),
  createClosure: (data) => api.post('/sales-channels/closures', data),
  reopenClosure: (id, reopen_reason) =>
    api.post(`/sales-channels/closures/${id}/reopen`, { reopen_reason }),
  getCompliance: (params) => api.get('/sales-channels/compliance', { params }),
}

export const supplyChainApi = {
  dashboard: () => api.get('/supply-chain/dashboard'),
  listBrands: (params) => api.get('/master/brands', { params }),
  listBrandCountItems: (brandId) => api.get(`/master/brands/${brandId}/count-items`),
  addBrandCountItem: (brandId, data) => api.post(`/master/brands/${brandId}/count-items`, data),
  updateBrandCountItem: (brandId, rowId, data) => api.patch(`/master/brands/${brandId}/count-items/${rowId}`, data),
  listKitchenSections: (params) => api.get('/master/kitchen-sections', { params }),
  listKitchens: (params) => api.get('/master/kitchens', { params }),
  createKitchen: (data) => api.post('/master/kitchens', data),

  listBranchRequests: (params) => api.get('/branch-requests', { params }),
  getBranchRequest: (id) => api.get(`/branch-requests/${id}`),
  getBranchRequestDetail: (id) => api.get(`/branch-requests/${id}/detail`),
  listAllowedItems: (params) => api.get('/branch-requests/allowed-items', { params }),
  createBranchRequest: (data) => api.post('/branch-requests', data),
  updateBranchRequest: (id, data) => api.patch(`/branch-requests/${id}`, data),
  submitBranchRequest: (id) => api.post(`/branch-requests/${id}/submit`),
  approveBranchRequest: (id, data = {}) => api.post(`/branch-requests/${id}/approve`, data),
  modifyApproveBranchRequest: (id, data) => api.post(`/branch-requests/${id}/modify-and-approve`, data),
  rejectBranchRequest: (id, data) => api.post(`/branch-requests/${id}/reject`, data),

  listProductionOrders: (params) => api.get('/production-orders', { params }),
  listDailyKitchenLines: () => api.get('/production-orders/daily-kitchen-lines'),
  listDailyKitchenOrders: () => api.get('/production-orders/daily-kitchen-orders'),
  receiveDailyKitchenOrder: (id) => api.post(`/production-orders/daily-kitchen-orders/${id}/receive`),
  startDailyKitchenOrder: (id) => api.post(`/production-orders/daily-kitchen-orders/${id}/start`),
  markDailyKitchenOrderReady: (id) => api.post(`/production-orders/daily-kitchen-orders/${id}/mark-ready`),
  sendDailyKitchenOrderToWarehouse: (id) => api.post(`/production-orders/daily-kitchen-orders/${id}/send-to-warehouse`),
  dailyKitchenOrderPdfUrl: (id) => `/api/v1/production-orders/daily-kitchen-orders/${id}/pdf`,
  dailyKitchenOrderPdf: (id) =>
    api.get(`/production-orders/daily-kitchen-orders/${id}/pdf`, { responseType: 'text' }),
  getProductionOrder: (id) => api.get(`/production-orders/${id}`),
  startProductionOrder: (id) => api.post(`/production-orders/${id}/start`),
  markProductionPartialReady: (id, data) => api.post(`/production-orders/${id}/mark-partial-ready`, data),
  markProductionReady: (id) => api.post(`/production-orders/${id}/mark-ready`),
  sendProductionToWarehouse: (id) => api.post(`/production-orders/${id}/send-to-warehouse`),
  requestProductionMaterials: (id, data) => api.post(`/production-orders/${id}/request-materials`, data),

  // Warehouse fulfillment lines
  listWarehouseLines: (params) => api.get('/warehouse-lines', { params }),
  getWarehouseLine: (id) => api.get(`/warehouse-lines/${id}`),
  receiveWarehouseLine: (id) => api.post(`/warehouse-lines/${id}/receive`),
  issueWarehouseLine: (id, data = {}) => api.post(`/warehouse-lines/${id}/issue`, data),
  partialIssueWarehouseLine: (id, data) => api.post(`/warehouse-lines/${id}/partial-issue`, data),
  addWarehouseDelayReason: (id, data) => api.post(`/warehouse-lines/${id}/delay-reason`, data),

  // Delivery orders
  listDeliveryOrders: (params) => api.get('/delivery-orders', { params }),
  listReadyDeliveryOrders: () => api.get('/delivery-orders/ready'),
  getDeliveryOrder: (id) => api.get(`/delivery-orders/${id}`),
  createDeliveryOrder: (data) => api.post('/delivery-orders', data),
  markOutForDelivery: (id) => api.post(`/delivery-orders/${id}/out-for-delivery`),
  deliverOrder: (id, data = {}) => api.post(`/delivery-orders/${id}/deliver`, data),
  // Returns absolute path that opens directly in a new browser tab.
  // Server returns HTMLResponse (browser-print) — no JSON wrapper needed.
  deliveryLabelsUrl: (id) => `/api/v1/delivery-orders/${id}/labels`,
}

export const assistantApi = {
  status: () => api.get('/assistant/status'),
  ask: (question) => api.post('/assistant/ask', { question }),
  // Admin endpoints:
  listSuggestions: (params = {}) => api.get('/assistant/suggestions', { params }),
  updateSuggestion: (id, data) => api.patch(`/assistant/suggestions/${id}`, data),
  suggestionsStats: () => api.get('/assistant/suggestions/stats'),
}
