// ShiftCountPage.jsx — جرد الشفت (شاشة كاشير)
import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { Save, Send, AlertTriangle, ArrowLeft, Undo2 } from 'lucide-react'
import toast from 'react-hot-toast'
import { shiftOpsApi } from '../../services/shiftOpsApi'
import { selectUserRoles } from '../../store'
import { PageLoader } from '../../components/common'
import { useT, useLanguage } from '../../i18n'
import ShiftManagerActions from './ShiftManagerActions'
import { shiftOpsError } from './shiftOpsError'
import { useNavigationBlocker } from './useNavigationBlocker'
import { processQtyInput, formatQtyOnBlur } from './shiftQtyInput'

const EDITABLE = ['received_qty', 'returned_qty', 'damaged_qty', 'closing_balance']
const QTY_FIELDS = ['received_qty', 'returned_qty', 'damaged_qty']
const QUICK_FILTERS = ['all', 'incomplete', 'negative', 'notes']

const toNum = (v) => {
  if (v === '' || v === null || v === undefined) return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

/** DB/UI: closing_balance absent — not the same as stored zero. */
const closingStored = (ln) =>
  ln.closing_balance !== null
  && ln.closing_balance !== undefined
  && String(ln.closing_balance).trim() !== ''

function cloneLines(arr) {
  return arr.map((ln) => ({ ...ln }))
}

function buildPayloadFromLines(lineArr) {
  return lineArr.map((ln) => {
    const item = { item_id: ln.item_id }
    EDITABLE.forEach((f) => {
      const v = toNum(ln[f])
      if (v !== null) item[f] = v
    })
    if (ln.movement_exception_reason) item.movement_exception_reason = ln.movement_exception_reason
    if (ln.item_notes) item.item_notes = ln.item_notes
    return item
  })
}

function normalizeLinesForCompare(lineArr) {
  return lineArr.map((ln) => ({
    item_id: ln.item_id,
    received_qty: ln.received_qty ?? '',
    returned_qty: ln.returned_qty ?? '',
    damaged_qty: ln.damaged_qty ?? '',
    closing_balance: ln.closing_balance ?? '',
    movement_exception_reason: ln.movement_exception_reason ?? '',
    item_notes: ln.item_notes ?? '',
  }))
}

function sortCountLines(arr) {
  return [...arr].sort((a, b) => {
    const ao = a.display_order ?? 999999
    const bo = b.display_order ?? 999999
    if (ao !== bo) return ao - bo
    if (a.item_id !== b.item_id) return a.item_id - b.item_id
    return String(a.item_name_snapshot || '').localeCompare(String(b.item_name_snapshot || ''), 'ar')
  })
}

function preventEnterSubmit(e) {
  if (e.key === 'Enter') e.preventDefault()
}

export function ShiftCountPage() {
  const t = useT()
  const { lang } = useLanguage()
  const { shiftId } = useParams()
  const navigate = useNavigate()
  const [search] = useSearchParams()
  const roles = useSelector(selectUserRoles) || []
  const canWrite = roles.includes('branch_manager')

  const [shift, setShift] = useState(null)
  const [count, setCount] = useState(null)
  const [lines, setLines] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [quickFilter, setQuickFilter] = useState('all')
  const [undoSnapshot, setUndoSnapshot] = useState(null)
  const [showUndo, setShowUndo] = useState(false)
  const [sessionLastSaved, setSessionLastSaved] = useState(null)
  const closingRefs = useRef({})
  const saveBtnRef = useRef(null)
  const savedSnapshotRef = useRef('')

  const markClean = useCallback((lineArr) => {
    savedSnapshotRef.current = JSON.stringify(normalizeLinesForCompare(lineArr))
  }, [])

  const invalidateUndo = () => {
    setShowUndo(false)
    setUndoSnapshot(null)
  }

  const load = useCallback(async () => {
    setLoading(true)
    invalidateUndo()
    try {
      const s = await shiftOpsApi.getShift(shiftId)
      setShift(s.data)

      let data = null
      if (canWrite) {
        const c = await shiftOpsApi.createOrGetCount(shiftId)
        data = c.data
      } else {
        try {
          const c = await shiftOpsApi.getCount(shiftId)
          data = c.data
        } catch (err) {
          if (err?.response?.status !== 404) throw err
        }
      }
      setCount(data)
      const sorted = sortCountLines(data?.lines || [])
      setLines(sorted)
      markClean(sorted)
    } catch (err) {
      toast.error(shiftOpsError(err, t, 'common.load_failed'))
    } finally {
      setLoading(false)
    }
  }, [shiftId, t, canWrite, markClean])

  useEffect(() => { load() }, [load])

  const locked = count?.status === 'submitted' || shift?.status === 'exception_locked'

  const isDirty = useMemo(() => {
    if (locked || !canWrite) return false
    return JSON.stringify(normalizeLinesForCompare(lines)) !== savedSnapshotRef.current
  }, [lines, locked, canWrite])

  const leaveGuardActive = isDirty && !loading

  useEffect(() => {
    const handler = (e) => {
      if (!leaveGuardActive) return
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [leaveGuardActive])

  useNavigationBlocker(leaveGuardActive, t('shift_ops.unsaved_changes_warning'))

  const setField = (itemId, field, value) => {
    invalidateUndo()
    setLines((prev) =>
      prev.map((ln) => (ln.item_id === itemId ? { ...ln, [field]: value } : ln)),
    )
  }

  const applyQtyInput = (itemId, field, raw) => {
    const next = processQtyInput(raw)
    if (next === null) return
    setField(itemId, field, next)
  }

  const handleQtyChange = (itemId, field) => (e) => {
    applyQtyInput(itemId, field, e.target.value)
  }

  const handleQtyPaste = (itemId, field) => (e) => {
    e.preventDefault()
    const text = e.clipboardData?.getData('text/plain') ?? ''
    applyQtyInput(itemId, field, text)
  }

  const handleQtyBlur = (itemId, field) => (e) => {
    const formatted = formatQtyOnBlur(e.target.value)
    if (formatted !== e.target.value) {
      setField(itemId, field, formatted)
    }
  }

  const qtyDisplay = (v) => (v === null || v === undefined || String(v).trim() === '' ? '' : String(v))

  const movementOf = (ln) => {
    const opening = toNum(ln.opening_balance) ?? 0
    const closing = toNum(ln.closing_balance)
    if (closing === null) return null
    const received = toNum(ln.received_qty) ?? 0
    const returned = toNum(ln.returned_qty) ?? 0
    const damaged = toNum(ln.damaged_qty) ?? 0
    return Math.round((opening + received - returned - damaged - closing) * 100) / 100
  }

  const displayMovement = (ln) => (closingStored(ln) ? movementOf(ln) : null)

  const closingEntered = (ln) => closingStored(ln)
  const isOpeningCount = Boolean(count?.is_opening_count)
  const rowNeedsReason = (ln) => {
    if (isOpeningCount) return false
    const m = movementOf(ln)
    return m !== null && m < 0 && !String(ln.movement_exception_reason || '').trim()
  }
  const hasNotes = (ln) =>
    Boolean(String(ln.item_notes || '').trim())
    || Boolean(String(ln.movement_exception_reason || '').trim())

  const rowHasActivity = (ln) =>
    (toNum(ln.received_qty) ?? 0) > 0
    || (toNum(ln.returned_qty) ?? 0) > 0
    || (toNum(ln.damaged_qty) ?? 0) > 0
    || hasNotes(ln)

  const closingMissing = (ln) => rowHasActivity(ln) && !closingStored(ln)

  const displayedLines = useMemo(() => lines.filter((ln) => {
    if (quickFilter === 'all') return true
    if (quickFilter === 'incomplete') return !closingStored(ln)
    if (quickFilter === 'negative') {
      const m = displayMovement(ln)
      return m !== null && m < 0
    }
    if (quickFilter === 'notes') return hasNotes(ln)
    return true
  }), [lines, quickFilter])

  const entered = lines.filter(closingEntered).length
  const receivedInShift = lines.filter((ln) => (toNum(ln.received_qty) ?? 0) > 0).length
  const notesCount = lines.filter((ln) => Boolean(String(ln.item_notes || '').trim())).length
  const blockedByReason = lines.some(rowNeedsReason)
  const blockedCount = lines.filter(rowNeedsReason).length
  const readyToSubmit = lines.length > 0 && !blockedByReason

  const branchDisplay = shift?.branch_name_ar || shift?.branch_name
    || (shift?.branch_id != null ? t('shift_ops.branch_fallback', { id: shift.branch_id }) : '—')

  const formatSessionTime = (d) => d.toLocaleTimeString(lang === 'ar' ? 'ar-SA' : 'en-GB', {
    hour: '2-digit',
    minute: '2-digit',
  })

  const buildSubmitPayload = () =>
    lines.map((ln) => {
      const item = { item_id: ln.item_id }
      EDITABLE.forEach((f) => {
        const v = toNum(ln[f])
        if (f === 'closing_balance') {
          item[f] = v !== null ? v : 0
        } else if (v !== null) {
          item[f] = v
        }
      })
      if (ln.movement_exception_reason) item.movement_exception_reason = ln.movement_exception_reason
      if (ln.item_notes) item.item_notes = ln.item_notes
      return item
    })

  const applySavedResponse = (data, beforeLines) => {
    setCount(data)
    const sorted = sortCountLines(data?.lines || [])
    setLines(sorted)
    markClean(sorted)
    setUndoSnapshot(cloneLines(beforeLines))
    setShowUndo(true)
  }

  const focusClosingRow = (itemId) => {
    const el = closingRefs.current[itemId]
    el?.focus()
    el?.select?.()
  }

  const handleNumberFocus = (e) => {
    e.target.select()
  }

  const handleClosingKeyDown = (e, displayIndex) => {
    if (e.key === 'Enter' || (e.key === 'Tab' && !e.shiftKey)) {
      e.preventDefault()
      const next = displayedLines[displayIndex + 1]
      if (next) {
        focusClosingRow(next.item_id)
      } else {
        saveBtnRef.current?.focus()
      }
    }
  }

  const save = async () => {
    setSaving(true)
    const beforeLines = cloneLines(lines)
    try {
      const r = await shiftOpsApi.patchCountLines(shiftId, buildPayloadFromLines(lines))
      applySavedResponse(r.data, beforeLines)
      setSessionLastSaved(new Date())
      toast.success(t('common.saved'))
    } catch (err) {
      toast.error(shiftOpsError(err, t, 'common.save_failed'))
    } finally {
      setSaving(false)
    }
  }

  const undoSave = async () => {
    if (!undoSnapshot || locked) return
    setSaving(true)
    try {
      const r = await shiftOpsApi.patchCountLines(shiftId, buildPayloadFromLines(undoSnapshot))
      setCount(r.data)
      const sorted = sortCountLines(r.data.lines || [])
      setLines(sorted)
      markClean(sorted)
      invalidateUndo()
      toast.success(t('shift_ops.undo_last_save'))
    } catch (err) {
      toast.error(shiftOpsError(err, t, 'common.save_failed'))
    } finally {
      setSaving(false)
    }
  }

  const goToReview = async () => {
    setSaving(true)
    const beforeLines = cloneLines(lines)
    try {
      const r = await shiftOpsApi.patchCountLines(shiftId, buildSubmitPayload())
      applySavedResponse(r.data, beforeLines)
      setSessionLastSaved(new Date())
      navigate(`/shift-ops/${shiftId}/count/review`)
    } catch (err) {
      toast.error(shiftOpsError(err, t, 'common.save_failed'))
    } finally {
      setSaving(false)
    }
  }

  const handleBack = () => {
    if (leaveGuardActive && !window.confirm(t('shift_ops.unsaved_changes_warning'))) return
    navigate('/shift-ops')
  }

  if (loading) return <PageLoader />

  return (
    <div className="flex flex-col h-[calc(100vh-0.5rem)] max-w-[100rem] mx-auto px-3 pt-2 pb-[4.5rem]">
      <button type="button" onClick={handleBack}
              className="inline-flex items-center gap-1 text-xs text-gray-600 shrink-0 mb-1 self-start">
        <ArrowLeft size={14} /> {t('shift_ops.back_to_shift_ops')}
      </button>

      <header className="shrink-0 border border-gray-200 rounded-lg px-3 py-2 bg-white mb-1">
        <h1 className="text-sm font-bold text-gray-900">
          {t('shift_ops.count_page_title', { branch: branchDisplay })}
        </h1>
        <p className="text-xs text-gray-600 mt-0.5">
          {t('shift_ops.count_header_meta', {
            date: shift?.shift_date ?? '—',
            number: shift?.shift_number ?? '—',
            status: t(`shift_ops.section_status.${count?.status || 'draft'}`),
          })}
        </p>
        <p className="text-xs text-gray-500 mt-0.5">
          {sessionLastSaved
            ? t('shift_ops.last_saved_session', { time: formatSessionTime(sessionLastSaved) })
            : t('shift_ops.last_saved_session_none')}
        </p>
      </header>

      {isOpeningCount && (
        <div
          data-testid="opening-count-banner"
          className="shrink-0 border border-sky-300 bg-sky-50 rounded-lg px-3 py-2 mb-2 text-xs text-sky-900"
        >
          <p className="font-bold">{t('shift_ops.opening_count_banner_title')}</p>
          <p className="mt-0.5">{t('shift_ops.opening_count_banner_body')}</p>
        </div>
      )}

      {lines.length > 0 && (
        <div className="shrink-0 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs border border-gray-200 rounded-lg px-3 py-1.5 bg-gray-50 mb-2">
          <span className="font-semibold text-gray-800">
            {t('shift_ops.entered_of', { done: entered, total: lines.length })}
          </span>
          <span className="text-gray-400">·</span>
          <span>{t('shift_ops.summary_received_in_shift', { count: receivedInShift })}</span>
          <span className="text-gray-400">·</span>
          <span className={blockedCount > 0 ? 'text-red-700 font-semibold' : 'text-gray-700'}>
            {t('shift_ops.summary_negative_no_reason', { count: blockedCount })}
          </span>
          <span className="text-gray-400">·</span>
          <span>{t('shift_ops.summary_notes', { count: notesCount })}</span>
        </div>
      )}

      <ShiftManagerActions
        shiftId={shiftId}
        roles={roles}
        shift={shift}
        openReopen={search.get('manage') === '1'}
        openCloseNoActivity={search.get('closeNoActivity') === '1'}
        onDone={load}
      />

      {locked && (
        <p className="text-xs bg-gray-100 border rounded-lg p-2 text-gray-600 shrink-0 mb-2">
          {t('shift_ops.locked_readonly')} {t('shift_ops.locked_reopen_hint')}
        </p>
      )}

      {lines.length === 0 && (
        <p className="text-sm bg-gray-50 border rounded-xl p-4 text-gray-600 text-center">
          {t('shift_ops.count_not_started')}
        </p>
      )}

      {lines.length > 0 && (
        <div className="flex flex-col flex-1 min-h-0 gap-2">
          <div className="flex flex-wrap items-center gap-1.5 shrink-0">
            <span className="text-xs text-gray-500 font-medium">{t('shift_ops.filter_show_label')}</span>
            {QUICK_FILTERS.map((key) => (
              <button
                key={key}
                type="button"
                onClick={() => setQuickFilter(key)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold border ${
                  quickFilter === key
                    ? 'bg-primary-600 text-white border-primary-600'
                    : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                }`}
              >
                {t(`shift_ops.quick_filter_${key}`)}
              </button>
            ))}
          </div>

          <div className="bg-white border border-gray-300 rounded-xl overflow-hidden flex-1 min-h-0 flex flex-col">
            <div className="overflow-auto flex-1 min-h-0">
              <table className="w-full text-sm border-collapse min-w-[960px]">
                <thead>
                  <tr className="bg-gray-50 text-xs text-gray-600 sticky top-0 z-20 shadow-[0_1px_0_#d1d5db]">
                    <th className="border border-gray-300 px-2 py-2 font-semibold text-start sticky right-0 z-30 bg-gray-50 min-w-[10rem]">
                      {t('shift_ops.field.item')}
                    </th>
                    <th className="border border-gray-300 px-2 py-2 font-semibold">{t('shift_ops.field.unit')}</th>
                    <th className="border border-gray-300 px-2 py-2 font-semibold">
                      {t('shift_ops.opening')}
                      <span className="block font-normal text-[10px] text-gray-500 mt-0.5">
                        {t('shift_ops.opening_hint')}
                      </span>
                    </th>
                    <th className="border border-gray-300 px-2 py-2 font-semibold bg-primary-50 text-primary-800">
                      {t('shift_ops.field.closing_balance')}
                    </th>
                    {QTY_FIELDS.map((f) => (
                      <th key={f} className="border border-gray-300 px-2 py-2 font-semibold">
                        {t(`shift_ops.field.${f}`)}
                      </th>
                    ))}
                    <th className="border border-gray-300 px-2 py-2 font-semibold">
                      {t('shift_ops.field.movement_diff')}
                      <span className="block font-normal text-[10px] text-gray-500 mt-0.5">
                        {t('shift_ops.movement_diff_hint')}
                      </span>
                    </th>
                    <th className="border border-gray-300 px-2 py-2 font-semibold">{t('shift_ops.field.item_notes')}</th>
                  </tr>
                </thead>
                <tbody>
                  {displayedLines.map((ln, displayIndex) => {
                    const movement = displayMovement(ln)
                    const negative = movement !== null && movement < 0
                    const needsReason = rowNeedsReason(ln)
                    const reasonField = negative && !isOpeningCount
                    const missingClosing = closingMissing(ln)
                    const rowBg = needsReason
                      ? 'bg-red-50 ring-2 ring-inset ring-red-400'
                      : negative
                        ? 'bg-amber-50'
                        : ''
                    return (
                      <tr key={ln.item_id} className={rowBg}>
                        <td className={`border border-gray-300 px-2 py-1 font-medium sticky right-0 z-10 min-w-[10rem] ${
                          needsReason ? 'bg-red-50' : negative ? 'bg-amber-50' : 'bg-white'
                        }`}>
                          {ln.item_name_snapshot}
                          {needsReason && (
                            <span className="block text-[10px] text-red-700 font-bold mt-0.5">
                              {t('shift_ops.reason_missing')}
                            </span>
                          )}
                          {missingClosing && (
                            <span className="block text-[10px] text-sky-700 mt-0.5">
                              {t('shift_ops.closing_missing')}
                            </span>
                          )}
                        </td>
                        <td className="border border-gray-300 px-2 py-1 text-center text-gray-500 whitespace-nowrap">
                          {ln.unit_snapshot}
                        </td>
                        <td className="border border-gray-300 px-2 py-1 text-center tabular-nums bg-gray-50">
                          {ln.opening_balance}
                        </td>
                        <td className="border border-gray-300 p-1 bg-primary-50/30">
                          <input
                            ref={(el) => { closingRefs.current[ln.item_id] = el }}
                            type="text"
                            inputMode="decimal"
                            autoComplete="off"
                            disabled={locked || !canWrite}
                            value={closingStored(ln) ? qtyDisplay(ln.closing_balance) : ''}
                            placeholder="0.00"
                            onChange={handleQtyChange(ln.item_id, 'closing_balance')}
                            onPaste={handleQtyPaste(ln.item_id, 'closing_balance')}
                            onBlur={handleQtyBlur(ln.item_id, 'closing_balance')}
                            onFocus={handleNumberFocus}
                            onKeyDown={(e) => {
                              preventEnterSubmit(e)
                              handleClosingKeyDown(e, displayIndex)
                            }}
                            className="w-24 border-2 border-primary-500 rounded-md px-2 py-1.5 text-center tabular-nums font-semibold disabled:bg-gray-100 focus:ring-2 focus:ring-primary-300"
                          />
                        </td>
                        {QTY_FIELDS.map((f) => (
                          <td key={f} className="border border-gray-300 p-1">
                            <input
                              type="text"
                              inputMode="decimal"
                              autoComplete="off"
                              disabled={locked || !canWrite}
                              value={qtyDisplay(ln[f])}
                              onChange={handleQtyChange(ln.item_id, f)}
                              onPaste={handleQtyPaste(ln.item_id, f)}
                              onBlur={handleQtyBlur(ln.item_id, f)}
                              onFocus={handleNumberFocus}
                              onKeyDown={preventEnterSubmit}
                              className="w-20 border border-gray-300 rounded px-1.5 py-1 text-center tabular-nums disabled:bg-gray-100"
                            />
                          </td>
                        ))}
                        <td className={`border border-gray-300 px-2 py-1 text-center font-bold tabular-nums ${
                          negative ? 'text-amber-800' : 'text-gray-800'
                        }`}>
                          {movement === null ? '—' : movement.toFixed(2)}
                        </td>
                        <td className="border border-gray-300 p-1">
                          <input
                            type="text"
                            disabled={locked || !canWrite}
                            value={(reasonField ? ln.movement_exception_reason : ln.item_notes) || ''}
                            onChange={(e) => setField(
                              ln.item_id,
                              reasonField ? 'movement_exception_reason' : 'item_notes',
                              e.target.value,
                            )}
                            onKeyDown={preventEnterSubmit}
                            placeholder={reasonField ? t('shift_ops.movement_reason_placeholder') : ''}
                            className={`w-40 border rounded px-1.5 py-1 text-xs disabled:bg-gray-100 ${
                              needsReason ? 'border-red-400 bg-red-50' : 'border-gray-300'
                            }`}
                          />
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
              <p className="text-[11px] text-gray-500 mt-2 text-center sm:text-start">
                {t('shift_ops.decimal_hint')}
              </p>
            </div>
          </div>
        </div>
      )}

      {!locked && canWrite && (
        <div className="fixed bottom-0 inset-x-0 bg-white border-t p-3 flex flex-wrap items-center justify-end gap-2 z-40">
          <p className="text-[10px] text-gray-500 w-full text-center sm:text-start sm:w-auto sm:me-auto">
            {t('shift_ops.draft_vs_submit_hint')}
          </p>
          {blockedByReason && (
            <span className="text-xs text-red-600 font-semibold me-auto flex items-center gap-1">
              <AlertTriangle size={14} /> {t('shift_ops.reason_missing')}
            </span>
          )}
          {showUndo && undoSnapshot && (
            <div className="flex items-center gap-2 me-auto text-xs text-gray-500">
              <button
                type="button"
                data-testid="undo-last-save"
                onClick={undoSave}
                disabled={saving}
                className="inline-flex items-center gap-1 border border-amber-400 text-amber-800 rounded-lg px-2.5 py-1.5 font-semibold hover:bg-amber-50"
              >
                <Undo2 size={14} /> {t('shift_ops.undo_last_save')}
              </button>
              <span>{t('shift_ops.undo_hint')}</span>
            </div>
          )}
          <button
            ref={saveBtnRef}
            type="button"
            onClick={save}
            disabled={saving}
            className="inline-flex items-center gap-1 bg-primary-600 text-white rounded-lg px-4 py-2 text-sm font-semibold disabled:bg-gray-300"
          >
            <Save size={15} /> {t('shift_ops.save_draft')}
          </button>
          <button
            type="button"
            onClick={goToReview}
            disabled={saving || !readyToSubmit}
            className="inline-flex items-center gap-1 border-2 border-primary-600 text-primary-700 rounded-lg px-4 py-2 text-sm font-semibold bg-white disabled:border-gray-300 disabled:text-gray-400"
          >
            <Send size={15} /> {t('shift_ops.review_before_final_lock')}
          </button>
        </div>
      )}
    </div>
  )
}

export default ShiftCountPage
