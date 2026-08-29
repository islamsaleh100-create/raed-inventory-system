// ShiftCashPage.jsx — كاش الشفت (شاشة مستقلة عن الجرد)
import React, { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { Save, Send, ArrowLeft, Info } from 'lucide-react'
import toast from 'react-hot-toast'
import { shiftOpsApi, previewCash, fieldErrors, CASH_VARIANCE_TOLERANCE } from '../../services/shiftOpsApi'
import { selectUserRoles } from '../../store'
import { PageLoader } from '../../components/common'
import { useT } from '../../i18n'
import ShiftManagerActions from './ShiftManagerActions'
import { shiftOpsError } from './shiftOpsError'

const SALES = ['total_sale', 'bill_count', 'mada_sales', 'cash_sales', 'app_sales']
// Informational only — never part of any formula. Kept visually separate, and the
// heading deliberately says "معلومات فقط" not "تعديلات": a cashier who reads
// "adjustments" assumes the refund reduces the cash they owe. It does not.
const INFO = ['refund_bill', 'exchange_amount', 'expiry_amount']
const DRAWER = ['cash_expense', 'cash_float_carried_forward', 'cash_deposited']
// Values MUST match app/models/branch_shift_ops.py::ShiftExpenseType (UPPERCASE).
// The column is String(30) with no enum constraint and validation only checks
// non-blank, so a lowercase value would be stored silently and split the report
// grouping into two buckets. Label keys stay lowercase to match i18n.
const EXPENSE_TYPES = ['INVOICES', 'ADVANCE', 'HANDED_TO_PERSON', 'OPERATIONAL', 'OTHER']

const EMPTY = {
  total_sale: '', bill_count: '', mada_sales: '', cash_sales: '', app_sales: '',
  refund_bill: '', exchange_amount: '', expiry_amount: '',
  cash_expense: '', cash_float_carried_forward: '', cash_deposited: '',
  expense_type: '', expense_details: '', shift_notes: '', cash_variance_reason: '',
}

const validationErrorMap = (list) => {
  const out = {}
  ;(Array.isArray(list) ? list : []).forEach((e) => {
    if (e?.field) out[e.field] = e.code || true
  })
  return out
}

// Defined at module scope on purpose. When this lived inside ShiftCashPage it was a
// NEW component type on every render, so React unmounted and remounted the <input>
// after each keystroke — the field lost focus and only the first character landed.
// Playwright's fill() sets the value in one shot, so no automated test caught it.
function Field({ name, type = 'number', value, onChange, disabled, error, t, wide = false }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs text-gray-600">{t(`shift_ops.field.${name}`)}</span>
      <input
        type={type}
        step={type === 'number' ? '0.01' : undefined}
        min={type === 'number' ? '0' : undefined}
        inputMode={type === 'number' ? 'decimal' : undefined}
        disabled={disabled}
        value={value ?? ''}
        onChange={(e) => onChange(name, e.target.value)}
        className={`border rounded-lg px-3 py-1.5 text-base tabular-nums disabled:bg-gray-100
          ${wide ? 'w-full' : 'w-full max-w-[11rem]'} ${error ? 'border-red-500' : 'border-gray-300'}`}
      />
      {error && <span className="text-xs text-red-600">{t(`shift_ops.error.${error}`)}</span>}
    </label>
  )
}

function Card({ title, icon, hint, children }) {
  return (
    <section className="bg-white border border-gray-200 rounded-xl p-4 space-y-3">
      <h2 className="text-sm font-bold flex items-center gap-1.5">{icon}{title}</h2>
      {hint && <p className="text-xs text-gray-500 leading-relaxed">{hint}</p>}
      {children}
    </section>
  )
}

export function ShiftCashPage() {
  const t = useT()
  const { shiftId } = useParams()
  const navigate = useNavigate()
  const [search] = useSearchParams()
  const roles = useSelector(selectUserRoles) || []
  const canWrite = roles.includes('branch_manager')

  const [shift, setShift] = useState(null)
  const [cash, setCash] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [errors, setErrors] = useState({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const s = await shiftOpsApi.getShift(shiftId)
      setShift(s.data)
      // 404 here means no cash draft yet — normal on first open, not an error.
      // Without this, branch managers see a red error toast every day on first open.
      let cashData = null
      try {
        const c = await shiftOpsApi.getCash(shiftId)
        cashData = c.data
      } catch (err) {
        if (err?.response?.status !== 404) throw err
      }
      setCash(cashData)
      const next = { ...EMPTY }
      Object.keys(EMPTY).forEach((k) => {
        if (cashData?.[k] !== null && cashData?.[k] !== undefined) next[k] = cashData[k]
      })
      setForm(next)
    } catch (err) {
      toast.error(shiftOpsError(err, t, 'common.load_failed'))
    } finally {
      setLoading(false)
    }
  }, [shiftId, t])

  useEffect(() => { load() }, [load])

  const locked = cash?.status === 'submitted' || shift?.status === 'exception_locked'
  const set = useCallback((k, v) => setForm((p) => ({ ...p, [k]: v })), [])

  const p = previewCash(form)
  const expenseNum = Number(form.cash_expense || 0)
  const expenseNeedsDetails = expenseNum > 0
  const expenseOk = !expenseNeedsDetails || (form.expense_type && String(form.expense_details).trim())

  // Derived, never sent. A wrong digit in total_sale shows up here as an absurd
  // average long before it reaches the review report.
  const bills = Number(form.bill_count || 0)
  const totalSale = Number(form.total_sale || 0)
  const avgBill = bills > 0 && totalSale > 0 ? totalSale / bills : null

  const payload = () => {
    const out = {}
    Object.entries(form).forEach(([k, v]) => {
      if (v === '' || v === null) return
      out[k] = ['expense_type', 'expense_details', 'shift_notes', 'cash_variance_reason'].includes(k)
        ? v
        : Number(v)
    })
    return out
  }

  const save = async () => {
    setSaving(true); setErrors({})
    try {
      const r = await shiftOpsApi.saveCash(shiftId, payload())
      setCash(r.data)
      const validationErrors = validationErrorMap(r.data?.validation_errors)
      setErrors(validationErrors)
      if (Object.keys(validationErrors).length === 0) toast.success(t('common.saved'))
    } catch (err) {
      setErrors(fieldErrors(err))
      toast.error(shiftOpsError(err, t, 'common.save_failed'))
    } finally { setSaving(false) }
  }

  const submit = async () => {
    setSaving(true); setErrors({})
    try {
      await shiftOpsApi.saveCash(shiftId, payload())
      await shiftOpsApi.submitCash(shiftId)
      toast.success(t('shift_ops.cash_submitted'))
      load()
    } catch (err) {
      setErrors(fieldErrors(err))
      toast.error(shiftOpsError(err, t, 'common.save_failed'))
    } finally { setSaving(false) }
  }

  if (loading) return <PageLoader />

  const readyToSubmit = p.payOk && p.expected !== null && !p.negativeExpected && expenseOk &&
    (!p.reasonRequired || String(form.cash_variance_reason).trim().length > 0)

  const status = cash?.status || 'draft'
  const fld = (name, opts = {}) => (
    <Field key={name} name={name} value={form[name]} onChange={set}
           disabled={locked || !canWrite} error={errors[name]} t={t} {...opts} />
  )

  return (
    <div className="p-4 pb-24 max-w-5xl mx-auto space-y-3">
      <button type="button" onClick={() => navigate('/shift-ops')}
              className="inline-flex items-center gap-1 text-sm text-gray-600">
        <ArrowLeft size={15} /> {t('common.back')}
      </button>

      {/* ── header ── */}
      <div className="bg-white border border-gray-200 rounded-xl px-4 py-3 flex items-center justify-between gap-3">
        <div>
          <div className="font-bold text-sm">
            {shift?.shift_date} · {t('shift_ops.shift_n', { n: shift?.shift_number })}
          </div>
          <div className="text-xs text-gray-500">{t('shift_ops.cash')}</div>
        </div>
        <span className={`text-xs font-semibold rounded-full px-3 py-1 ${
          status === 'submitted' ? 'bg-green-100 text-green-800' : 'bg-amber-100 text-amber-800'}`}>
          {t(`shift_ops.section_status.${status}`)}
        </span>
      </div>

      <ShiftManagerActions
        shiftId={shiftId} roles={roles} shift={shift}
        openReopen={search.get('manage') === '1'}
        openCloseNoActivity={search.get('closeNoActivity') === '1'}
        onDone={load}
      />

      {locked && (
        <p className="text-xs bg-gray-100 border rounded-lg p-2 text-gray-600">
          {t('shift_ops.locked_readonly')}
        </p>
      )}

      {/* Two columns on laptop, one on phone. The single-column stack wasted the
          horizontal half of a laptop screen and doubled the page height. */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 items-start">

        <Card title={t('shift_ops.group_sales')}>
          <div className="grid grid-cols-2 gap-x-4 gap-y-3">
            {SALES.map((f) => fld(f))}
          </div>
          {avgBill !== null && (
            <div className="flex items-center justify-between text-xs border-t pt-2">
              <span className="text-gray-500">{t('shift_ops.avg_bill')}</span>
              <span className="font-semibold tabular-nums">{avgBill.toFixed(2)}</span>
            </div>
          )}
          {p.payDiff !== null && (
            <p className={`text-xs rounded-lg px-3 py-2 ${p.payOk ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
              {p.payOk ? t('shift_ops.payment_match') : t('shift_ops.payment_mismatch', { diff: p.payDiff.toFixed(2) })}
            </p>
          )}
        </Card>

        <Card
          title={t('shift_ops.group_informational')}
          icon={<Info size={14} />}
          hint={t('shift_ops.informational_hint')}
        >
          <div className="grid grid-cols-2 gap-x-4 gap-y-3">
            {INFO.map((f) => fld(f))}
          </div>
        </Card>

        <Card title={t('shift_ops.group_drawer')}>
          <div className="grid grid-cols-2 gap-x-4 gap-y-3">
            {DRAWER.map((f) => fld(f))}
          </div>

          {expenseNeedsDetails && (
            <div className="grid grid-cols-1 gap-3 border-t pt-3">
              <label className="flex flex-col gap-1">
                <span className="text-xs text-gray-600">{t('shift_ops.field.expense_type')}</span>
                <select disabled={locked || !canWrite} value={form.expense_type}
                        onChange={(e) => set('expense_type', e.target.value)}
                        className={`border rounded-lg px-3 py-1.5 text-base w-full max-w-[14rem] disabled:bg-gray-100
                          ${errors.expense_type ? 'border-red-500' : 'border-gray-300'}`}>
                  <option value="">—</option>
                  {EXPENSE_TYPES.map((v) => (
                    <option key={v} value={v}>{t(`shift_ops.expense_type.${v.toLowerCase()}`)}</option>
                  ))}
                </select>
              </label>
              {fld('expense_details', { type: 'text', wide: true })}
            </div>
          )}

          {/* The rule in words, in front of the person it holds accountable — and it
              visibly has no refund term. */}
          <p className="text-xs text-gray-500 bg-gray-50 border rounded-lg px-3 py-2 leading-relaxed">
            {t('shift_ops.expected_formula')}
          </p>

          <div className="flex items-center justify-between border-t pt-2">
            <span className="text-xs text-gray-600">{t('shift_ops.expected_deposited')}</span>
            <span className="text-lg font-bold tabular-nums">
              {p.expected === null ? '—' : p.expected.toFixed(2)}
            </span>
          </div>

          {p.variance !== null && (
            <div className={`rounded-lg px-3 py-2 flex items-center justify-between ${
              p.reasonRequired ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'}`}>
              <span className="text-xs font-semibold">
                {t('shift_ops.variance')}
                {p.reasonRequired && ` — ${t('shift_ops.variance_over_tolerance', { tol: CASH_VARIANCE_TOLERANCE })}`}
              </span>
              <span className="text-lg font-bold tabular-nums">{p.variance.toFixed(2)}</span>
            </div>
          )}

          {p.negativeExpected && (
            <p className="text-xs bg-red-100 text-red-800 rounded-lg px-3 py-2">
              {t('shift_ops.negative_expected')}
            </p>
          )}

          {p.reasonRequired && fld('cash_variance_reason', { type: 'text', wide: true })}
        </Card>

        <Card title={t('shift_ops.group_notes')}>
          {fld('shift_notes', { type: 'text', wide: true })}
        </Card>
      </div>

      {!locked && canWrite && (
        <div className="fixed bottom-0 inset-x-0 bg-white border-t px-4 py-3 flex items-center justify-between gap-3">
          <span className="text-xs text-gray-600">
            {readyToSubmit ? t('shift_ops.cash_ready') : t('shift_ops.cash_incomplete')}
          </span>
          <div className="flex gap-2">
            <button type="button" onClick={save} disabled={saving}
                    className="inline-flex items-center gap-1 border rounded-lg px-3 py-2 text-sm">
              <Save size={15} /> {t('common.save')}
            </button>
            <button type="button" onClick={submit} disabled={saving || !readyToSubmit}
                    className="inline-flex items-center gap-1 bg-primary-600 text-white rounded-lg px-4 py-2 text-sm font-semibold disabled:bg-gray-300">
              <Send size={15} /> {t('shift_ops.submit_cash')}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default ShiftCashPage
