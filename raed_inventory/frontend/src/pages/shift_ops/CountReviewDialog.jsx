// CountReviewDialog.jsx — pre-submit review step (module scope; not nested in ShiftCountPage).
import React, { useEffect, useRef } from 'react'

/** Build review sections from server count lines — never recompute movement_diff client-side. */
export function buildReviewSections(lines = []) {
  const received = lines.filter((ln) => Number(ln.received_qty) > 0)
  const negative = lines.filter((ln) => {
    const d = ln.movement_diff
    return d != null && d !== '' && Number(d) < 0
  })
  const topPositive = lines
    .filter((ln) => ln.movement_diff != null && ln.movement_diff !== '' && Number(ln.movement_diff) > 0)
    .sort((a, b) => Number(b.movement_diff) - Number(a.movement_diff))
    .slice(0, 5)
  return {
    total: lines.length,
    received,
    negative,
    topPositive,
    receivedCount: received.length,
    negativeCount: negative.length,
  }
}

function formatDiff(value) {
  if (value == null || value === '') return '—'
  const n = Number(value)
  if (!Number.isFinite(n)) return String(value)
  if (n > 0) return `+${n}`
  return String(n)
}

export default function CountReviewDialog({
  open,
  count,
  zeroFilled = [],
  submitting,
  onClose,
  onConfirm,
  t,
}) {
  const backRef = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    const onKey = (e) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    const id = window.setTimeout(() => backRef.current?.focus(), 0)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.clearTimeout(id)
    }
  }, [open, onClose])

  if (!open || !count) return null

  const { received, negative, topPositive, total, receivedCount, negativeCount } = buildReviewSections(
    count.lines || [],
  )
  const zeroFilledCount = zeroFilled.length
  const allClosingZero = (count.lines || []).length > 0
    && (count.lines || []).every((ln) => Number(ln.closing_balance) === 0)

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4"
      role="presentation"
      onClick={onClose}
    >
      <div
        className="bg-white w-full sm:max-w-3xl rounded-t-2xl sm:rounded-2xl shadow-xl overflow-hidden text-right max-h-[80vh] flex flex-col"
        role="dialog"
        aria-modal="true"
        aria-labelledby="count-review-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-4 py-3 border-b border-gray-200 shrink-0">
          <h2 id="count-review-title" className="text-base font-bold text-gray-900">
            {t('shift_ops.review_title')}
          </h2>
          <p className="text-xs text-gray-500 mt-1">
            {t('shift_ops.review_summary', {
              total,
              received: receivedCount,
              negative: negativeCount,
            })}
          </p>
        </div>

        <div className="overflow-y-auto flex-1 min-h-0 py-1">
          {/* 1 — received (always visible) */}
          <section className="px-4 py-3 border-b border-gray-100">
            <h3 className="text-sm font-bold text-blue-700 flex items-center gap-2 mb-2">
              {t('shift_ops.review_received')}
              <span className="text-[11px] font-bold bg-blue-100 text-blue-700 rounded-full px-2 py-0.5">
                {receivedCount}
              </span>
            </h3>
            {receivedCount === 0 ? (
              <p className="text-xs text-gray-500 px-1">{t('shift_ops.review_no_received')}</p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-[11px] text-gray-500">
                    <th className="text-right font-semibold pb-1">{t('shift_ops.field.item')}</th>
                    <th className="text-right font-semibold pb-1 w-24">{t('shift_ops.field.qty')}</th>
                    <th className="text-right font-semibold pb-1 w-16">{t('shift_ops.field.unit')}</th>
                  </tr>
                </thead>
                <tbody>
                  {received.map((ln) => (
                    <tr key={ln.item_id} className="border-t border-gray-50">
                      <td className="py-1.5 pe-2 align-top">{ln.item_name_snapshot}</td>
                      <td className="py-1.5 tabular-nums font-bold text-blue-700 whitespace-nowrap">
                        {ln.received_qty}
                      </td>
                      <td className="py-1.5 text-gray-400 text-xs whitespace-nowrap">{ln.unit_snapshot}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          {/* 2 — negative (hidden when none) */}
          {negativeCount > 0 && (
            <section className="px-4 py-3 border-b border-gray-100 bg-red-50/40">
              <h3 className="text-sm font-bold text-red-700 flex items-center gap-2 mb-2">
                {t('shift_ops.review_negative')}
                <span className="text-[11px] font-bold bg-red-100 text-red-700 rounded-full px-2 py-0.5">
                  {negativeCount}
                </span>
              </h3>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-[11px] text-gray-500">
                    <th className="text-right font-semibold pb-1">{t('shift_ops.field.item')}</th>
                    <th className="text-right font-semibold pb-1 w-20">{t('shift_ops.field.movement_diff')}</th>
                  </tr>
                </thead>
                <tbody>
                  {negative.map((ln) => (
                    <tr key={ln.item_id} className="border-t border-red-100/80">
                      <td className="py-1.5 pe-2 align-top">
                        {ln.item_name_snapshot}
                        {ln.movement_exception_reason ? (
                          <span className="block text-[11px] text-gray-500 mt-0.5 leading-snug">
                            {ln.movement_exception_reason}
                          </span>
                        ) : null}
                      </td>
                      <td className="py-1.5 tabular-nums font-bold text-red-700 whitespace-nowrap">
                        {formatDiff(ln.movement_diff)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}

          {/* 3 — top positive */}
          {topPositive.length > 0 && (
            <section className="px-4 py-3">
              <h3 className="text-sm font-bold text-gray-600 mb-2">{t('shift_ops.review_top_diff')}</h3>
              <table className="w-full text-sm">
                <tbody>
                  {topPositive.map((ln) => (
                    <tr key={ln.item_id} className="border-t border-gray-50 first:border-t-0">
                      <td className="py-1.5 pe-2">{ln.item_name_snapshot}</td>
                      <td className="py-1.5 tabular-nums font-bold text-gray-800 whitespace-nowrap w-20 text-left">
                        {formatDiff(ln.movement_diff)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}

          {zeroFilledCount > 0 && (
            <section className="px-4 py-3 border-t border-gray-100 bg-gray-50/60">
              <h3 className="text-sm font-bold text-gray-700 flex items-center gap-2 mb-2">
                {t('shift_ops.review_zero_filled')}
                <span className="text-[11px] font-bold bg-gray-200 text-gray-700 rounded-full px-2 py-0.5">
                  {zeroFilledCount}
                </span>
              </h3>
              <ul className="text-sm text-gray-700 space-y-1 max-h-[40vh] overflow-y-auto">
                {zeroFilled.map((ln) => (
                  <li key={ln.item_id} className="leading-snug">{ln.item_name_snapshot}</li>
                ))}
              </ul>
            </section>
          )}
        </div>

        {allClosingZero && (
          <p className="px-4 py-2 text-xs font-semibold text-amber-800 bg-amber-50 border-t border-amber-100 shrink-0">
            ⚠ {t('shift_ops.review_all_zero_warning')}
          </p>
        )}

        <p className="px-4 py-2 text-xs text-gray-600 bg-gray-100 border-t border-gray-200 shrink-0">
          {t('shift_ops.review_lock_notice')}
        </p>

        <div className="flex gap-2 px-4 py-3 border-t border-gray-200 bg-gray-50 shrink-0">
          <button
            ref={backRef}
            type="button"
            disabled={submitting}
            onClick={onClose}
            className="flex-1 py-2.5 rounded-lg border-2 border-gray-400 text-gray-700 text-sm font-bold bg-white"
          >
            {t('shift_ops.review_back')}
          </button>
          <button
            type="button"
            disabled={submitting}
            onClick={onConfirm}
            className="flex-1 py-2.5 rounded-lg bg-primary-600 text-white text-sm font-bold disabled:bg-gray-300"
          >
            {submitting ? t('shift_ops.review_submitting') : t('shift_ops.review_confirm')}
          </button>
        </div>
      </div>
    </div>
  )
}
