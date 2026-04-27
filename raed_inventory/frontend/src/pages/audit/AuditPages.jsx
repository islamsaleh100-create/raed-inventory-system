import React from 'react'
import toast from 'react-hot-toast'
import { useSelector } from 'react-redux'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Modal } from '../../components/common'
import { auditApi } from '../../services/api'
import { selectUser, selectUserRoles } from '../../store'
import { useT } from '../../i18n'

function PageShell({ title, subtitle, actions, children }) {
  return (
    <div className="p-6 space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{title}</h1>
          {subtitle ? <p className="text-sm text-gray-500 mt-1">{subtitle}</p> : null}
        </div>
        {actions}
      </div>
      {children}
    </div>
  )
}

function StatCard({ label, value, accent = 'blue', onClick, hint }) {
  const styles = {
    blue: 'bg-blue-50 text-blue-700',
    amber: 'bg-amber-50 text-amber-700',
    red: 'bg-red-50 text-red-700',
    emerald: 'bg-emerald-50 text-emerald-700',
    indigo: 'bg-indigo-50 text-indigo-700',
  }
  const classes = onClick
    ? 'card p-5 text-right transition hover:shadow-md hover:border-blue-200 cursor-pointer'
    : 'card p-5'
  const content = (
    <>
      <p className="text-sm text-gray-500">{label}</p>
      <div className={`mt-3 inline-flex rounded-xl px-4 py-2 text-2xl font-bold ${styles[accent] || styles.blue}`}>
        {value ?? 0}
      </div>
      {hint ? <p className="mt-3 text-xs text-blue-600">{hint}</p> : null}
    </>
  )
  if (onClick) {
    return (
      <button type="button" className={classes} onClick={onClick}>
        {content}
      </button>
    )
  }
  return <div className={classes}>{content}</div>
}

function EmptyState({ label }) {
  return <div className="text-center text-sm text-gray-400 py-8">{label}</div>
}

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

function FindingStatusBadge({ status, t }) {
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

function safeT(t, key, fallback) {
  const value = t(key)
  return !value || value === key ? fallback : value
}

const AUDIT_MODULE_LABELS = {
  audit: 'المراجعة الداخلية',
  branch_employees: 'موظفو الفروع',
  branch_requests: 'طلبات الفروع',
  orders: 'الطلبات',
  quality: 'الجودة',
  training: 'التدريب',
  documents: 'الوثائق',
  warehouse: 'المستودع',
  warehouse_lines: 'سطور المستودع',
  delivery: 'التوصيل',
  kitchens: 'المطابخ',
  users: 'المستخدمون',
}

const AUDIT_ACTION_LABELS = {
  audit_finding_create: 'إنشاء ملاحظة مراجعة',
  audit_finding_update: 'تعديل ملاحظة مراجعة',
  audit_finding_acknowledge: 'تأكيد/رد على ملاحظة مراجعة',
  branch_employee_created: 'إنشاء موظف فرع',
  branch_employee_updated: 'تعديل موظف فرع',
  branch_employee_deactivated: 'تعطيل موظف فرع',
  area_review: 'اعتماد/مراجعة منطقة',
  approve: 'اعتماد',
  reject: 'رفض',
  create: 'إنشاء',
  update: 'تحديث',
  delete: 'حذف',
}

const AUDIT_ENTITY_LABELS = {
  branch_request: 'طلب فرع',
  branch_employee: 'موظف فرع',
  quality_visit: 'زيارة جودة',
  training_assessment: 'تقييم تدريب',
  document: 'وثيقة',
  warehouse_line: 'سطر مستودع',
  delivery_order: 'أمر توصيل',
  production_order: 'أمر إنتاج',
  audit_finding: 'ملاحظة مراجعة',
}

const AUDIT_VALUE_LABELS = {
  id: 'المعرّف',
  branch_id: 'معرّف الفرع',
  branch_name: 'اسم الفرع',
  full_name: 'الاسم الكامل',
  job_title: 'المسمى الوظيفي',
  work_number: 'رقم الموظف',
  phone: 'رقم الجوال',
  active: 'الحالة',
  created_at: 'تاريخ الإنشاء',
  updated_at: 'تاريخ التحديث',
  finding_no: 'رقم الملاحظة',
  severity: 'الدرجة',
  status: 'الحالة',
  title: 'العنوان',
  description: 'الوصف',
  response_text: 'نص الرد',
}

function prettifyAuditToken(value = '') {
  return String(value)
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, (m) => m.toUpperCase())
    .trim()
}

function formatAuditModule(value) {
  return AUDIT_MODULE_LABELS[value] || prettifyAuditToken(value) || '—'
}

function formatAuditAction(value) {
  return AUDIT_ACTION_LABELS[value] || prettifyAuditToken(value) || '—'
}

function formatAuditEntity(value, id = null) {
  const label = AUDIT_ENTITY_LABELS[value] || prettifyAuditToken(value) || '—'
  return id !== null && id !== undefined && id !== '' ? `${label} #${id}` : label
}

function formatAuditFieldLabel(key) {
  return AUDIT_VALUE_LABELS[key] || prettifyAuditToken(key)
}

function formatAuditFieldValue(key, value) {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'boolean') return value ? 'نعم' : 'لا'
  if (typeof value === 'string' && /(created_at|updated_at|acknowledged_at|submitted_at)$/i.test(key)) {
    const dt = new Date(value)
    return Number.isNaN(dt.getTime()) ? value : dt.toLocaleString()
  }
  return String(value)
}

function AuditKeyValueList({ values }) {
  const entries = Object.entries(values || {})
  if (!entries.length) {
    return <div className="rounded-2xl border border-gray-100 bg-gray-50 p-4 text-sm text-gray-400">لا توجد تفاصيل</div>
  }
  return (
    <div className="space-y-2">
      {entries.map(([key, value]) => (
        <div key={key} className="flex items-start justify-between gap-4 rounded-xl border border-gray-100 bg-gray-50 px-4 py-3">
          <span className="text-sm text-gray-500">{formatAuditFieldLabel(key)}</span>
          <span className="text-sm font-medium text-gray-900 text-left break-all">{formatAuditFieldValue(key, value)}</span>
        </div>
      ))}
    </div>
  )
}

export function AuditDashboardPage() {
  const t = useT()
  const navigate = useNavigate()
  const [loading, setLoading] = React.useState(true)
  const [summary, setSummary] = React.useState(null)
  const text = React.useCallback((key, fallback) => safeT(t, key, fallback), [t])

  React.useEffect(() => {
    let mounted = true
    ;(async () => {
      try {
        const res = await auditApi.dashboard()
        if (mounted) setSummary(res.data || {})
      } catch (error) {
        toast.error(error?.response?.data?.detail || 'Failed to load audit dashboard')
      } finally {
        if (mounted) setLoading(false)
      }
    })()
    return () => { mounted = false }
  }, [])

  const backlog = summary?.active_supply_chain_backlog || {}
  const approvalMinutes = Math.round(Number(summary?.average_approval_time_seconds || 0) / 60)
  const last7Days = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10)
  const goFindings = React.useCallback((params = {}) => {
    const query = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, value]) => value !== '' && value !== null && value !== undefined))
    ).toString()
    navigate(`/audit/findings${query ? `?${query}` : ''}`)
  }, [navigate])
  const goTrail = React.useCallback((params = {}) => {
    const query = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, value]) => value !== '' && value !== null && value !== undefined))
    ).toString()
    navigate(`/audit/trail${query ? `?${query}` : ''}`)
  }, [navigate])
  const goToPath = React.useCallback((path) => navigate(path), [navigate])

  return (
    <PageShell title={t('nav.audit_dashboard')} subtitle={t('audit.dashboard_subtitle')}>
      {loading ? (
        <div className="card p-8 text-center text-gray-500">{t('common.loading')}</div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
            <StatCard label={text('audit.open_findings_total', 'إجمالي الملاحظات المفتوحة')} value={summary?.open_findings_total || 0} accent="blue" onClick={() => goFindings({ status: 'open' })} hint="عرض التفاصيل" />
            <StatCard label={text('audit.violations_open', 'المخالفات المفتوحة')} value={summary?.violations_open || 0} accent="red" onClick={() => goFindings({ status: 'open', severity: 'violation' })} hint="عرض التفاصيل" />
            <StatCard label={text('audit.warnings_open', 'التحذيرات المفتوحة')} value={summary?.warnings_open || 0} accent="amber" onClick={() => goFindings({ status: 'open', severity: 'warning' })} hint="عرض التفاصيل" />
            <StatCard label={text('audit.info_open', 'ملاحظات العلم المفتوحة')} value={summary?.info_open || 0} accent="emerald" onClick={() => goFindings({ status: 'open', severity: 'info' })} hint="عرض التفاصيل" />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
            <StatCard label={text('audit.findings_last_7_days', 'الملاحظات خلال آخر 7 أيام')} value={summary?.findings_created_last_7_days || 0} accent="indigo" onClick={() => goFindings({ from_date: last7Days })} hint="عرض التفاصيل" />
            <StatCard label={text('audit.unacknowledged_older_than_7_days', 'ملاحظات مفتوحة أقدم من 7 أيام')} value={summary?.unacknowledged_findings_older_than_7_days || 0} accent="red" onClick={() => goFindings({ status: 'open' })} hint="عرض التفاصيل" />
            <StatCard label={text('audit.average_approval_time', 'متوسط زمن الاعتماد')} value={`${approvalMinutes || 0}m`} accent="emerald" onClick={() => goToPath('/supply-chain/approvals')} hint="فتح صفحة الاعتمادات" />
            <StatCard label={text('audit.delays_without_reason', 'تأخيرات بدون سبب')} value={summary?.delays_without_reason || 0} accent="amber" onClick={() => goToPath('/supply-chain/warehouse')} hint="فتح صفحة المستودع" />
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            <div className="card overflow-hidden">
              <div className="px-5 py-4 border-b border-gray-100">
                <h2 className="font-semibold text-gray-900">{text('audit.fast_approvals', 'اعتمادات سريعة أقل من 30 ثانية')}</h2>
              </div>
              <div className="p-4">
                {summary?.fast_approvals_under_30_seconds?.length ? (
                  <div className="space-y-2">
                    {summary.fast_approvals_under_30_seconds.map((row) => (
                      <button
                        type="button"
                        key={row.area_manager}
                        className="flex w-full items-center justify-between rounded-xl bg-gray-50 px-4 py-3 text-right transition hover:bg-blue-50"
                        onClick={() => goToPath('/supply-chain/approvals')}
                      >
                        <span className="text-sm font-medium text-gray-800">{row.area_manager}</span>
                        <span className="text-sm font-bold text-red-700">{row.count}</span>
                      </button>
                    ))}
                  </div>
                ) : <EmptyState label={t('common.no_data')} />}
              </div>
            </div>

            <div className="card overflow-hidden">
              <div className="px-5 py-4 border-b border-gray-100">
                <h2 className="font-semibold text-gray-900">{text('audit.partial_without_reason', 'صرف جزئي بدون سبب')}</h2>
              </div>
              <div className="p-5">
                <button
                  type="button"
                  className="text-4xl font-bold text-amber-700"
                  onClick={() => goToPath('/supply-chain/warehouse')}
                >
                  {summary?.partial_issues_without_reason || 0}
                </button>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            <div className="card overflow-hidden">
              <div className="px-5 py-4 border-b border-gray-100">
                <h2 className="font-semibold text-gray-900">{text('audit.top_variance_items', 'أكثر الأصناف ذات التباين')}</h2>
              </div>
              <div className="p-4">
                {summary?.top_variance_items?.length ? (
                  <div className="space-y-2">
                    {summary.top_variance_items.map((row, idx) => (
                      <button
                        type="button"
                        key={`${row.item_name}-${idx}`}
                        className="flex w-full items-center justify-between rounded-xl bg-gray-50 px-4 py-3 text-right transition hover:bg-blue-50"
                        onClick={() => goToPath('/supply-chain/warehouse')}
                      >
                        <span className="text-sm text-gray-800">{row.item_name}</span>
                        <span className="text-sm font-bold text-gray-900">{row.count}</span>
                      </button>
                    ))}
                  </div>
                ) : <EmptyState label={t('common.no_data')} />}
              </div>
            </div>

            <div className="card overflow-hidden">
              <div className="px-5 py-4 border-b border-gray-100">
                <h2 className="font-semibold text-gray-900">{text('audit.backlog_snapshot', 'نقطة ازدحام سلسلة الإمداد')}</h2>
              </div>
              <div className="p-4 grid grid-cols-2 gap-3">
                <button type="button" className="rounded-xl bg-gray-50 p-4 text-right transition hover:bg-blue-50" onClick={() => goToPath('/supply-chain/branch-requests')}><p className="text-xs text-gray-500">{text('audit.branch_requests_submitted', 'طلبات الفروع المرسلة')}</p><p className="text-xl font-bold">{backlog.branch_requests_submitted || 0}</p></button>
                <button type="button" className="rounded-xl bg-gray-50 p-4 text-right transition hover:bg-blue-50" onClick={() => goToPath('/supply-chain/kitchen')}><p className="text-xs text-gray-500">{text('audit.production_open', 'أوامر الإنتاج المفتوحة')}</p><p className="text-xl font-bold">{backlog.production_open || 0}</p></button>
                <button type="button" className="rounded-xl bg-gray-50 p-4 text-right transition hover:bg-blue-50" onClick={() => goToPath('/supply-chain/warehouse')}><p className="text-xs text-gray-500">{text('audit.warehouse_open', 'سطور المستودع المفتوحة')}</p><p className="text-xl font-bold">{backlog.warehouse_open || 0}</p></button>
                <button type="button" className="rounded-xl bg-gray-50 p-4 text-right transition hover:bg-blue-50" onClick={() => goToPath('/supply-chain/delivery')}><p className="text-xs text-gray-500">{text('audit.delivery_open', 'أوامر التوصيل المفتوحة')}</p><p className="text-xl font-bold">{backlog.delivery_open || 0}</p></button>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            <div className="card overflow-hidden">
              <div className="px-5 py-4 border-b border-gray-100">
                <h2 className="font-semibold text-gray-900">{text('audit.findings_by_entity_type', 'الملاحظات حسب نوع الكيان')}</h2>
              </div>
              <div className="p-4">
                {summary?.findings_by_entity_type?.length ? (
                  <div className="space-y-2">
                    {summary.findings_by_entity_type.map((row) => (
                      <button
                        type="button"
                        key={row.entity_type}
                        className="flex w-full items-center justify-between rounded-xl bg-gray-50 px-4 py-3 text-right transition hover:bg-blue-50"
                        onClick={() => goFindings({ entity_type: row.entity_type })}
                      >
                        <span className="text-sm text-gray-800">{row.entity_type}</span>
                        <span className="text-sm font-bold text-gray-900">{row.count}</span>
                      </button>
                    ))}
                  </div>
                ) : <EmptyState label={t('common.no_data')} />}
              </div>
            </div>

            <div className="card overflow-hidden">
              <div className="px-5 py-4 border-b border-gray-100">
                <h2 className="font-semibold text-gray-900">{text('audit.oldest_open_findings', 'أقدم الملاحظات المفتوحة')}</h2>
              </div>
              <div className="p-4">
                {summary?.oldest_open_findings?.length ? (
                  <div className="space-y-3">
                    {summary.oldest_open_findings.map((row) => (
                      <button
                        type="button"
                        key={row.finding_no}
                        className="w-full rounded-xl border border-gray-100 p-3 text-right transition hover:border-blue-200 hover:bg-blue-50"
                        onClick={() => goFindings({ entity_type: row.entity_type, status: 'open' })}
                      >
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <p className="font-medium text-gray-900">{row.title}</p>
                            <p className="text-xs text-gray-500 mt-1">{row.finding_no} • {row.entity_type} #{row.entity_id}</p>
                          </div>
                          <span className="text-xs font-bold text-red-700">{row.age_days}d</span>
                        </div>
                      </button>
                    ))}
                  </div>
                ) : <EmptyState label={t('common.no_data')} />}
              </div>
            </div>
          </div>
        </>
      )}
    </PageShell>
  )
}

export function AuditFindingsPage() {
  const t = useT()
  const text = React.useCallback((key, fallback) => safeT(t, key, fallback), [t])
  const user = useSelector(selectUser)
  const roles = useSelector(selectUserRoles)
  const [searchParams] = useSearchParams()
  const canCreate = roles.includes('internal_auditor') || roles.includes('admin') || roles.includes('super_admin')
  const canAcknowledge = roles.some((role) => ['area_manager', 'operations_manager', 'admin', 'super_admin'].includes(role))
  const [loading, setLoading] = React.useState(true)
  const [rows, setRows] = React.useState([])
  const [selectedFinding, setSelectedFinding] = React.useState(null)
  const [filters, setFilters] = React.useState({
    severity: searchParams.get('severity') || '',
    status: searchParams.get('status') || '',
    entity_type: searchParams.get('entity_type') || '',
    created_by: searchParams.get('created_by') || '',
    from_date: searchParams.get('from_date') || '',
    to_date: searchParams.get('to_date') || '',
  })
  const [form, setForm] = React.useState({
    entity_type: 'branch_request',
    entity_id: '',
    severity: 'warning',
    title: '',
    description: '',
  })
  const [ackById, setAckById] = React.useState({})

  const load = React.useCallback(async () => {
    setLoading(true)
    try {
      const params = Object.fromEntries(Object.entries(filters).filter(([, value]) => value !== '' && value !== null && value !== undefined))
      const res = await auditApi.listFindings(params)
      setRows(res.data?.items || [])
    } catch (error) {
      toast.error(error?.response?.data?.detail || 'Failed to load findings')
    } finally {
      setLoading(false)
    }
  }, [filters])

  React.useEffect(() => { load() }, [load])

  const handleCreate = async (e) => {
    e.preventDefault()
    try {
      await auditApi.createFinding({
        ...form,
        entity_id: Number(form.entity_id),
      })
      toast.success(t('audit.finding_created'))
      setForm({ entity_type: 'branch_request', entity_id: '', severity: 'warning', title: '', description: '' })
      load()
    } catch (error) {
      toast.error(error?.response?.data?.detail || 'Failed to create finding')
    }
  }

  const handleAcknowledge = async (id) => {
    const responseText = (ackById[id] || '').trim()
    if (!responseText) return toast.error(t('audit.response_required'))
    try {
      await auditApi.acknowledgeFinding(id, { response_text: responseText })
      toast.success(t('audit.finding_acknowledged'))
      setAckById((prev) => ({ ...prev, [id]: '' }))
      load()
    } catch (error) {
      toast.error(error?.response?.data?.detail || 'Failed to acknowledge finding')
    }
  }

  return (
    <PageShell
      title={text('nav.audit_findings', 'ملاحظات المراجعة')}
      subtitle={text('audit.findings_subtitle', 'راجع الملاحظات المسجلة وفلترها وصدّرها.')}
      actions={<a href={auditApi.exportFindingsUrl(filters)} className="btn-secondary">{text('audit.export_csv', 'تصدير CSV')}</a>}
    >
      <div className="card p-4 grid grid-cols-1 md:grid-cols-3 xl:grid-cols-6 gap-3">
        <select className="input-field" value={filters.severity} onChange={(e) => setFilters((prev) => ({ ...prev, severity: e.target.value }))}>
          <option value="">{t('common.all')}</option>
          <option value="info">{t('nav.audit_finding_severity_info')}</option>
          <option value="warning">{t('nav.audit_finding_severity_warning')}</option>
          <option value="violation">{t('nav.audit_finding_severity_violation')}</option>
        </select>
        <select className="input-field" value={filters.status} onChange={(e) => setFilters((prev) => ({ ...prev, status: e.target.value }))}>
          <option value="">{t('common.all')}</option>
          <option value="open">{t('nav.audit_finding_status_open')}</option>
          <option value="acknowledged">{t('nav.audit_finding_status_acknowledged')}</option>
          <option value="closed">{t('nav.audit_finding_status_closed')}</option>
        </select>
        <input className="input-field" value={filters.entity_type} onChange={(e) => setFilters((prev) => ({ ...prev, entity_type: e.target.value }))} placeholder={text('audit.entity_type', 'نوع الكيان')} />
        <input className="input-field" value={filters.created_by} onChange={(e) => setFilters((prev) => ({ ...prev, created_by: e.target.value }))} placeholder={text('audit.created_by', 'معرّف المستخدم المنشئ')} />
        <input className="input-field" type="date" value={filters.from_date} onChange={(e) => setFilters((prev) => ({ ...prev, from_date: e.target.value }))} />
        <input className="input-field" type="date" value={filters.to_date} onChange={(e) => setFilters((prev) => ({ ...prev, to_date: e.target.value }))} />
      </div>

      <div className="flex justify-end">
        <button className="btn-primary" onClick={load}>{t('common.refresh')}</button>
      </div>

      {canCreate ? (
        <form className="card p-5 space-y-4" onSubmit={handleCreate}>
          <h2 className="font-semibold text-gray-900">{text('audit.add_finding', 'إضافة ملاحظة مراجعة')}</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <input className="input-field" value={form.entity_type} onChange={(e) => setForm((prev) => ({ ...prev, entity_type: e.target.value }))} placeholder={text('audit.entity_type', 'نوع الكيان')} />
            <input className="input-field" value={form.entity_id} onChange={(e) => setForm((prev) => ({ ...prev, entity_id: e.target.value }))} placeholder={text('audit.entity_id', 'معرّف الكيان')} />
            <select className="input-field" value={form.severity} onChange={(e) => setForm((prev) => ({ ...prev, severity: e.target.value }))}>
              <option value="info">{t('nav.audit_finding_severity_info')}</option>
              <option value="warning">{t('nav.audit_finding_severity_warning')}</option>
              <option value="violation">{t('nav.audit_finding_severity_violation')}</option>
            </select>
            <input className="input-field" value={form.title} onChange={(e) => setForm((prev) => ({ ...prev, title: e.target.value }))} placeholder={t('audit.finding_title')} />
          </div>
          <textarea className="input-field min-h-[120px]" value={form.description} onChange={(e) => setForm((prev) => ({ ...prev, description: e.target.value }))} placeholder={text('audit.finding_description', 'وصف الملاحظة')} />
          <div className="flex justify-end">
            <button type="submit" className="btn-primary">+ {text('audit.add_finding', 'إضافة ملاحظة مراجعة')}</button>
          </div>
        </form>
      ) : null}

      <div className="card overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="font-semibold text-gray-900">{text('nav.audit_findings', 'ملاحظات المراجعة')}</h2>
          <span className="text-xs text-gray-500">{user?.full_name}</span>
        </div>
        <div className="p-4">
          {loading ? <EmptyState label={t('common.loading')} /> : rows.length === 0 ? <EmptyState label={t('common.no_data')} /> : (
            <div className="space-y-4">
              {rows.map((row) => (
                <div key={row.id} className="rounded-2xl border border-gray-100 p-4 space-y-3">
                  <div className="flex items-start justify-between gap-3 flex-wrap">
                    <div>
                      <p className="font-semibold text-gray-900">{row.title}</p>
                      <p className="text-xs text-gray-500 mt-1">{row.finding_no} • {row.entity_type} #{row.entity_id}</p>
                    </div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <SeverityBadge severity={row.severity} t={t} />
                      <FindingStatusBadge status={row.status} t={t} />
                    </div>
                  </div>
                  <p className="text-sm text-gray-700 whitespace-pre-wrap">{row.description}</p>
                  <div className="text-xs text-gray-500">
                    {row.created_by_name || row.created_by} • {row.created_at ? new Date(row.created_at).toLocaleString() : '—'}
                  </div>
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
                        placeholder={text('audit.response_text', 'نص الرد')}
                      />
                      <button className="btn-primary" onClick={() => handleAcknowledge(row.id)}>
                        {t('audit.acknowledge')}
                      </button>
                    </div>
                  ) : null}
                  <div className="flex justify-end">
                    <button type="button" className="btn-secondary" onClick={() => setSelectedFinding(row)}>
                      {text('common.details', 'عرض')}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <Modal open={Boolean(selectedFinding)} onClose={() => setSelectedFinding(null)} title={selectedFinding?.title || text('nav.audit_findings', 'ملاحظات المراجعة')} size="lg">
        {selectedFinding ? (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
              <div className="rounded-xl bg-gray-50 p-3"><span className="text-gray-500">ID:</span> <span className="font-medium">{selectedFinding.finding_no}</span></div>
              <div className="rounded-xl bg-gray-50 p-3"><span className="text-gray-500">{text('audit.entity', 'الكيان')}:</span> <span className="font-medium">{selectedFinding.entity_type} #{selectedFinding.entity_id}</span></div>
              <div className="rounded-xl bg-gray-50 p-3"><span className="text-gray-500">{text('audit.actor', 'المستخدم')}:</span> <span className="font-medium">{selectedFinding.created_by_name || selectedFinding.created_by}</span></div>
              <div className="rounded-xl bg-gray-50 p-3"><span className="text-gray-500">{t('common.date')}:</span> <span className="font-medium">{selectedFinding.created_at ? new Date(selectedFinding.created_at).toLocaleString() : '—'}</span></div>
            </div>
            <div>
              <h3 className="font-semibold text-gray-900 mb-2">{text('audit.finding_description', 'وصف الملاحظة')}</h3>
              <div className="rounded-2xl border border-gray-100 p-4 whitespace-pre-wrap text-sm text-gray-700">{selectedFinding.description}</div>
            </div>
            {selectedFinding.response_text ? (
              <div>
                <h3 className="font-semibold text-gray-900 mb-2">{text('audit.response_text', 'نص الرد')}</h3>
                <div className="rounded-2xl bg-emerald-50 p-4 whitespace-pre-wrap text-sm text-emerald-800">{selectedFinding.response_text}</div>
              </div>
            ) : null}
          </div>
        ) : null}
      </Modal>
    </PageShell>
  )
}

export function AuditTrailPage() {
  const t = useT()
  const text = React.useCallback((key, fallback) => safeT(t, key, fallback), [t])
  const [searchParams] = useSearchParams()
  const [loading, setLoading] = React.useState(true)
  const [rows, setRows] = React.useState([])
  const [modules, setModules] = React.useState([])
  const [actions, setActions] = React.useState([])
  const [selectedLog, setSelectedLog] = React.useState(null)
  const [filters, setFilters] = React.useState({
    module: searchParams.get('module') || '',
    action: searchParams.get('action') || '',
    entity_type: searchParams.get('entity_type') || '',
    entity_id: searchParams.get('entity_id') || '',
    user_id: searchParams.get('user_id') || '',
    date_from: searchParams.get('date_from') || '',
    date_to: searchParams.get('date_to') || '',
  })

  const load = React.useCallback(async () => {
    setLoading(true)
    try {
      const params = {
        module: filters.module || undefined,
        action: filters.action || undefined,
        entity_type: filters.entity_type || undefined,
        entity_id: filters.entity_id || undefined,
        user_id: filters.user_id || undefined,
        date_from: filters.date_from || undefined,
        date_to: filters.date_to || undefined,
        page_size: 100,
      }
      const [logsRes, modulesRes, actionsRes] = await Promise.all([
        auditApi.listLogs(params),
        auditApi.listModules(),
        auditApi.listActions(filters.module ? { module: filters.module } : {}),
      ])
      setRows(logsRes.data?.items || [])
      setModules(Array.isArray(modulesRes.data) ? modulesRes.data : [])
      setActions(Array.isArray(actionsRes.data) ? actionsRes.data : [])
    } catch (error) {
      toast.error(error?.response?.data?.detail || 'Failed to load audit trail')
    } finally {
      setLoading(false)
    }
  }, [filters])

  React.useEffect(() => { load() }, [load])

  return (
    <PageShell
      title={text('nav.audit_trail', 'سجل العمليات')}
      subtitle={text('audit.trail_subtitle', 'راجع سجل العمليات الثابت مع الفلاتر والتصدير.')}
      actions={<a href={auditApi.exportLogsUrl(filters)} className="btn-secondary">{text('audit.export_csv', 'تصدير CSV')}</a>}
    >
      <div className="card p-4 grid grid-cols-1 md:grid-cols-4 xl:grid-cols-7 gap-3">
        <select className="input-field" value={filters.module} onChange={(e) => setFilters((prev) => ({ ...prev, module: e.target.value, action: '' }))}>
          <option value="">{t('common.all')}</option>
          {modules.map((item) => <option key={item} value={item}>{item}</option>)}
        </select>
        <select className="input-field" value={filters.action} onChange={(e) => setFilters((prev) => ({ ...prev, action: e.target.value }))}>
          <option value="">{t('common.all')}</option>
          {actions.map((item) => <option key={item} value={item}>{item}</option>)}
        </select>
        <input className="input-field" value={filters.entity_type} onChange={(e) => setFilters((prev) => ({ ...prev, entity_type: e.target.value }))} placeholder={text('audit.entity_type', 'نوع الكيان')} />
        <input className="input-field" value={filters.entity_id} onChange={(e) => setFilters((prev) => ({ ...prev, entity_id: e.target.value }))} placeholder={text('audit.entity_id', 'معرّف الكيان')} />
        <input className="input-field" value={filters.user_id} onChange={(e) => setFilters((prev) => ({ ...prev, user_id: e.target.value }))} placeholder={text('audit.user_id', 'معرّف المستخدم')} />
        <input className="input-field" type="date" value={filters.date_from} onChange={(e) => setFilters((prev) => ({ ...prev, date_from: e.target.value }))} />
        <input className="input-field" type="date" value={filters.date_to} onChange={(e) => setFilters((prev) => ({ ...prev, date_to: e.target.value }))} />
      </div>

      <div className="flex justify-end">
        <button className="btn-primary" onClick={load}>{t('common.refresh')}</button>
      </div>

      <div className="card overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100">
          <h2 className="font-semibold text-gray-900">{text('nav.audit_trail', 'سجل العمليات')}</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="table">
            <thead>
              <tr>
                <th>ID</th>
                <th>{t('common.date')}</th>
                <th>{text('audit.actor', 'المستخدم')}</th>
                <th>{text('audit.module', 'الوحدة')}</th>
                <th>{text('audit.action', 'الإجراء')}</th>
                <th>{text('audit.entity', 'الكيان')}</th>
                <th>IP</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={8} className="text-center py-8 text-gray-400">{t('common.loading')}</td></tr>
              ) : rows.length === 0 ? (
                <tr><td colSpan={8} className="text-center py-8 text-gray-400">{t('common.no_data')}</td></tr>
              ) : rows.map((row) => (
                <tr key={row.id}>
                  <td>{row.id}</td>
                  <td>{row.created_at ? new Date(row.created_at).toLocaleString() : '—'}</td>
                  <td>{row.actor_username || '—'}</td>
                  <td>{formatAuditModule(row.module)}</td>
                  <td>{formatAuditAction(row.action)}</td>
                  <td>{row.entity_type ? formatAuditEntity(row.entity_type, row.entity_id) : '—'}</td>
                  <td>{row.ip_address || '—'}</td>
                  <td><button type="button" className="btn-secondary" onClick={() => setSelectedLog(row)}>{text('common.details', 'عرض')}</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <Modal open={Boolean(selectedLog)} onClose={() => setSelectedLog(null)} title={selectedLog ? `${formatAuditModule(selectedLog.module)} • ${formatAuditAction(selectedLog.action)}` : text('nav.audit_trail', 'سجل العمليات')} size="lg">
        {selectedLog ? (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
              <div className="rounded-xl bg-gray-50 p-3"><span className="text-gray-500">{text('audit.actor', 'المستخدم')}:</span> <span className="font-medium">{selectedLog.actor_username || '—'}</span></div>
              <div className="rounded-xl bg-gray-50 p-3"><span className="text-gray-500">{t('common.date')}:</span> <span className="font-medium">{selectedLog.created_at ? new Date(selectedLog.created_at).toLocaleString() : '—'}</span></div>
              <div className="rounded-xl bg-gray-50 p-3"><span className="text-gray-500">{text('audit.entity', 'الكيان')}:</span> <span className="font-medium">{formatAuditEntity(selectedLog.entity_type, selectedLog.entity_id)}</span></div>
              <div className="rounded-xl bg-gray-50 p-3"><span className="text-gray-500">IP:</span> <span className="font-medium">{selectedLog.ip_address || '—'}</span></div>
            </div>
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
              <div>
                <h3 className="font-semibold text-gray-900 mb-2">{text('audit.old_values', 'القيم السابقة')}</h3>
                <AuditKeyValueList values={selectedLog.old_values || {}} />
              </div>
              <div>
                <h3 className="font-semibold text-gray-900 mb-2">{text('audit.new_values', 'القيم الجديدة')}</h3>
                <AuditKeyValueList values={selectedLog.new_values || {}} />
              </div>
            </div>
          </div>
        ) : null}
      </Modal>
    </PageShell>
  )
}
