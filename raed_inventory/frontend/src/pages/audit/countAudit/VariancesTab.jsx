import React from 'react'
import toast from 'react-hot-toast'
import { countAuditApi } from '../../../services/countAuditApi'
import { useT } from '../../../i18n'
import { countAuditErrorMessage, validateDateRange, QtySpan, DiffCell } from './helpers'
import Pagination from './Pagination'

export default function VariancesTab({
  filters,
  apiParams,
  group,
  onGroupChange,
  direction,
  onDirectionChange,
  minOccurrences,
  onMinOccurrencesChange,
  page,
  onPageChange,
  onOpenCount,
}) {
  const t = useT()
  const [loading, setLoading] = React.useState(false)
  const [data, setData] = React.useState({ items: [], total: 0, page_size: 50, group: 'line' })

  const load = React.useCallback(() => {
    const err = validateDateRange(filters.date_from, filters.date_to, 93, t)
    if (err) {
      toast.error(err)
      return
    }
    setLoading(true)
    countAuditApi.listVariances({
      ...apiParams,
      group,
      direction,
      min_occurrences: minOccurrences,
      page,
      page_size: 50,
    })
      .then((res) => setData(res.data))
      .catch((e) => toast.error(countAuditErrorMessage(e, t)))
      .finally(() => setLoading(false))
  }, [apiParams, direction, filters.date_from, filters.date_to, group, minOccurrences, page, t])

  React.useEffect(() => { load() }, [load])

  return (
    <div className="space-y-4">
      <div className="card p-4 flex flex-wrap gap-3 items-end">
        <label className="space-y-1">
          <span className="text-xs text-gray-500">{t('count_audit.variance_mode')}</span>
          <select className="input-field" value={group} onChange={(e) => onGroupChange(e.target.value)}>
            <option value="line">{t('count_audit.variance_by_line')}</option>
            <option value="repeat">{t('count_audit.variance_repeat')}</option>
          </select>
        </label>
        <label className="space-y-1">
          <span className="text-xs text-gray-500">{t('count_audit.direction')}</span>
          <select className="input-field" value={direction} onChange={(e) => onDirectionChange(e.target.value)}>
            <option value="all">{t('common.all')}</option>
            <option value="shortage">{t('count_audit.direction_shortage')}</option>
            <option value="surplus">{t('count_audit.direction_surplus')}</option>
          </select>
        </label>
        {group === 'repeat' ? (
          <label className="space-y-1">
            <span className="text-xs text-gray-500">{t('count_audit.min_occurrences')}</span>
            <input
              type="number"
              min={2}
              className="input-field w-24"
              value={minOccurrences}
              onChange={(e) => onMinOccurrencesChange(parseInt(e.target.value, 10) || 2)}
            />
          </label>
        ) : null}
        <button type="button" className="btn-primary" onClick={load}>{t('common.refresh')}</button>
      </div>
      <div className="card p-4 overflow-x-auto">
        {loading ? <p className="text-sm text-gray-500">{t('common.loading')}</p> : null}
        {!loading && !data.items?.length ? (
          <p className="text-sm text-gray-400 py-6 text-center">{t('count_audit.empty_variances')}</p>
        ) : null}
        {!loading && data.items?.length && group === 'line' ? (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 text-xs border-b">
                <th className="p-2 text-right">{t('count_audit.branch')}</th>
                <th className="p-2">{t('common.date')}</th>
                <th className="p-2 text-right">{t('count_audit.item')}</th>
                <th className="p-2">{t('count_audit.diff')}</th>
                <th className="p-2">{t('common.reason')}</th>
                <th className="p-2">{t('common.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((row) => (
                <tr key={row.line_id} className="border-b">
                  <td className="p-2 text-right">{row.branch_name}</td>
                  <td className="p-2 whitespace-nowrap" dir="ltr">{row.shift_date}</td>
                  <td className="p-2 text-right">{row.item_name}</td>
                  <td className="p-2"><DiffCell value={row.movement_diff} t={t} /></td>
                  <td className="p-2 text-xs">{row.reason || '—'}</td>
                  <td className="p-2">
                    <button type="button" className="text-primary-600 text-sm" onClick={() => onOpenCount(row.shift_id, row.item_id)}>
                      {t('count_audit.open_count')}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
        {!loading && data.items?.length && group === 'repeat' ? (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 text-xs border-b">
                <th className="p-2 text-right">{t('count_audit.branch')}</th>
                <th className="p-2 text-right">{t('count_audit.item')}</th>
                <th className="p-2">{t('count_audit.occurrences')}</th>
                <th className="p-2">{t('count_audit.shortage_total')}</th>
                <th className="p-2">{t('count_audit.surplus_total')}</th>
                <th className="p-2">{t('count_audit.reason_sample')}</th>
                <th className="p-2">{t('count_audit.last_date')}</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((row) => {
                const reason = row.reasons_sample?.[0]
                return (
                  <tr key={`${row.branch_id}-${row.item_id}`} className="border-b">
                    <td className="p-2 text-right">{row.branch_name}</td>
                    <td className="p-2 text-right">{row.item_name}</td>
                    <td className="p-2">{row.occurrences}</td>
                    <td className="p-2"><QtySpan value={row.shortage_total} className="text-red-700" /></td>
                    <td className="p-2"><QtySpan value={row.surplus_total} className="text-amber-700" /></td>
                    <td className="p-2 text-xs max-w-[12rem] truncate" title={reason || undefined}>{reason || '—'}</td>
                    <td className="p-2 whitespace-nowrap" dir="ltr">{row.last_date}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        ) : null}
        <Pagination page={page} pageSize={data.page_size || 50} total={data.total} onPageChange={onPageChange} />
      </div>
    </div>
  )
}
