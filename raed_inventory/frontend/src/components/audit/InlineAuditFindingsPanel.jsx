import React from 'react'
import toast from 'react-hot-toast'
import { useSelector } from 'react-redux'
import { auditApi } from '../../services/api'
import { selectUserRoles } from '../../store'
import { useT } from '../../i18n'

function SeverityBadge({ severity, t }) {
  const styles = {
    info: 'bg-emerald-100 text-emerald-700',
    warning: 'bg-amber-100 text-amber-700',
    violation: 'bg-red-100 text-red-700',
  }
  const labels = {
    info: t('nav.audit_finding_severity_info'),
    warning: t('nav.audit_finding_severity_warning'),
    violation: t('nav.audit_finding_severity_violation'),
  }
  return <span className={`status-badge ${styles[severity] || 'bg-gray-100 text-gray-700'}`}>{labels[severity] || severity}</span>
}

function StatusBadge({ status, t }) {
  const styles = {
    open: 'bg-blue-100 text-blue-700',
    acknowledged: 'bg-indigo-100 text-indigo-700',
    closed: 'bg-gray-100 text-gray-700',
  }
  const labels = {
    open: t('nav.audit_finding_status_open'),
    acknowledged: t('nav.audit_finding_status_acknowledged'),
    closed: t('nav.audit_finding_status_closed'),
  }
  return <span className={`status-badge ${styles[status] || 'bg-gray-100 text-gray-700'}`}>{labels[status] || status}</span>
}

export default function InlineAuditFindingsPanel({
  entityType,
  entityId,
  title,
  className = '',
}) {
  const t = useT()
  const roles = useSelector(selectUserRoles)
  const canCreate = roles.some((role) => ['internal_auditor', 'admin', 'super_admin'].includes(role))
  const canAcknowledge = roles.some((role) => ['area_manager', 'operations_manager', 'admin', 'super_admin'].includes(role))
  const [loading, setLoading] = React.useState(true)
  const [rows, setRows] = React.useState([])
  const [showCreate, setShowCreate] = React.useState(false)
  const [ackById, setAckById] = React.useState({})
  const [form, setForm] = React.useState({
    severity: 'warning',
    title: '',
    description: '',
  })

  const load = React.useCallback(async () => {
    if (!entityType || !entityId) {
      setRows([])
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const res = await auditApi.findingsByEntity(entityType, entityId)
      setRows(Array.isArray(res.data) ? res.data : [])
    } catch (error) {
      toast.error(error?.response?.data?.detail || 'Failed to load audit findings')
    } finally {
      setLoading(false)
    }
  }, [entityType, entityId])

  React.useEffect(() => { load() }, [load])

  const handleCreate = async (e) => {
    e.preventDefault()
    try {
      await auditApi.createFinding({
        entity_type: entityType,
        entity_id: Number(entityId),
        severity: form.severity,
        title: form.title,
        description: form.description,
      })
      toast.success(t('audit.finding_created'))
      setForm({ severity: 'warning', title: '', description: '' })
      setShowCreate(false)
      load()
    } catch (error) {
      toast.error(error?.response?.data?.detail || 'Failed to create finding')
    }
  }

  const handleAcknowledge = async (findingId) => {
    const responseText = (ackById[findingId] || '').trim()
    if (!responseText) {
      toast.error(t('audit.response_required'))
      return
    }
    try {
      await auditApi.acknowledgeFinding(findingId, { response_text: responseText })
      toast.success(t('audit.finding_acknowledged'))
      setAckById((prev) => ({ ...prev, [findingId]: '' }))
      load()
    } catch (error) {
      toast.error(error?.response?.data?.detail || 'Failed to acknowledge finding')
    }
  }

  return (
    <div className={`card p-5 mb-4 ${className}`}>
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h2 className="font-semibold text-gray-900">{title || t('nav.audit_findings')}</h2>
          <p className="text-sm text-gray-500 mt-1">{entityType} #{entityId}</p>
        </div>
        <div className="flex gap-2">
          {canCreate ? (
            <button type="button" className="btn-secondary" onClick={() => setShowCreate((v) => !v)}>
              + {t('audit.add_finding')}
            </button>
          ) : null}
          <a href="/audit/findings" className="btn-secondary">
            {t('nav.audit_findings')}
          </a>
        </div>
      </div>

      {showCreate ? (
        <form className="mt-4 space-y-3 rounded-2xl border border-gray-100 bg-gray-50 p-4" onSubmit={handleCreate}>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <select className="input-field" value={form.severity} onChange={(e) => setForm((prev) => ({ ...prev, severity: e.target.value }))}>
              <option value="info">{t('nav.audit_finding_severity_info')}</option>
              <option value="warning">{t('nav.audit_finding_severity_warning')}</option>
              <option value="violation">{t('nav.audit_finding_severity_violation')}</option>
            </select>
            <input className="input-field" value={form.title} onChange={(e) => setForm((prev) => ({ ...prev, title: e.target.value }))} placeholder={t('audit.finding_title')} />
          </div>
          <textarea className="input-field min-h-[110px]" value={form.description} onChange={(e) => setForm((prev) => ({ ...prev, description: e.target.value }))} placeholder={t('audit.finding_description')} />
          <div className="flex justify-end gap-2">
            <button type="button" className="btn-secondary" onClick={() => setShowCreate(false)}>{t('common.cancel')}</button>
            <button type="submit" className="btn-primary">+ {t('audit.add_finding')}</button>
          </div>
        </form>
      ) : null}

      <div className="mt-4 space-y-3">
        {loading ? <div className="text-sm text-gray-400">{t('common.loading')}</div> : null}
        {!loading && rows.length === 0 ? <div className="text-sm text-gray-400">{t('common.no_data')}</div> : null}
        {rows.map((row) => (
          <div key={row.id} className="rounded-2xl border border-gray-100 p-4 space-y-3">
            <div className="flex items-start justify-between gap-3 flex-wrap">
              <div>
                <p className="font-semibold text-gray-900">{row.title}</p>
                <p className="text-xs text-gray-500 mt-1">{row.finding_no}</p>
              </div>
              <div className="flex gap-2">
                <SeverityBadge severity={row.severity} t={t} />
                <StatusBadge status={row.status} t={t} />
              </div>
            </div>
            <p className="text-sm text-gray-700 whitespace-pre-wrap">{row.description}</p>
            <p className="text-xs text-gray-500">
              {(row.created_by_name || row.created_by)} • {row.created_at ? new Date(row.created_at).toLocaleString() : '—'}
            </p>
            {row.response_text ? (
              <div className="rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-800 whitespace-pre-wrap">
                {row.response_text}
              </div>
            ) : null}
            {canAcknowledge && row.status === 'open' ? (
              <div className="flex gap-2 flex-wrap">
                <input
                  className="input-field flex-1"
                  value={ackById[row.id] || ''}
                  onChange={(e) => setAckById((prev) => ({ ...prev, [row.id]: e.target.value }))}
                  placeholder={t('audit.response_text')}
                />
                <button type="button" className="btn-primary" onClick={() => handleAcknowledge(row.id)}>
                  {t('audit.acknowledge')}
                </button>
              </div>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  )
}
