/** ISO yyyy-mm-dd helpers — no browser-local calendar reads. */
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/

export function isValidServerDate(value) {
  return typeof value === 'string' && ISO_DATE.test(value)
}

/** Add days using UTC calendar math (stable for date-only strings). */
export function addDays(isoDate, deltaDays) {
  const [y, m, d] = isoDate.split('-').map(Number)
  const dt = new Date(Date.UTC(y, m - 1, d + deltaDays))
  return dt.toISOString().slice(0, 10)
}

export function subtractDays(isoDate, days) {
  return addDays(isoDate, -days)
}

/** Device calendar date (yyyy-mm-dd) for mismatch warning display only — not for shift_date. */
export function browserCalendarDateString() {
  const now = new Date()
  const y = now.getFullYear()
  const m = String(now.getMonth() + 1).padStart(2, '0')
  const d = String(now.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}
