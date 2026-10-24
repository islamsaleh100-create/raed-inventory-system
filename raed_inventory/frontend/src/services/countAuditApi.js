import api from './api'

const BASE = '/audit/findings/count-audit'

export const countAuditApi = {
  getFilters: () => api.get(`${BASE}/filters`),
  getCoverage: (params) => api.get(`${BASE}/coverage`, { params }),
  listShifts: (params) => api.get(`${BASE}/shifts`, { params }),
  getShift: (shiftId) => api.get(`${BASE}/shifts/${shiftId}`),
  listVariances: (params) => api.get(`${BASE}/variances`, { params }),
  listFindings: (params) => api.get(`${BASE}/findings`, { params }),
  getFinding: (findingId) => api.get(`${BASE}/findings/${findingId}`),
  createFinding: (body) => api.post(`${BASE}/findings`, body),
  postFindingEvent: (findingId, body) => api.post(`${BASE}/findings/${findingId}/events`, body),
}

export default countAuditApi
