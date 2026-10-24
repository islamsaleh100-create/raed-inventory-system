import React from 'react'
import toast from 'react-hot-toast'
import { countAuditApi } from '../../../services/countAuditApi'
import { useT } from '../../../i18n'
import { countAuditErrorMessage, formatDateOnly, pendingPartyLabel, renderI18nLtr } from './helpers'
import Pagination from './Pagination'

function statusLabel(status, t) {
  const key = `count_audit.status_${status}`
  const v = t(key)
  return v !== key ? v : status
}

export default function FindingsTab({
  scopeParams,
  queue,
  onQueueChange,
  page,
  onPageChange,
  onOpenFinding,
}) {
  const t = useT()
  const [loading, setLoading] = React.useState(false)
  const [data, setData] = React.useState({ items: [], total: 0, summary: {}, page_size: 50 })
  const [createdFrom, setCreatedFrom] = React.useState('')
  const [createdTo, setCreatedTo] = React.useState('')

  const load = React.useCallback(() => {
    setLoading(true)
    const params = {
      ...scopeParams,
      queue: queue === 'all' ? 'all' : (queue || undefined),
      page,
      page_size: 50,
    }
    if (createdFrom) params.date_from = createdFrom
    if (createdTo) params.date_to = createdTo
    countAuditApi.listFindings(params)
      .then((res) => setData(res.data))
      .catch((e) => toast.error(countAuditErrorMessage(e, t)))
      .finally(() => setLoading(false))
  }, [scopeParams, createdFrom, createdTo, page, queue, t])

  React.useEffect(() => { load() }, [load])

  const chips = [
    { id: 'waiting_response', count: data.summary?.waiting_response },
    { id: 'waiting_auditor', count: data.summary?.waiting_auditor },
    { id: 'closed', count: data.summary?.closed },
    { id: 'all', count: null },
  ]

  const activeFilterParts = []
  if (scopeParams.brand_id) activeFilterParts.push(t('count_audit.filter_brand'))
  if (scopeParams.city) activeFilterParts.push(t('count_audit.filter_city'))
  if (scopeParams.branch_id) activeFilterParts.push(t('count_audit.filter_branch'))
  if (createdFrom || createdTo) activeFilterParts.push(t('count_audit.created_date_filter'))

  return (
    <div className="space-y-4">
      <div className="card p-4 grid grid-cols-2 gap-3 max-w-xl">
        <label className="space-y-1">
          <span className="text-xs text-gray-500">{t('count_audit.created_from')}</span>
          <input type="date" className="input-field w-full" value={createdFrom} onChange={(e) => setCreatedFrom(e.target.value)} />
        </label>
        <label className="space-y-1">
          <span className="text-xs text-gray-500">{t('count_audit.created_to')}</span>
          <input type="date" className="input-field w-full" value={createdTo} onChange={(e) => setCreatedTo(e.target.value)} />
        </label>
      </div>
      <div className="flex flex-wrap gap-2">
        {chips.map((chip) => (
          <button
            key={chip.id}
            type="button"
            className={`px-4 py-2 rounded-xl text-sm font-medium border ${queue === chip.id ? 'bg-primary-50 border-primary-300 text-primary-800' : 'bg-white border-gray-200 text-gray-700'}`}
            onClick={() => onQueueChange(chip.id)}
          >
            {t(`count_audit.queue_${chip.id}`)}
            {chip.count != null ? ` (${chip.count})` : ''}
          </button>
        ))}
      </div>
      <div className="card p-4 overflow-x-auto">
        {loading ? <p className="text-sm text-gray-500">{t('common.loading')}</p> : null}
        {!loading && !data.items?.length ? (
          <p className="text-sm text-gray-400 py-6 text-center">
            {activeFilterParts.length
              ? renderI18nLtr(t, 'count_audit.empty_findings_filtered', { filters: activeFilterParts.join(' · ') })
              : t('count_audit.empty_findings')}
          </p>
        ) : null}
        {!loading && data.items?.length ? (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 text-xs border-b">
                <th className="p-2">{t('count_audit.finding_no')}</th>
                <th className="p-2 text-right">{t('count_audit.branch')}</th>
                <th className="p-2">{t('common.status')}</th>
                <th className="p-2 text-right">{t('count_audit.finding_title')}</th>
                <th className="p-2">{t('count_audit.items_count_header')}</th>
                <th className="p-2">{t('count_audit.opened_at')}</th>
                <th className="p-2">{t('count_audit.pending_party')}</th>
                <th className="p-2">{t('count_audit.age_days')}</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((row) => (
                <tr
                  key={row.id}
                  className="border-b hover:bg-gray-50 cursor-pointer"
                  onClick={() => onOpenFinding(row.id)}
                >
                  <td className="p-2 font-medium">{row.finding_no}</td>
                  <td className="p-2 text-right">{row.branch_name}</td>
                  <td className="p-2">{statusLabel(row.status, t)}</td>
                  <td className="p-2 text-right">{row.title}</td>
                  <td className="p-2">{row.items_count}</td>
                  <td className="p-2 whitespace-nowrap" dir="ltr">{formatDateOnly(row.created_at)}</td>
                  <td className="p-2">{pendingPartyLabel(row.status, t)}</td>
                  <td className="p-2">{row.age_days ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
        <Pagination page={page} pageSize={data.page_size || 50} total={data.total} onPageChange={onPageChange} />
      </div>
    </div>
  )
}
