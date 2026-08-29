// ShiftOpsReportPage.jsx — تقرير عمليات الشفت لحساب المراجعة
// Read-only by contract: this page renders no write action of any kind.
import React, { useState, useEffect, useMemo, useRef } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { AlertTriangle, Unlock, Link2Off, Download, ExternalLink } from 'lucide-react'
import toast from 'react-hot-toast'
import { shiftOpsApi } from '../../services/shiftOpsApi'
import { PageLoader } from '../../components/common'
import { useT } from '../../i18n'
import { selectUser } from '../../store'

const FILTERS = [
  { key: 'partial_only', icon: AlertTriangle },
  { key: 'exception_only', icon: Link2Off },
  { key: 'reopened_only', icon: Unlock },
  { key: 'variance_only', icon: AlertTriangle },
  { key: 'negative_movement_only', icon: AlertTriangle },
]

const FILTER_KEYS = FILTERS.map((f) => f.key)

const API_FILTER_MAP = {
  variance_only: 'cash_variance_only',
}

function formatLocalDate(d) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

/** Last 7 calendar days inclusive (today + 6 prior days). */
export function defaultReportDateRange() {
  const to = new Date()
  const from = new Date()
  from.setDate(from.getDate() - 6)
  return { date_from: formatLocalDate(from), date_to: formatLocalDate(to) }
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

function rowsToCsvContent(rows, user, t) {
  const headers = [
    t('shift_ops.export_col_date'),
    t('shift_ops.export_col_branch'),
    t('shift_ops.export_col_shift'),
    t('shift_ops.export_col_status'),
    t('shift_ops.export_col_items'),
    t('shift_ops.export_col_filled'),
    t('shift_ops.movement_total'),
    t('shift_ops.damaged_total'),
    t('shift_ops.export_col_negative_count'),
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
      rawNumber(row.count_lines_total ?? 0),
      rawNumber(row.count_lines_filled ?? 0),
      rawNumber(row.movement_diff_total),
      rawNumber(row.damaged_total),
      rawNumber(negativeCount),
      rawNumber(reopenCount),
    ].map(csvEscape).join(',')
  })
  const bom = '\uFEFF'
  return bom + [headers.map(csvEscape).join(','), ...lines].join('\r\n')
}

function csvEscape(value) {
  if (value == null || value === '') return ''
  const s = String(value)
  if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`
  return s
}

function rawNumber(value) {
  if (value == null || value === '') return ''
  return String(value).replace(/,/g, '')
}

function exportFilename(dateFrom, dateTo) {
  const from = dateFrom || 'all'
  const to = dateTo || 'all'
  return `shift-ops-${from}_to_${to}.csv`
}

function formatBranch(row, user, t) {
  const name = row.branch_name_ar || row.branch_name
  if (name) return name
  if (user?.branch_id === row.branch_id) {
    const userName = user.branch_name_ar || user.branch_name
    if (userName) return userName
  }
  return t('shift_ops.branch_fallback', { id: row.branch_id })
}

function exceptionReason(ex, t) {
  const reason = ex.reason || ex.movement_exception_reason
  if (reason && String(reason).trim()) return reason
  return t('shift_ops.no_reason')
}

export function ShiftOpsReportPage() {
  const t = useT()
  const user = useSelector(selectUser)
  const [searchParams, setSearchParams] = useSearchParams()
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)
  const [initialLoad, setInitialLoad] = useState(true)
  const reqRef = useRef(0)
  const defaultDatesApplied = useRef(false)

  const dateFrom = searchParams.get('date_from') || ''
  const dateTo = searchParams.get('date_to') || ''
  const active = useMemo(() => {
    const state = {}
    FILTER_KEYS.forEach((key) => {
      if (searchParams.get(key) === '1') state[key] = true
    })
    return state
  }, [searchParams])

  const activeKey = FILTER_KEYS.filter((k) => active[k]).join(',')
  const dateRangeInvalid = Boolean(dateFrom && dateTo && dateFrom > dateTo)

  const updateParams = (patch) => {
    const next = new URLSearchParams(searchParams)
    Object.entries(patch).forEach(([key, value]) => {
      if (value === '' || value == null || value === false) next.delete(key)
      else next.set(key, value === true ? '1' : String(value))
    })
    setSearchParams(next, { replace: true })
  }

  const setDateFrom = (value) => updateParams({ date_from: value || null })
  const setDateTo = (value) => updateParams({ date_to: value || null })
  const toggle = (key) => updateParams({ [key]: active[key] ? null : '1' })

  useEffect(() => {
    if (defaultDatesApplied.current) return
    if (!searchParams.get('date_from') && !searchParams.get('date_to')) {
      defaultDatesApplied.current = true
      const { date_from, date_to } = defaultReportDateRange()
      updateParams({ date_from, date_to })
    } else {
      defaultDatesApplied.current = true
    }
  }, [searchParams])

  useEffect(() => {
    if (dateRangeInvalid) {
      setRows([])
      setLoading(false)
      setInitialLoad(false)
      return undefined
    }

    const reqId = ++reqRef.current
    setLoading(true)
    setRows([])

    const params = buildReportParams(dateFrom, dateTo, active)

    shiftOpsApi
      .report(params)
      .then((r) => {
        if (reqId !== reqRef.current) return
        setRows(r.data?.items || [])
      })
      .catch(() => {
        if (reqId !== reqRef.current) return
        setRows([])
        toast.error(t('common.load_failed'))
      })
      .finally(() => {
        if (reqId !== reqRef.current) return
        setLoading(false)
        setInitialLoad(false)
      })

    return () => {
      reqRef.current += 1
    }
  }, [dateFrom, dateTo, activeKey, dateRangeInvalid, t])

  const exportCsv = async () => {
    if (dateRangeInvalid) return
    const params = buildReportParams(dateFrom, dateTo, active)
    setExporting(true)
    try {
      const r = await shiftOpsApi.report(params)
      const exportRows = r.data?.items || []
      if (exportRows.length === 0) {
        toast.error(t('common.no_data'))
        return
      }
      const content = rowsToCsvContent(exportRows, user, t)
      const blob = new Blob([content], { type: 'text/csv;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = exportFilename(dateFrom, dateTo)
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      toast.error(t('common.load_failed'))
    } finally {
      setExporting(false)
    }
  }

  if (initialLoad && loading) return <PageLoader />

  const emptyMessage = dateRangeInvalid
    ? null
    : (dateFrom || dateTo)
      ? t('shift_ops.no_data_for_period')
      : t('common.no_data')

  return (
    <div className="p-4 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-bold">{t('shift_ops.report_title')}</h1>
        <button
          type="button"
          onClick={exportCsv}
          disabled={rows.length === 0 || loading || exporting}
          className="inline-flex items-center gap-1.5 rounded-lg border border-primary-600 text-primary-700 px-3 py-1.5 text-sm font-semibold disabled:opacity-40"
        >
          <Download size={16} />
          {t('shift_ops.export_csv')}
        </button>
      </div>

      <p className="text-xs text-gray-600 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
        {t('shift_ops.report_received_disclaimer')}
      </p>

      <div className="bg-white border rounded-xl p-3 space-y-3">
        <p className="text-xs text-gray-500">{t('shift_ops.report_default_period_hint')}</p>
        <div className="flex flex-wrap gap-3 items-end text-sm">
          <label className="flex flex-col gap-1">
            <span className="text-gray-500 text-xs">{t('common.date_from')}</span>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="border rounded-lg px-2 py-1.5"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-gray-500 text-xs">{t('common.date_to')}</span>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="border rounded-lg px-2 py-1.5"
            />
          </label>
        </div>
        {dateRangeInvalid && (
          <p className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
            {t('shift_ops.date_range_invalid')}
          </p>
        )}
        <div className="flex flex-wrap gap-2">
          {FILTERS.map(({ key, icon: Icon }) => (
            <button
              key={key}
              type="button"
              onClick={() => toggle(key)}
              className={`inline-flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs border ${
                active[key] ? 'bg-primary-600 text-white border-primary-600' : 'bg-white'
              }`}
            >
              <Icon size={13} /> {t(`shift_ops.filter.${key}`)}
            </button>
          ))}
        </div>
      </div>

      {loading && (
        <p className="text-sm text-gray-500 bg-white border rounded-xl p-4 text-center">
          {t('common.loading')}
        </p>
      )}

      {!loading && !dateRangeInvalid && rows.length === 0 && (
        <p className="text-sm text-gray-500 bg-white border rounded-xl p-6 text-center">
          {emptyMessage}
        </p>
      )}

      {!loading && rows.map((row) => (
        <div key={row.id} className="bg-white border rounded-xl p-3 space-y-2 text-sm">
          <div className="flex items-start justify-between gap-2 flex-wrap">
            <div className="font-semibold">
              {row.shift_date} · {t('shift_ops.shift_n', { n: row.shift_number })}
              <span className="text-xs text-gray-500 font-normal"> · {formatBranch(row, user, t)}</span>
            </div>
            <div className="flex flex-wrap gap-1 items-center">
              {row.is_partial && (
                <span className="bg-red-100 text-red-800 px-2 py-0.5 rounded text-xs font-bold">
                  {t('shift_ops.partial')}
                </span>
              )}
              {row.exception_type && (
                <span className="bg-gray-800 text-white px-2 py-0.5 rounded text-xs">
                  {t(`shift_ops.exception_type.${row.exception_type}`)}
                </span>
              )}
              <Link
                to={`/shift-ops/${row.id}/count`}
                className="inline-flex items-center gap-1 rounded-lg border border-primary-600 text-primary-700 px-2 py-0.5 text-xs font-semibold hover:bg-primary-50"
              >
                <ExternalLink size={12} />
                {t('shift_ops.view_details')}
              </Link>
            </div>
          </div>

          {row.cash && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs bg-gray-50 rounded-lg p-2">
              <div><span className="text-gray-500">{t('shift_ops.field.total_sale')}:</span> {row.cash.total_sale}</div>
              <div><span className="text-gray-500">{t('shift_ops.expected_deposited')}:</span> {row.cash.expected_deposited ?? '—'}</div>
              <div><span className="text-gray-500">{t('shift_ops.field.cash_deposited')}:</span> {row.cash.cash_deposited}</div>
              <div className={Number(row.cash.cash_variance || 0) !== 0 ? 'text-red-700 font-bold' : ''}>
                <span className="text-gray-500">{t('shift_ops.variance')}:</span> {row.cash.cash_variance ?? '—'}
              </div>
              {row.cash.cash_variance_reason && (
                <div className="col-span-full text-gray-700">
                  {t('shift_ops.variance_reason')}: {row.cash.cash_variance_reason}
                </div>
              )}
            </div>
          )}

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
            <div><span className="text-gray-500">{t('shift_ops.movement_total')}:</span> {row.movement_diff_total}</div>
            <div><span className="text-gray-500">{t('shift_ops.damaged_total')}:</span> {row.damaged_total}</div>
            <div className={Number(row.count_lines_total || 0) === 0 ? 'text-gray-400 italic' : ''}>
              <span className="text-gray-500">{t('shift_ops.count')}:</span>{' '}
              {row.count_lines_filled ?? 0}/{row.count_lines_total ?? 0}
              {Number(row.count_lines_total || 0) === 0 && (
                <span className="ms-1 rounded bg-gray-100 px-1.5 py-0.5 text-[10px] not-italic text-gray-500">
                  {t('shift_ops.no_count_items')}
                </span>
              )}
            </div>
          </div>

          {Array.isArray(row.negative_movement_exceptions) && row.negative_movement_exceptions.length > 0 && (
            <div className="border border-amber-300 bg-amber-50 rounded-lg p-2 space-y-1">
              <p className="text-xs font-bold text-amber-800">{t('shift_ops.negative_exceptions')}</p>
              {row.negative_movement_exceptions.map((ex, i) => (
                <p key={i} className="text-xs text-amber-900">
                  {ex.item_name_snapshot || ex.item_id}: {ex.movement_diff} — {exceptionReason(ex, t)}
                </p>
              ))}
            </div>
          )}

          {Array.isArray(row.reopen_events) && row.reopen_events.length > 0 && (
            <div className="border rounded-lg p-2 space-y-1">
              <p className="text-xs font-bold">{t('shift_ops.reopen_events')} ({row.reopen_events.length})</p>
              {row.reopen_events.map((ev, i) => (
                <p key={i} className="text-xs text-gray-700">
                  {ev.reopened_at} · {t(`shift_ops.reopen_target.${ev.target}`)} · {ev.reason}
                </p>
              ))}
            </div>
          )}

          {row.chain_gap && (
            <div className="border border-red-300 bg-red-50 rounded-lg p-2 text-xs text-red-800 space-y-0.5">
              <p className="font-bold">{t('shift_ops.chain_gap')}</p>
              <p>
                #{row.chain_gap.skipped_shift_id} · {row.chain_gap.skipped_shift_date} ·{' '}
                {t('shift_ops.shift_n', { n: row.chain_gap.skipped_shift_number })}
              </p>
              <p>
                {row.chain_gap.skipped_exception_type
                  ? t(`shift_ops.exception_type.${row.chain_gap.skipped_exception_type}`)
                  : '—'}
                {row.chain_gap.skipped_reason ? ` — ${row.chain_gap.skipped_reason}` : ''}
              </p>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

export default ShiftOpsReportPage
