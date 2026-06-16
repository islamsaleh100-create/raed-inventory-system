import React from 'react'
import toast from 'react-hot-toast'

function itemDisplayName(item) {
  const name = item?.item_name_ar || item?.item_name_en || item?.item_name || `#${item?.id}`
  const code = item?.item_code
  if (!code) return name
  const shortCode = code.length > 6 ? code.slice(-6) : code
  return `${name} — ${shortCode}`
}

function categoryName(item) {
  return item?.category?.name_ar || item?.category?.name_en || '—'
}

function unitLabel(item) {
  return item?.unit?.code || item?.unit?.name_ar || item?.unit?.name_en || '—'
}

/**
 * Catalog-style branch request form — branch users enter quantities only (no source/brand pickers).
 */
export default function BranchRequestCatalogForm({
  branchName,
  brandName,
  availableBrands = [],
  selectedBrandId,
  onBrandSelect,
  allowedItems = [],
  saving = false,
  onSubmit,
}) {
  const [search, setSearch] = React.useState('')
  const [categoryFilter, setCategoryFilter] = React.useState('')
  const [quantities, setQuantities] = React.useState({})
  const [notes, setNotes] = React.useState({})

  const categories = React.useMemo(() => {
    const set = new Set(allowedItems.map((item) => categoryName(item)))
    return Array.from(set).sort((a, b) => a.localeCompare(b, 'ar'))
  }, [allowedItems])

  const filteredItems = React.useMemo(() => {
    const q = search.trim().toLowerCase()
    return allowedItems.filter((item) => {
      if (categoryFilter && categoryName(item) !== categoryFilter) return false
      if (!q) return true
      const blob = `${itemDisplayName(item)} ${item?.item_code || ''}`.toLowerCase()
      return blob.includes(q)
    })
  }, [allowedItems, search, categoryFilter])

  const positiveCount = React.useMemo(
    () => Object.values(quantities).filter((v) => Number(v) > 0).length,
    [quantities],
  )

  const setQty = (itemId, value) => {
    setQuantities((prev) => ({ ...prev, [itemId]: value }))
  }

  const setNote = (itemId, value) => {
    setNotes((prev) => ({ ...prev, [itemId]: value }))
  }

  const handleSubmit = async () => {
    const lines = allowedItems
      .map((item) => ({
        item_id: item.id,
        qty_requested: Number(quantities[item.id]),
        notes: (notes[item.id] || '').trim() || null,
      }))
      .filter((line) => line.qty_requested > 0)

    if (lines.length === 0) {
      toast.error('أدخل كمية واحدة على الأقل لصنف قابل للطلب')
      return
    }

    for (const line of lines) {
      if (!Number.isFinite(line.qty_requested) || line.qty_requested <= 0) {
        toast.error('يجب أن تكون الكمية أكبر من صفر')
        return
      }
    }

    await onSubmit(lines)
    setQuantities({})
    setNotes({})
  }

  const multiBrand = availableBrands.length > 1

  return (
    <div className="card p-5 space-y-4" data-testid="branch-request-catalog">
      <div className="rounded-xl bg-gray-50 border border-gray-200 p-4 space-y-2 text-sm">
        <p><span className="font-semibold text-gray-700">الفرع:</span> {branchName || '—'}</p>
        <p><span className="font-semibold text-gray-700">البراند:</span> {brandName || '—'}</p>
      </div>

      {multiBrand && (
        <div className="flex flex-wrap gap-2" role="tablist" aria-label="Brand">
          {availableBrands.map(({ brand }) => (
            <button
              key={brand.id}
              type="button"
              role="tab"
              aria-selected={String(brand.id) === String(selectedBrandId)}
              onClick={() => onBrandSelect?.(brand.id)}
              className={`px-3 py-1.5 rounded-lg text-sm border ${
                String(brand.id) === String(selectedBrandId)
                  ? 'bg-primary-600 text-white border-primary-600'
                  : 'bg-white text-gray-700 border-gray-200 hover:bg-gray-50'
              }`}
            >
              {brand.name}
            </button>
          ))}
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-3">
        <div>
          <label className="label" htmlFor="catalog-item-search">بحث باسم الصنف</label>
          <input
            id="catalog-item-search"
            type="search"
            className="input-field"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="ابحث بالاسم أو الكود"
          />
        </div>
        <div>
          <label className="label" htmlFor="catalog-category-filter">فلتر التصنيف</label>
          <select
            id="catalog-category-filter"
            className="input-field"
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
          >
            <option value="">كل التصنيفات</option>
            {categories.map((cat) => (
              <option key={cat} value={cat}>{cat}</option>
            ))}
          </select>
        </div>
      </div>

      {!allowedItems.length && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-sm text-amber-800">
          لا توجد أصناف قابلة للطلب لهذا الفرع حاليًا.
        </div>
      )}

      <div className="table-container max-h-[28rem] overflow-y-auto border border-gray-200 rounded-xl">
        <table className="table text-sm">
          <thead className="sticky top-0 bg-white z-10">
            <tr>
              <th>الصنف</th>
              <th>التصنيف</th>
              <th>الوحدة</th>
              <th className="w-28">الكمية المطلوبة</th>
              <th>ملاحظة</th>
            </tr>
          </thead>
          <tbody>
            {filteredItems.map((item) => (
              <tr key={item.id}>
                <td className="font-medium text-gray-900">{itemDisplayName(item)}</td>
                <td>{categoryName(item)}</td>
                <td>{unitLabel(item)}</td>
                <td>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    className="input-field py-1.5"
                    value={quantities[item.id] ?? ''}
                    onChange={(e) => setQty(item.id, e.target.value)}
                    aria-label={`كمية ${itemDisplayName(item)}`}
                    data-testid={`catalog-qty-${item.id}`}
                  />
                </td>
                <td>
                  <input
                    type="text"
                    className="input-field py-1.5"
                    value={notes[item.id] ?? ''}
                    onChange={(e) => setNote(item.id, e.target.value)}
                    placeholder="اختياري"
                    aria-label={`ملاحظة ${itemDisplayName(item)}`}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex justify-end">
        <button
          type="button"
          className="btn-primary min-w-[10rem]"
          disabled={saving || positiveCount === 0}
          onClick={handleSubmit}
          data-testid="catalog-submit-request"
        >
          {saving ? 'جارٍ الإرسال...' : 'إرسال الطلب'}
        </button>
      </div>
    </div>
  )
}

export { itemDisplayName }
