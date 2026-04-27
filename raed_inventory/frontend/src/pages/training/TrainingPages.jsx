/**
 * Training Assessment Pages
 * - TrainingAssessmentListPage  → /training
 * - TrainingAssessmentFormPage  → /training/new
 * - TrainingAssessmentDetailPage → /training/:id
 */
import React from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useSelector } from 'react-redux'
import toast from 'react-hot-toast'
import { trainingApi, usersApi, masterApi } from '../../services/api'
import { selectUserRoles } from '../../store'
import { useT, useLanguage } from '../../i18n'
import { ReadOnlyBanner } from '../../components/common'
import InlineAuditFindingsPanel from '../../components/audit/InlineAuditFindingsPanel'

// ─── Helpers ──────────────────────────────────────────────────────────────────
const STATUS_KEYS = ['draft', 'submitted', 'approved', 'certified', 'needs_reeval']
const STATUS_COLOR = {
  draft: 'bg-gray-100 text-gray-600',
  submitted: 'bg-blue-100 text-blue-700',
  approved: 'bg-indigo-100 text-indigo-700',
  certified: 'bg-green-100 text-green-700',
  needs_reeval: 'bg-red-100 text-red-700',
}
const VERDICT_KEYS = ['passed', 'conditional', 'failed']
const VERDICT_COLOR = {
  passed: 'text-green-600',
  conditional: 'text-yellow-600',
  failed: 'text-red-600',
}
const ROLE_KEYS = ['branch_employee', 'branch_manager']

const nameOf = (obj, base, lang) => obj?.[`${base}_${lang}`] || obj?.[`${base}_ar`] || obj?.[base] || ''

function StatusBadge({ status }) {
  const t = useT()
  return (
    <span className={`status-badge text-xs font-medium px-2.5 py-1 rounded-full ${STATUS_COLOR[status] || 'bg-gray-100'}`}>
      {t(`training.status_${status}`)}
    </span>
  )
}

function ScoreBar({ score }) {
  if (score === null || score === undefined) return null
  const color = score >= 80 ? 'bg-green-500' : score >= 60 ? 'bg-yellow-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-gray-100 rounded-full h-2">
        <div className={`h-2 rounded-full ${color}`} style={{ width: `${score}%` }} />
      </div>
      <span className={`text-sm font-bold ${score >= 80 ? 'text-green-600' : score >= 60 ? 'text-yellow-600' : 'text-red-600'}`}>
        {score}%
      </span>
    </div>
  )
}

// ─── Signature Panel ──────────────────────────────────────────────────────────
function AssessmentSignatures({ assessment, canEvaluator, canApprover, onSigned }) {
  const t = useT()
  const [evalSig, setEvalSig] = React.useState('')
  const [apprSig, setApprSig] = React.useState('')
  const [busy, setBusy] = React.useState(false)
  const allowedStatus = ['submitted', 'approved', 'certified', 'needs_reeval']
  if (!allowedStatus.includes(assessment.status)) return null

  const sign = async (role, value) => {
    if (!value || value.trim().length < 2) {
      toast.error(t('training.sign_too_short'))
      return
    }
    setBusy(true)
    try {
      await trainingApi.sign(assessment.id, { role, signature: value.trim() })
      toast.success(t('training.signed_toast'))
      onSigned()
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('training.error_generic'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card p-4 mb-4 border-2 border-indigo-100 bg-indigo-50/40 no-print-hidden">
      <h3 className="font-semibold text-indigo-800 mb-3 text-sm">{t('training.signatures_title')}</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="label">{t('training.sig_evaluator')}</label>
          {assessment.evaluator_signature ? (
            <div className="text-sm bg-white rounded border border-indigo-200 px-3 py-2">
              <span className="font-medium">{assessment.evaluator_signature}</span>
              <span className="text-xs text-gray-500 mr-2"> — {assessment.evaluator_signed_at?.slice(0, 10)}</span>
            </div>
          ) : canEvaluator ? (
            <div className="flex gap-2">
              <input value={evalSig} onChange={e => setEvalSig(e.target.value)}
                className="input-field flex-1" placeholder={t('training.sig_placeholder_name')} />
              <button onClick={() => sign('evaluator', evalSig)} disabled={busy} className="btn-primary text-xs">
                {t('training.sig_sign')}
              </button>
            </div>
          ) : (
            <span className="text-sm text-gray-400">{t('training.sig_pending')}</span>
          )}
        </div>
        <div>
          <label className="label">{t('training.sig_approver')}</label>
          {assessment.approver_signature ? (
            <div className="text-sm bg-white rounded border border-indigo-200 px-3 py-2">
              <span className="font-medium">{assessment.approver_signature}</span>
              <span className="text-xs text-gray-500 mr-2"> — {assessment.approver_signed_at?.slice(0, 10)}</span>
            </div>
          ) : canApprover ? (
            <div className="flex gap-2">
              <input value={apprSig} onChange={e => setApprSig(e.target.value)}
                className="input-field flex-1" placeholder={t('training.sig_placeholder_name')} />
              <button onClick={() => sign('approver', apprSig)} disabled={busy} className="btn-primary text-xs">
                {t('training.sig_sign')}
              </button>
            </div>
          ) : (
            <span className="text-sm text-gray-400">{t('training.sig_pending')}</span>
          )}
        </div>
      </div>
    </div>
  )
}


// ─── List Page ─────────────────────────────────────────────────────────────────
export function TrainingAssessmentListPage() {
  const t = useT()
  const [assessments, setAssessments] = React.useState([])
  const [total, setTotal] = React.useState(0)
  const [loading, setLoading] = React.useState(true)
  const [page, setPage] = React.useState(1)
  const [statusFilter, setStatusFilter] = React.useState('')
  const [roleFilter, setRoleFilter] = React.useState('')
  const roles = useSelector(selectUserRoles)
  const canCreate = roles.some(r => ['area_manager', 'admin', 'super_admin'].includes(r))
  const isAuditor = roles.includes('internal_auditor')

  const load = React.useCallback(() => {
    setLoading(true)
    const params = { page, page_size: 20 }
    if (statusFilter) params.status = statusFilter
    if (roleFilter) params.role_type = roleFilter
    trainingApi.list(params)
      .then(r => {
        // K1: defensive — backend might return null, array, or {items, total}
        const data = r?.data
        if (Array.isArray(data)) {
          setAssessments(data); setTotal(data.length)
        } else {
          setAssessments(data?.items || [])
          setTotal(data?.total || 0)
        }
      })
      .catch(() => toast.error(t('training.load_error')))
      .finally(() => setLoading(false))
  }, [page, statusFilter, roleFilter, t])

  React.useEffect(() => { load() }, [load])

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('training.main_title')}</h1>
          <p className="text-sm text-gray-500 mt-1">{t('training.total_count', { total })}</p>
        </div>
        <div className="flex items-center gap-2">
          <Link to="/training/analytics" className="btn-secondary text-sm">
            {t('training.analytics_title')}
          </Link>
          {canCreate && (
            <Link to="/training/new" className="btn-primary flex items-center gap-2">
              <span className="text-lg leading-none">+</span> {t('training.new_assessment')}
            </Link>
          )}
        </div>
      </div>

      {isAuditor ? (
        <ReadOnlyBanner
          title="قراءة فقط"
          description="المراجع الداخلي يطّلع على التقييمات التدريبية وخطط التطوير دون اعتماد أو رفض أو إنشاء تقييمات جديدة."
        />
      ) : null}

      {/* Filters */}
      <div className="card p-4 mb-4 flex gap-3 items-center flex-wrap">
        <select value={statusFilter} onChange={e => { setStatusFilter(e.target.value); setPage(1) }}
          className="input-field w-44 text-sm">
          <option value="">{t('training.filter_all_status')}</option>
          {STATUS_KEYS.map(k => <option key={k} value={k}>{t(`training.status_${k}`)}</option>)}
        </select>
        <select value={roleFilter} onChange={e => { setRoleFilter(e.target.value); setPage(1) }}
          className="input-field w-40 text-sm">
          <option value="">{t('training.filter_all_roles')}</option>
          {ROLE_KEYS.map(k => <option key={k} value={k}>{t(`training.role_${k}`)}</option>)}
        </select>
        <button onClick={load} className="btn-secondary text-sm">{t('training.refresh')}</button>
      </div>

      {loading ? (
        <div className="card p-12 text-center text-gray-400">{t('training.loading')}</div>
      ) : assessments.length === 0 ? (
        <div className="card p-12 text-center text-gray-400">
          <p className="text-4xl mb-3">🎓</p>
          <p>{t('training.empty_subtitle')}</p>
          {canCreate && <Link to="/training/new" className="btn-primary mt-4 inline-block">{t('training.create_assessment')}</Link>}
        </div>
      ) : (
        <div className="card table-container">
          <table className="table">
            <thead>
              <tr>
                <th>#</th>
                <th>{t('training.col_trainee')}</th>
                <th>{t('training.col_trainer')}</th>
                <th>{t('training.col_branch')}</th>
                <th>{t('training.col_date')}</th>
                <th>{t('training.col_status')}</th>
                <th>{t('training.col_score')}</th>
                <th>{t('training.col_verdict')}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {assessments.map(a => (
                <tr key={a.id}>
                  <td className="text-gray-400 text-xs">{a.id}</td>
                  <td className="font-medium">
                    {/* H12: show name + employee no + role type */}
                    <div>{a.trainee_name || `#${a.trainee_id}`}</div>
                    <div className="text-xs text-gray-400 font-normal">
                      {a.trainee_employee_no && (
                        <span className="font-mono">{a.trainee_employee_no}</span>
                      )}
                      {a.role_type && (
                        <span className="ml-2">
                          · {t(`training.role_${a.role_type}`) || a.role_type}
                        </span>
                      )}
                    </div>
                  </td>
                  <td>{a.trainer_name || `#${a.trainer_id}`}</td>
                  <td>{a.branch_name || `#${a.branch_id}`}</td>
                  <td>{a.assessment_date}</td>
                  <td><StatusBadge status={a.status} /></td>
                  <td>
                    {a.overall_score !== null && a.overall_score !== undefined
                      ? <span className={`font-bold ${a.overall_score >= 80 ? 'text-green-600' : a.overall_score >= 60 ? 'text-yellow-600' : 'text-red-600'}`}>{a.overall_score}%</span>
                      : <span className="text-gray-400">—</span>}
                  </td>
                  <td>
                    {a.verdict
                      ? <span className={`text-sm font-medium ${VERDICT_COLOR[a.verdict]}`}>{t(`training.verdict_${a.verdict}`)}</span>
                      : <span className="text-gray-400">—</span>}
                  </td>
                  <td>
                    <Link to={`/training/${a.id}`} className="text-primary-600 hover:underline text-sm font-medium">{t('training.view')}</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {total > 20 && (
            <div className="flex justify-center gap-2 p-4 border-t border-gray-100">
              <button disabled={page === 1} onClick={() => setPage(p => p - 1)} className="btn-secondary text-sm px-3 py-1">{t('training.prev')}</button>
              <span className="text-sm text-gray-500 self-center">{t('training.page_label', { page })}</span>
              <button disabled={assessments.length < 20} onClick={() => setPage(p => p + 1)} className="btn-secondary text-sm px-3 py-1">{t('training.next')}</button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ─── Form Page (New Assessment) ────────────────────────────────────────────────
export function TrainingAssessmentFormPage() {
  const t = useT()
  const { lang } = useLanguage()
  const navigate = useNavigate()
  const [templates, setTemplates] = React.useState([])
  const [selectedTemplate, setSelectedTemplate] = React.useState(null)
  const [scores, setScores] = React.useState({}) // item_id → { score, notes }
  const [loading, setLoading] = React.useState(true)
  const [submitting, setSubmitting] = React.useState(false)
  // H12: lookup lists for employee/trainer/branch selection
  const [users, setUsers] = React.useState([])
  const [branches, setBranches] = React.useState([])
  const [form, setForm] = React.useState({
    template_id: '',
    trainee_id: '',
    trainer_id: '',
    branch_id: '',
    assessment_date: new Date().toISOString().slice(0, 10),
  })

  React.useEffect(() => {
    Promise.all([
      trainingApi.listTemplates(),
      usersApi.lookup().catch(() => ({ data: [] })),
      masterApi.listBranches({ active_only: true, page_size: 500 }).catch(() => ({ data: { items: [] } })),
    ])
      .then(([tplRes, usersRes, branchesRes]) => {
        setTemplates(tplRes.data || [])
        const uList = Array.isArray(usersRes.data) ? usersRes.data : []
        setUsers(uList)
        const bList = Array.isArray(branchesRes.data) ? branchesRes.data : (branchesRes.data?.items || [])
        setBranches(bList)
      })
      .catch(() => toast.error(t('training.load_templates_error')))
      .finally(() => setLoading(false))
  }, [])

  // H12: look up a user by ID for role/name display
  const userById = React.useCallback((id) => {
    if (!id) return null
    const n = parseInt(id)
    return users.find(u => u.id === n) || null
  }, [users])

  const roleOf = (user) => {
    if (!user) return ''
    const roles = user.roles || user.role_names || (user.user_roles?.map(ur => ur.role?.name) || [])
    if (!roles.length) return ''
    return roles.map(r => t(`roles.${r}`) || r).join(', ')
  }

  const selectTemplate = async (templateId) => {
    if (!templateId) { setSelectedTemplate(null); setScores({}); return }
    setLoading(true)
    try {
      const r = await trainingApi.getTemplate(parseInt(templateId))
      setSelectedTemplate(r.data)
      const init = {}
      // K1: null-safe guards — API may return template with null sections/items
      (r.data.sections || []).forEach(sec => (sec.items || []).forEach(item => {
        init[item.id] = { score: 3, notes: '' }
      }))
      setScores(init)
      setForm(p => ({ ...p, template_id: parseInt(templateId) }))
    } catch { toast.error(t('training.load_template_error')) }
    finally { setLoading(false) }
  }

  const setScore = (itemId, field, value) => {
    setScores(prev => ({ ...prev, [itemId]: { ...prev[itemId], [field]: value } }))
  }

  const overallPreview = React.useMemo(() => {
    const items = Object.values(scores)
    if (!items.length) return null
    const total = items.reduce((s, i) => s + parseInt(i.score || 3), 0)
    const max = items.length * 5
    return Math.round(total / max * 100)
  }, [scores])

  const handleSubmit = async (andSubmit = false) => {
    if (!form.template_id || !form.trainee_id || !form.trainer_id || !form.branch_id) {
      toast.error(t('training.required_fields'))
      return
    }
    setSubmitting(true)
    try {
      const payload = {
        ...form,
        trainee_id: parseInt(form.trainee_id),
        trainer_id: parseInt(form.trainer_id),
        branch_id: parseInt(form.branch_id),
        items: Object.entries(scores).map(([itemId, s]) => ({
          item_id: parseInt(itemId),
          score: parseInt(s.score),
          notes: s.notes || null,
        })),
      }
      const res = await trainingApi.create(payload)
      const aId = res.data.id
      toast.success(t('training.created_toast'))
      if (andSubmit) {
        await trainingApi.submit(aId)
        toast.success(t('training.submitted_toast'))
      }
      navigate(`/training/${aId}`)
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('training.save_error'))
    } finally {
      setSubmitting(false)
    }
  }

  const scoreColor = (s) => {
    const n = parseInt(s)
    if (n >= 5) return 'bg-green-500'
    if (n >= 4) return 'bg-green-400'
    if (n >= 3) return 'bg-yellow-400'
    if (n >= 2) return 'bg-orange-400'
    return 'bg-red-500'
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{t('training.new_title')}</h1>
        <button onClick={() => navigate('/training')} className="btn-secondary text-sm">{t('training.back')}</button>
      </div>

      {/* Header */}
      <div className="card p-5 mb-6 grid grid-cols-2 md:grid-cols-3 gap-4">
        <div className="col-span-full md:col-span-1">
          <label className="label">{t('training.field_template')}</label>
          <select value={form.template_id} onChange={e => selectTemplate(e.target.value)} className="input-field">
            <option value="">{t('training.template_placeholder')}</option>
            {templates.map(tpl => (
              <option key={tpl.id} value={tpl.id}>
                {nameOf(tpl, 'name', lang)} ({t(`training.role_${tpl.role_type}`) || tpl.role_type})
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label">{t('training.field_trainee_id')}</label>
          <select
            value={form.trainee_id}
            onChange={e => setForm(p => ({ ...p, trainee_id: e.target.value }))}
            className="input-field"
          >
            <option value="">{t('training.placeholder_trainee')}</option>
            {users.map(u => (
              <option key={u.id} value={u.id}>
                {u.full_name || u.username} — #{u.id}
              </option>
            ))}
          </select>
          {/* H12: show employee ID + role once a trainee is picked */}
          {form.trainee_id && userById(form.trainee_id) && (
            <div className="text-xs text-gray-500 mt-1">
              <span className="inline-block ml-2">
                {t('training.info_employee_id') || 'الرقم الوظيفي'}:{' '}
                <span className="font-mono">{userById(form.trainee_id).username || userById(form.trainee_id).id}</span>
              </span>
              {roleOf(userById(form.trainee_id)) && (
                <span className="inline-block ml-2">
                  {t('training.info_employee_type') || 'النوع'}:{' '}
                  <span className="font-medium">{roleOf(userById(form.trainee_id))}</span>
                </span>
              )}
            </div>
          )}
        </div>
        <div>
          <label className="label">{t('training.field_trainer_id')}</label>
          <select
            value={form.trainer_id}
            onChange={e => setForm(p => ({ ...p, trainer_id: e.target.value }))}
            className="input-field"
          >
            <option value="">{t('training.placeholder_trainer')}</option>
            {users.map(u => (
              <option key={u.id} value={u.id}>
                {u.full_name || u.username} — #{u.id}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label">{t('training.field_branch_id')}</label>
          <select
            value={form.branch_id}
            onChange={e => setForm(p => ({ ...p, branch_id: e.target.value }))}
            className="input-field"
          >
            <option value="">{t('training.placeholder_branch')}</option>
            {branches.map(b => (
              <option key={b.id} value={b.id}>
                {b.branch_name || b.name} {b.branch_code ? `(${b.branch_code})` : ''}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label">{t('training.assessment_date')}</label>
          <input type="date" value={form.assessment_date} onChange={e => setForm(p => ({ ...p, assessment_date: e.target.value }))}
            className="input-field" />
        </div>
      </div>

      {/* Score Preview */}
      {overallPreview !== null && (
        <div className={`card p-4 mb-4 border-2 ${overallPreview >= 80 ? 'border-green-200 bg-green-50' : overallPreview >= 60 ? 'border-yellow-200 bg-yellow-50' : 'border-red-200 bg-red-50'}`}>
          <div className="flex items-center gap-4">
            <span className="text-3xl">{overallPreview >= 80 ? '🟢' : overallPreview >= 60 ? '🟡' : '🔴'}</span>
            <div className="flex-1">
              <p className="font-bold text-xl">{overallPreview}%</p>
              <p className="text-sm text-gray-600">
                {t('training.score_preview_label')}{' '}
                {overallPreview >= 80 ? t('training.verdict_passed_short')
                  : overallPreview >= 60 ? t('training.verdict_conditional_short')
                  : t('training.verdict_needs_reeval_short')}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Assessment Items */}
      {selectedTemplate && (
        <>
          {/* J1: clear empty-template guard — shown when the template has no items yet */}
          {(!selectedTemplate.sections || selectedTemplate.sections.length === 0 ||
            selectedTemplate.sections.every(s => !s.items || s.items.length === 0)) && (
            <div className="card p-8 text-center text-amber-700 bg-amber-50 border border-amber-200 mb-4">
              <p className="text-3xl mb-2">⚠️</p>
              <p className="font-semibold">
                {t('training.template_empty_title') || 'القالب لا يحتوي على بنود تقييم بعد'}
              </p>
              <p className="text-sm text-amber-600 mt-1">
                {t('training.template_empty_hint') || 'يُرجى تشغيل seed القوالب (alembic upgrade head) أو إعادة تشغيل الخادم'}
              </p>
            </div>
          )}
          {(selectedTemplate.sections || []).map(section => (
            <div key={section.id} className="card mb-4 overflow-hidden">
              <div className="bg-indigo-50 border-b border-indigo-100 px-5 py-3 flex justify-between items-center">
                <h2 className="font-semibold text-indigo-800">{nameOf(section, 'name', lang)}</h2>
                <span className="text-xs bg-indigo-100 text-indigo-600 px-2 py-0.5 rounded-full">{t('training.section_weight', { weight: section.weight })}</span>
              </div>
              <div className="divide-y divide-gray-50">
                {(section.items || []).map((item, idx) => {
                  const s = scores[item.id] || { score: 3, notes: '' }
                  const primaryText = nameOf(item, 'text', lang)
                  const benchmark = nameOf(item, 'benchmark', lang)
                  return (
                    <div key={item.id} className="px-5 py-4">
                      <div className="flex items-start gap-3 mb-2">
                        <span className="text-xs text-gray-400 mt-1 w-5 flex-shrink-0">{idx + 1}</span>
                        <div className="flex-1">
                          <p className="text-sm font-medium text-gray-800">{primaryText}</p>
                          {benchmark && (
                            <p className="text-xs text-gray-500 mt-0.5 bg-gray-50 px-2 py-1 rounded">
                              {t('training.benchmark_prefix')} {benchmark}
                            </p>
                          )}
                        </div>
                      </div>
                      {/* Score Buttons 1-5 */}
                      <div className="flex items-center gap-2 mr-8">
                        <span className="text-xs text-gray-500 w-20">{t('training.score_label')}</span>
                        <div className="flex gap-1.5">
                          {[1, 2, 3, 4, 5].map(n => (
                            <button
                              key={n}
                              onClick={() => setScore(item.id, 'score', n)}
                              className={`w-9 h-9 rounded-full text-sm font-bold border-2 transition-all ${
                                parseInt(s.score) === n
                                  ? `${scoreColor(n)} text-white border-transparent`
                                  : 'bg-white text-gray-400 border-gray-200 hover:border-gray-400'
                              }`}
                            >
                              {n}
                            </button>
                          ))}
                        </div>
                        <span className="text-xs text-gray-400 mr-2">
                          {t(`training.score_${parseInt(s.score)}`)}
                        </span>
                        <input
                          type="text"
                          placeholder={t('training.note_placeholder')}
                          value={s.notes}
                          onChange={e => setScore(item.id, 'notes', e.target.value)}
                          className="input-field text-xs flex-1"
                        />
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
        </>
      )}

      {!selectedTemplate && form.template_id === '' && (
        <div className="card p-12 text-center text-gray-400">
          <p className="text-4xl mb-3">📋</p>
          <p>{t('training.select_template_first')}</p>
        </div>
      )}

      {/* Actions */}
      {selectedTemplate && (
        <div className="flex justify-end gap-3 mt-6 pb-6">
          <button onClick={() => navigate('/training')} className="btn-secondary">{t('training.cancel')}</button>
          <button onClick={() => handleSubmit(false)} disabled={submitting} className="btn-secondary">
            {submitting ? t('training.saving') : t('training.save_draft')}
          </button>
          <button onClick={() => handleSubmit(true)} disabled={submitting} className="btn-primary">
            {submitting ? t('training.submitting') : t('training.save_and_submit')}
          </button>
        </div>
      )}
    </div>
  )
}

// ─── Detail Page ───────────────────────────────────────────────────────────────
export function TrainingAssessmentDetailPage() {
  const t = useT()
  const { lang } = useLanguage()
  const { id } = useParams()
  const navigate = useNavigate()
  const roles = useSelector(selectUserRoles)
  const [assessment, setAssessment] = React.useState(null)
  const [loading, setLoading] = React.useState(true)
  const [actionLoading, setActionLoading] = React.useState(false)
  const [showApproveForm, setShowApproveForm] = React.useState(false)
  const [showRejectForm, setShowRejectForm] = React.useState(false)
  const [verdict, setVerdict] = React.useState('')  // '' = auto-derive from score
  const [reEvalDate, setReEvalDate] = React.useState('')
  const [rejectReason, setRejectReason] = React.useState('')
  const [devPlan, setDevPlan] = React.useState({ strengths: '', areas_for_improvement: '', required_actions: '', re_evaluation_date: '' })

  const isApprover = roles.some(r => ['quality_manager', 'operations_manager', 'admin', 'super_admin'].includes(r))
  const isEvaluator = roles.some(r => ['area_manager', 'admin', 'super_admin'].includes(r))
  const isAuditor = roles.includes('internal_auditor')

  const load = React.useCallback(() => {
    setLoading(true)
    trainingApi.get(id)
      .then(r => {
        setAssessment(r.data)
        if (r.data.dev_plan) {
          setDevPlan({
            strengths: r.data.dev_plan.strengths || '',
            areas_for_improvement: r.data.dev_plan.areas_for_improvement || '',
            required_actions: r.data.dev_plan.required_actions || '',
            re_evaluation_date: r.data.dev_plan.re_evaluation_date || '',
          })
        }
      })
      .catch(() => toast.error(t('training.load_assessment_error')))
      .finally(() => setLoading(false))
  }, [id, t])

  React.useEffect(() => { load() }, [load])

  const action = async (fn, msg) => {
    setActionLoading(true)
    try {
      await fn()
      toast.success(msg)
      load()
      setShowApproveForm(false)
      setShowRejectForm(false)
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('training.error_generic'))
    } finally {
      setActionLoading(false)
    }
  }

  if (loading) return <div className="p-6 text-center text-gray-400">{t('training.loading')}</div>
  if (!assessment) return <div className="p-6 text-center text-red-400">{t('training.not_found')}</div>

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('training.detail_title', { id: assessment.id })}</h1>
          <div className="flex items-center gap-3 mt-2">
            <StatusBadge status={assessment.status} />
            {assessment.verdict && (
              <span className={`text-sm font-bold ${VERDICT_COLOR[assessment.verdict]}`}>
                {t(`training.verdict_${assessment.verdict}`)}
              </span>
            )}
            <span className="text-sm text-gray-500">{assessment.assessment_date}</span>
          </div>
        </div>
        <div className="flex gap-2 no-print-hidden">
          <button onClick={() => window.print()} className="btn-secondary text-sm">
            {t('training.print')}
          </button>
          <button onClick={() => navigate('/training')} className="btn-secondary text-sm">{t('training.back')}</button>
        </div>
      </div>

      {isAuditor ? (
        <ReadOnlyBanner
          title="قراءة فقط"
          description="هذا التقييم معروض للمراجعة فقط. يمكنك توثيق ملاحظات مراجعة دون إرسال أو اعتماد أو رفض التقييم."
        />
      ) : null}

      {/* Info — H12: show names, employee no, role type */}
      <div className="card p-5 mb-4 grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
        <div>
          <span className="text-gray-400">{t('training.info_trainee')}</span>{' '}
          <span className="font-medium">{assessment.trainee_name || `#${assessment.trainee_id}`}</span>
          {assessment.trainee_employee_no && (
            <span className="text-xs text-gray-400 ml-2 font-mono">({assessment.trainee_employee_no})</span>
          )}
        </div>
        <div>
          <span className="text-gray-400">{t('training.info_trainer')}</span>{' '}
          <span className="font-medium">{assessment.trainer_name || `#${assessment.trainer_id}`}</span>
        </div>
        <div>
          <span className="text-gray-400">{t('training.info_branch')}</span>{' '}
          <span className="font-medium">{assessment.branch_name || `#${assessment.branch_id}`}</span>
        </div>
        {assessment.role_type && (
          <div>
            <span className="text-gray-400">{t('training.info_employee_type') || t('training.role_type_label') || 'النوع'}:</span>{' '}
            <span className="font-medium">{t(`training.role_${assessment.role_type}`) || assessment.role_type}</span>
          </div>
        )}
        {assessment.template && (
          <div><span className="text-gray-400">{t('training.info_template')}</span> <span className="font-medium">{nameOf(assessment.template, 'name', lang)}</span></div>
        )}
        {assessment.re_eval_date && (
          <div><span className="text-gray-400">{t('training.info_re_eval')}</span> <span className="font-medium text-orange-600">{assessment.re_eval_date}</span></div>
        )}
        {assessment.approved_by && (
          <div>
            <span className="text-gray-400">{t('training.info_approved_by')}</span>{' '}
            <span className="font-medium">{assessment.approver_name || `#${assessment.approved_by}`}</span>
          </div>
        )}
      </div>

      <InlineAuditFindingsPanel
        entityType="training_assessment"
        entityId={assessment.id}
        title="ملاحظات المراجعة على التقييم"
      />

      {/* Rejection reason — displayed when approver sent back to draft */}
      {assessment.status === 'draft' && assessment.rejection_reason && (
        <div className="card p-4 mb-4 border-2 border-red-300 bg-red-50">
          <p className="text-xs font-semibold text-red-700 mb-1">⚠ {t('training.rejection_reason_label')}</p>
          <p className="text-sm text-red-800 whitespace-pre-wrap">{assessment.rejection_reason}</p>
        </div>
      )}

      {/* Score */}
      {assessment.overall_score !== null && (
        <div className="card p-4 mb-4">
          <p className="text-sm font-medium text-gray-700 mb-2">{t('training.overall_score_label')}</p>
          <ScoreBar score={assessment.overall_score} />
        </div>
      )}

      {/* Workflow Actions */}
      <div className="card p-4 mb-4 flex flex-wrap gap-3 items-center">
        <span className="text-sm font-medium text-gray-600">{t('training.actions_label')}</span>

        {assessment.status === 'draft' && isEvaluator && (
          <button onClick={() => action(() => trainingApi.submit(id), t('training.submitted_for_approval_toast'))}
            disabled={actionLoading} className="btn-primary text-sm">{t('training.action_submit')}</button>
        )}

        {assessment.status === 'submitted' && isApprover && (
          <>
            <button onClick={() => { setShowApproveForm(f => !f); setShowRejectForm(false) }}
              className="btn-primary text-sm">{t('training.action_approve')}</button>
            <button onClick={() => { setShowRejectForm(f => !f); setShowApproveForm(false) }}
              className="btn-secondary text-sm text-red-600">{t('training.action_reject')}</button>
          </>
        )}
      </div>

      {/* Approve Form */}
      {showApproveForm && (
        <div className="card p-5 mb-4 border-2 border-green-200 bg-green-50">
          <h3 className="font-semibold text-green-800 mb-3">{t('training.approve_title')}</h3>
          <div className="space-y-3">
            <div>
              <label className="label">{t('training.approve_verdict_label')}</label>
              <div className="flex gap-3 flex-wrap">
                <button onClick={() => setVerdict('')}
                  className={`px-4 py-2 rounded-lg text-sm font-medium border-2 transition-all ${verdict === ''
                    ? 'border-indigo-500 bg-indigo-500 text-white'
                    : 'border-gray-200 bg-white text-gray-600 hover:border-gray-400'}`}>
                  ✨ {t('training.verdict_auto')}
                </button>
                {VERDICT_KEYS.map(k => (
                  <button key={k} onClick={() => setVerdict(k)}
                    className={`px-4 py-2 rounded-lg text-sm font-medium border-2 transition-all ${verdict === k
                      ? k === 'passed' ? 'border-green-500 bg-green-500 text-white'
                        : k === 'conditional' ? 'border-yellow-500 bg-yellow-400 text-white'
                        : 'border-red-500 bg-red-500 text-white'
                      : 'border-gray-200 bg-white text-gray-600 hover:border-gray-400'}`}>
                    {t(`training.verdict_${k}`)}
                  </button>
                ))}
              </div>
              <p className="text-xs text-gray-500 mt-1">{t('training.verdict_auto_hint')}</p>
            </div>
            {(verdict === 'conditional' || verdict === 'failed') && (
              <div>
                <label className="label">{t('training.approve_re_eval_date')}</label>
                <input type="date" value={reEvalDate} onChange={e => setReEvalDate(e.target.value)} className="input-field w-48" />
              </div>
            )}
            <div className="border-t pt-3">
              <p className="text-sm font-medium text-gray-700 mb-2">{t('training.dev_plan_optional')}</p>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="label text-xs">{t('training.strengths')}</label>
                  <textarea value={devPlan.strengths} onChange={e => setDevPlan(p => ({ ...p, strengths: e.target.value }))}
                    className="input-field text-xs min-h-16" placeholder={t('training.strengths_placeholder')} />
                </div>
                <div>
                  <label className="label text-xs">{t('training.areas_for_improvement')}</label>
                  <textarea value={devPlan.areas_for_improvement} onChange={e => setDevPlan(p => ({ ...p, areas_for_improvement: e.target.value }))}
                    className="input-field text-xs min-h-16" placeholder={t('training.areas_placeholder')} />
                </div>
                <div className="col-span-2">
                  <label className="label text-xs">{t('training.required_actions')}</label>
                  <textarea value={devPlan.required_actions} onChange={e => setDevPlan(p => ({ ...p, required_actions: e.target.value }))}
                    className="input-field text-xs min-h-16" placeholder={t('training.actions_placeholder')} />
                </div>
              </div>
            </div>
            <div className="flex gap-3">
              <button onClick={() => action(() => trainingApi.approve(id, {
                verdict: verdict || null,   // null → backend يشتق من الدرجة
                re_eval_date: reEvalDate || null,
                dev_plan: (devPlan.strengths || devPlan.areas_for_improvement || devPlan.required_actions)
                  ? { ...devPlan, re_evaluation_date: reEvalDate || null }
                  : null,
              }), t('training.approved_toast'))} disabled={actionLoading} className="btn-primary text-sm">
                {t('training.approve_confirm')}
              </button>
              <button onClick={() => setShowApproveForm(false)} className="btn-secondary text-sm">{t('training.cancel')}</button>
            </div>
          </div>
        </div>
      )}

      {/* Reject Form */}
      {showRejectForm && (
        <div className="card p-5 mb-4 border-2 border-red-200 bg-red-50">
          <h3 className="font-semibold text-red-700 mb-3">{t('training.reject_title')}</h3>
          <div>
            <label className="label">{t('training.reject_reason_label')}</label>
            <textarea value={rejectReason} onChange={e => setRejectReason(e.target.value)}
              className="input-field min-h-20" placeholder={t('training.reject_placeholder')} />
          </div>
          <div className="flex gap-3 mt-3">
            <button onClick={() => action(() => trainingApi.reject(id, rejectReason), t('training.rejected_toast'))}
              disabled={actionLoading || !rejectReason} className="btn-primary text-sm bg-red-500 hover:bg-red-600">
              {t('training.reject_confirm')}
            </button>
            <button onClick={() => setShowRejectForm(false)} className="btn-secondary text-sm">{t('training.cancel')}</button>
          </div>
        </div>
      )}

      {/* Signatures */}
      <AssessmentSignatures
        assessment={assessment}
        canEvaluator={isEvaluator}
        canApprover={isApprover}
        onSigned={load}
      />

      {/* Dev Plan */}
      {assessment.dev_plan && (
        <div className="card p-5 mb-4">
          <h3 className="font-semibold text-gray-800 mb-3">{t('training.dev_plan_title')}</h3>
          <div className="grid grid-cols-2 gap-3 text-sm">
            {assessment.dev_plan.strengths && (
              <div><span className="text-gray-400 text-xs block">{t('training.strengths')}</span>{assessment.dev_plan.strengths}</div>
            )}
            {assessment.dev_plan.areas_for_improvement && (
              <div><span className="text-gray-400 text-xs block">{t('training.areas_for_improvement')}</span>{assessment.dev_plan.areas_for_improvement}</div>
            )}
            {assessment.dev_plan.required_actions && (
              <div className="col-span-2"><span className="text-gray-400 text-xs block">{t('training.required_actions')}</span>{assessment.dev_plan.required_actions}</div>
            )}
            {assessment.dev_plan.re_evaluation_date && (
              <div><span className="text-gray-400 text-xs block">{t('training.re_evaluation_date')}</span>
                <span className="text-orange-600 font-medium">{assessment.dev_plan.re_evaluation_date}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Items */}
      {(assessment.template?.sections || []).map(section => {
        const sectionItems = (assessment.items || []).filter(i => i.item?.section_id === section.id)
        if (!sectionItems.length) return null
        const avg = Math.round(sectionItems.reduce((s, i) => s + i.score, 0) / sectionItems.length * 20)
        return (
          <div key={section.id} className="card mb-4 overflow-hidden">
            <div className="bg-indigo-50 border-b border-indigo-100 px-5 py-2.5 flex justify-between items-center">
              <h3 className="font-medium text-indigo-800 text-sm">{nameOf(section, 'name', lang)}</h3>
              <span className={`text-xs font-bold ${avg >= 80 ? 'text-green-600' : avg >= 60 ? 'text-yellow-600' : 'text-red-600'}`}>{avg}%</span>
            </div>
            <div className="divide-y divide-gray-50">
              {sectionItems.map(ai => {
                const itemText = nameOf(ai.item || {}, 'text', lang) || `${t('training.item_missing_prefix')}${ai.item_id}`
                const itemBenchmark = nameOf(ai.item || {}, 'benchmark', lang)
                return (
                  <div key={ai.id} className="px-5 py-3 flex items-start gap-3">
                    <div className="flex-1">
                      <p className="text-sm text-gray-800">{itemText}</p>
                      {itemBenchmark && (
                        <p className="text-xs text-gray-400 mt-0.5">{itemBenchmark}</p>
                      )}
                      {ai.notes && <p className="text-xs text-gray-500 mt-1">{t('training.note_prefix')} {ai.notes}</p>}
                    </div>
                    <div className="flex-shrink-0 flex items-center gap-1">
                      {[1, 2, 3, 4, 5].map(n => (
                        <div key={n} className={`w-6 h-6 rounded-full text-xs flex items-center justify-center font-bold
                          ${n === ai.score
                            ? n >= 4 ? 'bg-green-500 text-white' : n === 3 ? 'bg-yellow-400 text-white' : 'bg-red-500 text-white'
                            : 'bg-gray-100 text-gray-300'}`}>
                          {n}
                        </div>
                      ))}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )
      })}
    </div>
  )
}


// ─── Verdict Distribution Analytics ─────────────────────────────────────────────
export function TrainingAnalyticsPage() {
  const t = useT()
  const [rows, setRows] = React.useState([])
  const [loading, setLoading] = React.useState(true)
  const [months, setMonths] = React.useState(6)

  React.useEffect(() => {
    setLoading(true)
    trainingApi.verdictDistribution({ months })
      .then(r => setRows(r.data || []))
      .catch(() => toast.error(t('common.error')))
      .finally(() => setLoading(false))
  }, [months, t])

  // aggregate by month -> {passed, conditional, failed}
  const grouped = React.useMemo(() => {
    const buckets = {}
    for (const p of rows) {
      if (!buckets[p.month]) buckets[p.month] = { passed: 0, conditional: 0, failed: 0 }
      if (buckets[p.month][p.verdict] !== undefined) {
        buckets[p.month][p.verdict] += p.count
      }
    }
    return Object.entries(buckets)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([month, counts]) => ({ month, ...counts, total: counts.passed + counts.conditional + counts.failed }))
  }, [rows])

  const totals = React.useMemo(() => {
    const agg = { passed: 0, conditional: 0, failed: 0, total: 0 }
    for (const g of grouped) {
      agg.passed += g.passed
      agg.conditional += g.conditional
      agg.failed += g.failed
      agg.total += g.total
    }
    return agg
  }, [grouped])

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('training.analytics_title')}</h1>
          <p className="text-sm text-gray-500 mt-1">{t('training.verdict_distribution_subtitle')}</p>
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
          <Link to="/training" className="btn-secondary">{t('training.back_to_assessments')}</Link>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-10 text-gray-400">{t('common.loading')}</div>
      ) : grouped.length === 0 ? (
        <div className="text-center py-10 text-gray-400 bg-white rounded-lg border border-gray-200">
          {t('training.no_verdict_data')}
        </div>
      ) : (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-4 gap-4 mb-6">
            <div className="bg-white rounded-lg border border-gray-200 p-4">
              <div className="text-xs text-gray-500">{t('training.total_assessments')}</div>
              <div className="text-2xl font-bold text-gray-900">{totals.total}</div>
            </div>
            <div className="bg-white rounded-lg border border-gray-200 p-4">
              <div className="text-xs text-gray-500">{t('training.verdict_passed')}</div>
              <div className="text-2xl font-bold text-green-600">{totals.passed}</div>
              <div className="text-xs text-gray-400">{totals.total ? Math.round((totals.passed / totals.total) * 100) : 0}%</div>
            </div>
            <div className="bg-white rounded-lg border border-gray-200 p-4">
              <div className="text-xs text-gray-500">{t('training.verdict_conditional')}</div>
              <div className="text-2xl font-bold text-yellow-600">{totals.conditional}</div>
              <div className="text-xs text-gray-400">{totals.total ? Math.round((totals.conditional / totals.total) * 100) : 0}%</div>
            </div>
            <div className="bg-white rounded-lg border border-gray-200 p-4">
              <div className="text-xs text-gray-500">{t('training.verdict_failed')}</div>
              <div className="text-2xl font-bold text-red-600">{totals.failed}</div>
              <div className="text-xs text-gray-400">{totals.total ? Math.round((totals.failed / totals.total) * 100) : 0}%</div>
            </div>
          </div>

          {/* Stacked monthly bars */}
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <div className="flex items-end gap-3 h-64 border-b border-gray-100">
              {grouped.map(g => {
                const maxTotal = Math.max(...grouped.map(x => x.total), 1)
                const h = (g.total / maxTotal) * 100
                const pSeg = g.total ? (g.passed / g.total) * 100 : 0
                const cSeg = g.total ? (g.conditional / g.total) * 100 : 0
                const fSeg = g.total ? (g.failed / g.total) * 100 : 0
                return (
                  <div key={g.month} className="flex-1 flex flex-col items-center justify-end">
                    <div className="text-xs text-gray-500 mb-1">{g.total}</div>
                    <div className="w-full rounded-t overflow-hidden flex flex-col-reverse" style={{ height: `${h}%` }}>
                      {pSeg > 0 && <div className="bg-green-500" style={{ height: `${pSeg}%` }} title={`${t('training.verdict_passed')} ${g.passed}`} />}
                      {cSeg > 0 && <div className="bg-yellow-500" style={{ height: `${cSeg}%` }} title={`${t('training.verdict_conditional')} ${g.conditional}`} />}
                      {fSeg > 0 && <div className="bg-red-500" style={{ height: `${fSeg}%` }} title={`${t('training.verdict_failed')} ${g.failed}`} />}
                    </div>
                  </div>
                )
              })}
            </div>
            <div className="flex items-center gap-3 mt-2">
              {grouped.map(g => (
                <div key={g.month} className="flex-1 text-center text-xs text-gray-600">{g.month}</div>
              ))}
            </div>
            <div className="flex items-center gap-4 mt-4 text-xs text-gray-600">
              <span className="inline-flex items-center gap-1"><span className="w-3 h-3 bg-green-500 rounded-sm"></span> {t('training.verdict_passed')}</span>
              <span className="inline-flex items-center gap-1"><span className="w-3 h-3 bg-yellow-500 rounded-sm"></span> {t('training.verdict_conditional')}</span>
              <span className="inline-flex items-center gap-1"><span className="w-3 h-3 bg-red-500 rounded-sm"></span> {t('training.verdict_failed')}</span>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
