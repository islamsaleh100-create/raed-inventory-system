import React from 'react'
import { useT } from '../../../i18n'

export default function FilterBar({
  filters,
  setFilters,
  filterOptions,
  onApply,
  loading,
  showApply = true,
}) {
  const t = useT()
  const brands = filterOptions?.brands || []
  const cities = filterOptions?.cities || []
  const branches = filterOptions?.branches || []

  return (
    <div className="card p-4 space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <label className="space-y-1">
          <span className="text-xs text-gray-500">{t('common.date_from')}</span>
          <input
            type="date"
            className="input-field w-full"
            value={filters.date_from}
            onChange={(e) => setFilters((prev) => ({ ...prev, date_from: e.target.value }))}
          />
        </label>
        <label className="space-y-1">
          <span className="text-xs text-gray-500">{t('common.date_to')}</span>
          <input
            type="date"
            className="input-field w-full"
            value={filters.date_to}
            onChange={(e) => setFilters((prev) => ({ ...prev, date_to: e.target.value }))}
          />
        </label>
      </div>
      <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))' }}>
        <label className="space-y-1">
          <span className="text-xs text-gray-500">{t('count_audit.filter_brand')}</span>
          <select
            className="input-field w-full"
            value={filters.brand_id}
            onChange={(e) => setFilters((prev) => ({ ...prev, brand_id: e.target.value }))}
          >
            <option value="">{t('common.all')}</option>
            {brands.map((b) => (
              <option key={b.brand_id} value={String(b.brand_id)}>{b.name}</option>
            ))}
          </select>
        </label>
        <label className="space-y-1">
          <span className="text-xs text-gray-500">{t('count_audit.filter_city')}</span>
          <select
            className="input-field w-full"
            value={filters.city}
            onChange={(e) => setFilters((prev) => ({ ...prev, city: e.target.value }))}
          >
            <option value="">{t('common.all')}</option>
            {cities.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </label>
        <label className="space-y-1">
          <span className="text-xs text-gray-500">{t('count_audit.filter_branch')}</span>
          <select
            className="input-field w-full"
            value={filters.branch_id}
            onChange={(e) => setFilters((prev) => ({ ...prev, branch_id: e.target.value }))}
          >
            <option value="">{t('common.all')}</option>
            {branches.map((b) => (
              <option key={b.branch_id} value={String(b.branch_id)}>{b.branch_name}</option>
            ))}
          </select>
        </label>
      </div>
      {showApply ? (
        <div className="flex justify-end">
          <button type="button" className="btn-primary" disabled={loading} onClick={onApply}>
            {loading ? t('common.loading') : t('count_audit.apply_filters')}
          </button>
        </div>
      ) : null}
    </div>
  )
}
