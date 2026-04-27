/**
 * Quality Visit Pages
 * - QualityVisitListPage  → /quality
 * - QualityVisitFormPage  → /quality/new
 * - QualityVisitDetailPage → /quality/:id
 */
import React from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useSelector } from 'react-redux'
import toast from 'react-hot-toast'
import { qualityApi, masterApi, usersApi } from '../../services/api'
import { selectUserRoles } from '../../store'
import { useT, useLanguage } from '../../i18n'
import { ReadOnlyBanner } from '../../components/common'
import InlineAuditFindingsPanel from '../../components/audit/InlineAuditFindingsPanel'

// ─── Status helpers ────────────────────────────────────────────────────────────
const STATUS_COLOR = {
  draft: 'bg-gray-100 text-gray-600',
  submitted: 'bg-blue-100 text-blue-700',
  reviewed: 'bg-yellow-100 text-yellow-700',
  closed: 'bg-green-100 text-green-700',
}
const RESPONSE_COLOR = {
  yes: 'bg-green-100 text-green-700',
  no: 'bg-red-100 text-red-700',
  na: 'bg-gray-100 text-gray-500',
}

function StatusBadge({ status }) {
  const t = useT()
  return (
    <span className={`status-badge text-xs font-medium px-2.5 py-1 rounded-full ${STATUS_COLOR[status] || 'bg-gray-100 text-gray-500'}`}>
      {t(`quality.status_${status}`)}
    </span>
  )
}

const nameOf = (obj, base, lang) => obj?.[`${base}_${lang}`] || obj?.[`${base}_ar`] || obj?.[base] || ''

const QUALITY_BRANDS = [
  { key: 'onda', labelAr: 'أوندا', labelEn: 'Onda' },
  { key: 'ronaldos', labelAr: 'رونالدوز', labelEn: 'Ronaldos Pizza' },
  { key: 'shawarma', labelAr: 'شاورما', labelEn: 'Shawarma' },
  { key: 'griddle', labelAr: 'جريدل', labelEn: 'Griddle' },
]

const inferQualityBrandKey = (branch) => {
  const raw = String(branch?.branch_name || branch?.name || '').toLowerCase()
  if (!raw) return ''
  if (raw.includes('ronaldos') || raw.includes('pizza')) return 'ronaldos'
  if (raw.includes('shawarma')) return 'shawarma'
  if (raw.includes('griddle') || raw.includes('burger') || raw.includes('grill')) return 'griddle'
  if (raw.includes('onda') || raw.includes('coffee') || raw.includes('cafe')) return 'onda'
  return ''
}

const qualityBrandLabel = (brandKey, lang) => {
  const brand = QUALITY_BRANDS.find((entry) => entry.key === brandKey)
  if (!brand) return ''
  return lang === 'en' ? brand.labelEn : brand.labelAr
}

function ComplianceBadge({ pct }) {
  if (pct === null || pct === undefined) return <span className="text-gray-400 text-sm">—</span>
  const color = pct >= 80 ? 'text-green-600' : pct >= 60 ? 'text-yellow-600' : 'text-red-600'
  return <span className={`font-bold text-lg ${color}`}>{pct}%</span>
}

// ─── Signature Panel ──────────────────────────────────────────────────────
function SignaturePanel({ visit, onSigned, canVisitorSign, canBranchSign }) {
  const t = useT()
  const [visitorSig, setVisitorSig] = React.useState('')
  const [branchSig, setBranchSig] = React.useState('')
  const [busy, setBusy] = React.useState(false)
  const sign = async (role, value) => {
    if (!value || value.trim().length < 2) {
      toast.error(t('quality.sign_too_short'))
      return
    }
    setBusy(true)
    try {
      await qualityApi.signVisit(visit.id, { role, signature: value.trim() })
      toast.success(t('quality.signed_toast'))
      onSigned()
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('quality.error_generic'))
    } finally {
      setBusy(false)
    }
  }
  if (!['submitted', 'reviewed', 'closed'].includes(visit.status)) return null
  return (
    <div className="card p-4 mb-4 border-2 border-indigo-100 bg-indigo-50/40 no-print-hidden">
      <h3 className="font-semibold text-indigo-800 mb-3 text-sm">{t('quality.signatures_title')}</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="label">{t('quality.sig_visitor')}</label>
          {visit.visitor_signature ? (
            <div className="text-sm bg-white rounded border border-indigo-200 px-3 py-2">
              <span className="font-medium">{visit.visitor_signature}</span>
              <span className="text-xs text-gray-500 mr-2"> — {visit.visitor_signed_at?.slice(0, 10)}</span>
            </div>
          ) : canVisitorSign ? (
            <div className="flex gap-2">
              <input value={visitorSig} onChange={e => setVisitorSig(e.target.value)}
                className="input-field flex-1" placeholder={t('quality.sig_placeholder_name')} />
              <button onClick={() => sign('visitor', visitorSig)} disabled={busy} className="btn-primary text-xs">
                {t('quality.sig_sign')}
              </button>
            </div>
          ) : (
            <span className="text-sm text-gray-400">{t('quality.sig_pending')}</span>
          )}
        </div>
        <div>
          <label className="label">{t('quality.sig_branch_mgr')}</label>
          {visit.branch_mgr_signature ? (
            <div className="text-sm bg-white rounded border border-indigo-200 px-3 py-2">
              <span className="font-medium">{visit.branch_mgr_signature}</span>
              <span className="text-xs text-gray-500 mr-2"> — {visit.branch_mgr_signed_at?.slice(0, 10)}</span>
            </div>
          ) : canBranchSign ? (
            <div className="flex gap-2">
              <input value={branchSig} onChange={e => setBranchSig(e.target.value)}
                className="input-field flex-1" placeholder={t('quality.sig_placeholder_name')} />
              <button onClick={() => sign('branch_manager', branchSig)} disabled={busy} className="btn-primary text-xs">
                {t('quality.sig_sign')}
              </button>
            </div>
          ) : (
            <span className="text-sm text-gray-400">{t('quality.sig_pending')}</span>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Attachments Panel ────────────────────────────────────────────────────
function AttachmentsPanel({ responseId, initial, canEdit, onChange }) {
  const t = useT()
  const [items, setItems] = React.useState(initial || [])
  const [uploading, setUploading] = React.useState(false)
  const inputRef = React.useRef(null)

  React.useEffect(() => { setItems(initial || []) }, [initial])

  const upload = async (file) => {
    setUploading(true)
    try {
      const res = await qualityApi.uploadAttachment(responseId, file, 'photo')
      const next = [...items, res.data]
      setItems(next)
      if (onChange) onChange(next)
      toast.success(t('quality.att_uploaded'))
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('quality.error_generic'))
    } finally {
      setUploading(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  const remove = async (id) => {
    if (!window.confirm(t('quality.att_confirm_delete'))) return
    try {
      await qualityApi.deleteAttachment(id)
      const next = items.filter(i => i.id !== id)
      setItems(next)
      if (onChange) onChange(next)
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('quality.error_generic'))
    }
  }

  return (
    <div className="mt-2">
      {items.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-2">
          {items.map(a => {
            const isImg = (a.mime_type || '').startsWith('image/')
            const url = qualityApi.downloadAttachmentUrl(a.id)
            const token = typeof localStorage !== 'undefined' ? localStorage.getItem('access_token') : null
            const hrefed = token ? `${url}?token=${encodeURIComponent(token)}` : url
            return (
              <div key={a.id} className="relative group border border-gray-200 rounded overflow-hidden bg-white">
                <a href={hrefed} target="_blank" rel="noreferrer" className="block">
                  {isImg ? (
                    <div className="w-20 h-20 bg-gray-100 flex items-center justify-center text-xs text-gray-400">
                      📷 {a.original_name?.slice(0, 12) || 'image'}
                    </div>
                  ) : (
                    <div className="w-20 h-20 bg-gray-100 flex items-center justify-center text-xs text-gray-500 p-1 text-center">
                      📎 {a.original_name?.slice(0, 12) || 'file'}
                    </div>
                  )}
                </a>
                {canEdit && (
                  <button onClick={() => remove(a.id)}
                    className="absolute top-0 left-0 bg-red-500 text-white text-[10px] px-1 opacity-0 group-hover:opacity-100">
                    ✕
                  </button>
                )}
              </div>
            )
          })}
        </div>
      )}
      {canEdit && (
        <div className="flex items-center gap-2 no-print-hidden">
          <input ref={inputRef} type="file" accept="image/*,application/pdf"
            onChange={e => e.target.files?.[0] && upload(e.target.files[0])}
            disabled={uploading} className="text-xs" />
          {uploading && <span className="text-xs text-gray-400">{t('quality.att_uploading')}</span>}
        </div>
      )}
    </div>
  )
}


// I3 — Visit-level attachments panel (photos/PDFs attached directly to the visit)
function VisitAttachmentsPanel({ visitId, initial, canEdit, onChange }) {
  const t = useT()
  const [items, setItems] = React.useState(initial || [])
  const [uploading, setUploading] = React.useState(false)
  const inputRef = React.useRef(null)

  React.useEffect(() => { setItems(initial || []) }, [initial])

  const upload = async (file) => {
    setUploading(true)
    try {
      const res = await qualityApi.uploadVisitAttachment(visitId, file, 'photo')
      const next = [...items, res.data]
      setItems(next)
      if (onChange) onChange(next)
      toast.success(t('quality.att_uploaded'))
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('quality.error_generic'))
    } finally {
      setUploading(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  const remove = async (id) => {
    if (!window.confirm(t('quality.att_confirm_delete'))) return
    try {
      await qualityApi.deleteAttachment(id)
      const next = items.filter(i => i.id !== id)
      setItems(next)
      if (onChange) onChange(next)
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('quality.error_generic'))
    }
  }

  // لو مفيش ولا صورة ومفيش صلاحية ترفع — ماتظهرش الـ panel (keep detail page clean)
  if (!canEdit && items.length === 0) return null

  return (
    <div className="card p-4 mb-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-700">
          {t('quality.visit_attachments_title') || 'صور/مرفقات الزيارة'}
        </h3>
        {canEdit && (
          <div className="flex items-center gap-2 no-print-hidden">
            <input ref={inputRef} type="file" accept="image/*,application/pdf"
              onChange={e => e.target.files?.[0] && upload(e.target.files[0])}
              disabled={uploading} className="text-xs" />
            {uploading && <span className="text-xs text-gray-400">{t('quality.att_uploading')}</span>}
          </div>
        )}
      </div>
      {items.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {items.map(a => {
            const isImg = (a.mime_type || '').startsWith('image/')
            const url = qualityApi.downloadAttachmentUrl(a.id)
            const token = typeof localStorage !== 'undefined' ? localStorage.getItem('access_token') : null
            const hrefed = token ? `${url}?token=${encodeURIComponent(token)}` : url
            return (
              <div key={a.id} className="relative group border border-gray-200 rounded overflow-hidden bg-white">
                <a href={hrefed} target="_blank" rel="noreferrer" className="block">
                  <div className="w-20 h-20 bg-gray-100 flex items-center justify-center text-xs text-gray-500 p-1 text-center">
                    {isImg ? '📷' : '📎'} {a.original_name?.slice(0, 12) || (isImg ? 'image' : 'file')}
                  </div>
                </a>
                {canEdit && (
                  <button onClick={() => remove(a.id)}
                    className="absolute top-0 left-0 bg-red-500 text-white text-[10px] px-1 opacity-0 group-hover:opacity-100 no-print-hidden">
                    ✕
                  </button>
                )}
              </div>
            )
          })}
        </div>
      ) : (
        <p className="text-xs text-gray-400">
          {t('quality.visit_attachments_empty') || 'لا توجد مرفقات على مستوى الزيارة بعد'}
        </p>
      )}
    </div>
  )
}

// ─── List Page ─────────────────────────────────────────────────────────────────
export function QualityVisitListPage() {
  const t = useT()
  const [visits, setVisits] = React.useState([])
  const [total, setTotal] = React.useState(0)
  const [loading, setLoading] = React.useState(true)
  const [page, setPage] = React.useState(1)
  const [statusFilter, setStatusFilter] = React.useState('')
  const roles = useSelector(selectUserRoles)
  const canCreate = roles.some(r => ['quality_visitor', 'quality_manager', 'admin', 'super_admin'].includes(r))
  const isAuditor = roles.includes('internal_auditor')

  const load = React.useCallback(() => {
    setLoading(true)
    const params = { page, page_size: 20 }
    if (statusFilter) params.status = statusFilter
    qualityApi.list(params)
      .then(r => {
        // K1: defensive — backend might return null, array, or {items, total}
        const data = r?.data
        if (Array.isArray(data)) {
          setVisits(data); setTotal(data.length)
        } else {
          setVisits(data?.items || [])
          setTotal(data?.total || 0)
        }
      })
      .catch(() => toast.error(t('quality.load_visits_error')))
      .finally(() => setLoading(false))
  }, [page, statusFilter, t])

  React.useEffect(() => { load() }, [load])

  const statusKeys = ['draft', 'submitted', 'reviewed', 'closed']

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('quality.list_title')}</h1>
          <p className="text-sm text-gray-500 mt-1">{t('quality.total_count', { total })}</p>
        </div>
        <div className="flex items-center gap-2">
          <Link to="/quality/open-actions" className="btn-secondary text-sm">
            {t('quality.open_actions_title')}
          </Link>
          <Link to="/quality/analytics" className="btn-secondary text-sm">
            {t('quality.analytics_title')}
          </Link>
          {canCreate && (
            <Link to="/quality/new" className="btn-primary flex items-center gap-2">
              <span className="text-lg leading-none">+</span> {t('quality.new_visit')}
            </Link>
          )}
        </div>
      </div>

      {isAuditor ? (
        <ReadOnlyBanner
          title="قراءة فقط"
          description="المراجع الداخلي يراجع زيارات الجودة وإجراءاتها التصحيحية دون تنفيذ أو تعديل تشغيلي."
        />
      ) : null}

      {/* Filters */}
      <div className="card p-4 mb-4 flex gap-3 items-center flex-wrap">
        <label className="text-sm text-gray-600 font-medium">{t('quality.filter_label')}</label>
        <select
          value={statusFilter}
          onChange={e => { setStatusFilter(e.target.value); setPage(1) }}
          className="input-field w-48 text-sm"
        >
          <option value="">{t('quality.filter_all')}</option>
          {statusKeys.map(k => (
            <option key={k} value={k}>{t(`quality.status_${k}`)}</option>
          ))}
        </select>
        <button onClick={load} className="btn-secondary text-sm">{t('quality.refresh')}</button>
      </div>

      {loading ? (
        <div className="card p-12 text-center text-gray-400">{t('quality.loading')}</div>
      ) : visits.length === 0 ? (
        <div className="card p-12 text-center text-gray-400">
          <p className="text-4xl mb-3">📋</p>
          <p>{t('quality.empty_subtitle')}</p>
          {canCreate && <Link to="/quality/new" className="btn-primary mt-4 inline-block">{t('quality.create_visit')}</Link>}
        </div>
      ) : (
        <div className="card table-container">
          <table className="table">
            <thead>
              <tr>
                <th>#</th>
                <th>{t('quality.col_date')}</th>
                <th>{t('quality.col_branch')}</th>
                <th>{t('quality.col_shift')}</th>
                <th>{t('quality.col_status')}</th>
                <th>{t('quality.col_compliance')}</th>
                <th>{t('quality.col_followup')}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {visits.map(v => (
                <tr key={v.id}>
                  <td className="text-gray-400 text-xs">{v.id}</td>
                  <td className="font-medium">{v.visit_date}</td>
                  <td>{v.branch_name || v.branch_name_ar || `#${v.branch_id}`}</td>
                  <td>{v.shift || '—'}</td>
                  <td><StatusBadge status={v.status} /></td>
                  <td><ComplianceBadge pct={v.compliance_pct} /></td>
                  <td className="text-sm text-gray-500">{v.follow_up_date || '—'}</td>
                  <td>
                    <Link to={`/quality/${v.id}`} className="text-primary-600 hover:underline text-sm font-medium">
                      {t('quality.view')}
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {total > 20 && (
            <div className="flex justify-center gap-2 p-4 border-t border-gray-100">
              <button disabled={page === 1} onClick={() => setPage(p => p - 1)} className="btn-secondary text-sm px-3 py-1">{t('quality.prev')}</button>
              <span className="text-sm text-gray-500 self-center">{t('quality.page_label', { page })}</span>
              <button disabled={visits.length < 20} onClick={() => setPage(p => p + 1)} className="btn-secondary text-sm px-3 py-1">{t('quality.next')}</button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ─── Form Page (New Visit) ─────────────────────────────────────────────────────
export function QualityVisitFormPage() {
  const t = useT()
  const { lang } = useLanguage()
  const navigate = useNavigate()
  const roles = useSelector(selectUserRoles)
  const canChooseAnyBranch = roles.some((role) =>
    ['admin', 'super_admin', 'quality_manager', 'quality_visitor', 'area_manager'].includes(role)
  )
  const [checklist, setChecklist] = React.useState([])
  const [loading, setLoading] = React.useState(true)
  const [submitting, setSubmitting] = React.useState(false)
  const [branches, setBranches] = React.useState([])
  const [users, setUsers] = React.useState([])
  const [currentUser, setCurrentUser] = React.useState(null)
  const [form, setForm] = React.useState({
    branch_id: '',
    brand_key: '',
    visitor_id: '',
    visit_date: new Date().toISOString().slice(0, 10),
    shift: 'morning',
    summary_notes: '',
  })
  const [responses, setResponses] = React.useState({}) // item_id → { status, notes, corrective_action, action_owner, due_date }

  React.useEffect(() => {
    // Load checklist + branches + users in parallel; auto-fill current user as visitor
    const cu = (() => {
      try { return JSON.parse(localStorage.getItem('user') || 'null') } catch { return null }
    })()
    setCurrentUser(cu)
    Promise.all([
      masterApi.listBranches({ active_only: true, page_size: 500 }).catch(() => ({ data: { items: [] } })),
      usersApi.lookup().catch(() => ({ data: [] })),
    ])
      .then(([brRes, usrRes]) => {
        // K1: defensive — checklist may be null/undefined or missing items
        const rawBranches = Array.isArray(brRes.data) ? brRes.data : (brRes.data?.items || [])
        const brData = canChooseAnyBranch || !cu?.branch_id
          ? rawBranches
          : rawBranches.filter((b) => String(b.id) === String(cu.branch_id))
        const usrData = Array.isArray(usrRes.data) ? usrRes.data : []
        setBranches(brData)
        setUsers(usrData)
        // Auto-fill visitor_id with current user, and branch_id if user has one
        if (cu?.id) {
          const defaultBranch = cu.branch_id ? brData.find(b => String(b.id) === String(cu.branch_id)) : null
          setForm(p => ({
            ...p,
            visitor_id: String(cu.id),
            branch_id: cu.branch_id ? String(cu.branch_id) : p.branch_id,
            brand_key: defaultBranch ? inferQualityBrandKey(defaultBranch) : p.brand_key,
          }))
        }
      })
      .catch(() => toast.error(t('quality.load_checklist_error')))
      .finally(() => setLoading(false))
  }, [canChooseAnyBranch, t])

  React.useEffect(() => {
    if (!form.branch_id && !form.brand_key) {
      setChecklist([])
      setResponses({})
      return
    }
    qualityApi.getChecklist({
      branch_id: form.branch_id || undefined,
      brand_key: form.brand_key || undefined,
    })
      .then((chkRes) => {
        const checklistData = Array.isArray(chkRes.data) ? chkRes.data : []
        setChecklist(checklistData)
        const init = {}
        checklistData.forEach(sec => (sec.items || []).forEach(item => {
          const rtype = item.response_type || 'yes_no'
          init[item.id] = {
            response_type: rtype,
            status: rtype === 'yes_no' ? 'na' : null,
            numeric_value: '',
            text_value: '',
            notes: '',
            corrective_action: '',
            action_owner: '',
            due_date: '',
          }
        }))
        setResponses(init)
      })
      .catch(() => {
        setChecklist([])
        setResponses({})
        toast.error(t('quality.load_checklist_error'))
      })
  }, [form.branch_id, form.brand_key, t])

  const setResponse = (itemId, field, value) => {
    setResponses(prev => ({ ...prev, [itemId]: { ...prev[itemId], [field]: value } }))
  }

  const handleSubmit = async (andSubmit = false) => {
    if (!form.branch_id || !form.brand_key || !form.visitor_id) {
      toast.error(t('quality.required_fields'))
      return
    }
    setSubmitting(true)
    try {
      const payload = {
        ...form,
        branch_id: parseInt(form.branch_id),
        visitor_id: parseInt(form.visitor_id),
        responses: Object.entries(responses).map(([itemId, r]) => {
          const base = {
            item_id: parseInt(itemId),
            notes: r.notes || null,
            corrective_action: r.corrective_action || null,
            action_owner: r.action_owner || null,
            due_date: r.due_date || null,
          }
          if (r.response_type === 'numeric') {
            return { ...base, status: null, numeric_value: r.numeric_value === '' ? null : Number(r.numeric_value), text_value: null }
          }
          if (r.response_type === 'text') {
            return { ...base, status: null, numeric_value: null, text_value: r.text_value || null }
          }
          return { ...base, status: r.status, numeric_value: null, text_value: null }
        }),
      }
      const res = await qualityApi.create(payload)
      const visitId = res.data.id
      toast.success(t('quality.created_toast'))

      if (andSubmit) {
        await qualityApi.submit(visitId)
        toast.success(t('quality.submitted_toast'))
      }
      navigate(`/quality/${visitId}`)
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('quality.save_error'))
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <div className="p-6 text-center text-gray-400">{t('quality.loading_checklist')}</div>

  const selectedBranch = branches.find(b => String(b.id) === String(form.branch_id))
  const suggestedBrandKey = inferQualityBrandKey(selectedBranch)
  const totalItems = Object.keys(responses).length
  // Preview: يعتمد فقط على بنود yes_no المجابة (غير na)
  const ynResponses = Object.values(responses).filter(r => r.response_type === 'yes_no')
  const answered = ynResponses.filter(r => r.status !== 'na').length
  const yesCount = ynResponses.filter(r => r.status === 'yes').length
  const preview = answered > 0 ? Math.round(yesCount / answered * 100) : null

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('quality.new_visit_title')}</h1>
          <p className="text-sm text-gray-500 mt-1">{t('quality.answered_count', { answered, total: totalItems })}</p>
        </div>
        <button onClick={() => navigate('/quality')} className="btn-secondary text-sm">{t('quality.back')}</button>
      </div>

      {/* Header Info */}
      <div className="card p-5 mb-6 grid grid-cols-2 md:grid-cols-3 gap-4">
        <div>
          <label className="label">{t('quality.field_branch_id') || 'الفرع *'}</label>
          <select value={form.branch_id} onChange={e => {
            const branch = branches.find(b => String(b.id) === String(e.target.value))
            setForm(p => ({
              ...p,
              branch_id: e.target.value,
              brand_key: inferQualityBrandKey(branch) || '',
            }))
          }}
            disabled={!canChooseAnyBranch && !!currentUser?.branch_id}
            className="input-field">
            <option value="">{t('quality.placeholder_branch_id') || '— اختر الفرع —'}</option>
            {branches.map(b => (
              <option key={b.id} value={b.id}>
                {nameOf(b, 'branch_name', lang) || nameOf(b, 'name', lang) || `#${b.id}`}
              </option>
            ))}
          </select>
          {!canChooseAnyBranch && currentUser?.branch_id && (
            <p className="text-xs text-gray-500 mt-1">
              {t('quality.branch_scoped_note') || 'هذه الزيارة مربوطة بفرعك الحالي فقط.'}
            </p>
          )}
        </div>
        <div>
          <label className="label">{t('quality.field_brand') || 'البراند *'}</label>
          <select
            value={form.brand_key}
            onChange={e => setForm(p => ({ ...p, brand_key: e.target.value }))}
            className="input-field"
          >
            <option value="">{t('quality.placeholder_brand') || '— اختر البراند —'}</option>
            {QUALITY_BRANDS.map((brand) => (
              <option key={brand.key} value={brand.key}>
                {qualityBrandLabel(brand.key, lang)}
              </option>
            ))}
          </select>
          {suggestedBrandKey && form.brand_key === suggestedBrandKey && (
            <p className="text-xs text-gray-500 mt-1">
              {t('quality.brand_autodetected') || `تم التعرف تلقائيًا على ${qualityBrandLabel(suggestedBrandKey, lang)} من اسم الفرع`}
            </p>
          )}
        </div>
        <div>
          <label className="label">{t('quality.field_visitor_id') || 'المراجع *'}</label>
          <select value={form.visitor_id} onChange={e => setForm(p => ({ ...p, visitor_id: e.target.value }))}
            className="input-field">
            <option value="">{t('quality.placeholder_visitor_id') || '— اختر المراجع —'}</option>
            {users.map(u => (
              <option key={u.id} value={u.id}>
                {u.full_name || u.username || `#${u.id}`}
              </option>
            ))}
            {currentUser?.id && !users.find(u => String(u.id) === String(currentUser.id)) && (
              <option value={currentUser.id}>
                {currentUser.full_name || currentUser.username || `#${currentUser.id}`} (أنت)
              </option>
            )}
          </select>
          {currentUser?.id && String(form.visitor_id) === String(currentUser.id) && (
            <p className="text-xs text-gray-500 mt-1">
              {t('quality.visitor_autofilled') || 'تم التعبئة باسم المستخدم الحالي'}
            </p>
          )}
        </div>
        <div>
          <label className="label">{t('quality.visit_date')}</label>
          <input type="date" value={form.visit_date} onChange={e => setForm(p => ({ ...p, visit_date: e.target.value }))}
            className="input-field" />
        </div>
        <div>
          <label className="label">{t('quality.field_shift')}</label>
          <select value={form.shift} onChange={e => setForm(p => ({ ...p, shift: e.target.value }))} className="input-field">
            <option value="morning">{t('quality.shift_morning')}</option>
            <option value="evening">{t('quality.shift_evening')}</option>
            <option value="night">{t('quality.shift_night')}</option>
          </select>
        </div>
        <div className="col-span-2">
          <label className="label">{t('quality.field_summary')}</label>
          <input type="text" value={form.summary_notes} onChange={e => setForm(p => ({ ...p, summary_notes: e.target.value }))}
            className="input-field" placeholder={t('quality.placeholder_notes')} />
        </div>
      </div>

      {/* Preview Score */}
      {preview !== null && (
        <div className={`card p-4 mb-4 flex items-center gap-3 border-2 ${preview >= 80 ? 'border-green-200 bg-green-50' : preview >= 60 ? 'border-yellow-200 bg-yellow-50' : 'border-red-200 bg-red-50'}`}>
          <span className="text-3xl">{preview >= 80 ? '🟢' : preview >= 60 ? '🟡' : '🔴'}</span>
          <div>
            <p className="font-bold text-xl">{preview}%</p>
            <p className="text-sm text-gray-600">{t('quality.preview_subtitle', { yes: yesCount, answered })}</p>
          </div>
        </div>
      )}

      {/* Checklist Sections */}
      {(checklist || []).map(section => (
        <div key={section.id} className="card mb-4 overflow-hidden">
          <div className="bg-primary-50 border-b border-primary-100 px-5 py-3 flex items-center justify-between">
            <h2 className="font-semibold text-primary-800">{nameOf(section, 'name', lang)}</h2>
            <span className="text-xs text-primary-500 bg-primary-100 px-2 py-0.5 rounded-full">{t('quality.section_weight', { weight: section.weight })}</span>
          </div>
          <div className="divide-y divide-gray-50">
            {(section.items || []).map((item, idx) => {
              const resp = responses[item.id] || { status: 'na', response_type: 'yes_no' }
              const rtype = item.response_type || 'yes_no'
              const primaryText = nameOf(item, 'text', lang)
              const secondaryText = lang === 'en' ? item.text_ar : item.text_en
              const benchmark = nameOf(item, 'benchmark', lang)
              return (
                <div key={item.id} className={`px-5 py-3 ${resp.status === 'no' ? 'bg-red-50' : ''}`}>
                  <div className="flex items-start gap-4">
                    <span className="text-xs text-gray-400 mt-1 w-5 flex-shrink-0">{idx + 1}</span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-800">{primaryText}</p>
                      {secondaryText && <p className="text-xs text-gray-400 mt-0.5">{secondaryText}</p>}
                      {benchmark && (
                        <p className="text-xs text-blue-600 mt-1 bg-blue-50 inline-block px-2 py-0.5 rounded">
                          📏 {benchmark}
                        </p>
                      )}
                    </div>
                    {/* Response control — depends on response_type */}
                    <div className="flex gap-1.5 flex-shrink-0 items-center">
                      {rtype === 'yes_no' && ['yes', 'no', 'na'].map(opt => (
                        <button
                          key={opt}
                          type="button"
                          onClick={() => setResponse(item.id, 'status', opt)}
                          className={`text-xs px-2.5 py-1 rounded-full font-medium border transition-all ${
                            resp.status === opt
                              ? opt === 'yes' ? 'bg-green-500 text-white border-green-500'
                                : opt === 'no' ? 'bg-red-500 text-white border-red-500'
                                : 'bg-gray-400 text-white border-gray-400'
                              : 'bg-white text-gray-500 border-gray-200 hover:border-gray-400'
                          }`}
                        >
                          {t(`quality.resp_${opt}`)}
                        </button>
                      ))}
                      {rtype === 'numeric' && (
                        <div className="flex items-center gap-1">
                          <input
                            type="number"
                            step="any"
                            value={resp.numeric_value}
                            onChange={e => setResponse(item.id, 'numeric_value', e.target.value)}
                            className="input-field text-xs w-24 text-center"
                            placeholder={t('quality.numeric_placeholder')}
                          />
                          {item.numeric_unit && (
                            <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">{item.numeric_unit}</span>
                          )}
                        </div>
                      )}
                      {rtype === 'text' && (
                        <textarea
                          rows={2}
                          value={resp.text_value}
                          onChange={e => setResponse(item.id, 'text_value', e.target.value)}
                          className="input-field text-xs w-64"
                          placeholder={t('quality.text_placeholder')}
                        />
                      )}
                    </div>
                  </div>

                  {/* H10: optional note per item — visible for all response types */}
                  <div className="mt-2 mr-9">
                    <input
                      type="text"
                      placeholder={t('quality.item_note_placeholder') || 'ملاحظة (اختياري)'}
                      value={resp.notes || ''}
                      onChange={e => setResponse(item.id, 'notes', e.target.value)}
                      className="input-field text-xs"
                    />
                  </div>

                  {/* Corrective action — shown when Y/N = No */}
                  {rtype === 'yes_no' && resp.status === 'no' && (
                    <div className="mt-2 grid grid-cols-2 gap-2 mr-9">
                      <input
                        type="text"
                        placeholder={t('quality.corrective_placeholder')}
                        value={resp.corrective_action}
                        onChange={e => setResponse(item.id, 'corrective_action', e.target.value)}
                        className="input-field text-xs col-span-2"
                      />
                      <input
                        type="text"
                        placeholder={t('quality.owner_placeholder')}
                        value={resp.action_owner}
                        onChange={e => setResponse(item.id, 'action_owner', e.target.value)}
                        className="input-field text-xs"
                      />
                      <input
                        type="date"
                        value={resp.due_date}
                        onChange={e => setResponse(item.id, 'due_date', e.target.value)}
                        className="input-field text-xs"
                        title={t('quality.due_date_title')}
                      />
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      ))}

      {/* Actions */}
      <div className="flex justify-end gap-3 mt-6 pb-6">
        <button onClick={() => navigate('/quality')} className="btn-secondary">{t('quality.cancel')}</button>
        <button onClick={() => handleSubmit(false)} disabled={submitting} className="btn-secondary">
          {submitting ? t('quality.saving') : t('quality.save_draft')}
        </button>
        <button onClick={() => handleSubmit(true)} disabled={submitting} className="btn-primary">
          {submitting ? t('quality.submitting') : t('quality.save_and_submit')}
        </button>
      </div>
    </div>
  )
}

// ─── Detail Page ───────────────────────────────────────────────────────────────
export function QualityVisitDetailPage() {
  const t = useT()
  const { lang } = useLanguage()
  const { id } = useParams()
  const navigate = useNavigate()
  const roles = useSelector(selectUserRoles)
  const [visit, setVisit] = React.useState(null)
  const [loading, setLoading] = React.useState(true)
  const [actionLoading, setActionLoading] = React.useState(false)
  const [reviewNotes, setReviewNotes] = React.useState('')
  const [followUpDate, setFollowUpDate] = React.useState('')
  const [showReviewForm, setShowReviewForm] = React.useState(false)

  const isReviewer = roles.some(r => ['quality_manager', 'admin', 'super_admin'].includes(r))
  const isVisitor = roles.some(r => ['quality_visitor', 'quality_manager', 'admin', 'super_admin'].includes(r))
  const isBranchMgr = roles.some(r => ['branch_manager', 'area_manager', 'quality_manager', 'admin', 'super_admin'].includes(r))
  const isAuditor = roles.includes('internal_auditor')

  const load = React.useCallback(() => {
    setLoading(true)
    qualityApi.get(id)
      .then(r => setVisit(r.data))
      .catch(() => toast.error(t('quality.load_visit_error')))
      .finally(() => setLoading(false))
  }, [id, t])

  React.useEffect(() => { load() }, [load])

  const action = async (fn, msg) => {
    setActionLoading(true)
    try {
      await fn()
      toast.success(msg)
      load()
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('quality.error_generic'))
    } finally {
      setActionLoading(false)
    }
  }

  if (loading) return <div className="p-6 text-center text-gray-400">{t('quality.loading')}</div>
  if (!visit) return <div className="p-6 text-center text-red-400">{t('quality.not_found')}</div>

  const grouped = (visit.responses || []).reduce((acc, r) => {
    const secId = r.item?.section_id
    if (!acc[secId]) acc[secId] = []
    acc[secId].push(r)
    return acc
  }, {})

  const shiftDisplay = visit.shift
    ? (['morning', 'evening', 'night'].includes(visit.shift) ? t(`quality.shift_${visit.shift}`) : visit.shift)
    : '—'

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('quality.detail_title', { id: visit.id })}</h1>
          <div className="flex items-center gap-3 mt-2">
            <StatusBadge status={visit.status} />
            <ComplianceBadge pct={visit.compliance_pct} />
            <span className="text-sm text-gray-500">{visit.visit_date} — {t('quality.detail_shift_label', { shift: shiftDisplay })}</span>
          </div>
        </div>
        <div className="flex gap-2 no-print-hidden">
          <button onClick={() => window.print()} className="btn-secondary text-sm">
            {t('quality.print')}
          </button>
          <button onClick={() => navigate('/quality')} className="btn-secondary text-sm">{t('quality.back')}</button>
        </div>
      </div>

      {isAuditor ? (
        <ReadOnlyBanner
          title="قراءة فقط"
          description="هذه الزيارة معروضة للمراجعة فقط. يمكنك إضافة ملاحظة مراجعة، لكن لا يمكنك إرسال أو مراجعة أو إغلاق الزيارة."
        />
      ) : null}

      {/* Info Card */}
      <div className="card p-5 mb-4 grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
        <div><span className="text-gray-400">{t('quality.info_branch')}</span> <span className="font-medium">{visit.branch_name || visit.branch_name_ar || `#${visit.branch_id}`}</span></div>
        <div><span className="text-gray-400">{t('quality.info_visitor')}</span> <span className="font-medium">{visit.visitor_name || `#${visit.visitor_id}`}</span></div>
        <div><span className="text-gray-400">{t('quality.info_branch_in_charge')}</span> <span className="font-medium">{visit.branch_in_charge_name || visit.branch_in_charge || '—'}</span></div>
        <div><span className="text-gray-400">{t('quality.info_follow_up')}</span> <span className="font-medium">{visit.follow_up_date || '—'}</span></div>
        <div><span className="text-gray-400">{t('quality.info_reviewed_by')}</span> <span className="font-medium">{visit.reviewed_by_name || visit.reviewed_by || '—'}</span></div>
        {visit.summary_notes && (
          <div className="col-span-full p-3 bg-yellow-50 rounded border border-yellow-200 print:border-gray-300">
            <div className="text-xs font-semibold text-yellow-800 mb-1">{t('quality.info_notes')}</div>
            <div className="text-sm text-gray-800 whitespace-pre-wrap">{visit.summary_notes}</div>
          </div>
        )}
      </div>

      <InlineAuditFindingsPanel
        entityType="quality_visit"
        entityId={visit.id}
        title="ملاحظات المراجعة على الزيارة"
      />

      {/* I3 — Visit-level attachments (photos/PDFs attached to the visit itself) */}
      <VisitAttachmentsPanel
        visitId={visit.id}
        initial={visit.visit_attachments || []}
        canEdit={isVisitor && ['draft', 'submitted', 'reviewed'].includes(visit.status)}
      />

      {/* Compliance Bar */}
      {visit.compliance_pct !== null && (
        <div className="card p-4 mb-4">
          <div className="flex justify-between text-sm mb-2">
            <span className="font-medium text-gray-700">{t('quality.overall_compliance')}</span>
            <span className={`font-bold ${visit.compliance_pct >= 80 ? 'text-green-600' : visit.compliance_pct >= 60 ? 'text-yellow-600' : 'text-red-600'}`}>
              {visit.compliance_pct}%
            </span>
          </div>
          <div className="w-full bg-gray-100 rounded-full h-3">
            <div
              className={`h-3 rounded-full transition-all ${visit.compliance_pct >= 80 ? 'bg-green-500' : visit.compliance_pct >= 60 ? 'bg-yellow-500' : 'bg-red-500'}`}
              style={{ width: `${visit.compliance_pct}%` }}
            />
          </div>
        </div>
      )}

      {/* Workflow Actions */}
      <div className="card p-4 mb-4 flex flex-wrap gap-3 items-center">
        <span className="text-sm font-medium text-gray-600">{t('quality.actions_label')}</span>

        {visit.status === 'draft' && isVisitor && (
          <button onClick={() => action(() => qualityApi.submit(id), t('quality.submitted_review_toast'))}
            disabled={actionLoading} className="btn-primary text-sm">
            {t('quality.action_submit_review')}
          </button>
        )}

        {visit.status === 'submitted' && isReviewer && (
          <button onClick={() => setShowReviewForm(f => !f)} className="btn-primary text-sm">
            {t('quality.action_do_review')}
          </button>
        )}

        {visit.status === 'reviewed' && isReviewer && (
          <button onClick={() => action(() => qualityApi.close(id), t('quality.closed_toast'))}
            disabled={actionLoading} className="btn-secondary text-sm">
            {t('quality.action_close_visit')}
          </button>
        )}

        {visit.status === 'draft' && isVisitor && (
          <button onClick={async () => {
            if (!window.confirm(t('quality.confirm_delete'))) return
            await qualityApi.delete(id)
            toast.success(t('quality.deleted_toast')); navigate('/quality')
          }} className="text-red-500 hover:text-red-700 text-sm">
            {t('quality.action_delete')}
          </button>
        )}
      </div>

      {/* Signature Panel */}
      <SignaturePanel
        visit={visit}
        onSigned={load}
        canVisitorSign={isVisitor}
        canBranchSign={isBranchMgr}
      />

      {/* Review Form */}
      {showReviewForm && visit.status === 'submitted' && (
        <div className="card p-5 mb-4 border-2 border-blue-200 bg-blue-50">
          <h3 className="font-semibold text-blue-800 mb-3">{t('quality.review_form_title')}</h3>
          <div className="space-y-3">
            <div>
              <label className="label">{t('quality.review_notes_label')}</label>
              <textarea value={reviewNotes} onChange={e => setReviewNotes(e.target.value)}
                className="input-field min-h-20" placeholder={t('quality.placeholder_notes')} />
            </div>
            <div>
              <label className="label">{t('quality.review_date_label')}</label>
              <input type="date" value={followUpDate} onChange={e => setFollowUpDate(e.target.value)} className="input-field w-48" />
            </div>
            <div className="flex gap-3">
              <button onClick={() => action(
                () => qualityApi.review(id, { summary_notes: reviewNotes, follow_up_date: followUpDate || null }),
                t('quality.reviewed_toast')
              )} disabled={actionLoading} className="btn-primary text-sm">
                {t('quality.review_confirm')}
              </button>
              <button onClick={() => setShowReviewForm(false)} className="btn-secondary text-sm">{t('quality.cancel')}</button>
            </div>
          </div>
        </div>
      )}

      {/* Responses by Section */}
      <h2 className="text-lg font-bold text-gray-800 mb-3">{t('quality.results_title', { count: (visit.responses || []).length })}</h2>
      {Object.entries(grouped).map(([secId, items]) => (
        <div key={secId} className="card mb-4 overflow-hidden">
          <div className="bg-gray-50 border-b border-gray-200 px-5 py-2.5">
            <span className="font-medium text-gray-700 text-sm">
              {items[0]?.item?.text_ar ? t('quality.results_section_label') : ''} — {items.length} {t('quality.results_item_suffix')}
            </span>
          </div>
          <div className="divide-y divide-gray-50">
            {items.map(r => {
              const itemText = nameOf(r.item || {}, 'text', lang) || `${t('quality.item_missing_prefix')}${r.item_id}`
              const benchmark = r.item ? nameOf(r.item, 'benchmark', lang) : ''
              const rtype = r.item?.response_type || 'yes_no'
              return (
                <div key={r.id} className={`px-5 py-3 ${r.status === 'no' ? 'bg-red-50' : ''}`}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1">
                      <p className="text-sm text-gray-800">{itemText}</p>
                      {benchmark && (
                        <p className="text-xs text-blue-600 mt-0.5">📏 {benchmark}</p>
                      )}
                    </div>
                    {rtype === 'yes_no' && r.status && (
                      <span className={`status-badge text-xs px-2.5 py-1 rounded-full flex-shrink-0 ${RESPONSE_COLOR[r.status]}`}>
                        {t(`quality.resp_${r.status}`)}
                      </span>
                    )}
                    {rtype === 'numeric' && (
                      <span className="text-sm font-bold text-gray-700 bg-gray-100 px-2.5 py-1 rounded-full flex-shrink-0">
                        {r.numeric_value ?? '—'} {r.item?.numeric_unit || ''}
                      </span>
                    )}
                    {rtype === 'text' && r.text_value && (
                      <span className="text-xs text-gray-600 bg-gray-50 px-2.5 py-1 rounded max-w-xs">
                        {r.text_value}
                      </span>
                    )}
                  </div>
                  {r.corrective_action && (
                    <div className="mt-1.5 text-xs text-gray-600 bg-orange-50 rounded p-2">
                      <span className="font-medium">{t('quality.action_prefix')}</span> {r.corrective_action}
                      {r.action_owner && <span className="mr-3 text-gray-500">| {t('quality.owner_prefix')} {r.action_owner}</span>}
                      {r.due_date && <span className="mr-3 text-gray-500">| {t('quality.due_prefix')} {r.due_date}</span>}
                      {r.is_resolved && <span className="mr-3 text-green-600">{t('quality.resolved_prefix')}</span>}
                    </div>
                  )}
                  {r.notes && <p className="text-xs text-gray-500 mt-1">{t('quality.note_prefix')} {r.notes}</p>}
                  {/* Attachments */}
                  {(isVisitor || (r.attachments && r.attachments.length > 0)) && (
                    <AttachmentsPanel
                      responseId={r.id}
                      initial={r.attachments || []}
                      canEdit={isVisitor && ['draft', 'submitted', 'reviewed'].includes(visit.status)}
                    />
                  )}
                </div>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}


// ─── Open Corrective Actions Page ──────────────────────────────────────────────
export function QualityOpenActionsPage() {
  const t = useT()
  const { lang } = useLanguage()
  const [rows, setRows] = React.useState([])
  const [loading, setLoading] = React.useState(true)
  const [filter, setFilter] = React.useState('all') // all | overdue | due_soon
  const [owner, setOwner] = React.useState('')
  const [owners, setOwners] = React.useState([])
  const [selected, setSelected] = React.useState(new Set())
  const roles = useSelector(selectUserRoles)
  const canResolve = roles.some(r => ['quality_manager', 'branch_manager', 'area_manager', 'admin', 'super_admin'].includes(r))

  // استخدم ref لتفادي toast مكرر بسبب React 18 StrictMode + race conditions
  const lastErrorRef = React.useRef(0)
  const showLoadError = React.useCallback((err) => {
    const now = Date.now()
    if (now - lastErrorRef.current < 1000) return   // ده خلال ثانية من toast سابق — سيبه
    lastErrorRef.current = now
    const detail = err?.response?.data?.detail
    toast.error(detail || t('quality.load_open_actions_error'))
  }, [t])

  const load = React.useCallback(() => {
    setLoading(true)
    const params = {}
    if (filter === 'overdue') params.overdue_only = true
    else if (filter === 'due_soon') params.due_within_days = 7
    if (owner) params.owner = owner
    let cancelled = false
    qualityApi.listOpenActions(params)
      .then(r => {
        if (cancelled) return
        setRows(Array.isArray(r?.data) ? r.data : [])
        setSelected(new Set())
      })
      .catch(err => { if (!cancelled) { setRows([]); showLoadError(err) } })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [filter, owner, showLoadError])

  React.useEffect(() => {
    const cleanup = load()
    return cleanup
  }, [load])

  React.useEffect(() => {
    let cancelled = false
    qualityApi.listActionOwners()
      .then(r => { if (!cancelled) setOwners(Array.isArray(r?.data) ? r.data : []) })
      .catch(() => {})
    return () => { cancelled = true }
  }, [])

  const resolve = (responseId) => {
    const notes = window.prompt(t('quality.resolve_notes_prompt'))
    if (notes === null) return
    qualityApi.resolveOpenAction(responseId, notes || null)
      .then(() => { toast.success(t('quality.resolved_success')); load() })
      .catch(err => toast.error(err.response?.data?.detail || t('common.error')))
  }

  const toggleOne = (id) => {
    const next = new Set(selected)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setSelected(next)
  }
  const toggleAll = () => {
    if (selected.size === rows.length) setSelected(new Set())
    else setSelected(new Set(rows.map(r => r.id)))
  }
  const bulkResolve = async () => {
    if (selected.size === 0) return
    const notes = window.prompt(t('quality.bulk_resolve_prompt', { n: selected.size }))
    if (notes === null) return
    try {
      const r = await qualityApi.bulkResolveActions({
        response_ids: Array.from(selected),
        notes: notes || null,
      })
      toast.success(t('quality.bulk_resolve_result', {
        resolved: r.data.resolved, skipped: r.data.skipped,
      }))
      load()
    } catch (err) {
      toast.error(err.response?.data?.detail || t('common.error'))
    }
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('quality.open_actions_title')}</h1>
          <p className="text-sm text-gray-500 mt-1">{t('quality.total_count', { total: rows.length })}</p>
        </div>
        <Link to="/quality" className="btn-secondary">{t('quality.back_to_visits')}</Link>
      </div>

      <div className="flex flex-wrap items-center gap-2 mb-4">
        {['all', 'overdue', 'due_soon'].map(key => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={`px-3 py-1.5 text-sm rounded-lg ${filter === key ? 'bg-primary-600 text-white' : 'bg-white border border-gray-200 text-gray-700'}`}
          >
            {t(`quality.filter_${key}`)}
          </button>
        ))}
        <select
          value={owner}
          onChange={(e) => setOwner(e.target.value)}
          className="form-input text-sm ms-2"
        >
          <option value="">{t('quality.owner_filter_all')}</option>
          {owners.map(o => <option key={o} value={o}>{o}</option>)}
        </select>
        {canResolve && selected.size > 0 && (
          <button
            onClick={bulkResolve}
            className="ms-auto text-sm px-3 py-1.5 bg-green-600 text-white rounded-lg hover:bg-green-700"
          >
            {t('quality.bulk_resolve_btn', { n: selected.size })}
          </button>
        )}
      </div>

      {loading ? (
        <div className="text-center py-10 text-gray-400">{t('common.loading')}</div>
      ) : rows.length === 0 ? (
        <div className="text-center py-10 text-gray-400 bg-white rounded-lg border border-gray-200">
          {t('quality.no_open_actions')}
        </div>
      ) : (
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
              <tr>
                {canResolve && (
                  <th className="px-3 py-3 text-right w-8">
                    <input type="checkbox"
                      checked={selected.size > 0 && selected.size === rows.length}
                      onChange={toggleAll} />
                  </th>
                )}
                <th className="px-4 py-3 text-right">{t('quality.item_col')}</th>
                <th className="px-4 py-3 text-right">{t('quality.action_col')}</th>
                <th className="px-4 py-3 text-right">{t('quality.owner_col')}</th>
                <th className="px-4 py-3 text-right">{t('quality.due_col')}</th>
                <th className="px-4 py-3 text-right">{t('quality.visit_col')}</th>
                {canResolve && <th className="px-4 py-3 text-right"></th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {rows.filter(r => r && r.id != null).map(row => {
                // I4 — defensive rendering: every row field is treated as possibly null
                const itemText = nameOf(row.item || {}, 'text', lang) || `#${row.item_id ?? '-'}`
                const sectionName = row.item && row.item.section
                  ? nameOf(row.item.section, 'name', lang)
                  : ''
                const visitId = row.visit_id ?? '-'
                const visitDate = row.visit_date || ''
                return (
                  <tr key={row.id} className={row.is_overdue ? 'bg-red-50' : ''}>
                    {canResolve && (
                      <td className="px-3 py-3 text-center">
                        <input type="checkbox"
                          checked={selected.has(row.id)}
                          onChange={() => toggleOne(row.id)} />
                      </td>
                    )}
                    <td className="px-4 py-3">
                      <div className="font-medium text-gray-900">{itemText}</div>
                      {sectionName && (
                        <div className="text-xs text-gray-500">{sectionName}</div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-700 max-w-xs">{row.corrective_action || '—'}</td>
                    <td className="px-4 py-3 text-gray-700">{row.action_owner || '—'}</td>
                    <td className="px-4 py-3">
                      {row.due_date ? (
                        <span className={row.is_overdue ? 'text-red-600 font-semibold' : 'text-gray-700'}>
                          {row.due_date}
                          {row.is_overdue && <span className="ms-2 text-xs">⚠ {t('quality.overdue_label')}</span>}
                        </span>
                      ) : '—'}
                    </td>
                    <td className="px-4 py-3">
                      {row.visit_id ? (
                        <Link to={`/quality/${visitId}`} className="text-primary-600 hover:underline">
                          #{visitId}{visitDate ? ` · ${visitDate}` : ''}
                        </Link>
                      ) : '—'}
                    </td>
                    {canResolve && (
                      <td className="px-4 py-3">
                        <button
                          onClick={() => resolve(row.id)}
                          className="text-xs px-2.5 py-1 bg-green-600 text-white rounded hover:bg-green-700"
                        >
                          {t('quality.mark_resolved')}
                        </button>
                      </td>
                    )}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}


// ─── Compliance Analytics Page ─────────────────────────────────────────────────
export function QualityAnalyticsPage() {
  const t = useT()
  const { lang } = useLanguage()
  const [trend, setTrend] = React.useState([])
  const [sections, setSections] = React.useState([])
  const [loading, setLoading] = React.useState(true)
  const [months, setMonths] = React.useState(6)

  React.useEffect(() => {
    let cancelled = false
    setLoading(true)
    Promise.all([
      qualityApi.complianceTrend({ months }).catch(() => ({ data: [] })),
      qualityApi.sectionCompliance({ months }).catch(() => ({ data: [] })),
    ])
      .then(([trendRes, secRes]) => {
        if (cancelled) return
        setTrend(Array.isArray(trendRes?.data) ? trendRes.data : [])
        setSections(Array.isArray(secRes?.data) ? secRes.data : [])
      })
      .catch(() => { if (!cancelled) toast.error(t('common.error') || 'حدث خطأ') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [months, t])

  // aggregate: {month: {total, count}} for a simple overall trend
  const overall = React.useMemo(() => {
    const buckets = {}
    for (const p of trend) {
      if (!buckets[p.month]) buckets[p.month] = { total: 0, visits: 0 }
      buckets[p.month].total += p.avg_compliance * p.visits_count
      buckets[p.month].visits += p.visits_count
    }
    return Object.entries(buckets)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([month, { total, visits }]) => ({
        month,
        avg: visits > 0 ? Math.round((total / visits) * 10) / 10 : 0,
        visits,
      }))
  }, [trend])

  const maxVal = 100
  const barColor = (v) => (v >= 80 ? 'bg-green-500' : v >= 60 ? 'bg-yellow-500' : 'bg-red-500')

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('quality.analytics_title')}</h1>
          <p className="text-sm text-gray-500 mt-1">{t('quality.compliance_trend_subtitle')}</p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={months}
            onChange={(e) => setMonths(parseInt(e.target.value, 10))}
            className="form-input text-sm"
          >
            <option value={3}>{t('quality.months_3')}</option>
            <option value={6}>{t('quality.months_6')}</option>
            <option value={12}>{t('quality.months_12')}</option>
          </select>
          <Link to="/quality" className="btn-secondary">{t('quality.back_to_visits')}</Link>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-10 text-gray-400">{t('common.loading')}</div>
      ) : overall.length === 0 ? (
        <div className="text-center py-10 text-gray-400 bg-white rounded-lg border border-gray-200">
          {t('quality.no_trend_data')}
        </div>
      ) : (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="flex items-end gap-3 h-64 border-b border-gray-100">
            {overall.map(pt => (
              <div key={pt.month} className="flex-1 flex flex-col items-center justify-end">
                <div className="text-xs font-semibold text-gray-700 mb-1">{pt.avg}%</div>
                <div
                  className={`w-full rounded-t ${barColor(pt.avg)}`}
                  style={{ height: `${(pt.avg / maxVal) * 100}%` }}
                />
              </div>
            ))}
          </div>
          <div className="flex items-center gap-3 mt-2">
            {overall.map(pt => (
              <div key={pt.month} className="flex-1 text-center">
                <div className="text-xs text-gray-600">{pt.month}</div>
                <div className="text-xs text-gray-400">{t('quality.visits_count', { count: pt.visits })}</div>
              </div>
            ))}
          </div>

          <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
            {overall.slice(-3).reverse().map(pt => (
              <div key={pt.month} className="bg-gray-50 rounded p-4">
                <div className="text-xs text-gray-500">{pt.month}</div>
                <div className={`text-2xl font-bold ${pt.avg >= 80 ? 'text-green-600' : pt.avg >= 60 ? 'text-yellow-600' : 'text-red-600'}`}>
                  {pt.avg}%
                </div>
                <div className="text-xs text-gray-400 mt-1">{t('quality.visits_count', { count: pt.visits })}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Section-level Compliance */}
      {sections.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-6 mt-6">
          <h2 className="text-lg font-bold text-gray-800 mb-3">{t('quality.section_compliance_title')}</h2>
          <div className="space-y-2">
            {sections.map(s => (
              <div key={s.section_id} className="flex items-center gap-3">
                <div className="w-48 text-sm text-gray-700 truncate" title={nameOf(s, 'section_name', lang)}>
                  {nameOf(s, 'section_name', lang)}
                </div>
                <div className="flex-1 bg-gray-100 rounded-full h-4 relative overflow-hidden">
                  <div
                    className={`h-4 rounded-full ${barColor(s.avg_compliance)}`}
                    style={{ width: `${s.avg_compliance}%` }}
                  />
                </div>
                <div className="w-16 text-right text-sm font-semibold">{s.avg_compliance}%</div>
                <div className="w-24 text-xs text-gray-400 text-right">
                  {t('quality.section_stats', { total: s.responses_count, no: s.no_count })}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
