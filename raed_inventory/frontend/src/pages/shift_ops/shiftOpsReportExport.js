/** CSV export helpers — shared by report page and verification scripts. */

export const FILTER_KEYS = [
  'partial_only',
  'exception_only',
  'reopened_only',
  'variance_only',
  'negative_movement_only',
]

const API_FILTER_MAP = {
  variance_only: 'cash_variance_only',
}

/** Same query params for table load and CSV export (single source of truth). */
export function buildReportParams(dateFrom, dateTo, active) {
  const params = {}
  FILTER_KEYS.forEach((key) => {
    if (active[key]) {
      params[API_FILTER_MAP[key] || key] = true
    }
  })
  if (dateFrom) params.date_from = dateFrom
  if (dateTo) params.date_to = dateTo
  return params
}

export function csvEscape(value) {
  if (value == null || value === '') return ''
  const s = String(value)
  if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`
  return s
}

function rawNumber(value) {
  if (value == null || value === '') return ''
  return String(value).replace(/,/g, '')
}

export function exceptionReason(ex, t) {
  const reason = ex.reason || ex.movement_exception_reason
  if (reason && String(reason).trim()) return reason
  return t('shift_ops.no_reason')
}

/** Movement-reason cell: opening tag · negative reasons · empty when none. */
export function formatExportMovementReason(row, t) {
  if (row.is_opening_count) {
    return t('shift_ops.opening_count_report_badge')
  }
  const exceptions = Array.isArray(row.negative_movement_exceptions)
    ? row.negative_movement_exceptions
    : []
  if (exceptions.length === 0) return ''
  return exceptions.map((ex) => exceptionReason(ex, t)).join(' · ')
}

export function formatExportOpeningTag(row, t) {
  return row.is_opening_count ? t('shift_ops.opening_count_report_badge') : ''
}

export function formatBranch(row, user, t) {
  const name = row.branch_name_ar || row.branch_name
  if (name) return name
  if (user?.branch_id === row.branch_id) {
    const userName = user.branch_name_ar || user.branch_name
    if (userName) return userName
  }
  return t('shift_ops.branch_fallback', { id: row.branch_id })
}

export function rowsToCsvContent(rows, user, t) {
  const headers = [
    t('shift_ops.export_col_date'),
    t('shift_ops.export_col_branch'),
    t('shift_ops.export_col_shift'),
    t('shift_ops.export_col_status'),
    t('shift_ops.export_col_opening_count'),
    t('shift_ops.export_col_items'),
    t('shift_ops.export_col_filled'),
    t('shift_ops.movement_total'),
    t('shift_ops.damaged_total'),
    t('shift_ops.export_col_negative_count'),
    t('shift_ops.export_col_movement_reason'),
    t('shift_ops.export_col_reopened'),
  ]
  const lines = rows.map((row) => {
    const statusKey = row.count_status || row.status || 'none'
    const statusLabel = t(`shift_ops.section_status.${statusKey}`, statusKey)
    const negativeCount = Array.isArray(row.negative_movement_exceptions)
      ? row.negative_movement_exceptions.length
      : 0
    const reopenCount = Array.isArray(row.reopen_events) ? row.reopen_events.length : 0
    return [
      row.shift_date,
      formatBranch(row, user, t),
      row.shift_number,
      statusLabel,
      formatExportOpeningTag(row, t),
      rawNumber(row.count_lines_total ?? 0),
      rawNumber(row.count_lines_filled ?? 0),
      rawNumber(row.movement_diff_total),
      rawNumber(row.damaged_total),
      rawNumber(negativeCount),
      formatExportMovementReason(row, t),
      rawNumber(reopenCount),
    ].map(csvEscape).join(',')
  })
  const bom = '\uFEFF'
  return bom + [headers.map(csvEscape).join(','), ...lines].join('\r\n')
}

export function exportFilename(dateFrom, dateTo) {
  const from = dateFrom || 'all'
  const to = dateTo || 'all'
  return `shift-ops-${from}_to_${to}.csv`
}

/** Parse one CSV record line into fields (RFC4180-style quoting). */
export function parseCsvLine(line) {
  const fields = []
  let field = ''
  let inQuotes = false
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i]
    if (inQuotes) {
      if (ch === '"') {
        if (line[i + 1] === '"') {
          field += '"'
          i += 1
        } else {
          inQuotes = false
        }
      } else {
        field += ch
      }
    } else if (ch === '"') {
      inQuotes = true
    } else if (ch === ',') {
      fields.push(field)
      field = ''
    } else {
      field += ch
    }
  }
  fields.push(field)
  return fields
}

/** Parse CSV text (with optional BOM) into rows of string arrays. */
export function parseCsvContent(content) {
  const text = content.replace(/^\uFEFF/, '').replace(/\r\n/g, '\n').replace(/\r/g, '\n')
  const lines = text.split('\n').filter((line) => line.length > 0)
  return lines.map(parseCsvLine)
}
