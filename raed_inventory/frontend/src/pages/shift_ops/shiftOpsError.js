// shiftOpsError.js — maps shift-ops API error_code to localized text (never raw English message).
export function shiftOpsError(err, t, fallbackKey = 'common.save_failed') {
  const data = err?.response?.data || {}
  const raw = data.error_code || ''
  // Backend uses two conventions: shift_ops.negative_qty and MOVEMENT_EXCEPTION_REASON_REQUIRED
  const code = raw.startsWith('shift_ops.') ? raw.slice('shift_ops.'.length) : raw
  if (code) {
    const key = `shift_ops.error.${code}`
    const detail = data.detail || {}
    const text = t(key, detail)
    if (text !== key) return text
    return `${t('shift_ops.error.unknown')} (${raw})`
  }
  return t(fallbackKey)
}
