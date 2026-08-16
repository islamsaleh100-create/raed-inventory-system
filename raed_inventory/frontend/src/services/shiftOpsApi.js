// shiftOpsApi.js — Shift Operations (جرد الشفت + الكاش)
// Every call here targets /shift-ops only. Nothing in this module may reach
// /inventory, /orders, /stock, /branch-requests or /supply-chain.
import api from './api'

const BASE = '/shift-ops'

export const shiftOpsApi = {
  // ── shifts ────────────────────────────────────────────────────────────
  listShifts: (params) => api.get(`${BASE}/shifts`, { params }),
  getShift: (shiftId) => api.get(`${BASE}/shifts/${shiftId}`),
  openShift: (data) => api.post(`${BASE}/shifts`, data),

  // manager-only
  reopenShift: (shiftId, data) => api.post(`${BASE}/shifts/${shiftId}/reopen`, data),
  closeNoActivity: (shiftId, data) => api.post(`${BASE}/shifts/${shiftId}/close-no-activity`, data),

  // ── count ─────────────────────────────────────────────────────────────
  // Idempotent by contract: safe to call on every page open. 201 on create,
  // 200 when it already exists (including when already submitted).
  createOrGetCount: (shiftId) => api.post(`${BASE}/shifts/${shiftId}/count`),
  getCount: (shiftId) => api.get(`${BASE}/shifts/${shiftId}/count`),
  patchCountLines: (shiftId, lines) => api.patch(`${BASE}/shifts/${shiftId}/count/lines`, { lines }),
  submitCount: (shiftId) => api.post(`${BASE}/shifts/${shiftId}/count/submit`),

  // ── cash ──────────────────────────────────────────────────────────────
  getCash: (shiftId) => api.get(`${BASE}/shifts/${shiftId}/cash`),
  saveCash: (shiftId, data) => api.put(`${BASE}/shifts/${shiftId}/cash`, data),
  submitCash: (shiftId) => api.post(`${BASE}/shifts/${shiftId}/cash/submit`),

  // ── audit report (read-only) ──────────────────────────────────────────
  report: (params) => api.get(`${BASE}/reports/shift-operations`, { params }),
}

export default shiftOpsApi

// ── shared client-side helpers ──────────────────────────────────────────

/** Cash tolerance mirrors backend CASH_VARIANCE_TOLERANCE. Display only. */
export const CASH_VARIANCE_TOLERANCE = 5

const num = (v) => {
  if (v === '' || v === null || v === undefined) return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

/**
 * Preview of the backend cash rule, for instant feedback only. The backend
 * remains the source of truth.
 *
 * expected = cash_sales - cash_expense - cash_float_carried_forward
 *
 * refund_bill is deliberately NOT subtracted: POS figures already arrive net
 * of refunds, so subtracting again double-counts and invents a shortfall.
 */
export function previewCash(form) {
  const cash = num(form.cash_sales)
  const expense = num(form.cash_expense)
  const float = num(form.cash_float_carried_forward)
  const deposited = num(form.cash_deposited)
  const total = num(form.total_sale)
  const mada = num(form.mada_sales)
  const app = num(form.app_sales)

  const cashReady = cash !== null && expense !== null && float !== null
  const expected = cashReady ? Math.round((cash - expense - float) * 100) / 100 : null
  const variance =
    expected !== null && deposited !== null ? Math.round((deposited - expected) * 100) / 100 : null

  const payReady = [total, mada, cash, app].every((v) => v !== null)
  const payDiff = payReady ? Math.round((mada + cash + app - total) * 100) / 100 : null

  return {
    expected,
    variance,
    payDiff,
    payOk: payDiff === null ? null : Math.abs(payDiff) <= 0.01,
    reasonRequired: variance !== null && Math.abs(variance) > CASH_VARIANCE_TOLERANCE,
    negativeExpected: expected !== null && expected < 0,
  }
}

/** Maps a backend validation error payload to { field: code } for inline display. */
export function fieldErrors(error) {
  const detail = error?.response?.data?.detail
  const list = Array.isArray(detail?.errors) ? detail.errors : Array.isArray(detail) ? detail : []
  const out = {}
  list.forEach((e) => {
    if (e && e.field) out[e.field] = e.code || true
  })
  return out
}
