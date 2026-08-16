// ShiftCountPage.jsx — جرد الشفت
// Mobile-first: every item is a vertical card, never a 4-column table. A branch
// user closes the shift from a phone; a wide table is an error factory.
import React, { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { Save, Send, AlertTriangle, ArrowLeft } from 'lucide-react'
import toast from 'react-hot-toast'
import { shiftOpsApi } from '../../services/shiftOpsApi'
import { selectUserRoles } from '../../store'
import { PageLoader } from '../../components/common'
import { useT } from '../../i18n'
import ShiftManagerActions from './ShiftManagerActions'

const EDITABLE = ['received_qty', 'returned_qty', 'damaged_qty', 'closing_balance']

const toNum = (v) => {
  if (v === '' || v === null || v === undefined) return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

export function ShiftCountPage() {
  const t = useT()
  const { shiftId } = useParams()
  const navigate = useNavigate()
  const [search] = useSearchParams()
  const roles = useSelector(selectUserRoles) || []

  const [shift, setShift] = useState(null)
  const [count, setCount] = useState(null)
  const [lines, setLines] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const s = await shiftOpsApi.getShift(shiftId)
      setShift(s.data)
      // Idempotent by contract — safe on every open, including refresh.
      const c = await shiftOpsApi.createOrGetCount(shiftId)
      setCount(c.data)
      setLines(c.data.lines || [])
    } catch (err) {
      toast.error(err?.response?.data?.message || t('common.load_failed'))
    } finally {
      setLoading(false)
    }
  }, [shiftId, t])

  useEffect(() => { load() }, [load])

  const locked = count?.status === 'submitted' || shift?.status === 'exception_locked'

  const setField = (itemId, field, value) => {
    setLines((prev) =>
      prev.map((ln) => (ln.item_id === itemId ? { ...ln, [field]: value } : ln)),
    )
  }

  // Display-only preview; the server recomputes and is authoritative.
  const movementOf = (ln) => {
    const opening = toNum(ln.opening_balance) ?? 0
    const vals = EDITABLE.map((f) => toNum(ln[f]))
    if (vals.some((v) => v === null)) return null
    const [received, returned, damaged, closing] = vals
    return Math.round((opening + received - returned - damaged - closing) * 100) / 100
  }

  const rowComplete = (ln) => EDITABLE.every((f) => toNum(ln[f]) !== null)
  const rowNeedsReason = (ln) => {
    const m = movementOf(ln)
    return m !== null && m < 0 && !String(ln.movement_exception_reason || '').trim()
  }

  const completed = lines.filter(rowComplete).length
  const blockedByReason = lines.some(rowNeedsReason)
  const readyToSubmit = completed === lines.length && lines.length > 0 && !blockedByReason

  const buildPayload = () =>
    lines.map((ln) => {
      const item = { item_id: ln.item_id }
      EDITABLE.forEach((f) => {
        const v = toNum(ln[f])
        if (v !== null) item[f] = v
      })
      if (ln.movement_exception_reason) item.movement_exception_reason = ln.movement_exception_reason
      if (ln.item_notes) item.item_notes = ln.item_notes
      return item
      // opening_balance is intentionally never sent — the server owns it.
    })

  const save = async () => {
    setSaving(true)
    try {
      const r = await shiftOpsApi.patchCountLines(shiftId, buildPayload())
      setCount(r.data)
      setLines(r.data.lines || [])
      toast.success(t('common.saved'))
    } catch (err) {
      toast.error(err?.response?.data?.message || t('common.save_failed'))
    } finally {
      setSaving(false)
    }
  }

  const submit = async () => {
    setSaving(true)
    try {
      await shiftOpsApi.patchCountLines(shiftId, buildPayload())
      await shiftOpsApi.submitCount(shiftId)
      toast.success(t('shift_ops.count_submitted'))
      load()
    } catch (err) {
      toast.error(err?.response?.data?.message || t('common.save_failed'))
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <PageLoader />

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
          {t('shift_ops.count')} — {t(`shift_ops.section_status.${count?.status || 'draft'}`)}
        </div>
      </div>

      <ShiftManagerActions
        shiftId={shiftId}
        roles={roles}
        shift={shift}
        openReopen={search.get('manage') === '1'}
        openCloseNoActivity={search.get('closeNoActivity') === '1'}
        onDone={load}
      />

      {locked && (
        <p className="text-xs bg-gray-100 border rounded-lg p-2 text-gray-600">
          {t('shift_ops.locked_readonly')}
        </p>
      )}

      {lines.map((ln) => {
        const movement = movementOf(ln)
        const negative = movement !== null && movement < 0
        const needsReason = rowNeedsReason(ln)
        return (
          <div
            key={ln.item_id}
            className={`bg-white border rounded-xl p-3 space-y-2 ${
              negative ? 'border-amber-400 bg-amber-50' : rowComplete(ln) ? 'border-green-300' : ''
            }`}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="font-semibold text-sm">
                {ln.item_name_snapshot}
                <span className="text-xs text-gray-400 font-normal"> · {ln.unit_snapshot}</span>
              </div>
              <span className="text-xs bg-gray-100 px-2 py-0.5 rounded whitespace-nowrap">
                {t('shift_ops.opening')}: {ln.opening_balance}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2">
              {EDITABLE.map((f) => (
                <label key={f} className="flex flex-col gap-1">
                  <span className="text-[11px] text-gray-500">{t(`shift_ops.field.${f}`)}</span>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    inputMode="decimal"
                    disabled={locked}
                    value={ln[f] ?? ''}
                    onChange={(e) => setField(ln.item_id, f, e.target.value)}
                    className="border rounded-lg px-2 py-2 text-center disabled:bg-gray-100"
                  />
                </label>
              ))}
            </div>

            <div className="flex items-center justify-between gap-2 text-sm">
              <span className="text-[11px] text-gray-500">{t('shift_ops.field.movement_diff')}</span>
              <span className={`font-bold ${negative ? 'text-amber-800' : 'text-gray-800'}`}>
                {movement === null ? '—' : movement.toFixed(2)}
              </span>
            </div>

            {/* Negative movement is allowed — it just requires a reason. */}
            {negative && (
              <div className="space-y-1">
                <p className="text-[11px] text-amber-800 flex items-center gap-1">
                  <AlertTriangle size={12} /> {t('shift_ops.negative_movement_hint')}
                </p>
                <input
                  type="text"
                  disabled={locked}
                  value={ln.movement_exception_reason || ''}
                  onChange={(e) => setField(ln.item_id, 'movement_exception_reason', e.target.value)}
                  placeholder={t('shift_ops.movement_reason_placeholder')}
                  className={`w-full border rounded-lg px-2 py-2 text-sm disabled:bg-gray-100 ${
                    needsReason ? 'border-red-400' : ''
                  }`}
                />
              </div>
            )}
          </div>
        )
      })}

      {!locked && (
        <div className="fixed bottom-0 inset-x-0 bg-white border-t p-3 flex items-center justify-between gap-3">
          <div className="text-xs text-gray-600">
            {t('shift_ops.completed_of', { done: completed, total: lines.length })}
            {blockedByReason && (
              <span className="block text-red-600 font-semibold">
                {t('shift_ops.reason_missing')}
              </span>
            )}
          </div>
          <div className="flex gap-2">
            <button type="button" onClick={save} disabled={saving}
                    className="inline-flex items-center gap-1 border rounded-lg px-3 py-2 text-sm">
              <Save size={15} /> {t('common.save')}
            </button>
            <button type="button" onClick={submit} disabled={saving || !readyToSubmit}
                    className="inline-flex items-center gap-1 bg-primary-600 text-white rounded-lg px-4 py-2 text-sm font-semibold disabled:bg-gray-300">
              <Send size={15} /> {t('shift_ops.submit_count')}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default ShiftCountPage
