import React from 'react'
import { useT } from '../../../i18n'

const STATE_STYLES = {
  submitted: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  draft: 'bg-amber-100 text-amber-900 border-amber-200',
  exception: 'bg-red-100 text-red-800 border-red-200',
  partial: 'bg-orange-100 text-orange-900 border-orange-200',
  no_record: 'bg-gray-100 text-gray-600 border-gray-200',
}

export default function CoverageGrid({ coverage, onCellClick, selectedBranchId, selectedDate }) {
  const t = useT()
  if (!coverage?.dates?.length) {
    return <div className="text-sm text-gray-400 py-6 text-center">{t('count_audit.empty_coverage')}</div>
  }

  const legendStates = ['submitted', 'draft', 'exception', 'partial', 'no_record']
  const legend = legendStates.map((state) => (
    <span key={state} className="inline-flex items-center gap-1 text-xs text-gray-600 ml-3">
      <span className={`inline-block px-1.5 py-0.5 rounded border font-semibold ${STATE_STYLES[state]}`}>
        {t(`count_audit.coverage_letter_${state}`)}
      </span>
      {t(`count_audit.coverage_state_${state}`)}
    </span>
  ))

  return (
    <div className="card p-4 space-y-3 overflow-x-auto">
      <p className="text-sm text-gray-600">{t('count_audit.coverage_legend_intro')}</p>
      <div className="flex flex-wrap gap-1 items-center">
        {legend}
        <span className="inline-flex items-center gap-1 text-xs text-gray-600 ml-3">
          <span className="inline-block w-2 h-2 rounded-full bg-red-500 align-middle" aria-hidden="true" />
          {t('count_audit.coverage_has_diff_legend')}
        </span>
      </div>
      <table className="min-w-full text-xs border-collapse">
        <thead>
          <tr>
            <th className="text-right p-2 border-b sticky right-0 bg-white">{t('count_audit.branch')}</th>
            {coverage.dates.map((d) => (
              <th key={d} className="p-2 border-b whitespace-nowrap font-medium text-gray-600">{d.slice(5)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {coverage.branches.map((row) => (
            <tr key={row.branch_id}>
              <td className="p-2 border-b sticky right-0 bg-white font-medium text-gray-800 whitespace-nowrap">
                {row.branch_name}
              </td>
              {coverage.dates.map((d) => {
                const cell = row.days?.[d] || { state: 'no_record', shift_id: null, has_diff: false }
                const state = cell.state || 'no_record'
                const selected = String(selectedBranchId) === String(row.branch_id) && selectedDate === d
                const stateLabel = t(`count_audit.coverage_state_${state}`)
                const tooltip = `${row.branch_name} — ${d} — ${stateLabel}`
                return (
                  <td key={d} className="p-1 border-b text-center">
                    <button
                      type="button"
                      title={tooltip}
                      className={`relative w-full min-w-[2.5rem] px-1 py-1 rounded border font-bold ${STATE_STYLES[state] || STATE_STYLES.no_record} ${selected ? 'ring-2 ring-primary-500' : ''}`}
                      onClick={() => onCellClick({
                        branch_id: row.branch_id,
                        branch_name: row.branch_name,
                        date: d,
                        shift_id: cell.shift_id,
                      })}
                    >
                      {t(`count_audit.coverage_letter_${state}`)}
                      {cell.has_diff ? (
                        <span className="absolute top-0.5 left-0.5 w-1.5 h-1.5 rounded-full bg-red-600" aria-hidden="true" />
                      ) : null}
                    </button>
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
