/**
 * Documents Module — Phase F3.5
 *
 * Pages:
 *   - DocumentsListPage:     قائمة الوثائق مع فلاتر (نوع، فرع، موظف، حالة)
 *   - DocumentsExpiringPage: لوحة الوثائق المقاربة على الانتهاء (dashboard)
 *   - DocumentFormPage:      نموذج إنشاء/تعديل + رفع ملف + تجديد
 *
 * صلاحيات:
 *   - admin/super_admin/area_manager/quality_manager: كامل
 *   - branch_manager: فرعه فقط
 *   - warehouse_manager: عرض فقط
 */
import React, { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import { useSelector } from 'react-redux'
import toast from 'react-hot-toast'
import {
  FileText, Calendar, AlertTriangle, CheckCircle, Clock,
  Archive, Upload, RefreshCw, Plus, ArrowLeft, Download, Trash2, Edit2,
} from 'lucide-react'
import { documentsApi } from '../../services/api'
import { selectUserRoles } from '../../store'
import { masterApi, usersApi } from '../../services/api'
import { useT, useLanguage } from '../../i18n'
import { StatusBadge, PageLoader, Modal, ReadOnlyBanner } from '../../components/common'
import InlineAuditFindingsPanel from '../../components/audit/InlineAuditFindingsPanel'
import { formatDate } from '../../utils/helpers'

const DOC_TYPES_BRANCH = [
  'municipality_license',
  'civil_defense_license',
  'commercial_registration',
  'food_safety_permit',
  'branch_other',
]
const DOC_TYPES_EMPLOYEE = [
  'health_certificate',
  'national_id',
  'work_permit',
  'work_contract',
  'employee_other',
]

function statusColor(status) {
  switch (status) {
    case 'expired':  return 'bg-red-100 text-red-700 border-red-200'
    case 'due_soon': return 'bg-orange-100 text-orange-700 border-orange-200'
    case 'valid':    return 'bg-green-100 text-green-700 border-green-200'
    case 'archived': return 'bg-gray-100 text-gray-600 border-gray-200'
    default:         return 'bg-gray-100 text-gray-600 border-gray-200'
  }
}

function StatusBadgeDoc({ status, t }) {
  const label = t(`documents.status_${status}`) || status
  return (
    <span className={`status-badge text-xs border ${statusColor(status)}`}>
      {label}
    </span>
  )
}

/* ───────────────────────────────── LIST ───────────────────────────────── */

export function DocumentsListPage() {
  const t = useT()
  const navigate = useNavigate()
  const roles = useSelector(selectUserRoles)
  const canEdit = roles.some(r => ['admin', 'super_admin', 'area_manager', 'branch_manager', 'quality_manager'].includes(r))
  const isAuditor = roles.includes('internal_auditor')

  const [ownerType, setOwnerType] = useState('branch')    // 'branch' | 'employee'
  const [statusFilter, setStatusFilter] = useState('')    // '' | valid | due_soon | expired | archived
  const [docTypeFilter, setDocTypeFilter] = useState('')
  const [includeArchived, setIncludeArchived] = useState(false)
  const [rows, setRows] = useState([])
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    const params = { owner_type: ownerType, include_archived: includeArchived }
    if (statusFilter) params.status = statusFilter
    if (docTypeFilter) params.doc_type = docTypeFilter
    let cancelled = false
    // J2: use allSettled so a failing /summary doesn't blank out the table
    Promise.allSettled([
      documentsApi.list(params),
      documentsApi.summary(),
    ])
      .then(([listRes, summaryRes]) => {
        if (cancelled) return
        if (listRes.status === 'fulfilled') {
          // K1: coerce to array — backend might 200-with-null if a legacy row
          // makes serialize fail, and rows.map would crash otherwise
          const data = listRes.value?.data
          setRows(Array.isArray(data) ? data : [])
        } else {
          const err = listRes.reason
          const status = err?.response?.status
          const detail = err?.response?.data?.detail
          if (status === 404 && detail === 'Not Found') {
            toast.error(t('documents.endpoint_missing') || 'خدمة الوثائق غير متاحة')
          } else {
            toast.error(detail || t('documents.load_error') || 'تعذّر تحميل الوثائق')
          }
          setRows([])
        }
        if (summaryRes.status === 'fulfilled') {
          setSummary(summaryRes.value?.data || null)
        } else {
          setSummary(null)
        }
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }

  useEffect(() => {
    const cleanup = load()
    return cleanup
  }, [ownerType, statusFilter, docTypeFilter, includeArchived])

  const typeOptions = ownerType === 'branch' ? DOC_TYPES_BRANCH : DOC_TYPES_EMPLOYEE

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('documents.title') || 'إدارة الوثائق'}</h1>
          <p className="text-gray-500 text-sm">{t('documents.subtitle') || 'رخص الفرع وشهادات الموظفين'}</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => navigate('/documents/expiring')}
            className="btn-secondary"
          >
            <AlertTriangle className="w-4 h-4" />
            {t('documents.expiring_cta') || 'المقاربة على الانتهاء'}
          </button>
          {canEdit && (
            <button onClick={() => navigate('/documents/new')} className="btn-primary">
              <Plus className="w-4 h-4" />
              {t('documents.new') || 'وثيقة جديدة'}
            </button>
          )}
        </div>
      </div>

      {isAuditor ? (
        <ReadOnlyBanner
          title="قراءة فقط"
          description="المراجع الداخلي يطّلع على الوثائق وحالات الانتهاء والتجديد دون إنشاء أو تعديل أو أرشفة."
        />
      ) : null}

      {/* Summary cards */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <SummaryCard icon={<FileText className="w-5 h-5" />} label={t('documents.total') || 'الإجمالي'} value={summary.total} tone="blue" />
          <SummaryCard icon={<CheckCircle className="w-5 h-5" />} label={t('documents.status_valid') || 'سارية'} value={summary.valid} tone="green" />
          <SummaryCard icon={<Clock className="w-5 h-5" />} label={t('documents.status_due_soon') || 'قريبة الانتهاء'} value={summary.due_soon} tone="orange" />
          <SummaryCard icon={<AlertTriangle className="w-5 h-5" />} label={t('documents.status_expired') || 'منتهية'} value={summary.expired} tone="red" />
        </div>
      )}

      {/* Tabs + filters */}
      <div className="card mb-4">
        <div className="flex flex-wrap items-center gap-3 p-4">
          <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
            <button
              onClick={() => { setOwnerType('branch'); setDocTypeFilter('') }}
              className={`px-4 py-2 rounded-md text-sm font-medium ${ownerType === 'branch' ? 'bg-white shadow text-primary-700' : 'text-gray-600'}`}
            >
              {t('documents.tab_branches') || 'وثائق الفروع'}
            </button>
            <button
              onClick={() => { setOwnerType('employee'); setDocTypeFilter('') }}
              className={`px-4 py-2 rounded-md text-sm font-medium ${ownerType === 'employee' ? 'bg-white shadow text-primary-700' : 'text-gray-600'}`}
            >
              {t('documents.tab_employees') || 'وثائق الموظفين'}
            </button>
          </div>

          <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} className="input-field w-auto">
            <option value="">{t('documents.all_statuses') || 'كل الحالات'}</option>
            <option value="valid">{t('documents.status_valid') || 'سارية'}</option>
            <option value="due_soon">{t('documents.status_due_soon') || 'قريبة الانتهاء'}</option>
            <option value="expired">{t('documents.status_expired') || 'منتهية'}</option>
            {includeArchived && <option value="archived">{t('documents.status_archived') || 'مؤرشفة'}</option>}
          </select>

          <select value={docTypeFilter} onChange={e => setDocTypeFilter(e.target.value)} className="input-field w-auto">
            <option value="">{t('documents.all_types') || 'كل الأنواع'}</option>
            {typeOptions.map(dt => (
              <option key={dt} value={dt}>{t(`documents.type_${dt}`) || dt}</option>
            ))}
          </select>

          <label className="flex items-center gap-2 text-sm text-gray-600">
            <input type="checkbox" checked={includeArchived} onChange={e => setIncludeArchived(e.target.checked)} />
            {t('documents.include_archived') || 'إظهار المؤرشفة'}
          </label>

          <button onClick={load} className="btn-secondary ms-auto">
            <RefreshCw className="w-4 h-4" /> {t('common.refresh') || 'تحديث'}
          </button>
        </div>
      </div>

      {/* Table */}
      {loading ? (
        <PageLoader />
      ) : rows.length === 0 ? (
        <div className="card p-12 text-center text-gray-500">
          <FileText className="w-12 h-12 mx-auto mb-3 text-gray-300" />
          {t('documents.empty') || 'لا توجد وثائق'}
        </div>
      ) : (
        <div className="card">
          <div className="table-container">
            <table className="table">
              <thead>
                <tr>
                  <th>{t('documents.col_title') || 'العنوان'}</th>
                  <th>{t('documents.col_type') || 'النوع'}</th>
                  <th>{ownerType === 'branch' ? (t('documents.col_branch') || 'الفرع') : (t('documents.col_employee') || 'الموظف')}</th>
                  <th>{t('documents.col_expiry') || 'تاريخ الانتهاء'}</th>
                  <th>{t('documents.col_days_left') || 'أيام متبقية'}</th>
                  <th>{t('documents.col_status') || 'الحالة'}</th>
                  <th>{t('documents.col_file') || 'الملف'}</th>
                  <th>{t('documents.col_actions') || 'إجراءات'}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(doc => (
                  <tr key={doc.id} className={doc.status === 'expired' ? 'bg-red-50' : doc.status === 'due_soon' ? 'bg-orange-50' : ''}>
                    <td>
                      <div className="font-medium text-sm">{doc.title}</div>
                      {doc.doc_number && <div className="text-xs text-gray-400">#{doc.doc_number}</div>}
                    </td>
                    <td className="text-xs">{t(`documents.type_${doc.doc_type}`) || doc.doc_type}</td>
                    <td className="text-sm">
                      {ownerType === 'branch' ? (doc.branch_name || '—') : (doc.user_full_name || '—')}
                    </td>
                    <td className="text-sm">{formatDate(doc.expiry_date)}</td>
                    <td className="text-center text-sm font-medium">
                      {doc.days_until_expiry < 0
                        ? <span className="text-red-600">{doc.days_until_expiry}</span>
                        : <span>{doc.days_until_expiry}</span>}
                    </td>
                    <td><StatusBadgeDoc status={doc.status} t={t} /></td>
                    <td>
                      {doc.file_path ? (
                        <a
                          href={documentsApi.downloadUrl(doc.id)}
                          target="_blank"
                          rel="noreferrer"
                          className="text-primary-600 hover:underline text-xs inline-flex items-center gap-1"
                        >
                          <Download className="w-3 h-3" /> {t('documents.download') || 'تنزيل'}
                        </a>
                      ) : (
                        <span className="text-xs text-gray-400">—</span>
                      )}
                    </td>
                    <td>
                      <div className="flex gap-2">
                        <Link to={`/documents/${doc.id}`} className="text-primary-600 text-xs hover:underline">
                          {t('documents.action_view') || 'عرض'}
                        </Link>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

function SummaryCard({ icon, label, value, tone }) {
  const tones = {
    blue: 'bg-blue-50 text-blue-700',
    green: 'bg-green-50 text-green-700',
    orange: 'bg-orange-50 text-orange-700',
    red: 'bg-red-50 text-red-700',
  }
  return (
    <div className={`card p-4 flex items-center gap-3 ${tones[tone] || tones.blue}`}>
      <div className="p-2 bg-white/60 rounded-lg">{icon}</div>
      <div>
        <p className="text-xs opacity-80">{label}</p>
        <p className="text-2xl font-bold">{value}</p>
      </div>
    </div>
  )
}

/* ─────────────────────────── EXPIRING DASHBOARD ─────────────────────────── */

export function DocumentsExpiringPage() {
  const t = useT()
  const navigate = useNavigate()
  const roles = useSelector(selectUserRoles)
  const isAuditor = roles.includes('internal_auditor')
  const [days, setDays] = useState(30)
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    let cancelled = false
    documentsApi.expiring(days)
      .then(r => { if (!cancelled) setRows(Array.isArray(r?.data) ? r.data : []) })
      .catch(err => {
        if (cancelled) return
        const status = err?.response?.status
        const detail = err?.response?.data?.detail
        // If backend returns the default FastAPI 404 "Not Found" it means the
        // endpoint isn't registered — likely backend not restarted after the
        // documents module was added. Show a more actionable message.
        let msg
        if (status === 404 && detail === 'Not Found') {
          msg = t('documents.endpoint_missing') || 'خدمة الوثائق غير متاحة — أعد تشغيل الخادم'
        } else if (detail) {
          msg = detail
        } else {
          msg = t('documents.load_error') || 'تعذّر تحميل الوثائق'
        }
        toast.error(msg)
        // eslint-disable-next-line no-console
        console.error('[DocumentsExpiringPage] failed to load:', status, err)
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }

  useEffect(() => {
    const cleanup = load()
    return cleanup
  }, [days])

  return (
    <div className="p-6">
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => navigate(-1)} className="p-2 hover:bg-gray-100 rounded-lg">
          <ArrowLeft className="w-5 h-5 text-gray-600" />
        </button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-gray-900">{t('documents.expiring_title') || 'وثائق مقاربة على الانتهاء'}</h1>
          <p className="text-gray-500 text-sm">{t('documents.expiring_subtitle') || 'يجب التجديد قبل أن تنتهي الصلاحية'}</p>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-600">{t('documents.within_days') || 'خلال كم يوم'}:</label>
          <select value={days} onChange={e => setDays(Number(e.target.value))} className="input-field w-auto">
            <option value={7}>7</option>
            <option value={14}>14</option>
            <option value={30}>30</option>
            <option value={60}>60</option>
            <option value={90}>90</option>
          </select>
        </div>
      </div>

      {isAuditor ? (
        <ReadOnlyBanner
          title="قراءة فقط"
          description="هذه اللوحة مخصصة لمراجعة الوثائق القريبة من الانتهاء فقط."
        />
      ) : null}

      {loading ? (
        <PageLoader />
      ) : rows.length === 0 ? (
        <div className="card p-12 text-center text-green-700">
          <CheckCircle className="w-12 h-12 mx-auto mb-3 text-green-500" />
          {t('documents.no_expiring') || 'لا توجد وثائق مقاربة على الانتهاء'}
        </div>
      ) : (
        <div className="space-y-3">
          {rows.map(doc => (
            <div key={doc.id} className={`card p-4 flex items-center gap-4 border-l-4 ${doc.status === 'expired' ? 'border-red-500' : 'border-orange-500'}`}>
              <div className={`p-3 rounded-lg ${doc.status === 'expired' ? 'bg-red-50 text-red-600' : 'bg-orange-50 text-orange-600'}`}>
                <AlertTriangle className="w-5 h-5" />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <p className="font-semibold text-sm">{doc.title}</p>
                  <StatusBadgeDoc status={doc.status} t={t} />
                </div>
                <p className="text-xs text-gray-500 mt-0.5">
                  {t(`documents.type_${doc.doc_type}`) || doc.doc_type}
                  {doc.branch_name ? ` — ${doc.branch_name}` : ''}
                  {doc.user_full_name ? ` — ${doc.user_full_name}` : ''}
                </p>
                <p className="text-xs text-gray-400 mt-1">
                  {t('documents.expires_on') || 'ينتهي بتاريخ'}: {formatDate(doc.expiry_date)}
                  {' '}({doc.days_until_expiry < 0
                    ? (t('documents.expired_days_ago') || 'منذ {n} يوم').replace('{n}', Math.abs(doc.days_until_expiry))
                    : (t('documents.in_n_days') || 'خلال {n} يوم').replace('{n}', doc.days_until_expiry)})
                </p>
              </div>
              <Link to={`/documents/${doc.id}`} className="btn-secondary text-xs">
                {t('documents.action_view') || 'عرض'}
              </Link>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/* ─────────────────────────── FORM / DETAIL ─────────────────────────── */

export function DocumentFormPage() {
  const t = useT()
  const navigate = useNavigate()
  const { id } = useParams()
  const roles = useSelector(selectUserRoles)
  const canEdit = roles.some(r => ['admin', 'super_admin', 'area_manager', 'branch_manager', 'quality_manager'].includes(r))
  const isAuditor = roles.includes('internal_auditor')
  const isEdit = Boolean(id && id !== 'new')

  const [loading, setLoading] = useState(isEdit)
  const [saving, setSaving] = useState(false)
  const [branches, setBranches] = useState([])
  const [users, setUsers] = useState([])
  const [doc, setDoc] = useState(null)
  const [renewOpen, setRenewOpen] = useState(false)
  const [renewData, setRenewData] = useState({ new_expiry_date: '', new_issue_date: '', new_doc_number: '', notes: '' })

  const [form, setForm] = useState({
    owner_type: 'branch',
    branch_id: '',
    user_id: '',
    doc_type: 'municipality_license',
    title: '',
    issuer: '',
    doc_number: '',
    issue_date: '',
    expiry_date: '',
    reminder_days: 30,
    notes: '',
  })

  useEffect(() => {
    // K1: catch handlers so a failing dropdown load doesn't surface as an
    // unhandled promise rejection / ErrorBoundary crash
    masterApi.listBranches({ active_only: true })
      .then(r => setBranches(Array.isArray(r?.data) ? r.data : (r?.data?.items || [])))
      .catch(() => setBranches([]))
    usersApi.list({ page: 1, page_size: 500 })
      .then(r => setUsers(r?.data?.items || (Array.isArray(r?.data) ? r.data : [])))
      .catch(() => setUsers([]))
  }, [])

  useEffect(() => {
    if (!isEdit) return
    let cancelled = false
    documentsApi.get(id)
      .then(r => {
        if (cancelled) return
        const d = r.data
        setDoc(d)
        setForm({
          owner_type: d.owner_type,
          branch_id: d.branch_id || '',
          user_id: d.user_id || '',
          doc_type: d.doc_type,
          title: d.title || '',
          issuer: d.issuer || '',
          doc_number: d.doc_number || '',
          issue_date: d.issue_date || '',
          expiry_date: d.expiry_date || '',
          reminder_days: d.reminder_days || 30,
          notes: d.notes || '',
        })
      })
      .catch(err => toast.error(err?.response?.data?.detail || t('documents.load_error') || 'تعذّر تحميل الوثيقة'))
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [id, isEdit])

  const setField = (k, v) => setForm(prev => ({ ...prev, [k]: v }))

  const typeOptions = form.owner_type === 'branch' ? DOC_TYPES_BRANCH : DOC_TYPES_EMPLOYEE

  useEffect(() => {
    // when switching owner_type, reset doc_type to a matching default + clear the other FK
    if (form.owner_type === 'branch') {
      if (!DOC_TYPES_BRANCH.includes(form.doc_type)) setField('doc_type', 'municipality_license')
      if (form.user_id) setField('user_id', '')
    } else {
      if (!DOC_TYPES_EMPLOYEE.includes(form.doc_type)) setField('doc_type', 'health_certificate')
      if (form.branch_id) setField('branch_id', '')
    }
  }, [form.owner_type])  // eslint-disable-line

  const handleSave = async () => {
    if (!form.title.trim()) { toast.error(t('documents.err_title') || 'أدخل عنوان الوثيقة'); return }
    if (!form.expiry_date)  { toast.error(t('documents.err_expiry') || 'أدخل تاريخ الانتهاء'); return }
    if (form.owner_type === 'branch' && !form.branch_id) { toast.error(t('documents.err_branch') || 'اختر الفرع'); return }
    if (form.owner_type === 'employee' && !form.user_id) { toast.error(t('documents.err_employee') || 'اختر الموظف'); return }

    setSaving(true)
    try {
      const payload = {
        ...form,
        branch_id: form.owner_type === 'branch' ? Number(form.branch_id) : null,
        user_id:   form.owner_type === 'employee' ? Number(form.user_id) : null,
        reminder_days: Number(form.reminder_days) || 30,
        issue_date: form.issue_date || null,
      }
      if (isEdit) {
        // partial update
        await documentsApi.update(id, {
          title: payload.title,
          issuer: payload.issuer || null,
          doc_number: payload.doc_number || null,
          issue_date: payload.issue_date,
          expiry_date: payload.expiry_date,
          reminder_days: payload.reminder_days,
          notes: payload.notes || null,
        })
        toast.success(t('documents.toast_updated') || 'تم تحديث الوثيقة')
        navigate('/documents')
      } else {
        const r = await documentsApi.create(payload)
        toast.success(t('documents.toast_created') || 'تم إنشاء الوثيقة')
        navigate(`/documents/${r.data.id}`)
      }
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('documents.toast_error') || 'حدث خطأ')
    } finally {
      setSaving(false)
    }
  }

  const handleUpload = async (file) => {
    if (!file || !isEdit) return
    try {
      await documentsApi.uploadFile(id, file)
      toast.success(t('documents.toast_uploaded') || 'تم رفع الملف')
      const r = await documentsApi.get(id)
      setDoc(r.data)
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('documents.toast_error') || 'حدث خطأ')
    }
  }

  const handleDelete = async () => {
    if (!window.confirm(t('documents.confirm_delete') || 'تأكيد حذف الوثيقة؟')) return
    try {
      await documentsApi.remove(id)
      toast.success(t('documents.toast_deleted') || 'تم حذف الوثيقة')
      navigate('/documents')
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('documents.toast_error') || 'حدث خطأ')
    }
  }

  const handleRenew = async () => {
    if (!renewData.new_expiry_date) { toast.error(t('documents.err_new_expiry') || 'أدخل تاريخ الانتهاء الجديد'); return }
    try {
      const r = await documentsApi.renew(id, {
        new_expiry_date: renewData.new_expiry_date,
        new_issue_date: renewData.new_issue_date || null,
        new_doc_number: renewData.new_doc_number || null,
        notes: renewData.notes || null,
      })
      toast.success(t('documents.toast_renewed') || 'تم تجديد الوثيقة')
      setRenewOpen(false)
      navigate(`/documents/${r.data.id}`)
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('documents.toast_error') || 'حدث خطأ')
    }
  }

  if (loading) return <PageLoader />

  return (
    <div className="p-6">
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => navigate(-1)} className="p-2 hover:bg-gray-100 rounded-lg">
          <ArrowLeft className="w-5 h-5 text-gray-600" />
        </button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-gray-900">
            {isEdit ? (t('documents.edit_title') || 'تفاصيل الوثيقة') : (t('documents.new') || 'وثيقة جديدة')}
          </h1>
          {doc && (
            <div className="flex items-center gap-3 mt-1">
              <StatusBadgeDoc status={doc.status} t={t} />
              {doc.is_archived && (
                <span className="text-xs text-gray-500 inline-flex items-center gap-1">
                  <Archive className="w-3 h-3" /> {t('documents.archived_note') || 'مؤرشفة (تم تجديدها)'}
                </span>
              )}
            </div>
          )}
        </div>
        {isEdit && canEdit && !doc?.is_archived && (
          <>
            <button onClick={() => setRenewOpen(true)} className="btn-secondary">
              <RefreshCw className="w-4 h-4" /> {t('documents.action_renew') || 'تجديد'}
            </button>
            <button onClick={handleDelete} className="btn-danger">
              <Trash2 className="w-4 h-4" /> {t('common.delete') || 'حذف'}
            </button>
          </>
        )}
      </div>

      {isAuditor ? (
        <ReadOnlyBanner
          title="قراءة فقط"
          description="الوثيقة معروضة للمراجعة فقط. يمكنك تنزيل الملف وإضافة ملاحظة مراجعة دون تعديل أو تجديد."
        />
      ) : null}

      {isEdit && doc ? (
        <InlineAuditFindingsPanel
          entityType="document"
          entityId={doc.id}
          title="ملاحظات المراجعة على الوثيقة"
        />
      ) : null}

      <div className="card p-6 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {!isEdit && (
            <Field label={t('documents.field_owner_type') || 'نوع الوثيقة'}>
              <select value={form.owner_type} onChange={e => setField('owner_type', e.target.value)} className="input-field">
                <option value="branch">{t('documents.tab_branches') || 'وثيقة فرع'}</option>
                <option value="employee">{t('documents.tab_employees') || 'وثيقة موظف'}</option>
              </select>
            </Field>
          )}
          <Field label={t('documents.field_type') || 'النوع'}>
            <select value={form.doc_type} onChange={e => setField('doc_type', e.target.value)} className="input-field" disabled={isEdit || !canEdit}>
              {typeOptions.map(dt => (
                <option key={dt} value={dt}>{t(`documents.type_${dt}`) || dt}</option>
              ))}
            </select>
          </Field>

          {form.owner_type === 'branch' ? (
            <Field label={t('documents.field_branch') || 'الفرع'}>
              <select value={form.branch_id} onChange={e => setField('branch_id', e.target.value)} className="input-field" disabled={isEdit || !canEdit}>
                <option value="">—</option>
                {branches.map(b => <option key={b.id} value={b.id}>{b.branch_name}</option>)}
              </select>
            </Field>
          ) : (
            <Field label={t('documents.field_employee') || 'الموظف'}>
              <select value={form.user_id} onChange={e => setField('user_id', e.target.value)} className="input-field" disabled={isEdit || !canEdit}>
                <option value="">—</option>
                {users.map(u => <option key={u.id} value={u.id}>{u.full_name} ({u.username})</option>)}
              </select>
            </Field>
          )}

          <Field label={t('documents.field_title') || 'عنوان الوثيقة'}>
            <input value={form.title} onChange={e => setField('title', e.target.value)} className="input-field" disabled={!canEdit} />
          </Field>

          <Field label={t('documents.field_issuer') || 'الجهة المُصدرة'}>
            <input value={form.issuer} onChange={e => setField('issuer', e.target.value)} className="input-field" disabled={!canEdit} />
          </Field>

          <Field label={t('documents.field_doc_number') || 'رقم الوثيقة'}>
            <input value={form.doc_number} onChange={e => setField('doc_number', e.target.value)} className="input-field" disabled={!canEdit} />
          </Field>

          <Field label={t('documents.field_issue_date') || 'تاريخ الإصدار'}>
            <input type="date" value={form.issue_date || ''} onChange={e => setField('issue_date', e.target.value)} className="input-field" disabled={!canEdit} />
          </Field>

          <Field label={t('documents.field_expiry_date') || 'تاريخ الانتهاء'} required>
            <input type="date" value={form.expiry_date || ''} onChange={e => setField('expiry_date', e.target.value)} className="input-field" disabled={!canEdit} />
          </Field>

          <Field label={t('documents.field_reminder_days') || 'بدء التذكير قبل (أيام)'}>
            <input type="number" min="1" max="365" value={form.reminder_days} onChange={e => setField('reminder_days', e.target.value)} className="input-field" disabled={!canEdit} />
          </Field>
        </div>

        <Field label={t('documents.field_notes') || 'ملاحظات'}>
          <textarea value={form.notes} onChange={e => setField('notes', e.target.value)} className="input-field min-h-20" disabled={!canEdit} />
        </Field>

        <div className="flex gap-3 justify-end pt-4 border-t">
          <button onClick={() => navigate('/documents')} className="btn-secondary">{t('common.cancel') || 'إلغاء'}</button>
          {canEdit && !doc?.is_archived && (
            <button onClick={handleSave} disabled={saving} className="btn-primary">
              {saving ? (t('common.saving') || 'جاري الحفظ...') : (t('common.save') || 'حفظ')}
            </button>
          )}
        </div>
      </div>

      {/* File upload (only after creation) */}
      {isEdit && (
        <div className="card p-6 mt-4">
          <h2 className="font-semibold text-gray-900 mb-3">{t('documents.file_section') || 'ملف الوثيقة'}</h2>
          {doc?.file_path ? (
            <div className="flex items-center gap-3 mb-3">
              <FileText className="w-5 h-5 text-primary-600" />
              <div className="flex-1">
                <p className="text-sm font-medium">{doc.file_name || 'document'}</p>
                <p className="text-xs text-gray-500">
                  {doc.size_bytes ? `${(doc.size_bytes / 1024).toFixed(1)} KB` : ''}
                  {doc.mime_type ? ` · ${doc.mime_type}` : ''}
                </p>
              </div>
              <a
                href={documentsApi.downloadUrl(doc.id)}
                target="_blank"
                rel="noreferrer"
                className="btn-secondary text-xs"
              >
                <Download className="w-3 h-3" /> {t('documents.download') || 'تنزيل'}
              </a>
            </div>
          ) : (
            <p className="text-sm text-gray-500 mb-3">{t('documents.no_file') || 'لم يُرفع ملف بعد'}</p>
          )}
          {canEdit && !doc?.is_archived && (
            <label className="btn-primary cursor-pointer inline-flex">
              <Upload className="w-4 h-4" />
              {doc?.file_path ? (t('documents.replace_file') || 'استبدال الملف') : (t('documents.upload_file') || 'رفع ملف')}
              <input
                type="file"
                className="hidden"
                accept="image/*,application/pdf"
                onChange={e => handleUpload(e.target.files?.[0])}
              />
            </label>
          )}
          <p className="text-xs text-gray-400 mt-2">
            {t('documents.file_hint') || 'المسموح: صور أو PDF بحد أقصى 15 ميجا'}
          </p>
        </div>
      )}

      {/* Renew modal */}
      <Modal open={renewOpen} onClose={() => setRenewOpen(false)} title={t('documents.renew_modal_title') || 'تجديد الوثيقة'}>
        <div className="space-y-3">
          <Field label={t('documents.new_expiry_date') || 'تاريخ الانتهاء الجديد'} required>
            <input type="date" value={renewData.new_expiry_date} onChange={e => setRenewData(p => ({ ...p, new_expiry_date: e.target.value }))} className="input-field" />
          </Field>
          <Field label={t('documents.new_issue_date') || 'تاريخ الإصدار الجديد'}>
            <input type="date" value={renewData.new_issue_date} onChange={e => setRenewData(p => ({ ...p, new_issue_date: e.target.value }))} className="input-field" />
          </Field>
          <Field label={t('documents.new_doc_number') || 'رقم الوثيقة الجديدة'}>
            <input value={renewData.new_doc_number} onChange={e => setRenewData(p => ({ ...p, new_doc_number: e.target.value }))} className="input-field" />
          </Field>
          <Field label={t('documents.field_notes') || 'ملاحظات'}>
            <textarea value={renewData.notes} onChange={e => setRenewData(p => ({ ...p, notes: e.target.value }))} className="input-field min-h-16" />
          </Field>
          <p className="text-xs text-gray-500">
            {t('documents.renew_hint') || 'سيتم إنشاء وثيقة جديدة وأرشفة القديمة.'}
          </p>
        </div>
        <div className="flex gap-3 justify-end mt-4">
          <button onClick={() => setRenewOpen(false)} className="btn-secondary">{t('common.cancel') || 'إلغاء'}</button>
          <button onClick={handleRenew} className="btn-primary">
            <RefreshCw className="w-4 h-4" /> {t('documents.action_renew') || 'تجديد'}
          </button>
        </div>
      </Modal>
    </div>
  )
}

function Field({ label, required, children }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        {label} {required && <span className="text-red-500">*</span>}
      </label>
      {children}
    </div>
  )
}
