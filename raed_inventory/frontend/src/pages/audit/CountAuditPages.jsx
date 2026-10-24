import React from 'react'
import toast from 'react-hot-toast'
import { useSearchParams } from 'react-router-dom'
import { countAuditApi } from '../../services/countAuditApi'
import { useT } from '../../i18n'
import { countAuditErrorMessage, defaultMonthRange, parseIntParam } from './countAudit/helpers'
import FilterBar from './countAudit/FilterBar'
import DailyTab from './countAudit/DailyTab'
import VariancesTab from './countAudit/VariancesTab'
import FindingsTab from './countAudit/FindingsTab'
import ShiftDrawer from './countAudit/ShiftDrawer'
import FindingDrawer from './countAudit/FindingDrawer'

const TABS = ['daily', 'variances', 'findings']

function buildScopeParams(filters) {
  const params = {}
  if (filters.brand_id) params.brand_id = parseInt(filters.brand_id, 10)
  if (filters.city) params.city = filters.city
  if (filters.branch_id) params.branch_id = parseInt(filters.branch_id, 10)
  return params
}

function buildApiParams(filters) {
  return {
    date_from: filters.date_from,
    date_to: filters.date_to,
    ...buildScopeParams(filters),
  }
}

export function CountAuditPage() {
  const t = useT()
  const [searchParams, setSearchParams] = useSearchParams()
  const defaults = React.useMemo(() => defaultMonthRange(), [])

  const tab = TABS.includes(searchParams.get('tab')) ? searchParams.get('tab') : 'daily'
  const shiftParam = searchParams.get('shift') ? parseInt(searchParams.get('shift'), 10) : null
  const findingId = searchParams.get('finding') ? parseInt(searchParams.get('finding'), 10) : null
  const highlightItem = searchParams.get('item') ? parseInt(searchParams.get('item'), 10) : null

  const [filters, setFilters] = React.useState({
    date_from: searchParams.get('date_from') || defaults.date_from,
    date_to: searchParams.get('date_to') || defaults.date_to,
    brand_id: searchParams.get('brand_id') || '',
    city: searchParams.get('city') || '',
    branch_id: searchParams.get('branch_id') || '',
  })
  const [appliedFilters, setAppliedFilters] = React.useState(filters)
  const [filterOptions, setFilterOptions] = React.useState(null)
  const [filtersLoading, setFiltersLoading] = React.useState(true)
  const [refreshKey, setRefreshKey] = React.useState(0)

  const [drawerShiftId, setDrawerShiftId] = React.useState(null)
  const deepLinkShiftApplied = React.useRef(false)

  const tableBranchId = searchParams.get('grid_branch') || ''
  const tableDate = searchParams.get('grid_date') || ''
  const shiftsPage = parseIntParam(searchParams.get('shifts_page'), 1)
  const variancesPage = parseIntParam(searchParams.get('var_page'), 1)
  const findingsPage = parseIntParam(searchParams.get('find_page'), 1)
  const queue = searchParams.get('queue') || 'waiting_response'
  const group = searchParams.get('group') === 'repeat' ? 'repeat' : 'line'
  const direction = searchParams.get('direction') || 'all'
  const minOccurrences = parseIntParam(searchParams.get('min_occ'), 2)

  React.useEffect(() => {
    countAuditApi.getFilters()
      .then((res) => setFilterOptions(res.data))
      .catch((err) => toast.error(countAuditErrorMessage(err, t)))
      .finally(() => setFiltersLoading(false))
  }, [t])

  React.useEffect(() => {
    if (!deepLinkShiftApplied.current && shiftParam) {
      setDrawerShiftId(shiftParam)
      deepLinkShiftApplied.current = true
    }
  }, [shiftParam])

  const patchParams = React.useCallback((updates, replace = false) => {
    setSearchParams(() => {
      const next = new URLSearchParams(window.location.search)
      Object.entries(updates).forEach(([key, value]) => {
        if (value === null || value === undefined || value === '') next.delete(key)
        else next.set(key, String(value))
      })
      return next
    }, { replace })
  }, [setSearchParams])

  const applyFilters = () => {
    setAppliedFilters({ ...filters })
    patchParams({
      date_from: filters.date_from,
      date_to: filters.date_to,
      brand_id: filters.brand_id,
      city: filters.city,
      branch_id: filters.branch_id,
      shifts_page: null,
      var_page: null,
      find_page: null,
    })
    setRefreshKey((k) => k + 1)
  }

  const apiParams = React.useMemo(
    () => buildApiParams(appliedFilters),
    [appliedFilters.date_from, appliedFilters.date_to, appliedFilters.brand_id, appliedFilters.city, appliedFilters.branch_id],
  )

  const findingsScopeParams = React.useMemo(
    () => buildScopeParams(appliedFilters),
    [appliedFilters.brand_id, appliedFilters.city, appliedFilters.branch_id],
  )

  const branchNameById = React.useMemo(() => {
    const map = {}
    ;(filterOptions?.branches || []).forEach((b) => {
      map[b.branch_id] = b.branch_name
    })
    return map
  }, [filterOptions])

  const setTab = (nextTab) => {
    patchParams({ tab: nextTab })
  }

  const onCellSelect = (cell) => {
    if (!cell) {
      patchParams({ grid_branch: null, grid_date: null, shifts_page: 1, shift: null })
      setDrawerShiftId(null)
      return
    }
    patchParams({
      grid_branch: cell.branch_id,
      grid_date: cell.date,
      shifts_page: 1,
      shift: null,
    })
    setDrawerShiftId(null)
  }

  const onOpenShift = React.useCallback((id, itemId) => {
    setDrawerShiftId(id)
    patchParams({
      shift: id,
      item: itemId || null,
      tab: 'daily',
    })
  }, [patchParams])

  const onOpenFinding = (id) => {
    patchParams({ finding: id, tab: 'findings' })
  }

  const closeShift = () => {
    setDrawerShiftId(null)
    patchParams({ shift: null, item: null })
  }
  const closeFinding = () => patchParams({ finding: null })

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{t('count_audit.page_title')}</h1>
        <p className="text-sm text-gray-500 mt-1">{t('count_audit.page_subtitle')}</p>
      </div>

      <FilterBar
        filters={filters}
        setFilters={setFilters}
        filterOptions={filterOptions}
        onApply={applyFilters}
        loading={filtersLoading}
      />

      <div className="flex flex-wrap gap-2 border-b border-gray-200 pb-2">
        {TABS.map((id) => (
          <button
            key={id}
            type="button"
            className={`px-4 py-2 rounded-t-lg text-sm font-medium ${tab === id ? 'bg-white border border-b-0 border-gray-200 text-primary-700' : 'text-gray-600 hover:text-gray-900'}`}
            onClick={() => setTab(id)}
          >
            {t(`count_audit.tab_${id}`)}
          </button>
        ))}
      </div>

      {tab === 'daily' ? (
        <DailyTab
          key={`daily-${refreshKey}`}
          filters={appliedFilters}
          apiParams={apiParams}
          tableBranchId={tableBranchId}
          tableDate={tableDate}
          shiftsPage={shiftsPage}
          onShiftsPageChange={(p) => patchParams({ shifts_page: p })}
          onCellSelect={onCellSelect}
          onOpenShift={onOpenShift}
        />
      ) : null}
      {tab === 'variances' ? (
        <VariancesTab
          key={`var-${refreshKey}`}
          filters={appliedFilters}
          apiParams={apiParams}
          group={group}
          onGroupChange={(g) => patchParams({ group: g, var_page: 1 })}
          direction={direction}
          onDirectionChange={(d) => patchParams({ direction: d, var_page: 1 })}
          minOccurrences={minOccurrences}
          onMinOccurrencesChange={(n) => patchParams({ min_occ: n, var_page: 1 })}
          page={variancesPage}
          onPageChange={(p) => patchParams({ var_page: p })}
          onOpenCount={onOpenShift}
        />
      ) : null}
      {tab === 'findings' ? (
        <FindingsTab
          key={`find-${refreshKey}`}
          scopeParams={findingsScopeParams}
          queue={queue}
          onQueueChange={(q) => patchParams({ queue: q, find_page: 1 })}
          page={findingsPage}
          onPageChange={(p) => patchParams({ find_page: p })}
          onOpenFinding={onOpenFinding}
        />
      ) : null}

      {drawerShiftId ? (
        <>
          <button type="button" className="fixed inset-0 z-40 bg-black/30" aria-hidden="true" tabIndex={-1} onClick={closeShift} />
          <ShiftDrawer
            shiftId={drawerShiftId}
            branchNameById={branchNameById}
            highlightItemIds={highlightItem ? [highlightItem] : []}
            onClose={closeShift}
            onOpenFinding={onOpenFinding}
          />
        </>
      ) : null}
      {findingId ? (
        <>
          <button type="button" className="fixed inset-0 z-[55] bg-black/20" aria-hidden="true" tabIndex={-1} onClick={closeFinding} />
          <FindingDrawer
            findingId={findingId}
            onClose={closeFinding}
            onOpenCount={onOpenShift}
            onUpdated={() => setRefreshKey((k) => k + 1)}
          />
        </>
      ) : null}
    </div>
  )
}

export default CountAuditPage
