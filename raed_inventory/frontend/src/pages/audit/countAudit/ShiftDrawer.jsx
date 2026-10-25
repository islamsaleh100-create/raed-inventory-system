import React from 'react'
import toast from 'react-hot-toast'
import { useSelector } from 'react-redux'
import { countAuditApi } from '../../../services/countAuditApi'
import { selectUserRoles } from '../../../store'
import { useT } from '../../../i18n'
import {
  countAuditErrorMessage,
  clientRequestIdForCreate,
  rememberCreateAttempt,
  QtySpan,
  DiffCell,
  formatDateTimeDisplay,
  reopenTargetLabel,
  TLtr,
  renderI18nLtr,
} from './helpers'

function LineTable({ lines, selectedIds, onToggle, highlightItemIds, openingBaseline, t }) {
  if (!lines?.length) {
    return <p className="text-sm text-gray-400 py-4">{t('count_audit.empty_lines')}</p>
  }
  return (
    <div>
      <h3 className="font-semibold text-sm mb-1">{t('count_audit.lines_table_title')}</h3>
      {openingBaseline ? (
        <p className="text-xs text-sky-800 bg-sky-50 border border-sky-100 rounded px-2 py-1.5 mb-2">
          {t('count_audit.opening_count_lines_hint')}
        </p>
      ) : (
        <p className="text-xs text-gray-500 mb-2">{t('count_audit.diff_legend')}</p>
      )}
      <div className="overflow-x-auto max-h-[40vh] overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 z-10 bg-white shadow-sm">
            <tr className="text-gray-500 text-xs">
              <th className="p-2 w-8 bg-white">{t('count_audit.line_select')}</th>
              <th className="p-2 text-right bg-white">{t('count_audit.item')}</th>
              <th className="p-2 bg-white">{t('count_audit.opening')}</th>
              <th className="p-2 bg-white">{t('count_audit.received')}</th>
              <th className="p-2 bg-white">{t('count_audit.returned')}</th>
              <th className="p-2 bg-white">{t('count_audit.damaged')}</th>
              <th className="p-2 bg-white">{t('count_audit.closing')}</th>
              <th className="p-2 bg-white">{t('count_audit.diff')}</th>
              <th className="p-2 bg-white">{t('common.reason')}</th>
            </tr>
          </thead>
          <tbody>
            {lines.map((line) => {
              const highlighted = highlightItemIds?.includes(line.item_id)
              const checked = selectedIds.includes(line.item_id)
              return (
                <tr key={line.id} className={highlighted ? 'bg-amber-50' : ''}>
                  <td className="p-2">
                    <input
                      type="checkbox"
                      checked={checked}
                      disabled={openingBaseline}
                      onChange={() => onToggle(line.item_id)}
                      aria-label={line.item_name_snapshot}
                    />
                  </td>
                  <td className="p-2 text-right font-medium">{line.item_name_snapshot}</td>
                  <td className="p-2"><QtySpan value={line.opening_balance} /></td>
                  <td className="p-2"><QtySpan value={line.received_qty} /></td>
                  <td className="p-2"><QtySpan value={line.returned_qty} /></td>
                  <td className="p-2"><QtySpan value={line.damaged_qty} /></td>
                  <td className="p-2"><QtySpan value={line.closing_balance} /></td>
                  <td className="p-2">
                    {openingBaseline ? <span className="text-gray-400">—</span> : <DiffCell value={line.movement_diff} t={t} />}
                  </td>
                  <td className="p-2 text-xs">{line.movement_exception_reason || '—'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default function ShiftDrawer({
  shiftId,
  branchNameById,
  highlightItemIds,
  onClose,
  onOpenFinding,
}) {
  const t = useT()
  const roles = useSelector(selectUserRoles)
  const canCreate = roles.some((r) => ['internal_auditor', 'admin', 'super_admin'].includes(r))
  const [loading, setLoading] = React.useState(true)
  const [detail, setDetail] = React.useState(null)
  const [selectedIds, setSelectedIds] = React.useState([])
  const [form, setForm] = React.useState({ severity: 'warning', title: '', description: '' })
  const [lastCreateAttempt, setLastCreateAttempt] = React.useState(null)
  const [submitting, setSubmitting] = React.useState(false)

  React.useEffect(() => {
    if (!shiftId) return undefined
    let cancelled = false
    setLoading(true)
    countAuditApi.getShift(shiftId)
      .then((res) => {
        if (!cancelled) setDetail(res.data)
      })
      .catch((err) => {
        if (!cancelled) toast.error(countAuditErrorMessage(err, t))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [shiftId, t])

  React.useEffect(() => {
    setSelectedIds([])
    setForm({ severity: 'warning', title: '', description: '' })
    setLastCreateAttempt(null)
  }, [shiftId])

  const toggleItem = (itemId) => {
    setSelectedIds((prev) => (prev.includes(itemId) ? prev.filter((id) => id !== itemId) : [...prev, itemId]))
  }

  const submitFinding = async (e) => {
    e.preventDefault()
    const payload = {
      shift_id: shiftId,
      severity: form.severity,
      title: form.title,
      description: form.description,
      item_ids: selectedIds,
    }
    const reqId = clientRequestIdForCreate(lastCreateAttempt, payload)
    setSubmitting(true)
    try {
      const res = await countAuditApi.createFinding({
        client_request_id: reqId,
        shift_id: shiftId,
        severity: form.severity,
        title: form.title.trim(),
        description: form.description.trim(),
        item_ids: selectedIds,
      })
      toast.success(t('count_audit.finding_created'))
      onOpenFinding?.(res.data?.finding?.id)
      setForm({ severity: 'warning', title: '', description: '' })
      setSelectedIds([])
      setLastCreateAttempt(null)
    } catch (err) {
      setLastCreateAttempt(rememberCreateAttempt(reqId, payload))
      toast.error(countAuditErrorMessage(err, t))
    } finally {
      setSubmitting(false)
    }
  }

  if (!shiftId) return null

  const lines = detail?.count?.lines || []
  const branchName = detail?.shift?.branch_id != null
    ? (branchNameById?.[detail.shift.branch_id] || '')
    : ''
  const titleEmpty = !form.title.trim()
  const noLines = selectedIds.length === 0

  return (
    <div className="fixed top-16 left-0 bottom-0 z-50 w-full max-w-3xl bg-white shadow-xl border-r border-gray-200 flex flex-col md:top-0 md:inset-y-0">
      <div className="p-4 border-b flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-gray-900">{t('count_audit.shift_drawer_title')}</h2>
          {detail?.shift ? (
            <p className="text-sm text-gray-500 mt-1 flex flex-wrap items-center gap-x-1">
              <TLtr>{branchName || '—'}</TLtr>
              <span aria-hidden="true">—</span>
              <TLtr>{detail.shift.shift_date}</TLtr>
              <span aria-hidden="true">—</span>
              <span>{renderI18nLtr(t, 'count_audit.shift_title_number', { n: detail.shift.shift_number })}</span>
              {detail.is_opening_count ? (
                <span className="bg-sky-100 text-sky-900 px-2 py-0.5 rounded text-xs font-bold">
                  {t('count_audit.opening_count_badge')}
                </span>
              ) : null}
            </p>
          ) : null}
        </div>
        <button type="button" className="btn-secondary" onClick={onClose}>{t('common.close')}</button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {loading ? <p className="text-sm text-gray-500">{t('common.loading')}</p> : null}
        {!loading && detail?.reopen_events?.length ? (
          <div className="card p-3">
            <h3 className="font-semibold text-sm mb-2">{t('count_audit.reopen_events')}</h3>
            <ul className="space-y-2 text-sm">
              {detail.reopen_events.map((ev) => (
                <li key={ev.id} className="text-gray-700">
                  <span className="text-gray-500" dir="ltr">{formatDateTimeDisplay(ev.created_at)}</span>
                  {' · '}
                  {reopenTargetLabel(ev.target, t)}: {ev.reason}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {!loading && detail?.findings?.length ? (
          <div className="card p-3">
            <h3 className="font-semibold text-sm mb-2">{t('count_audit.linked_findings')}</h3>
            <ul className="space-y-1 text-sm">
              {detail.findings.map((f) => (
                <li key={f.id}>
                  <button type="button" className="text-primary-600 hover:underline" onClick={() => onOpenFinding?.(f.id)}>
                    {f.finding_no} — {f.title}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {!loading ? (
          <LineTable
            lines={lines}
            selectedIds={selectedIds}
            onToggle={toggleItem}
            highlightItemIds={highlightItemIds}
            openingBaseline={Boolean(detail?.is_opening_count)}
            t={t}
          />
        ) : null}
        {canCreate && !loading ? (
          <form className="card p-4 space-y-3" onSubmit={submitFinding}>
            <h3 className="font-semibold">{t('count_audit.create_finding')}</h3>
            <p className="text-xs text-gray-500">{t('count_audit.create_finding_hint')}</p>
            <label className="block space-y-1">
              <span className="text-xs font-medium text-gray-700">{t('count_audit.severity_label')}</span>
              <select className="input-field w-full" value={form.severity} onChange={(e) => setForm((p) => ({ ...p, severity: e.target.value }))}>
                <option value="info">{t('nav.audit_finding_severity_info')}</option>
                <option value="warning">{t('nav.audit_finding_severity_warning')}</option>
                <option value="violation">{t('nav.audit_finding_severity_violation')}</option>
              </select>
            </label>
            <label className="block space-y-1">
              <span className="text-xs font-medium text-gray-700">{t('count_audit.finding_title')}</span>
              <input className="input-field w-full" value={form.title} onChange={(e) => setForm((p) => ({ ...p, title: e.target.value }))} required minLength={5} />
            </label>
            <label className="block space-y-1">
              <span className="text-xs font-medium text-gray-700">{t('count_audit.finding_description')}</span>
              <textarea className="input-field min-h-[100px] w-full" value={form.description} onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))} required minLength={10} />
            </label>
            {noLines ? <p className="text-xs text-amber-700">{t('count_audit.hint_select_line')}</p> : null}
            {titleEmpty ? <p className="text-xs text-amber-700">{t('count_audit.hint_title_required')}</p> : null}
            <button type="submit" className="btn-primary w-full" disabled={submitting || noLines || titleEmpty}>
              {submitting ? t('common.saving') : t('count_audit.submit_finding')}
            </button>
          </form>
        ) : null}
      </div>
    </div>
  )
}
