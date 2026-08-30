import React, { useCallback, useEffect, useState } from 'react'
import { ChevronDown, ChevronUp, Plus, Search } from 'lucide-react'
import toast from 'react-hot-toast'
import { masterApi } from '../../services/api'
import { PageLoader, Modal, SearchInput } from '../../components/common'
import { useLanguage, useT } from '../../i18n'

export default function BrandCountItemsAdminPage() {
  const t = useT()
  const { lang } = useLanguage()
  const itemName = (row) => row?.[`item_name_${lang}`] || row?.item_name_ar || row?.item_name_en || ''
  const unitName = (row) => row?.[`unit_name_${lang}`] || row?.unit_name_ar || row?.unit_name_en || ''

  const [brands, setBrands] = useState([])
  const [brandId, setBrandId] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [savingId, setSavingId] = useState(null)
  const [showBranches, setShowBranches] = useState(false)

  const [addOpen, setAddOpen] = useState(false)
  const [itemSearch, setItemSearch] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [searchLoading, setSearchLoading] = useState(false)

  useEffect(() => {
    masterApi.listBrands({ active_only: false })
      .then((r) => {
        const list = Array.isArray(r.data) ? r.data : []
        setBrands(list)
        if (list.length) setBrandId(String(list[0].id))
      })
      .catch((e) => toast.error(e?.response?.data?.message || t('admin.brand_count_items_load_error')))
      .finally(() => setLoading(false))
  }, [t])

  const loadItems = useCallback(async (id) => {
    if (!id) {
      setData(null)
      return
    }
    setLoading(true)
    try {
      const r = await masterApi.listBrandCountItems(id)
      setData(r.data)
    } catch (e) {
      toast.error(e?.response?.data?.message || t('admin.brand_count_items_load_error'))
      setData(null)
    } finally {
      setLoading(false)
    }
  }, [t])

  useEffect(() => {
    if (brandId) loadItems(brandId)
  }, [brandId, loadItems])

  const patchRow = async (rowId, body) => {
    setSavingId(rowId)
    try {
      await masterApi.updateBrandCountItem(brandId, rowId, body)
      await loadItems(brandId)
      toast.success(t('admin.brand_count_items_saved'))
    } catch (e) {
      toast.error(e?.response?.data?.message || t('admin.brand_count_items_save_error'))
    } finally {
      setSavingId(null)
    }
  }

  const moveRow = async (row, direction) => {
    const items = [...(data?.items || [])].sort((a, b) => a.display_order - b.display_order || a.id - b.id)
    const idx = items.findIndex((x) => x.id === row.id)
    const swapIdx = direction === 'up' ? idx - 1 : idx + 1
    if (swapIdx < 0 || swapIdx >= items.length) return
    const other = items[swapIdx]
    setSavingId(row.id)
    try {
      await masterApi.updateBrandCountItem(brandId, row.id, { display_order: other.display_order })
      await masterApi.updateBrandCountItem(brandId, other.id, { display_order: row.display_order })
      await loadItems(brandId)
    } catch (e) {
      toast.error(e?.response?.data?.message || t('admin.brand_count_items_save_error'))
    } finally {
      setSavingId(null)
    }
  }

  const runItemSearch = async (q) => {
    setItemSearch(q)
    if (!q.trim()) {
      setSearchResults([])
      return
    }
    setSearchLoading(true)
    try {
      const r = await masterApi.listItems({ page: 1, page_size: 20, search: q.trim(), active_only: true })
      setSearchResults(r.data?.items || [])
    } catch {
      setSearchResults([])
    } finally {
      setSearchLoading(false)
    }
  }

  const addItem = async (item) => {
    try {
      await masterApi.addBrandCountItem(brandId, { item_id: item.id })
      toast.success(t('admin.brand_count_items_added'))
      setAddOpen(false)
      setItemSearch('')
      setSearchResults([])
      await loadItems(brandId)
    } catch (e) {
      toast.error(e?.response?.data?.message || t('admin.brand_count_items_save_error'))
    }
  }

  if (loading && !data && !brandId) return <PageLoader />

  const sortedItems = [...(data?.items || [])].sort((a, b) => a.display_order - b.display_order || a.id - b.id)

  return (
    <div className="p-6 space-y-6 max-w-6xl">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{t('admin.brand_count_items_title')}</h1>
        <p className="text-sm text-gray-500 mt-1">{t('admin.brand_count_items_subtitle')}</p>
      </div>

      <div className="card p-4 flex flex-col sm:flex-row sm:items-end gap-4">
        <div className="flex-1">
          <label htmlFor="brand-select" className="label">{t('admin.brand_count_items_brand')}</label>
          <select
            id="brand-select"
            className="input-field"
            value={brandId}
            onChange={(e) => setBrandId(e.target.value)}
          >
            {brands.map((b) => (
              <option key={b.id} value={b.id}>{b.name}</option>
            ))}
          </select>
        </div>
        <button type="button" className="btn-primary flex items-center gap-2" onClick={() => setAddOpen(true)} disabled={!brandId}>
          <Plus size={16} />
          {t('admin.brand_count_items_add')}
        </button>
      </div>

      {data && (
        <>
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
            <p className="font-medium">{t('admin.brand_count_items_impact', { count: data.branch_count })}</p>
            {data.branch_count > 0 && (
              <button
                type="button"
                className="mt-1 text-amber-800 underline text-xs"
                onClick={() => setShowBranches((v) => !v)}
              >
                {showBranches ? t('admin.brand_count_items_hide_branches') : t('admin.brand_count_items_show_branches')}
              </button>
            )}
            {showBranches && data.branches?.length > 0 && (
              <ul className="mt-2 list-disc list-inside text-xs space-y-0.5">
                {data.branches.map((b) => (
                  <li key={b.id}>{b.branch_code} — {b.branch_name}{b.city ? ` (${b.city})` : ''}</li>
                ))}
              </ul>
            )}
          </div>

          <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900">
            {t('admin.brand_count_items_timing_notice')}
          </div>
        </>
      )}

      {loading ? (
        <PageLoader />
      ) : (
        <div className="card overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50 text-gray-600">
                <th className="px-3 py-2 text-start w-24">{t('admin.brand_count_items_order')}</th>
                <th className="px-3 py-2 text-start">{t('admin.item_code')}</th>
                <th className="px-3 py-2 text-start">{t('admin.item_name')}</th>
                <th className="px-3 py-2 text-start">{t('admin.unit')}</th>
                <th className="px-3 py-2 text-start">{t('admin.active')}</th>
                <th className="px-3 py-2 text-start w-28">{t('admin.brand_count_items_actions')}</th>
              </tr>
            </thead>
            <tbody>
              {sortedItems.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-3 py-8 text-center text-gray-500">
                    {t('admin.brand_count_items_empty')}
                  </td>
                </tr>
              ) : sortedItems.map((row, idx) => (
                <tr key={row.id} className="border-b hover:bg-gray-50">
                  <td className="px-3 py-2 font-mono text-gray-700">{row.display_order}</td>
                  <td className="px-3 py-2 font-mono">{row.item_code}</td>
                  <td className="px-3 py-2">{itemName(row)}</td>
                  <td className="px-3 py-2">{unitName(row)}</td>
                  <td className="px-3 py-2">
                    <span className={`text-xs px-2 py-0.5 rounded ${row.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'}`}>
                      {row.is_active ? t('admin.active') : t('admin.inactive')}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-1">
                      <button
                        type="button"
                        className="p-1 rounded hover:bg-gray-200 disabled:opacity-30"
                        disabled={idx === 0 || savingId === row.id}
                        onClick={() => moveRow(row, 'up')}
                        title={t('admin.brand_count_items_move_up')}
                      >
                        <ChevronUp size={16} />
                      </button>
                      <button
                        type="button"
                        className="p-1 rounded hover:bg-gray-200 disabled:opacity-30"
                        disabled={idx === sortedItems.length - 1 || savingId === row.id}
                        onClick={() => moveRow(row, 'down')}
                        title={t('admin.brand_count_items_move_down')}
                      >
                        <ChevronDown size={16} />
                      </button>
                      <button
                        type="button"
                        className="text-xs px-2 py-1 rounded border hover:bg-gray-100 disabled:opacity-50"
                        disabled={savingId === row.id}
                        onClick={() => patchRow(row.id, { is_active: !row.is_active })}
                      >
                        {row.is_active ? t('admin.brand_count_items_disable') : t('admin.brand_count_items_enable')}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal open={addOpen} onClose={() => setAddOpen(false)} title={t('admin.brand_count_items_add')}>
        <div className="space-y-4">
          <SearchInput
            value={itemSearch}
            onChange={runItemSearch}
            placeholder={t('admin.brand_count_items_search_placeholder')}
          />
          {searchLoading && <p className="text-sm text-gray-500">{t('common.loading')}</p>}
          {!searchLoading && itemSearch.trim() && searchResults.length === 0 && (
            <p className="text-sm text-gray-500">{t('admin.brand_count_items_no_results')}</p>
          )}
          <ul className="divide-y max-h-64 overflow-y-auto">
            {searchResults.map((item) => (
              <li key={item.id} className="py-2 flex items-center justify-between gap-2">
                <div>
                  <span className="font-mono text-xs text-gray-500">{item.item_code}</span>
                  <span className="mx-2">—</span>
                  <span>{lang === 'en' ? item.item_name_en : item.item_name_ar}</span>
                  <span className="text-xs text-gray-500 ms-2">
                    ({item.unit?.name_ar || item.unit?.name_en || '—'})
                  </span>
                </div>
                <button type="button" className="btn-primary text-xs py-1 px-2" onClick={() => addItem(item)}>
                  {t('admin.brand_count_items_add_btn')}
                </button>
              </li>
            ))}
          </ul>
        </div>
      </Modal>
    </div>
  )
}
