// CountReviewPage.jsx — full-page pre-submit review (F5-safe, GET-only data)
import React, { useState, useEffect, useCallback, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { ArrowLeft } from 'lucide-react'
import toast from 'react-hot-toast'
import { shiftOpsApi } from '../../services/shiftOpsApi'
import { selectUserRoles } from '../../store'
import { PageLoader } from '../../components/common'
import { useT } from '../../i18n'
import { shiftOpsError } from './shiftOpsError'
import { buildReviewSections } from './CountReviewDialog'

const toNum = (v) => {
  if (v === '' || v === null || v === undefined) return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

const closingStored = (ln) =>
  ln.closing_balance !== null
  && ln.closing_balance !== undefined
  && String(ln.closing_balance).trim() !== ''

const qtyPositive = (v) => (toNum(v) ?? 0) > 0

export function buildTopDiffsByAbs(lines = [], limit = 5) {
  return [...lines]
    .filter((ln) => ln.movement_diff != null && ln.movement_diff !== '')
    .sort((a, b) => Math.abs(Number(b.movement_diff)) - Math.abs(Number(a.movement_diff)))
    .slice(0, limit)
}

export function deriveZeroFilledLines(lines = []) {
  return lines.filter((ln) => {
    if (!closingStored(ln)) return false
    if (Number(ln.closing_balance) !== 0) return false
    const hasQty = qtyPositive(ln.received_qty) || qtyPositive(ln.returned_qty) || qtyPositive(ln.damaged_qty)
    const hasNotes = Boolean(String(ln.item_notes || '').trim())
    return !hasQty && !hasNotes
  })
}

function rowNeedsReason(ln) {
  const d = ln.movement_diff
  return d != null && d !== '' && Number(d) < 0 && !String(ln.movement_exception_reason || '').trim()
}

function sumField(lines, field) {
  return lines.reduce((acc, ln) => acc + (toNum(ln[field]) ?? 0), 0)
}

function branchLabel(shift, t) {
  return t('shift_ops.branch_fallback', { id: shift?.branch_id ?? '—' })
}

function displayQty(v) {
  if (v === null || v === undefined || v === '') return '0'
  return String(v)
}

function SummaryCard({ label, value, valueClassName = 'text-gray-900' }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white px-3 py-2.5 shadow-sm">
      <p className="text-[11px] font-medium text-gray-500 leading-snug">{label}</p>
      <p className={`text-xl font-bold tabular-nums mt-0.5 ${valueClassName}`}>{value}</p>
    </div>
  )
}

function SectionPanel({ title, testId, children, className = '' }) {
  return (
    <section
      data-testid={testId}
      className={`rounded-lg border border-gray-200 bg-white p-4 shadow-sm ${className}`}
    >
      <h2 className="text-sm font-bold text-gray-800 mb-3">{title}</h2>
      {children}
    </section>
  )
}

function EmptyHint({ children }) {
  return (
    <p className="text-xs text-gray-500 bg-gray-50 border border-gray-100 rounded-md px-3 py-2">
      {children}
    </p>
  )
}

export function CountReviewPage() {
  const t = useT()
  const { shiftId } = useParams()
  const navigate = useNavigate()
  const roles = useSelector(selectUserRoles) || []
  const canWrite = roles.includes('branch_manager')

  const [shift, setShift] = useState(null)
  const [count, setCount] = useState(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const submitInFlight = useRef(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [shiftRes, countRes] = await Promise.all([
        shiftOpsApi.getShift(shiftId),
        shiftOpsApi.getCount(shiftId),
      ])
      setShift(shiftRes.data)
      setCount(countRes.data)
    } catch (err) {
      if (err?.response?.status === 404) {
        toast.error(t('shift_ops.error.count_not_found'))
        navigate(`/shift-ops/${shiftId}/count`, { replace: true })
        return
      }
      toast.error(shiftOpsError(err, t, 'common.load_failed'))
    } finally {
      setLoading(false)
    }
  }, [shiftId, t, navigate])

  useEffect(() => { load() }, [load])

  const locked = count?.status === 'submitted' || shift?.status === 'exception_locked'
  const lines = count?.lines || []
  const { received, negative, receivedCount, negativeCount } = buildReviewSections(lines)
  const zeroFilled = deriveZeroFilledLines(lines)
  const topDiffs = buildTopDiffsByAbs(lines)
  const blockedByReason = lines.some(rowNeedsReason)
  const blockedCount = lines.filter(rowNeedsReason).length
  const damagedLines = lines.filter((ln) => qtyPositive(ln.damaged_qty))
  const notesLines = lines.filter((ln) => Boolean(String(ln.item_notes || '').trim()))
  const allClosingZero = lines.length > 0
    && lines.every((ln) => closingStored(ln) && Number(ln.closing_balance) === 0)
  const movementTotal = sumField(lines, 'movement_diff')
  const damagedTotal = sumField(lines, 'damaged_qty')
  const showConfirm = canWrite && !locked && !blockedByReason
  const hasLargeDiffs = topDiffs.some((ln) => Math.abs(Number(ln.movement_diff)) > 0)

  const confirmSubmit = async () => {
    if (submitInFlight.current || !showConfirm) return
    submitInFlight.current = true
    setSubmitting(true)
    try {
      await shiftOpsApi.submitCount(shiftId)
      toast.success(t('shift_ops.count_submitted'))
      navigate(`/shift-ops/${shiftId}/count`)
    } catch (err) {
      toast.error(shiftOpsError(err, t, 'common.save_failed'))
    } finally {
      setSubmitting(false)
      submitInFlight.current = false
    }
  }

  if (loading) return <PageLoader />

  if (!count || !shift) {
    return (
      <div className="p-6 text-center text-gray-600">
        {t('shift_ops.count_not_started')}
      </div>
    )
  }

  return (
    <div className="w-full min-h-[calc(100vh-0.5rem)] max-w-7xl mx-auto px-4 sm:px-6 pt-3 pb-28">
      <button
        type="button"
        onClick={() => navigate(`/shift-ops/${shiftId}/count`)}
        className="inline-flex items-center gap-1 text-xs text-gray-600 mb-3"
      >
        <ArrowLeft size={14} /> {t('shift_ops.review_back')}
      </button>

      <header className="mb-4 border-b border-gray-200 pb-3">
        <h1 className="text-lg font-bold text-gray-900">{t('shift_ops.review_page_title')}</h1>
        <p className="text-sm text-gray-600 mt-1">
          {t('shift_ops.review_page_header', {
            branch: branchLabel(shift, t),
            date: shift.shift_date,
            number: shift.shift_number,
            status: t(`shift_ops.section_status.${count.status || 'draft'}`),
          })}
        </p>
      </header>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-4" data-testid="review-summary-cards">
        <SummaryCard label={t('shift_ops.review_stat_items')} value={lines.length} />
        <SummaryCard label={t('shift_ops.review_stat_zero')} value={zeroFilled.length} />
        <SummaryCard
          label={t('shift_ops.review_stat_blocked')}
          value={blockedCount}
          valueClassName={blockedCount > 0 ? 'text-red-700' : 'text-gray-900'}
        />
        <SummaryCard label={t('shift_ops.movement_total')} value={movementTotal.toFixed(2)} />
        <SummaryCard label={t('shift_ops.damaged_total')} value={damagedTotal.toFixed(2)} />
        <SummaryCard label={t('shift_ops.review_received')} value={receivedCount} />
      </div>

      {allClosingZero && (
        <p className="mb-4 text-xs font-semibold text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
          {t('shift_ops.review_all_zero_warning')}
        </p>
      )}

      <p className="mb-4 text-xs text-gray-700 bg-gray-100 border border-gray-200 rounded-lg px-3 py-2">
        {t('shift_ops.review_lock_notice')}
      </p>

      <div className="space-y-4">
        <SectionPanel
          title={t('shift_ops.review_zero_filled_count', { count: zeroFilled.length })}
          testId="review-zero-filled"
        >
          {zeroFilled.length === 0 ? (
            <EmptyHint>{t('shift_ops.no_zero_filled')}</EmptyHint>
          ) : (
            <ul className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2 max-h-52 overflow-y-auto text-sm text-gray-800">
              {zeroFilled.map((ln) => (
                <li
                  key={ln.item_id}
                  className="rounded-md border border-gray-200 bg-gray-50 px-2 py-1.5 leading-snug"
                >
                  {ln.item_name_snapshot}
                </li>
              ))}
            </ul>
          )}
        </SectionPanel>

        <SectionPanel title={t('shift_ops.review_received')} testId="review-received-section">
          {receivedCount === 0 ? (
            <EmptyHint>{t('shift_ops.no_received_in_shift')}</EmptyHint>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm min-w-[420px]">
                <thead>
                  <tr className="text-[11px] text-gray-500 border-b border-gray-100">
                    <th className="text-start font-semibold pb-2 pe-2">{t('shift_ops.field.item')}</th>
                    <th className="text-center font-semibold pb-2 w-24">{t('shift_ops.field.qty')}</th>
                    <th className="text-center font-semibold pb-2 w-20">{t('shift_ops.field.unit')}</th>
                  </tr>
                </thead>
                <tbody>
                  {received.map((ln) => (
                    <tr key={ln.item_id} className="border-t border-gray-50">
                      <td className="py-1.5 pe-2">{ln.item_name_snapshot}</td>
                      <td className="py-1.5 text-center tabular-nums font-semibold text-blue-700">{ln.received_qty}</td>
                      <td className="py-1.5 text-center text-gray-500 text-xs">{ln.unit_snapshot}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SectionPanel>

        <SectionPanel title={t('shift_ops.large_diffs')} testId="review-top-diffs">
          {!hasLargeDiffs ? (
            <EmptyHint>{t('shift_ops.no_large_diffs')}</EmptyHint>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm min-w-[720px]">
                <thead>
                  <tr className="text-[11px] text-gray-500 border-b border-gray-100">
                    <th className="text-start font-semibold pb-2 pe-2">{t('shift_ops.field.item')}</th>
                    <th className="text-center font-semibold pb-2 w-20">{t('shift_ops.opening')}</th>
                    <th className="text-center font-semibold pb-2 w-16">{t('shift_ops.field.received_qty')}</th>
                    <th className="text-center font-semibold pb-2 w-16">{t('shift_ops.field.returned_qty')}</th>
                    <th className="text-center font-semibold pb-2 w-16">{t('shift_ops.field.damaged_qty')}</th>
                    <th className="text-center font-semibold pb-2 w-20">{t('shift_ops.field.closing_balance')}</th>
                    <th className="text-center font-semibold pb-2 w-24">{t('shift_ops.field.movement_diff')}</th>
                  </tr>
                </thead>
                <tbody>
                  {topDiffs.map((ln) => {
                    const needsReason = rowNeedsReason(ln)
                    const rowClass = needsReason ? 'bg-red-50' : ''
                    return (
                      <tr key={ln.item_id} className={`border-t border-gray-50 ${rowClass}`}>
                        <td className="py-1.5 pe-2 font-medium">{ln.item_name_snapshot}</td>
                        <td className="py-1.5 text-center tabular-nums">{displayQty(ln.opening_balance)}</td>
                        <td className="py-1.5 text-center tabular-nums">{displayQty(ln.received_qty)}</td>
                        <td className="py-1.5 text-center tabular-nums">{displayQty(ln.returned_qty)}</td>
                        <td className="py-1.5 text-center tabular-nums">{displayQty(ln.damaged_qty)}</td>
                        <td className="py-1.5 text-center tabular-nums">{displayQty(ln.closing_balance)}</td>
                        <td className={`py-1.5 text-center tabular-nums font-bold ${needsReason ? 'text-red-700' : 'text-gray-800'}`}>
                          {ln.movement_diff}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </SectionPanel>

        <SectionPanel title={t('shift_ops.review_negative_reasons')} testId="review-negative-section">
          {negativeCount === 0 ? (
            <EmptyHint>{t('shift_ops.no_negative_diffs')}</EmptyHint>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm min-w-[480px]">
                <thead>
                  <tr className="text-[11px] text-gray-500 border-b border-gray-100">
                    <th className="text-start font-semibold pb-2 pe-2">{t('shift_ops.field.item')}</th>
                    <th className="text-center font-semibold pb-2 w-24">{t('shift_ops.field.movement_diff')}</th>
                    <th className="text-start font-semibold pb-2">{t('shift_ops.review_col_reason')}</th>
                  </tr>
                </thead>
                <tbody>
                  {negative.map((ln) => (
                    <tr key={ln.item_id} className="border-t border-gray-50">
                      <td className="py-1.5 pe-2">{ln.item_name_snapshot}</td>
                      <td className="py-1.5 text-center tabular-nums font-semibold text-red-700">{ln.movement_diff}</td>
                      <td className="py-1.5 text-xs text-gray-600">
                        {ln.movement_exception_reason || t('shift_ops.reason_missing')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SectionPanel>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <SectionPanel title={t('shift_ops.review_section_damaged')} testId="review-damaged-section">
            {damagedLines.length === 0 ? (
              <EmptyHint>{t('shift_ops.no_damaged_items')}</EmptyHint>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-[11px] text-gray-500 border-b border-gray-100">
                      <th className="text-start font-semibold pb-2">{t('shift_ops.field.item')}</th>
                      <th className="text-center font-semibold pb-2 w-20">{t('shift_ops.field.qty')}</th>
                      <th className="text-center font-semibold pb-2 w-16">{t('shift_ops.field.unit')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {damagedLines.map((ln) => (
                      <tr key={ln.item_id} className="border-t border-gray-50">
                        <td className="py-1.5">{ln.item_name_snapshot}</td>
                        <td className="py-1.5 text-center tabular-nums">{ln.damaged_qty}</td>
                        <td className="py-1.5 text-center text-xs text-gray-500">{ln.unit_snapshot}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </SectionPanel>

          <SectionPanel title={t('shift_ops.review_section_notes')} testId="review-notes-section">
            {notesLines.length === 0 ? (
              <EmptyHint>{t('shift_ops.no_notes')}</EmptyHint>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-[11px] text-gray-500 border-b border-gray-100">
                      <th className="text-start font-semibold pb-2 w-2/5">{t('shift_ops.field.item')}</th>
                      <th className="text-start font-semibold pb-2">{t('shift_ops.field.item_notes')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {notesLines.map((ln) => (
                      <tr key={ln.item_id} className="border-t border-gray-50">
                        <td className="py-1.5 pe-2 font-medium">{ln.item_name_snapshot}</td>
                        <td className="py-1.5 text-xs text-gray-600">{ln.item_notes}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </SectionPanel>
        </div>
      </div>

      <div className="fixed bottom-0 inset-x-0 bg-white border-t shadow-[0_-4px_12px_rgba(0,0,0,0.06)] z-40" data-testid="review-action-bar">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex flex-wrap items-center gap-2 justify-end">
          {blockedByReason && canWrite && !locked && (
            <span className="text-xs text-red-600 font-semibold me-auto">
              {t('shift_ops.reason_missing')}
            </span>
          )}
          <button
            type="button"
            onClick={() => navigate(`/shift-ops/${shiftId}/count`)}
            disabled={submitting}
            className="inline-flex items-center border-2 border-gray-400 text-gray-700 rounded-lg px-4 py-2.5 text-sm font-bold bg-white"
          >
            {t('shift_ops.review_back')}
          </button>
          {showConfirm && (
            <button
              type="button"
              data-testid="confirm-final-submit"
              onClick={confirmSubmit}
              disabled={submitting}
              className="inline-flex items-center bg-primary-600 text-white rounded-lg px-5 py-2.5 text-sm font-bold disabled:bg-gray-300"
            >
              {submitting ? t('shift_ops.review_submitting') : t('shift_ops.review_confirm_final')}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export default CountReviewPage
