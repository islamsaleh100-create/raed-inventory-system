import React from 'react'

/** @returns {string} YYYY-MM-DD */
export function formatDateLocal(d) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function defaultMonthRange() {
  const today = new Date()
  const start = new Date(today.getFullYear(), today.getMonth(), 1)
  return { date_from: formatDateLocal(start), date_to: formatDateLocal(today) }
}

export function daysInclusive(fromStr, toStr) {
  if (!fromStr || !toStr) return 0
  const a = new Date(`${fromStr}T12:00:00`)
  const b = new Date(`${toStr}T12:00:00`)
  if (Number.isNaN(a.getTime()) || Number.isNaN(b.getTime())) return 0
  return Math.floor((b - a) / 86400000) + 1
}

export function validateDateRange(fromStr, toStr, maxDays, t) {
  if (!fromStr || !toStr) {
    return t('count_audit.errors.missing_dates')
  }
  if (fromStr > toStr) {
    return t('count_audit.errors.COUNT_AUDIT_INVALID_RANGE')
  }
  if (daysInclusive(fromStr, toStr) > maxDays) {
    return t('count_audit.errors.COUNT_AUDIT_RANGE_TOO_LARGE')
  }
  return null
}

export function newClientRequestId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID().replace(/-/g, '')
  }
  return `cr${Date.now()}${Math.random().toString(36).slice(2, 12)}`
}

export function countAuditErrorMessage(error, t) {
  const data = error?.response?.data
  const detail = data?.detail
  const code = (typeof detail === 'object' && detail?.error_code) || data?.error_code
  if (code) {
    const key = `count_audit.errors.${code}`
    const translated = t(key)
    if (translated && translated !== key) {
      if (code === 'COUNT_AUDIT_DUPLICATE_OPEN_FINDING' && detail?.existing_finding_no) {
        return `${translated} (${detail.existing_finding_no})`
      }
      if (code === 'COUNT_AUDIT_INVALID_TRANSITION' && detail?.current_status) {
        return `${translated} (${detail.current_status})`
      }
      return translated
    }
  }
  if (typeof detail === 'object' && detail?.message) return detail.message
  if (typeof detail === 'string') return detail
  return t('common.error_generic')
}

export function parseIntParam(value, fallback) {
  const n = parseInt(value, 10)
  return Number.isFinite(n) && n > 0 ? n : fallback
}

/** Reuse client_request_id only when retrying the same event action + note. */
export function clientRequestIdForEvent(lastAttempt, action, noteTrimmed) {
  if (
    lastAttempt
    && lastAttempt.action === action
    && lastAttempt.note === noteTrimmed
    && lastAttempt.id
  ) {
    return lastAttempt.id
  }
  return newClientRequestId()
}

function createFindingAttemptKey({ shift_id, severity, title, description, item_ids }) {
  const sorted = [...item_ids].sort((a, b) => a - b)
  return {
    shift_id,
    severity,
    title: title.trim(),
    description: description.trim(),
    item_ids: sorted.join(','),
  }
}

/** Reuse client_request_id only when retrying create with identical payload fields. */
export function clientRequestIdForCreate(lastAttempt, payload) {
  const key = createFindingAttemptKey(payload)
  if (
    lastAttempt
    && lastAttempt.id
    && lastAttempt.shift_id === key.shift_id
    && lastAttempt.severity === key.severity
    && lastAttempt.title === key.title
    && lastAttempt.description === key.description
    && lastAttempt.item_ids === key.item_ids
  ) {
    return lastAttempt.id
  }
  return newClientRequestId()
}

export function rememberCreateAttempt(id, payload) {
  return { id, ...createFindingAttemptKey(payload) }
}

/** Display-only quantity: strip float noise, 2–6 fraction digits. */
export function formatQty(v) {
  if (v === null || v === undefined || v === '') return '—'
  const n = Number(Number(v).toFixed(6))
  if (!Number.isFinite(n)) return '—'
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 6, useGrouping: false })
}

export function normalizedQtyNumber(v) {
  if (v === null || v === undefined || v === '') return null
  const n = Number(Number(v).toFixed(6))
  return Number.isFinite(n) ? n : null
}

const LTR_NUM = 'tabular-nums text-right inline-block [unicode-bidi:isolate]'

export function QtySpan({ value, className = '' }) {
  return React.createElement('span', { dir: 'ltr', className: `${LTR_NUM} ${className}`.trim() }, formatQty(value))
}

export function formatDateTimeDisplay(iso) {
  if (!iso) return '—'
  const s = String(iso).replace('T', ' ').slice(0, 16)
  return s
}

/** Date-only for list columns (avoids misleading time vs timeline until backend TZ fix). */
export function formatDateOnly(iso) {
  if (!iso) return '—'
  return String(iso).slice(0, 10)
}

const LTR_ISOLATE = '[unicode-bidi:isolate]'

export function TLtr({ children, className = '' }) {
  return React.createElement(
    'bdi',
    { dir: 'ltr', className: `${LTR_ISOLATE} ${className}`.trim() },
    children,
  )
}

function ltrSentinel(i) {
  return `\uE000LTR${i}\uE001`
}

/** Render t(key, placeholders) with chosen fields wrapped in TLtr (bdi). */
export function renderI18nLtr(t, key, ltrFields) {
  const fieldKeys = Object.keys(ltrFields)
  const sentinels = {}
  fieldKeys.forEach((k, i) => {
    sentinels[k] = ltrSentinel(i)
  })
  const text = t(key, sentinels)
  const nodes = []
  let rest = text
  fieldKeys.forEach((fieldKey, i) => {
    const mark = ltrSentinel(i)
    const idx = rest.indexOf(mark)
    if (idx === -1) return
    if (idx > 0) nodes.push(rest.slice(0, idx))
    nodes.push(
      React.createElement(TLtr, { key: `${key}-${fieldKey}` }, ltrFields[fieldKey]),
    )
    rest = rest.slice(idx + mark.length)
  })
  if (rest) nodes.push(rest)
  return nodes
}

export function reopenTargetLabel(target, t) {
  const key = `count_audit.reopen_target_${target}`
  const v = t(key)
  return v !== key ? v : target
}

export function pendingPartyLabel(status, t) {
  const map = {
    open: 'count_audit.pending_branch_manager',
    clarification_requested: 'count_audit.pending_branch_manager',
    escalated: 'count_audit.pending_operations',
    acknowledged: 'count_audit.pending_auditor',
    accepted: 'count_audit.pending_auditor',
    closed: 'count_audit.pending_none',
  }
  const key = map[status]
  return key ? t(key) : '—'
}

export function diffKind(movementDiff) {
  const n = normalizedQtyNumber(movementDiff)
  if (n === null || n === 0) return 'zero'
  return n > 0 ? 'shortage' : 'surplus'
}

export function DiffCell({ value, t, showTag = true }) {
  const kind = diffKind(value)
  const color =
    kind === 'shortage' ? 'text-red-700 font-medium' : kind === 'surplus' ? 'text-amber-700 font-medium' : 'text-gray-600'
  const tag =
    showTag && kind === 'shortage'
      ? t('count_audit.tag_shortage')
      : showTag && kind === 'surplus'
        ? t('count_audit.tag_surplus')
        : null
  return React.createElement(
    'span',
    { className: 'inline-flex items-center gap-1' },
    React.createElement(QtySpan, { value, className: color }),
    tag ? React.createElement('span', { className: `text-[10px] px-1 rounded ${kind === 'shortage' ? 'bg-red-100 text-red-800' : 'bg-amber-100 text-amber-900'}` }, tag) : null,
  )
}

export function CountBadge({ value, variant = 'neutral' }) {
  const n = Number(value) || 0
  if (n === 0) return React.createElement('span', { className: 'text-gray-400' }, '0')
  const cls =
    variant === 'shortage'
      ? 'inline-flex min-w-[1.25rem] justify-center px-1.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800'
      : variant === 'surplus'
        ? 'inline-flex min-w-[1.25rem] justify-center px-1.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-900'
        : variant === 'accent'
          ? 'inline-flex min-w-[1.25rem] justify-center px-1.5 py-0.5 rounded-full text-xs font-medium bg-primary-100 text-primary-800'
          : 'inline-flex min-w-[1.25rem] justify-center px-1.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700'
  return React.createElement('span', { className: cls }, String(n))
}
