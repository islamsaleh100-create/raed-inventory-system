import React, { useState, useEffect, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { Save, Send, Search, AlertTriangle, CheckCircle } from 'lucide-react'
import toast from 'react-hot-toast'
import { inventoryApi, masterApi, dashboardApi } from '../../services/api'
import { selectUser } from '../../store'
import { formatQty, todayString, getVarianceBadge } from '../../utils/helpers'
import { PageLoader, Modal, StatusBadge } from '../../components/common'
import { useT, useLanguage } from '../../i18n'

export default function InventoryEntryPage() {
  const navigate = useNavigate()
  const user = useSelector(selectUser)
  const branchId = user?.branch_id
  const t = useT()
  const { lang } = useLanguage()
  const nameOf = (obj, base = 'item_name') => obj?.[`${base}_${lang}`] || obj?.[`${base}_ar`] || obj?.[base] || ''
  const userRoles = Array.isArray(user?.roles) ? user.roles : []
  const isAdmin = userRoles.includes('admin') || userRoles.includes('super_admin') || ['admin', 'super_admin'].includes(user?.primary_role)

  const [items, setItems] = useState([])
  const [counts, setCounts] = useState({}) // { item_id: { counted_qty, notes, variance_reason_id } }
  const [varianceReasons, setVarianceReasons] = useState([])
  const [stockMap, setStockMap] = useState({}) // { item_id: current_qty } — الكمية في الـ system (book qty)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [existingInventory, setExistingInventory] = useState(null)
  const [showReasonModal, setShowReasonModal] = useState(null) // item with critical variance
  // H9: inventory type — daily (default) / weekly / monthly
  const [inventoryType, setInventoryType] = useState('daily')
  const [branches, setBranches] = useState([])
  const [selectedBranchId, setSelectedBranchId] = useState(branchId || '')
  const today = todayString()
  const effectiveBranchId = selectedBranchId || branchId

  useEffect(() => {
    if (!effectiveBranchId && !isAdmin) {
      // مستخدم بدون فرع — ما نبعتش requests مع id مفقود
      setLoading(false)
      return
    }
    const branchesPromise = isAdmin
      ? masterApi.listBranches({ active_only: true }).catch(() => ({ data: [] }))
      : Promise.resolve({ data: [] })
    Promise.all([
      branchesPromise,
      effectiveBranchId
        ? masterApi.listItems({
            active_only: true,
            page_size: 400,
            branch_id: effectiveBranchId,
            visible_in_branch_ui_only: true,
          }).catch(() => ({ data: { items: [] } }))
        : Promise.resolve({ data: { items: [] } }),
      masterApi.listVarianceReasons().catch(() => ({ data: [] })),
      effectiveBranchId
        ? inventoryApi.list({ branch_id: effectiveBranchId, status: 'draft', date_from: today, date_to: today }).catch(() => ({ data: { items: [] } }))
        : Promise.resolve({ data: { items: [] } }),
      effectiveBranchId
        ? dashboardApi.branchStock(effectiveBranchId).catch(() => ({ data: [] }))
        : Promise.resolve({ data: [] }),
    ]).then(([branchesRes, itemsRes, reasonsRes, invRes, stockRes]) => {
      const branchRows = Array.isArray(branchesRes?.data) ? branchesRes.data : []
      setBranches(branchRows)
      setItems(Array.isArray(itemsRes?.data?.items) ? itemsRes.data.items : [])
      setVarianceReasons(Array.isArray(reasonsRes?.data) ? reasonsRes.data : [])

      // بناء map للـ item_id → current_qty (book qty)
      const stock = Array.isArray(stockRes?.data) ? stockRes.data : []
      const sMap = {}
      stock.forEach((s) => {
        if (s?.item_id != null) sMap[s.item_id] = Number.parseFloat(s.current_qty) || 0
      })
      setStockMap(sMap)

      // Pre-fill if draft exists
      const drafts = Array.isArray(invRes?.data?.items) ? invRes.data.items : []
      if (drafts.length > 0) {
        const draft = drafts[0]
        setExistingInventory(draft)
        if (draft.inventory_type) setInventoryType(draft.inventory_type)
        // Fetch full draft with lines (احمِ من exceptions)
        inventoryApi.get(draft.id)
          .then((r) => {
            const lines = Array.isArray(r?.data?.lines) ? r.data.lines : []
            const filled = {}
            lines.forEach((l) => {
              if (l?.item_id != null) {
                filled[l.item_id] = {
                  counted_qty: l.counted_qty ?? '',
                  notes: l.notes || '',
                  variance_reason_id: l.variance_reason_id || '',
                }
              }
            })
            setCounts(filled)
          })
          .catch((err) => {
            console.error('Failed to load draft lines', err)
          })
      }
    }).finally(() => setLoading(false))
  }, [branchId, effectiveBranchId, isAdmin, selectedBranchId, today])

  const updateCount = (itemId, field, value) => {
    setCounts((prev) => ({
      ...prev,
      [itemId]: { ...prev[itemId], [field]: value },
    }))
  }

  const safeNum = (v, def = 0) => {
    const n = Number.parseFloat(v)
    return Number.isFinite(n) ? n : def
  }

  const getVarianceInfo = (item) => {
    const c = counts[item?.id]
    if (!c || c.counted_qty === '' || c.counted_qty === undefined) return null
    const counted = safeNum(safeNum(c.counted_qty).toFixed(2))
    // book_qty = الكمية في الـ system (المفروض تكون موجودة)
    const book = safeNum(safeNum(stockMap[item?.id] ?? 0).toFixed(2))
    const variance = safeNum((counted - book).toFixed(2))
    const minQty = safeNum(item?.min_qty)
    // إذا book = 0 ومفيش counted: ok. إذا book = 0 وفيه counted: عرض كـ surplus (100% زيادة)
    const pct = book > 0
      ? safeNum((Math.abs(variance / book * 100)).toFixed(2))
      : (counted > 0 ? 999 : 0)
    return {
      counted,
      book,
      variance,
      pct,
      status: pct >= 25 ? 'critical' : pct >= 10 ? 'warning' : 'ok',
      below_min: counted < minQty,
      out_of_stock: counted <= 0,
      // علامة الزيادة (H8): لما الجرد فعلاً أكبر من الـ book — يظهر للمستودع
      surplus: book > 0 && counted > book,
    }
  }

  const filteredItems = items.filter((item) => {
    if (!item) return false
    if (!search) return true
    const q = search.toLowerCase()
    const nameAr = String(item.item_name_ar || '')
    const nameEn = String(item.item_name_en || '').toLowerCase()
    const code = String(item.item_code || '').toLowerCase()
    return nameAr.includes(q) || nameEn.includes(q) || code.includes(q)
  })

  const buildPayload = () => ({
    branch_id: effectiveBranchId,
    inventory_date: today,
    inventory_type: inventoryType || 'daily',
    lines: Object.entries(counts)
      .filter(([, v]) => v.counted_qty !== '' && v.counted_qty !== undefined)
      .map(([item_id, v]) => ({
        item_id: parseInt(item_id),
        counted_qty: Number.parseFloat(Number.parseFloat(v.counted_qty).toFixed(2)) || 0,
        notes: v.notes || null,
        variance_reason_id: v.variance_reason_id ? parseInt(v.variance_reason_id) : null,
      })),
  })

  const handleSaveDraft = async () => {
    if (Object.keys(counts).length === 0) {
      toast.error(t('inventory.please_enter_inventory_first_toast'))
      return
    }
    setSaving(true)
    try {
      const res = await inventoryApi.create(buildPayload())
      setExistingInventory(res.data)
      toast.success(t('inventory.draft_saved_toast'))
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('inventory.save_error_toast'))
    } finally {
      setSaving(false)
    }
  }

  const handleSubmit = async () => {
    // Validate critical items
    const criticalItems = items.filter((i) => i.critical_item)
    const missing = criticalItems.filter((i) => !counts[i.id] || counts[i.id].counted_qty === '')
    if (missing.length > 0) {
      toast.error(t('inventory.critical_items_missing_toast', { items: missing.map((i) => nameOf(i)).join(', ') }))
      return
    }

    setSaving(true)
    let inventoryId = existingInventory?.id
    try {
      const saved = await inventoryApi.create(buildPayload())
      inventoryId = saved.data.id
    } catch (err) {
      setSaving(false)
      toast.error(err?.response?.data?.detail || t('inventory.save_error_toast'))
      return
    }
    setSaving(false)
    setSubmitting(true)
    try {
      await inventoryApi.submit(inventoryId)
      toast.success(t('inventory.submit_success_toast'))
      navigate('/inventory')
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('inventory.submit_error_toast'))
    } finally {
      setSubmitting(false)
    }
  }

  const countedItemsCount = Object.values(counts).filter(
    (v) => v.counted_qty !== '' && v.counted_qty !== undefined
  ).length

  if (loading) return <PageLoader />

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('inventory.entry_page_title')}</h1>
          <p className="text-gray-500 text-sm mt-1">
            {t('inventory.entry_date_label')}: <strong>{today}</strong> —{' '}
            {t('inventory.entry_progress', { counted: countedItemsCount, total: items.length })}
          </p>
        </div>
        <div className="flex gap-3 items-center">
          {/* H9: type selector — locked once draft is created so reports stay consistent */}
          <label className="flex items-center gap-2 text-sm text-gray-600">
            <span>{t('inventory.type_label') || 'النوع'}:</span>
            <select
              value={inventoryType}
              onChange={(e) => setInventoryType(e.target.value)}
              disabled={!!existingInventory}
              className="input-field py-1.5 text-sm"
            >
              <option value="daily">{t('inventory.type_daily') || 'يومي'}</option>
              <option value="weekly">{t('inventory.type_weekly') || 'أسبوعي'}</option>
              <option value="monthly">{t('inventory.type_monthly') || 'شهري'}</option>
            </select>
          </label>
          <button
            onClick={handleSaveDraft}
            disabled={saving || submitting}
            className="btn-secondary"
          >
            <Save className="w-4 h-4" />
            {saving ? t('common.saving') : t('inventory.save_draft')}
          </button>
          <button
            onClick={handleSubmit}
            disabled={saving || submitting}
            className="btn-primary"
          >
            <Send className="w-4 h-4" />
            {submitting ? t('inventory.submitting_in_progress') : t('inventory.submit_for_approval')}
          </button>
        </div>
      </div>

      {isAdmin && branches.length > 0 && (
        <div className="mb-4 bg-blue-50 border border-blue-200 rounded-xl p-4">
          <label className="label text-blue-900 font-medium mb-2 block">{t('manual_order.admin_branch_label') || 'الفرع'}</label>
          <select
            value={selectedBranchId || ''}
            onChange={(e) => {
              const next = parseInt(e.target.value, 10)
              setSelectedBranchId(Number.isFinite(next) ? next : '')
              setCounts({})
              setExistingInventory(null)
            }}
            className="input-field w-full md:w-96"
          >
            <option value="">{t('manual_order.admin_branch_select_placeholder') || 'اختر الفرع'}</option>
            {branches.map((b) => (
              <option key={b.id} value={b.id}>
                {(b.branch_name_ar || b.branch_name || b.name)} ({b.branch_code})
              </option>
            ))}
          </select>
        </div>
      )}

      {isAdmin && !effectiveBranchId && (
        <div className="mb-4 bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-800">
          {t('manual_order.admin_branch_select_placeholder') || 'اختر الفرع أولًا لعرض الأصناف وحالة المخزون.'}
        </div>
      )}

      {existingInventory && (
        <div className="mb-4 flex items-center gap-2 bg-blue-50 border border-blue-200 rounded-lg px-4 py-2 text-sm text-blue-700">
          <CheckCircle className="w-4 h-4" />
          <span>{t('inventory.draft_exists_banner', { date: existingInventory.updated_at?.substring(0,16) || '' })}</span>
        </div>
      )}

      {/* Search */}
      <div className="relative mb-4">
        <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
        <input
          type="text"
          placeholder={t('inventory.search_item_placeholder')}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="input-field pr-9"
        />
      </div>

      {/* Items table */}
      <div className="table-container">
        <table className="table">
          <thead>
            <tr>
              <th>{t('inventory.item')}</th>
              <th>{t('inventory.col_category')}</th>
              <th>{t('inventory.col_unit')}</th>
              <th>{t('inventory.col_min_qty')}</th>
              <th className="w-24">{t('inventory.col_book_qty') || 'كمية النظام'}</th>
              <th className="w-32">{t('inventory.col_actual_qty')}</th>
              <th className="w-28">{t('inventory.col_variance')}</th>
              <th className="w-40">{t('common.notes')}</th>
              <th className="w-32">{t('inventory.col_variance_reason')}</th>
            </tr>
          </thead>
          <tbody>
            {filteredItems.map((item) => {
              const count = counts[item.id] || {}
              const countedQty = count.counted_qty ?? ''
              const isCountedNum = countedQty !== '' && !isNaN(Number.parseFloat(countedQty))
              const counted = isCountedNum ? safeNum(safeNum(countedQty).toFixed(2)) : null
              const minQty = safeNum(item?.min_qty)
              const belowMin = counted !== null && counted < minQty
              const outOfStock = counted !== null && counted <= 0
              // book_qty من system + حساب الفرق الفعلي
              const vInfo = getVarianceInfo(item)
              const bookQty = safeNum((safeNum(stockMap[item.id] ?? 0)).toFixed(2))

              return (
                <tr
                  key={item.id}
                  className={
                    outOfStock ? 'bg-red-50' :
                    belowMin ? 'bg-orange-50' :
                    item.critical_item ? 'bg-blue-50/30' : ''
                  }
                >
                  <td>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-gray-900">{nameOf(item)}</span>
                        {item.critical_item && (
                          <span className="status-badge bg-red-100 text-red-700 text-[10px]">{t('inventory.critical_badge')}</span>
                        )}
                      </div>
                      <p className="text-xs text-gray-400">{item.item_code}</p>
                    </div>
                  </td>
                  <td className="text-gray-500 text-xs">{nameOf(item.category, 'name')}</td>
                  <td className="text-gray-500 text-xs">{nameOf(item.unit, 'name')}</td>
                  <td className="font-medium text-gray-700">{formatQty(item.min_qty)}</td>
                  <td className="text-center font-mono text-sm text-gray-600">
                    {bookQty > 0 ? formatQty(bookQty) : <span className="text-gray-300">—</span>}
                  </td>
                  <td>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={countedQty}
                      onChange={(e) => updateCount(item.id, 'counted_qty', e.target.value)}
                      className={`w-full border rounded-lg px-2 py-1.5 text-sm text-center
                        focus:outline-none focus:ring-2 focus:ring-primary-500
                        ${outOfStock ? 'border-red-300 bg-red-50' :
                          belowMin ? 'border-orange-300 bg-orange-50' :
                          'border-gray-300 bg-white'}`}
                      placeholder="0"
                    />
                  </td>
                  <td className="text-center">
                    {outOfStock && (
                      <span className="status-badge bg-red-100 text-red-700 text-xs">{t('inventory.out_of_stock_badge')}</span>
                    )}
                    {!outOfStock && belowMin && (
                      <span className="status-badge bg-orange-100 text-orange-700 text-xs">{t('inventory.below_min_badge')}</span>
                    )}
                    {/* عرض نسبة الفرق الفعلي لما يكون فيه book qty */}
                    {!outOfStock && !belowMin && vInfo && bookQty > 0 && (
                      <div className="flex flex-col items-center gap-0.5">
                        <span className={`status-badge text-xs ${
                          vInfo.status === 'critical' ? 'bg-red-100 text-red-700' :
                          vInfo.status === 'warning' ? 'bg-orange-100 text-orange-700' :
                          'bg-green-100 text-green-700'
                        }`}>
                          {vInfo.variance > 0 ? '+' : ''}{vInfo.variance} ({vInfo.pct}%)
                        </span>
                        {/* H8: علامة الزيادة — counted > book */}
                        {vInfo.surplus && (
                          <span
                            className="status-badge bg-purple-100 text-purple-700 text-[10px]"
                            title={t('inventory.surplus_hint') || 'الجرد أكبر من رصيد النظام — يحتاج مراجعة'}
                          >
                            {t('inventory.surplus_badge') || 'زيادة'}
                          </span>
                        )}
                      </div>
                    )}
                    {!outOfStock && !belowMin && counted !== null && bookQty === 0 && (
                      <span className="status-badge bg-green-100 text-green-700 text-xs">{t('inventory.ok_badge')}</span>
                    )}
                  </td>
                  <td>
                    <input
                      type="text"
                      value={count.notes || ''}
                      onChange={(e) => updateCount(item.id, 'notes', e.target.value)}
                      className="input-field text-xs py-1"
                      placeholder={t('inventory.note_placeholder')}
                    />
                  </td>
                  <td>
                    <select
                      value={count.variance_reason_id || ''}
                      onChange={(e) => updateCount(item.id, 'variance_reason_id', e.target.value)}
                      className="input-field text-xs py-1"
                    >
                      <option value="">—</option>
                      {varianceReasons.map((r) => (
                        <option key={r.id} value={r.id}>{nameOf(r, 'reason')}</option>
                      ))}
                    </select>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="mt-4 flex flex-wrap gap-4 text-xs text-gray-500">
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded bg-red-100 border border-red-200" />
          <span>{t('inventory.legend_out_of_stock')}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded bg-orange-100 border border-orange-200" />
          <span>{t('inventory.legend_below_min')}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded bg-blue-50 border border-blue-100" />
          <span>{t('inventory.legend_critical')}</span>
        </div>
      </div>
    </div>
  )
}
