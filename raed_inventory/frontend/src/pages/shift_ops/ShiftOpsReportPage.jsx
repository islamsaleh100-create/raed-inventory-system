// ShiftOpsReportPage.jsx — تقرير عمليات الشفت لحساب المراجعة
// Read-only by contract: this page renders no write action of any kind.
import React, { useState, useEffect, useCallback } from 'react'
import { AlertTriangle, Unlock, Link2Off } from 'lucide-react'
import toast from 'react-hot-toast'
import { shiftOpsApi } from '../../services/shiftOpsApi'
import { PageLoader } from '../../components/common'
import { useT } from '../../i18n'

const FILTERS = [
  { key: 'partial_only', icon: AlertTriangle },
  { key: 'exception_only', icon: Link2Off },
  { key: 'reopened_only', icon: Unlock },
  { key: 'variance_only', icon: AlertTriangle },
  { key: 'negative_movement_only', icon: AlertTriangle },
]

export function ShiftOpsReportPage() {
  const t = useT()
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [active, setActive] = useState({})
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    const params = {}
    Object.entries(active).forEach(([k, v]) => { if (v) params[k] = true })
    if (dateFrom) params.date_from = dateFrom
    if (dateTo) params.date_to = dateTo
    shiftOpsApi
      .report(params)
      .then((r) => setRows(r.data?.items || []))
      .catch(() => toast.error(t('common.load_failed')))
      .finally(() => setLoading(false))
  }, [active, dateFrom, dateTo, t])

  useEffect(() => { load() }, [load])

  const toggle = (key) => setActive((p) => ({ ...p, [key]: !p[key] }))

  if (loading) return <PageLoader />

  return (
    <div className="p-4 space-y-3">
      <h1 className="text-xl font-bold">{t('shift_ops.report_title')}</h1>

      <div className="bg-white border rounded-xl p-3 space-y-3">
        <div className="flex flex-wrap gap-3 items-end text-sm">
          <label className="flex flex-col gap-1">
            <span className="text-gray-500 text-xs">{t('common.date_from')}</span>
            <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)}
                   className="border rounded-lg px-2 py-1.5" />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-gray-500 text-xs">{t('common.date_to')}</span>
            <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)}
                   className="border rounded-lg px-2 py-1.5" />
          </label>
        </div>
        <div className="flex flex-wrap gap-2">
          {FILTERS.map(({ key, icon: Icon }) => (
            <button key={key} type="button" onClick={() => toggle(key)}
                    className={`inline-flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs border ${
                      active[key] ? 'bg-primary-600 text-white border-primary-600' : 'bg-white'
                    }`}>
              <Icon size={13} /> {t(`shift_ops.filter.${key}`)}
            </button>
          ))}
        </div>
      </div>

      {rows.length === 0 && (
        <p className="text-sm text-gray-500 bg-white border rounded-xl p-6 text-center">
          {t('common.no_data')}
        </p>
      )}

      {rows.map((row) => (
        <div key={row.id} className="bg-white border rounded-xl p-3 space-y-2 text-sm">
          <div className="flex items-start justify-between gap-2 flex-wrap">
            <div className="font-semibold">
              {row.shift_date} · {t('shift_ops.shift_n', { n: row.shift_number })}
              <span className="text-xs text-gray-400 font-normal"> · #{row.branch_id}</span>
            </div>
            <div className="flex flex-wrap gap-1">
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

          {/* negative movement exceptions are listed apart from the normal total */}
          {Array.isArray(row.negative_movement_exceptions) && row.negative_movement_exceptions.length > 0 && (
            <div className="border border-amber-300 bg-amber-50 rounded-lg p-2 space-y-1">
              <p className="text-xs font-bold text-amber-800">{t('shift_ops.negative_exceptions')}</p>
              {row.negative_movement_exceptions.map((ex, i) => (
                <p key={i} className="text-xs text-amber-900">
                  {ex.item_name_snapshot || ex.item_id}: {ex.movement_diff} — {ex.movement_exception_reason || '—'}
                </p>
              ))}
            </div>
          )}

          {/* every reopen event, not just the last reason */}
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
