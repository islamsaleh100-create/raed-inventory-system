import React from 'react'
import toast from 'react-hot-toast'
import { countAuditApi } from '../../../services/countAuditApi'
import { useT } from '../../../i18n'
import { countAuditErrorMessage, validateDateRange, CountBadge, renderI18nLtr } from './helpers'
import CoverageGrid from './CoverageGrid'
import Pagination from './Pagination'

function countStatusLabel(row, t) {
  const cs = row.count_status
  if (cs) {
    const key = `count_audit.coverage_state_${cs}`
    const v = t(key)
    if (v !== key) return v
  }
  const ss = row.shift_status
  if (ss) {
    const key = `count_audit.shift_status_${ss}`
    const v = t(key)
    if (v !== key) return v
  }
  return '—'
}

export default function DailyTab({
  filters,
  apiParams,
  tableBranchId,
  tableDate,
  shiftsPage,
  onShiftsPageChange,
  onCellSelect,
  onOpenShift,
}) {
  const t = useT()
  const [coverageLoading, setCoverageLoading] = React.useState(false)
  const [shiftsLoading, setShiftsLoading] = React.useState(false)
  const [coverage, setCoverage] = React.useState(null)
  const [shifts, setShifts] = React.useState({ items: [], total: 0, page_size: 50 })
  const [dayPicker, setDayPicker] = React.useState({
    loading: false,
    items: [],
    branchName: '',
    date: '',
  })
  const gridSelectionRef = React.useRef({ branchId: '', date: '' })

  React.useEffect(() => {
    gridSelectionRef.current = { branchId: String(tableBranchId || ''), date: tableDate || '' }
  }, [tableBranchId, tableDate])

  const loadCoverage = React.useCallback(() => {
    const err = validateDateRange(filters.date_from, filters.date_to, 62, t)
    if (err) {
      toast.error(err)
      return
    }
    setCoverageLoading(true)
    countAuditApi.getCoverage(apiParams)
      .then((res) => setCoverage(res.data))
      .catch((e) => toast.error(countAuditErrorMessage(e, t)))
      .finally(() => setCoverageLoading(false))
  }, [apiParams, filters.date_from, filters.date_to, t])

  const loadShifts = React.useCallback(() => {
    const err = validateDateRange(filters.date_from, filters.date_to, 93, t)
    if (err) {
      toast.error(err)
      return
    }
    setShiftsLoading(true)
    const params = {
      ...apiParams,
      page: shiftsPage,
      page_size: 50,
    }
    if (tableBranchId) params.branch_id = tableBranchId
    if (tableDate) {
      params.date_from = tableDate
      params.date_to = tableDate
    }
    countAuditApi.listShifts(params)
      .then((res) => setShifts(res.data))
      .catch((e) => toast.error(countAuditErrorMessage(e, t)))
      .finally(() => setShiftsLoading(false))
  }, [apiParams, filters.date_from, filters.date_to, shiftsPage, tableBranchId, tableDate, t])

  React.useEffect(() => { loadCoverage() }, [loadCoverage])
  React.useEffect(() => { loadShifts() }, [loadShifts])

  const loadDayPicker = React.useCallback((branchId, date, branchName) => {
    const requestFor = { branchId: String(branchId), date }
    setDayPicker({ loading: true, items: [], branchName, date })
    const params = {
      ...apiParams,
      branch_id: parseInt(branchId, 10),
      date_from: date,
      date_to: date,
      page: 1,
      page_size: 20,
    }
    countAuditApi.listShifts(params)
      .then((res) => {
        const cur = gridSelectionRef.current
        if (cur.branchId !== requestFor.branchId || cur.date !== requestFor.date) return
        const items = res.data?.items || []
        setDayPicker({ loading: false, items, branchName, date })
        if (items.length === 1) {
          onOpenShift(items[0].shift_id)
        }
      })
      .catch((e) => {
        const cur = gridSelectionRef.current
        if (cur.branchId !== requestFor.branchId || cur.date !== requestFor.date) return
        toast.error(countAuditErrorMessage(e, t))
        setDayPicker({ loading: false, items: [], branchName, date })
      })
  }, [apiParams, onOpenShift, t])

  const handleCellClick = (cell) => {
    onCellSelect(cell)
    if (cell?.branch_id && cell?.date) {
      loadDayPicker(cell.branch_id, cell.date, cell.branch_name || '')
    } else {
      setDayPicker({ loading: false, items: [], branchName: '', date: '' })
    }
  }

  const clearDayFilter = () => {
    onCellSelect(null)
    setDayPicker({ loading: false, items: [], branchName: '', date: '' })
  }

  React.useEffect(() => {
    if (!tableBranchId || !tableDate) {
      setDayPicker({ loading: false, items: [], branchName: '', date: '' })
    }
  }, [tableBranchId, tableDate])

  const dayFilterActive = Boolean(tableBranchId && tableDate)
  const showDayEmptyCard = dayFilterActive && !dayPicker.loading && dayPicker.items.length === 0 && dayPicker.date === tableDate

  return (
    <div className="space-y-4">
      {coverageLoading ? <p className="text-sm text-gray-500">{t('common.loading')}</p> : null}
      {!coverageLoading ? (
        <CoverageGrid
          coverage={coverage}
          onCellClick={handleCellClick}
          selectedBranchId={tableBranchId}
          selectedDate={tableDate}
        />
      ) : null}

      {dayPicker.loading ? (
        <div className="card p-4">
          <p className="text-sm text-gray-500">{t('count_audit.day_picker_loading')}</p>
        </div>
      ) : null}

      {!dayPicker.loading && dayFilterActive && dayPicker.items.length > 1 ? (
        <div className="card p-4 space-y-3">
          <h3 className="font-semibold text-sm">{t('count_audit.pick_shift_title')}</h3>
          <div className="flex flex-wrap gap-2">
            {dayPicker.items.map((row) => (
              <button
                key={row.shift_id}
                type="button"
                className="btn-secondary text-sm flex flex-wrap items-center gap-2"
                onClick={() => onOpenShift(row.shift_id)}
              >
                <span>{renderI18nLtr(t, 'count_audit.pick_shift_button', { n: row.shift_number })}</span>
                <span className="text-xs text-gray-600">{countStatusLabel(row, t)}</span>
                {row.open_findings ? <CountBadge value={row.open_findings} variant="accent" /> : null}
                {row.reopen_count ? <CountBadge value={row.reopen_count} variant="neutral" /> : null}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {showDayEmptyCard ? (
        <div className="card p-4">
          <p className="text-sm text-gray-600">
            {renderI18nLtr(t, 'count_audit.empty_day_branch', {
              branch: dayPicker.branchName || tableBranchId,
              date: tableDate,
            })}
          </p>
        </div>
      ) : null}

      <div className="card p-4 overflow-x-auto">
        <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
          <h3 className="font-semibold">{t('count_audit.shifts_table')}</h3>
          {dayFilterActive ? (
            <button type="button" className="text-sm text-primary-600" onClick={clearDayFilter}>
              {t('count_audit.clear_day_filter')}
            </button>
          ) : null}
        </div>
        {shiftsLoading ? <p className="text-sm text-gray-500">{t('common.loading')}</p> : null}
        {!shiftsLoading && !shifts.items?.length && !showDayEmptyCard ? (
          <p className="text-sm text-gray-400 py-6 text-center">
            {dayFilterActive ? t('count_audit.empty_shifts_day') : t('count_audit.empty_shifts')}
          </p>
        ) : null}
        {!shiftsLoading && shifts.items?.length ? (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 text-xs border-b">
                <th className="p-2 text-right">{t('count_audit.branch')}</th>
                <th className="p-2">{t('common.date')}</th>
                <th className="p-2">{t('count_audit.shift_no')}</th>
                <th className="p-2">{t('count_audit.shortage_lines')}</th>
                <th className="p-2">{t('count_audit.surplus_lines')}</th>
                <th className="p-2">{t('count_audit.open_findings')}</th>
                <th className="p-2">{t('count_audit.reopens')}</th>
              </tr>
            </thead>
            <tbody>
              {shifts.items.map((row) => (
                <tr
                  key={row.shift_id}
                  className="border-b hover:bg-gray-50 cursor-pointer"
                  onClick={() => onOpenShift(row.shift_id)}
                >
                  <td className="p-2 text-right font-medium">{row.branch_name}</td>
                  <td className="p-2 whitespace-nowrap" dir="ltr">{row.shift_date}</td>
                  <td className="p-2">{row.shift_number}</td>
                  <td className="p-2">
                    <CountBadge value={row.shortage_lines} variant={row.shortage_lines ? 'shortage' : 'neutral'} />
                  </td>
                  <td className="p-2">
                    <CountBadge value={row.surplus_lines} variant={row.surplus_lines ? 'surplus' : 'neutral'} />
                  </td>
                  <td className="p-2">
                    <CountBadge value={row.open_findings} variant={row.open_findings ? 'accent' : 'neutral'} />
                  </td>
                  <td className="p-2">
                    <CountBadge value={row.reopen_count} variant={row.reopen_count ? 'accent' : 'neutral'} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
        <Pagination
          page={shifts.page || shiftsPage}
          pageSize={shifts.page_size || 50}
          total={shifts.total}
          onPageChange={onShiftsPageChange}
        />
      </div>
    </div>
  )
}
