import React from 'react'
import toast from 'react-hot-toast'
import { countAuditApi } from '../../../services/countAuditApi'
import { useT } from '../../../i18n'
import { countAuditErrorMessage, clientRequestIdForEvent, formatDateTimeDisplay, QtySpan } from './helpers'

function statusLabel(status, t) {
  const key = `count_audit.status_${status}`
  const v = t(key)
  return v !== key ? v : status
}

function actionLabel(action, t) {
  const key = `count_audit.action_${action}`
  const v = t(key)
  return v !== key ? v : action
}

function formatActor(ev) {
  const name = ev.actor_name
  const role = ev.actor_role
  if (name && role && name !== role) return `${name} (${role})`
  return name || role || '—'
}

export default function FindingDrawer({ findingId, onClose, onOpenCount, onUpdated }) {
  const t = useT()
  const [loading, setLoading] = React.useState(true)
  const [payload, setPayload] = React.useState(null)
  const [note, setNote] = React.useState('')
  const [lastEventAttempt, setLastEventAttempt] = React.useState(null)
  const [submitting, setSubmitting] = React.useState(false)

  const load = React.useCallback(() => {
    if (!findingId) return undefined
    setLoading(true)
    return countAuditApi.getFinding(findingId)
      .then((res) => setPayload(res.data))
      .catch((err) => toast.error(countAuditErrorMessage(err, t)))
      .finally(() => setLoading(false))
  }, [findingId, t])

  React.useEffect(() => {
    load()
    setNote('')
    setLastEventAttempt(null)
  }, [findingId, load])

  const submitAction = async (action) => {
    const noteTrimmed = note.trim()
    const reqId = clientRequestIdForEvent(lastEventAttempt, action, noteTrimmed)
    setSubmitting(true)
    try {
      await countAuditApi.postFindingEvent(findingId, {
        client_request_id: reqId,
        action,
        note: noteTrimmed,
      })
      toast.success(t('count_audit.action_done'))
      setNote('')
      setLastEventAttempt(null)
      await load()
      onUpdated?.()
    } catch (err) {
      setLastEventAttempt({ id: reqId, action, note: noteTrimmed })
      toast.error(countAuditErrorMessage(err, t))
    } finally {
      setSubmitting(false)
    }
  }

  if (!findingId) return null

  const finding = payload?.finding
  const events = payload?.events || []
  const items = payload?.items || []
  const allowed = payload?.allowed_actions || []

  return (
    <div className="fixed top-16 left-0 bottom-0 z-[60] w-full max-w-xl bg-white shadow-xl border-r border-gray-200 flex flex-col md:top-0 md:inset-y-0">
      <div className="p-4 border-b flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-gray-900">{finding?.finding_no || t('count_audit.finding_drawer_title')}</h2>
          {finding ? (
            <p className="text-sm text-gray-500 mt-1">{finding.title}</p>
          ) : null}
        </div>
        <button type="button" className="btn-secondary" onClick={onClose}>{t('common.close')}</button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {loading ? <p className="text-sm text-gray-500">{t('common.loading')}</p> : null}
        {!loading && finding ? (
          <>
            <div className="text-sm space-y-1">
              <p><span className="text-gray-500">{t('common.status')}:</span> {statusLabel(finding.status, t)}</p>
              <p><span className="text-gray-500">{t('count_audit.branch')}:</span> {finding.branch_name}</p>
              <p><span className="text-gray-500">{t('count_audit.shift_date')}:</span> {finding.shift_date}</p>
              {finding.shift_id ? (
                <button type="button" className="text-primary-600 text-sm font-medium" onClick={() => onOpenCount?.(finding.shift_id)}>
                  {t('count_audit.open_count')}
                </button>
              ) : null}
              <p className="text-gray-700 mt-2">{finding.description}</p>
            </div>
            {items.length ? (
              <div className="card p-3 space-y-2">
                <h3 className="font-semibold text-sm">{t('count_audit.items_snapshot')}</h3>
                {items.map((it) => (
                  <div key={`${it.item_id}-${it.line_id}`} className="text-sm border-b pb-2">
                    <p className="font-medium">{it.item_name_snapshot}</p>
                    <p className="text-gray-600 flex flex-wrap items-center gap-x-1 gap-y-0.5">
                      <span>{t('count_audit.snapshot_at_open')}</span>
                      <span>{t('count_audit.snapshot_closing')}</span>
                      <QtySpan value={it.closing_balance_snapshot} />
                      <span>·</span>
                      <span>{t('count_audit.snapshot_diff')}</span>
                      <QtySpan value={it.movement_diff_snapshot} />
                      <span>—</span>
                      <span>{t('count_audit.snapshot_now')}</span>
                      <span>{t('count_audit.snapshot_closing')}</span>
                      <QtySpan value={it.closing_balance_current} />
                      <span>·</span>
                      <span>{t('count_audit.snapshot_diff')}</span>
                      <QtySpan value={it.movement_diff_current} />
                    </p>
                    {it.changed_since_finding ? (
                      <span className="status-badge bg-amber-100 text-amber-800 mt-1 inline-block">
                        {t('count_audit.changed_since_finding')}
                      </span>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : null}
            <div className="card p-3">
              <h3 className="font-semibold text-sm mb-3">{t('count_audit.event_timeline')}</h3>
              <ul className="space-y-3">
                {events.map((ev) => (
                  <li key={ev.id} className="border-r-2 border-primary-200 pr-3">
                    <p className="text-xs text-gray-500" dir="ltr">{formatDateTimeDisplay(ev.created_at)}</p>
                    <p className="text-sm font-medium">{actionLabel(ev.event_type, t)}</p>
                    <p className="text-xs text-gray-600">{formatActor(ev)}</p>
                    <p className="text-sm text-gray-800 mt-1 whitespace-pre-wrap">{ev.note}</p>
                    {ev.from_status || ev.to_status ? (
                      <p className="text-xs text-gray-500 mt-1">
                        {statusLabel(ev.from_status, t)} → {statusLabel(ev.to_status, t)}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
            {allowed.length ? (
              <div className="card p-3 space-y-3">
                <h3 className="font-semibold text-sm">{t('count_audit.actions_title')}</h3>
                <textarea
                  className="input-field min-h-[80px]"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder={t('count_audit.action_note_placeholder')}
                />
                <div className="flex flex-wrap gap-2">
                  {allowed.map((action) => (
                    <div key={action} className="w-full sm:w-auto">
                      <button
                        type="button"
                        className="btn-primary w-full sm:w-auto"
                        disabled={submitting}
                        onClick={() => submitAction(action)}
                      >
                        {actionLabel(action, t)}
                      </button>
                      {action === 'accept' ? (
                        <p className="text-xs text-gray-500 mt-1">{t('count_audit.accept_helper')}</p>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </>
        ) : null}
      </div>
    </div>
  )
}
