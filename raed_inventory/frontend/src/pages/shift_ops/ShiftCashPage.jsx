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

const SALES = ['total_sale', 'bill_count', 'mada_sales', 'cash_sales', 'app_sales']
// Informational only — never part of any formula. Kept visually separate so the
// screen does not imply the system reconciles them.
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

export function ShiftCashPage() {
  const t = useT()
  const { shiftId } = useParams()
  const navigate = useNavigate()
  const [search] = useSearchParams()
  const roles = useSelector(selectUserRoles) || []

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
      const c = await shiftOpsApi.getCash(shiftId)
      setCash(c.data)
      const next = { ...EMPTY }
      Object.keys(EMPTY).forEach((k) => {
        if (c.data?.[k] !== null && c.data?.[k] !== undefined) next[k] = c.data[k]
      })
      setForm(next)
    } catch (err) {
      toast.error(err?.response?.data?.message || t('common.load_failed'))
    } finally {
      setLoading(false)
    }
  }, [shiftId, t])

  useEffect(() => { load() }, [load])

  const locked = cash?.status === 'submitted' || shift?.status === 'exception_locked'
  const set = (k, v) => setForm((p) => ({ ...p, [k]: v }))

  const p = previewCash(form)
  const expenseNum = Number(form.cash_expense || 0)
  const expenseNeedsDetails = expenseNum > 0
  const expenseOk = !expenseNeedsDetails || (form.expense_type && String(form.expense_details).trim())

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
      toast.success(t('common.saved'))
    } catch (err) {
      setErrors(fieldErrors(err))
      toast.error(err?.response?.data?.message || t('common.save_failed'))
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
      toast.error(err?.response?.data?.message || t('common.save_failed'))
    } finally { setSaving(false) }
  }

  const Field = ({ name, type = 'number' }) => (
    <label className="flex flex-col gap-1">
      <span className="text-[11px] text-gray-500">{t(`shift_ops.field.${name}`)}</span>
      <input
        type={type}
        step={type === 'number' ? '0.01' : undefined}
        min={type === 'number' ? '0' : undefined}
        inputMode={type === 'number' ? 'decimal' : undefined}
        disabled={locked}
        value={form[name] ?? ''}
        onChange={(e) => set(name, e.target.value)}
        className={`border rounded-lg px-3 py-2 disabled:bg-gray-100 ${errors[name] ? 'border-red-500' : ''}`}
      />
      {errors[name] && (
        <span className="text-[11px] text-red-600">{t(`shift_ops.error.${errors[name]}`)}</span>
      )}
    </label>
  )

  if (loading) return <PageLoader />

  const readyToSubmit = p.payOk && p.expected !== null && !p.negativeExpected && expenseOk &&
    (!p.reasonRequired || String(form.cash_variance_reason).trim().length > 0)

  return (
    <div className="p-4 pb-28 space-y-3">
      <button type="button" onClick={() => navigate('/shift-ops')}
              className="inline-flex items-center gap-1 text-sm text-gray-600">
        <ArrowLeft size={15} /> {t('common.back')}
      </button>

      <div className="bg-white border rounded-xl p-3">
        <div className="font-bold text-sm">
          {shift?.shift_date} · {t('shift_ops.shift_n', { n: shift?.shift_number })}
        </div>
        <div className="text-xs text-gray-500">
          {t('shift_ops.cash')} — {t(`shift_ops.section_status.${cash?.status || 'draft'}`)}
        </div>
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

      {/* ── sales ── */}
      <section className="bg-white border rounded-xl p-3 space-y-2">
        <h2 className="text-sm font-bold">{t('shift_ops.group_sales')}</h2>
        <div className="grid grid-cols-2 gap-2">
          {SALES.map((f) => <Field key={f} name={f} type={f === 'bill_count' ? 'number' : 'number'} />)}
        </div>
        {p.payDiff !== null && (
          <p className={`text-xs rounded-lg px-3 py-2 ${p.payOk ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
            {p.payOk ? t('shift_ops.payment_match') : t('shift_ops.payment_mismatch', { diff: p.payDiff.toFixed(2) })}
          </p>
        )}
      </section>

      {/* ── informational only ── */}
      <section className="bg-white border rounded-xl p-3 space-y-2">
        <h2 className="text-sm font-bold flex items-center gap-1">
          <Info size={14} /> {t('shift_ops.group_informational')}
        </h2>
        <p className="text-[11px] text-gray-500">{t('shift_ops.informational_hint')}</p>
        <div className="grid grid-cols-2 gap-2 opacity-90">
          {INFO.map((f) => <Field key={f} name={f} />)}
        </div>
      </section>

      {/* ── drawer reconciliation ── */}
      <section className="bg-white border rounded-xl p-3 space-y-2">
        <h2 className="text-sm font-bold">{t('shift_ops.group_drawer')}</h2>
        <div className="grid grid-cols-2 gap-2">
          {DRAWER.map((f) => <Field key={f} name={f} />)}
        </div>

        {expenseNeedsDetails && (
          <div className="grid grid-cols-1 gap-2">
            <label className="flex flex-col gap-1">
              <span className="text-[11px] text-gray-500">{t('shift_ops.field.expense_type')}</span>
              <select disabled={locked} value={form.expense_type}
                      onChange={(e) => set('expense_type', e.target.value)}
                      className={`border rounded-lg px-3 py-2 disabled:bg-gray-100 ${errors.expense_type ? 'border-red-500' : ''}`}>
                <option value="">—</option>
                {EXPENSE_TYPES.map((v) => (
                  <option key={v} value={v}>{t(`shift_ops.expense_type.${v.toLowerCase()}`)}</option>
                ))}
              </select>
            </label>
            <Field name="expense_details" type="text" />
          </div>
        )}

        <div className="flex items-center justify-between text-sm border-t pt-2">
          <span className="text-[11px] text-gray-500">{t('shift_ops.expected_deposited')}</span>
          <span className="font-bold">{p.expected === null ? '—' : p.expected.toFixed(2)}</span>
        </div>

        {p.variance !== null && (
          <div className={`rounded-lg px-3 py-2 text-sm font-bold ${
            p.reasonRequired ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'}`}>
            {t('shift_ops.variance')}: {p.variance.toFixed(2)}
            {p.reasonRequired && ` — ${t('shift_ops.variance_over_tolerance', { tol: CASH_VARIANCE_TOLERANCE })}`}
          </div>
        )}

        {p.negativeExpected && (
          <p className="text-xs bg-red-100 text-red-800 rounded-lg px-3 py-2">
            {t('shift_ops.negative_expected')}
          </p>
        )}

        {p.reasonRequired && <Field name="cash_variance_reason" type="text" />}
      </section>

      {!locked && (
        <div className="fixed bottom-0 inset-x-0 bg-white border-t p-3 flex items-center justify-between gap-3">
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
