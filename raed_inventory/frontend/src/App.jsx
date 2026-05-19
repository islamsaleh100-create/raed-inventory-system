import React, { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate, Outlet, Link } from 'react-router-dom'
import { Provider, useSelector } from 'react-redux'
import toast, { Toaster } from 'react-hot-toast'
import { store, selectIsAuthenticated, selectUser, selectUserRoles } from './store'
import AppLayout from './components/layout/AppLayoutV2'
import { PageLoader, ErrorBoundary } from './components/common'
import RouteRoleGuard from './components/common/RouteRoleGuard'
import InlineAuditFindingsPanel from './components/audit/InlineAuditFindingsPanel'
import { LanguageProvider, useT, useLanguage } from './i18n'
import { dashboardApi, itemChangeRequestsApi, masterApi, notificationsApi, ordersApi, stockApi } from './services/api'
import './index.css'

// Pages
import LoginPage from './pages/auth/LoginPage'
import BranchDashboard from './pages/branch/BranchDashboard'
import InventoryEntryPage from './pages/branch/InventoryEntryPage'
import BranchEmployeesPage from './pages/branch/BranchEmployeesPage'
import { InventoryListPage } from './pages/branch/InventoryListPage'
import OrdersListPage from './pages/shared/OrdersListPage'
import OrderDetailPage from './pages/shared/OrderDetailPage'
import ReceivingPage from './pages/branch/ReceivingPage'
import { OperationsDashboard, WarehouseDashboard } from './pages/shared/DashboardPages'
import { ItemsManagementPage, UsersManagementPage } from './pages/admin/AdminPages'
import KitchensAdminPage from './pages/admin/KitchensAdminPage'
import AssistantSuggestionsPage from './pages/admin/AssistantSuggestionsPage'
import { ConsumptionTrendPage, OrderDelayAnalyticsPage, BranchesOpenActionsPage } from './pages/admin/AnalyticsDashboards'
import { QualityVisitListPage, QualityVisitFormPage, QualityVisitDetailPage, QualityOpenActionsPage, QualityAnalyticsPage } from './pages/quality/QualityPages'
import { DocumentsListPage, DocumentsExpiringPage, DocumentFormPage } from './pages/documents/DocumentsPages'
import { TrainingAssessmentListPage, TrainingAssessmentFormPage, TrainingAssessmentDetailPage, TrainingAnalyticsPage } from './pages/training/TrainingPages'
import { AuditDashboardPage, AuditFindingsPage, AuditTrailPage } from './pages/audit/AuditPages'
import {
  SupplyChainControlDashboard,
  SupplyChainBranchRequestsPage,
  SupplyChainApprovalsPage,
  SupplyChainKitchenPage,
  SupplyChainWarehousePage,
  SupplyChainDeliveryPage,
} from './pages/supply_chain/SupplyChainPages'
import {
  DeliveryDashboardPage,
  DeliveryBranchStatsPage,
  DeliveryBrandStatsPage,
  DeliveryImportPage,
  DeliveryBranchesManagementPage,
  DeliveryUnmatchedPage,
  // ظ„ظ„طھظˆط§ظپظ‚ ظ…ط¹ ط§ظ„ط£ط³ظ…ط§ط، ط§ظ„ظ‚ط¯ظٹظ…ط©
  DeliveryDashboardPage as DeliveryAnalyticsDashboardPage,
  DeliveryBranchesManagementPage as DeliveryAnalyticsBranchesPage,
  DeliveryImportPage as DeliveryAnalyticsImportsPage,
} from './pages/delivery/DeliveryAnalyticsPages'
import {
  SalesChannelsAdminPage,
  SalesChannelsClosuresPage,
  SalesChannelsCompliancePage,
  SalesChannelsDailyEntryPage,
  SalesChannelsReconciliationPage,
  SalesChannelsStatementsPage,
} from './pages/delivery/SalesChannelsPages'

// Branch stock page
function BranchStockPage() {
  const t = useT()
  const { lang } = useLanguage()
  const user = useSelector((s) => s.auth.user)
  const roles = useSelector(selectUserRoles)
  const isAdmin = roles.includes('admin') || roles.includes('super_admin')
  const [stock, setStock] = React.useState([])
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState(null)
  const [branches, setBranches] = React.useState([])
  const [selectedBranchId, setSelectedBranchId] = React.useState(user?.branch_id || null)

  const nameOf = (obj, base = 'item_name') =>
    obj?.[`${base}_${lang}`] || obj?.[`${base}_ar`] || obj?.[base] || ''

  // ظ„ظ„ط£ط¯ظ…ظ†: ط­ظ…ظ‘ظ„ ظ‚ط§ط¦ظ…ط© ط§ظ„ظپط±ظˆط¹ ط¹ظ„ط´ط§ظ† ظٹط®طھط§ط± ظ…ظ†ظ‡ظ…
  React.useEffect(() => {
    if (!isAdmin) return
    let cancelled = false
    import('./services/api').then(({ masterApi }) => {
      masterApi.listBranches({ active_only: true }).then((r) => {
        if (cancelled) return
        const list = Array.isArray(r?.data) ? r.data : []
        setBranches(list)
      }).catch(() => {})
    })
    return () => { cancelled = true }
  }, [isAdmin])

  React.useEffect(() => {
    let cancelled = false
    // ظ„ظˆ ظ…ط§ ظپظٹط´ ظپط±ط¹ ظ…ط­ط¯ط¯ (ظˆظ„ط§ ط­طھظ‰ ظ…ظ† user.branch_id) ظˆظ„ط§ ط§ظ„ط£ط¯ظ…ظ† ط§ط®طھط§ط± ظپط±ط¹ â†’ ظˆظ‚ظپ ط§ظ„طھط­ظ…ظٹظ„
    if (!selectedBranchId) {
      setLoading(false)
      setStock([])
      return () => { cancelled = true }
    }
    setLoading(true)
    setError(null)
    import('./services/api').then(({ dashboardApi }) => {
      dashboardApi.branchStock(selectedBranchId)
        .then((r) => {
          if (cancelled) return
          setStock(Array.isArray(r?.data) ? r.data : [])
        })
        .catch((err) => {
          if (cancelled) return
          setStock([])
          setError(err?.response?.data?.detail || t('branch_stock.load_error') || 'طھط¹ط°ظ‘ط± طھط­ظ…ظٹظ„ ط§ظ„ظ…ط®ط²ظˆظ†')
        })
        .finally(() => { if (!cancelled) setLoading(false) })
    })
    return () => { cancelled = true }
  }, [selectedBranchId])

  // Admin ط¨ط¯ظˆظ† branch_id ظˆط¨ط¯ظˆظ† ط§ط®طھظٹط§ط± â†’ ط±ط³ط§ظ„ط© ط¥ط±ط´ط§ط¯ظٹط©
  if (!selectedBranchId && !isAdmin) {
    return (
      <div className="p-6">
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-6 text-center">
          <p className="text-yellow-700 font-medium">{t('branch_stock.no_branch') || 'ظ„ط§ ظٹظˆط¬ط¯ ظپط±ط¹ ظ…ط±طھط¨ط· ط¨ط­ط³ط§ط¨ظƒ'}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <h1 className="text-2xl font-bold text-gray-900">{t('branch_stock.title')}</h1>
        {isAdmin && branches.length > 1 && (
          <select
            value={selectedBranchId || ''}
            onChange={(e) => setSelectedBranchId(e.target.value ? parseInt(e.target.value, 10) : null)}
            className="input-field w-64"
          >
            <option value="">{t('branch_stock.select_branch') || 'ط§ط®طھط± ط§ظ„ظپط±ط¹'}</option>
            {branches.map((b) => (
              <option key={b.id} value={b.id}>{b.branch_name_ar || b.branch_name || b.name}</option>
            ))}
          </select>
        )}
      </div>
      {!selectedBranchId && isAdmin ? (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-6 text-center">
          <p className="text-blue-700 font-medium">{t('branch_stock.select_branch_prompt') || 'ط§ط®طھط± ط§ظ„ظپط±ط¹ ط£ظˆظ„ظ‹ط§ ظ„ط¹ط±ط¶ ط­ط§ظ„ط© ط§ظ„ظ…ط®ط²ظˆظ†'}</p>
        </div>
      ) : loading ? (
        <PageLoader />
      ) : error ? (
        <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center">
          <p className="text-red-700 font-medium">{error}</p>
        </div>
      ) : (
        <div className="card table-container">
          <table className="table">
            <thead>
              <tr>
                <th>{t('branch_stock.item')}</th>
                <th>{t('branch_stock.col_code')}</th>
                <th>{t('branch_stock.current_qty')}</th>
                <th>{t('branch_stock.col_in_transit')}</th>
                <th>{t('branch_stock.col_min_qty')}</th>
                <th>{t('branch_stock.reorder_point')}</th>
                <th>{t('common.status')}</th>
              </tr>
            </thead>
            <tbody>
              {stock.length === 0 ? (
                <tr><td colSpan={7} className="text-center text-gray-400 py-8">{t('branch_stock.empty') || 'ظ„ط§ طھظˆط¬ط¯ ط¨ظٹط§ظ†ط§طھ'}</td></tr>
              ) : stock.map((s) => (
                <tr key={s?.item_id} className={
                  s?.status === 'out_of_stock' ? 'bg-red-50' :
                  s?.status === 'below_min' ? 'bg-orange-50' :
                  s?.status === 'reorder' ? 'bg-yellow-50' : ''
                }>
                  <td className="font-medium">{nameOf(s)}</td>
                  <td className="font-mono text-xs text-gray-400">{s?.item_code}</td>
                  <td className="text-center font-bold text-lg">{parseFloat(s?.current_qty || 0)}</td>
                  <td className="text-center text-blue-600">{parseFloat(s?.in_transit_qty || 0)}</td>
                  <td className="text-center text-gray-500">{parseFloat(s?.min_qty || 0)}</td>
                  <td className="text-center text-gray-500">{parseFloat(s?.reorder_point || 0)}</td>
                  <td>
                    <span className={`status-badge text-xs
                      ${s?.status === 'out_of_stock' ? 'bg-red-100 text-red-700' :
                        s?.status === 'below_min' ? 'bg-orange-100 text-orange-700' :
                        s?.status === 'reorder' ? 'bg-yellow-100 text-yellow-700' :
                        'bg-green-100 text-green-700'}`}>
                      {t(`branch_stock.status_${s?.status || 'ok'}`)}
                    </span>
                    {s?.critical_item && (
                      <span className="status-badge bg-red-100 text-red-700 text-xs mr-1">{t('branch_stock.critical_badge')}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// Warehouse stock page
function WarehouseStockPage({ readOnly = false, title = null, subtitle = null }) {
  const t = useT()
  const { lang } = useLanguage()
  const user = useSelector((s) => s.auth.user)
  const roles = useSelector(selectUserRoles)
  const isAdmin = roles.includes('admin') || roles.includes('super_admin')
  const canSelectWarehouse = isAdmin || readOnly || roles.includes('internal_auditor')
  const nameOf = (obj, base = 'item_name') =>
    obj?.[`${base}_${lang}`] || obj?.[`${base}_ar`] || obj?.[base] || ''

  const [stock, setStock] = React.useState([])
  const [loading, setLoading] = React.useState(false)
  const [warehouses, setWarehouses] = React.useState([])
  const [selectedWh, setSelectedWh] = React.useState(user?.warehouse_id || null)
  const [items, setItems] = React.useState([])
  const [adjustOpen, setAdjustOpen] = React.useState(false)
  const [adjustForm, setAdjustForm] = React.useState({
    item_id: '',
    adjustment_type: 'set',
    qty: '',
    reason: 'Warehouse stock update',
  })
  const [requestOpen, setRequestOpen] = React.useState(false)
  const [requestForm, setRequestForm] = React.useState({
    type: 'new_item',
    item_id: '',
    item_label: '',
    proposed_item_name_ar: '',
    proposed_unit: '',
    proposed_source_type: 'WAREHOUSE',
    reason: '',
  })
  const [quickQtys, setQuickQtys] = React.useState({})
  const [selectedStockAudit, setSelectedStockAudit] = React.useState(null)
  const fileInputRef = React.useRef(null)

  const loadStock = React.useCallback(() => {
    if (!selectedWh) return undefined
    let cancelled = false
    setLoading(true)
    dashboardApi.warehouseStock(selectedWh)
      .then((r) => { if (!cancelled) setStock(Array.isArray(r?.data) ? r.data : []) })
      .catch(() => { if (!cancelled) setStock([]) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [selectedWh])

  // ظ„ظˆ admin: ط­ظ…ظ‘ظ„ ظ‚ط§ط¦ظ…ط© ط§ظ„ظ…ط³طھظˆط¯ط¹ط§طھ
  React.useEffect(() => {
    if (!canSelectWarehouse) return
    let cancelled = false
    import('./services/api').then(({ masterApi }) => {
      masterApi.listWarehouses().then((r) => {
        if (cancelled) return
        const list = Array.isArray(r?.data) ? r.data : []
        setWarehouses(list)
      }).catch(() => {})
    })
    return () => { cancelled = true }
  }, [canSelectWarehouse])

  // ط­ظ…ظ‘ظ„ ط§ظ„ظ…ط®ط²ظˆظ† ظ„ظ…ط§ ظٹطھط­ط¯ط¯ ط§ظ„ظ…ط³طھظˆط¯ط¹
  React.useEffect(() => {
    if (!selectedWh) return
    return loadStock()
  }, [selectedWh, loadStock])

  React.useEffect(() => {
    let cancelled = false
    const loadItems = async () => {
      const pageSize = 200
      let pageNo = 1
      let all = []
      let total = null
      do {
        const r = await masterApi.listItems({ page: pageNo, page_size: pageSize, active_only: false })
        const batch = Array.isArray(r?.data) ? r.data : (r?.data?.items || [])
        all = [...all, ...batch]
        total = Array.isArray(r?.data) ? all.length : (r?.data?.total ?? all.length)
        pageNo += 1
      } while (all.length < total && pageNo < 50)
      return all
    }
    loadItems()
      .then((all) => {
        if (cancelled) return
        setItems(all)
      })
      .catch(() => { if (!cancelled) setItems([]) })
    return () => { cancelled = true }
  }, [])

  const itemIdByCode = React.useMemo(() => {
    const map = new Map()
    items.forEach((item) => {
      if (item.item_code) map.set(String(item.item_code).trim().toLowerCase(), item.id)
    })
    return map
  }, [items])

  const displayedStock = React.useMemo(() => {
    const stockByItemId = new Map(stock.map((row) => [String(row.item_id), row]))
    const rows = items.map((item) => {
      const stockRow = stockByItemId.get(String(item.id))
      return {
        item_id: item.id,
        item_code: item.item_code,
        item_name: item.item_name,
        item_name_ar: item.item_name_ar,
        item_name_en: item.item_name_en,
        current_qty: stockRow?.current_qty ?? 0,
        reserved_qty: stockRow?.reserved_qty ?? 0,
      }
    })
    stock.forEach((stockRow) => {
      if (!items.some((item) => String(item.id) === String(stockRow.item_id))) {
        rows.push(stockRow)
      }
    })
    return rows
  }, [items, stock])

  const downloadWarehouseStock = async () => {
    if (!selectedWh) return
    try {
      const res = await stockApi.exportWarehouseStock(selectedWh, 'xlsx')
      const url = URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = `warehouse_${selectedWh}_stock.xlsx`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      toast.error(err?.response?.data?.message || 'فشل تنزيل ملف المخزون')
    }
  }

  const saveAdjustment = async () => {
    if (!selectedWh || !adjustForm.item_id || adjustForm.qty === '') {
      toast.error('اختر الصنف والكمية')
      return
    }
    try {
      await stockApi.adjustWarehouse(selectedWh, {
        item_id: Number(adjustForm.item_id),
        adjustment_type: adjustForm.adjustment_type,
        qty: Number(adjustForm.qty),
        reason: adjustForm.reason || 'Warehouse stock update',
      })
      toast.success('تم تحديث مخزون المستودع')
      setAdjustOpen(false)
      setAdjustForm({ item_id: '', adjustment_type: 'set', qty: '', reason: 'Warehouse stock update' })
      loadStock()
    } catch (err) {
      toast.error(err?.response?.data?.message || err?.response?.data?.detail || 'فشل تحديث المخزون')
    }
  }

  const openAdjustmentForItem = (itemId, qty = '') => {
    setAdjustForm({
      item_id: String(itemId || ''),
      adjustment_type: 'set',
      qty: qty === null || qty === undefined ? '' : String(qty),
      reason: 'Warehouse stock update',
    })
    setAdjustOpen(true)
  }

  const saveQuickQty = async (itemId) => {
    if (!selectedWh) return
    const qty = quickQtys[itemId]
    if (qty === '' || qty === undefined) {
      toast.error('اكتب الكمية')
      return
    }
    try {
      await stockApi.adjustWarehouse(selectedWh, {
        item_id: Number(itemId),
        adjustment_type: 'set',
        qty: Number(qty),
        reason: 'Quick warehouse stock update',
      })
      toast.success('تم تحديث الكمية')
      setQuickQtys((prev) => {
        const next = { ...prev }
        delete next[itemId]
        return next
      })
      loadStock()
    } catch (err) {
      toast.error(err?.response?.data?.message || err?.response?.data?.detail || 'فشل تحديث الكمية')
    }
  }

  const openWarehouseRequestForm = (type = 'new_item', row = null) => {
    setRequestForm({
      type,
      item_id: row?.item_id ? String(row.item_id) : '',
      item_label: row ? `${nameOf(row) || row.item_code} (${row.item_code || ''})` : '',
      proposed_item_name_ar: '',
      proposed_unit: '',
      proposed_source_type: 'WAREHOUSE',
      reason: '',
    })
    setRequestOpen(true)
  }

  const submitWarehouseItemRequest = async () => {
    if (!selectedWh) return
    try {
      if (requestForm.type === 'warehouse_remove') {
        if (!requestForm.item_id || !requestForm.reason.trim()) {
          toast.error('اختر الصنف واكتب سبب الإزالة')
          return
        }
        await itemChangeRequestsApi.requestWarehouseRemove({
          warehouse_id: Number(selectedWh),
          item_id: Number(requestForm.item_id),
          reason: requestForm.reason.trim(),
        })
        toast.success('تم إرسال طلب الإزالة للمراجعة')
      } else {
        if (!requestForm.proposed_item_name_ar.trim()) {
          toast.error('اكتب اسم الصنف الجديد')
          return
        }
        await itemChangeRequestsApi.requestNewItem({
          target_type: 'warehouse',
          warehouse_id: Number(selectedWh),
          proposed_item_name_ar: requestForm.proposed_item_name_ar.trim(),
          proposed_unit: requestForm.proposed_unit.trim(),
          proposed_source_type: requestForm.proposed_source_type,
          reason: requestForm.reason.trim(),
        })
        toast.success('تم إرسال طلب إنشاء الصنف للمراجعة')
      }
      setRequestOpen(false)
      setRequestForm({
        type: 'new_item',
        item_id: '',
        item_label: '',
        proposed_item_name_ar: '',
        proposed_unit: '',
        proposed_source_type: 'WAREHOUSE',
        reason: '',
      })
    } catch (err) {
      toast.error(err?.response?.data?.message || err?.response?.data?.detail || 'فشل إرسال الطلب')
    }
  }

  const handleUpload = async (event) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file || !selectedWh) return
    try {
      const XLSX = await import('xlsx')
      const data = await file.arrayBuffer()
      const workbook = XLSX.read(data)
      const sheet = workbook.Sheets[workbook.SheetNames[0]]
      const rows = XLSX.utils.sheet_to_json(sheet, { defval: '' })
      const lines = []
      for (const row of rows) {
        const rawItemId = row.item_id || row.ItemID || row['Item ID']
        const rawCode = row.item_code || row.ItemCode || row['Item Code']
        const rawQty = row.current_qty ?? row.qty ?? row.quantity ?? row['Current Qty'] ?? row['Quantity']
        const resolvedItemId = Number(rawItemId || itemIdByCode.get(String(rawCode || '').trim().toLowerCase()))
        const qty = Number(rawQty)
        if (!resolvedItemId || Number.isNaN(qty)) continue
        lines.push({
          item_id: resolvedItemId,
          qty,
        })
      }
      if (lines.length === 0) {
        toast.error('ملف Excel لا يحتوي صفوف صالحة')
        return
      }
      const result = await stockApi.bulkAdjustWarehouse(selectedWh, {
        adjustment_type: 'set',
        reason: `Excel import: ${file.name}`,
        lines,
      })
      const updated = result?.data?.updated ?? lines.length
      const errors = result?.data?.errors || []
      toast.success(`تم تحديث ${updated} صنف من Excel${errors.length ? `، وفشل ${errors.length}` : ''}`)
      loadStock()
    } catch (err) {
      toast.error(err?.response?.data?.message || 'فشل رفع ملف Excel')
    }
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{title || t('branch_stock.warehouse_title')}</h1>
          {subtitle && <p className="text-sm text-gray-500 mt-1">{subtitle}</p>}
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {selectedWh && !readOnly && (
            <>
              <button type="button" onClick={() => setAdjustOpen(true)} className="btn-primary">تعديل صنف</button>
              <button type="button" onClick={() => openWarehouseRequestForm('new_item')} className="btn-secondary">طلب تغيير/صنف جديد</button>
              <button type="button" onClick={downloadWarehouseStock} className="btn-secondary">تنزيل Excel</button>
              <button type="button" onClick={() => fileInputRef.current?.click()} className="btn-secondary">رفع Excel</button>
              <input ref={fileInputRef} type="file" accept=".xlsx,.xls,.csv" onChange={handleUpload} className="hidden" />
            </>
          )}
          {canSelectWarehouse && warehouses.length > 1 && (
          <select
            value={selectedWh || ''}
            onChange={(e) => setSelectedWh(e.target.value ? parseInt(e.target.value, 10) : null)}
            className="input-field w-64"
          >
            <option value="">{t('branch_stock.select_warehouse') || 'اختر المستودع'}</option>
            {warehouses.map((w) => (
              <option key={w.id} value={w.id}>{w.warehouse_name}</option>
            ))}
          </select>
          )}
        </div>
      </div>

      {loading && <div className="p-6"><PageLoader /></div>}

      {!loading && !selectedWh && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-6 text-center">
          <p className="text-yellow-700 font-medium">{t('branch_stock.wh_select_prompt')}</p>
        </div>
      )}

      {requestOpen && !readOnly && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl p-5">
          <div className="flex items-center justify-between gap-3 mb-4">
            <div>
              <h2 className="font-semibold text-lg text-gray-900">طلب تغيير صنف</h2>
              <p className="text-sm text-gray-500 mt-1">اكتب كل بيانات الطلب هنا مرة واحدة، وسيذهب للمراجعة عند الأوديت.</p>
            </div>
            <button type="button" onClick={() => setRequestOpen(false)} className="btn-secondary">إغلاق</button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
            <div>
              <label className="label">نوع الطلب</label>
              <select
                className="input-field"
                value={requestForm.type}
                onChange={(e) => setRequestForm((p) => ({ ...p, type: e.target.value, item_id: '', item_label: '' }))}
              >
                <option value="new_item">صنف جديد غير موجود</option>
                <option value="warehouse_remove">إزالة صنف من المستودع</option>
              </select>
            </div>
            {requestForm.type === 'warehouse_remove' ? (
              <div className="md:col-span-2">
                <label className="label">الصنف المطلوب إزالته</label>
                <select
                  className="input-field"
                  value={requestForm.item_id}
                  onChange={(e) => {
                    const item = displayedStock.find((row) => String(row.item_id) === e.target.value)
                    setRequestForm((p) => ({
                      ...p,
                      item_id: e.target.value,
                      item_label: item ? `${nameOf(item) || item.item_code} (${item.item_code || ''})` : '',
                    }))
                  }}
                >
                  <option value="">اختر صنف</option>
                  {displayedStock.map((row) => (
                    <option key={row.item_id} value={row.item_id}>{nameOf(row)} ({row.item_code})</option>
                  ))}
                </select>
              </div>
            ) : (
              <>
                <div>
                  <label className="label">اسم الصنف</label>
                  <input
                    className="input-field"
                    value={requestForm.proposed_item_name_ar}
                    onChange={(e) => setRequestForm((p) => ({ ...p, proposed_item_name_ar: e.target.value }))}
                  />
                </div>
                <div>
                  <label className="label">الوحدة</label>
                  <input
                    className="input-field"
                    placeholder="قطعة / كرتون / كيلوجرام"
                    value={requestForm.proposed_unit}
                    onChange={(e) => setRequestForm((p) => ({ ...p, proposed_unit: e.target.value }))}
                  />
                </div>
                <div>
                  <label className="label">المصدر</label>
                  <select
                    className="input-field"
                    value={requestForm.proposed_source_type}
                    onChange={(e) => setRequestForm((p) => ({ ...p, proposed_source_type: e.target.value }))}
                  >
                    <option value="WAREHOUSE">مستودع</option>
                    <option value="KITCHEN">مطبخ</option>
                  </select>
                </div>
              </>
            )}
            <div className={requestForm.type === 'warehouse_remove' ? 'md:col-span-2 xl:col-span-1' : 'md:col-span-2 xl:col-span-4'}>
              <label className="label">السبب</label>
              <input
                className="input-field"
                value={requestForm.reason}
                onChange={(e) => setRequestForm((p) => ({ ...p, reason: e.target.value }))}
              />
            </div>
          </div>
          <div className="flex justify-end mt-4">
            <button type="button" onClick={submitWarehouseItemRequest} className="btn-primary">إرسال الطلب للمراجعة</button>
          </div>
          </div>
        </div>
      )}

      {!loading && selectedWh && (
        <div className="card table-container">
          <table className="table">
            <thead>
              <tr>
                <th>{t('branch_stock.item')}</th>
                <th>{t('branch_stock.col_code')}</th>
                <th>{t('branch_stock.wh_col_qty')}</th>
                <th>{t('branch_stock.reserved_qty')}</th>
                <th>{readOnly ? 'مراجعة' : 'تعديل'}</th>
              </tr>
            </thead>
            <tbody>
              {displayedStock.length === 0 ? (
                <tr><td colSpan={5} className="text-center text-gray-400 py-8">{t('branch_stock.wh_empty')}</td></tr>
              ) : displayedStock.map((s) => (
                <tr key={s.item_id}>
                  <td className="font-medium">{nameOf(s)}</td>
                  <td className="font-mono text-xs text-gray-400">{s.item_code}</td>
                  <td className="text-center font-bold">{parseFloat(s.current_qty)}</td>
                  <td className="text-center text-gray-500">{parseFloat(s.reserved_qty)}</td>
                  <td className="text-center">
                    {readOnly ? (
                      <button
                        type="button"
                        className="btn-secondary text-xs py-1 px-2"
                        onClick={() => setSelectedStockAudit(s)}
                      >
                        ملاحظة
                      </button>
                    ) : (
                      <div className="flex items-center justify-center gap-2">
                        <input
                          type="number"
                          min="0"
                          value={quickQtys[s.item_id] ?? ''}
                          placeholder={String(s.current_qty ?? 0)}
                          onChange={(e) => setQuickQtys((p) => ({ ...p, [s.item_id]: e.target.value }))}
                          className="w-24 border border-gray-300 rounded px-2 py-1 text-sm text-center"
                        />
                        <button
                          type="button"
                          onClick={() => saveQuickQty(s.item_id)}
                          className="btn-primary text-xs py-1 px-2"
                        >
                          حفظ
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {readOnly && selectedStockAudit && (
        <InlineAuditFindingsPanel
          entityType="warehouse_stock"
          entityId={selectedStockAudit.item_id}
          title={`ملاحظات مراجعة المخزون - ${nameOf(selectedStockAudit) || selectedStockAudit.item_code}`}
        />
      )}

      {adjustOpen && (
        <div className="fixed inset-0 z-50 bg-black/30 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-lg">تعديل مخزون صنف</h2>
              <button type="button" onClick={() => setAdjustOpen(false)} className="text-gray-500 hover:text-gray-800">×</button>
            </div>
            <div className="grid grid-cols-1 gap-4">
              <div>
                <label className="label">الصنف</label>
                <select
                  value={adjustForm.item_id}
                  onChange={(e) => setAdjustForm((p) => ({ ...p, item_id: e.target.value }))}
                  className="input-field"
                >
                  <option value="">اختر صنف</option>
                  {items.map((item) => (
                    <option key={item.id} value={item.id}>
                      {nameOf(item)} ({item.item_code})
                    </option>
                  ))}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label">نوع التعديل</label>
                  <select
                    value={adjustForm.adjustment_type}
                    onChange={(e) => setAdjustForm((p) => ({ ...p, adjustment_type: e.target.value }))}
                    className="input-field"
                  >
                    <option value="set">تعيين الكمية</option>
                    <option value="increase">زيادة</option>
                    <option value="decrease">نقص</option>
                  </select>
                </div>
                <div>
                  <label className="label">الكمية</label>
                  <input
                    type="number"
                    min="0"
                    value={adjustForm.qty}
                    onChange={(e) => setAdjustForm((p) => ({ ...p, qty: e.target.value }))}
                    className="input-field"
                  />
                </div>
              </div>
              <div>
                <label className="label">السبب</label>
                <input
                  value={adjustForm.reason}
                  onChange={(e) => setAdjustForm((p) => ({ ...p, reason: e.target.value }))}
                  className="input-field"
                />
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button type="button" onClick={() => setAdjustOpen(false)} className="btn-secondary">إلغاء</button>
              <button type="button" onClick={saveAdjustment} className="btn-primary">حفظ</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ط¹ط±ط¶ ظ†طµ ط¢ظ…ظ† ظپظٹ JSX (ظ†طµظˆطµ/ط£ط±ظ‚ط§ظ… ظƒظ€ StringطŒ ظƒط§ط¦ظ†ط§طھ ظƒظ€ JSON ظ„طھط¬ظ†ط¨ ط®ط·ط£ React children)
function safeItemText(v) {
  if (v === null || v === undefined) return ''
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

// ط·ظ„ط¨ ط§ط³طھط«ظ†ط§ط¦ظٹ ط£ظˆ ط·ظ„ط¨ظٹط© ظٹظˆظ…ظٹط© (ظ†ظپط³ ط§ظ„ظ†ظ…ظˆط°ط¬)
function ManualOrderPage({ orderType = 'exceptional' }) {
  const t = useT()
  const { lang } = useLanguage()
  const user = useSelector((s) => s.auth.user)
  const roles = useSelector(selectUserRoles)
  const isAdmin = roles.includes('admin') || roles.includes('super_admin')
  const nameOf = (obj, base = 'item_name') =>
    obj?.[`${base}_${lang}`] || obj?.[`${base}_ar`] || obj?.[base] || ''

  const [allItems, setAllItems] = React.useState([])
  const [branchStockByItem, setBranchStockByItem] = React.useState({})
  const [quantities, setQuantities] = React.useState({})
  const [lineNotes, setLineNotes] = React.useState({})
  const [orderNotes, setOrderNotes] = React.useState('')
  const [search, setSearch] = React.useState('')
  const [loading, setLoading] = React.useState(false)
  const [fetching, setFetching] = React.useState(true)

  // Branch selector ظ„ظ„ط£ط¯ظ…ظ† ط§ظ„ظ„ظٹ ظ…ط´ ظ…ط±ط¨ظˆط· ط¨ظپط±ط¹ ظˆط§ط­ط¯ â€” ط¨ط¯ظˆظ†ظ‡ط§ ط§ظ„ظ€ submit
  // ط¨ظٹظپط´ظ„ ط¨ظ€ "branch_id is required" ظˆط§ظ„ظ…ط³طھط®ط¯ظ… ظٹط´ظˆظپ toast ظپط§ط¶ظٹط© {}.
  const [branches, setBranches] = React.useState([])
  const [selectedBranchId, setSelectedBranchId] = React.useState(user?.branch_id || null)

  const isDaily = orderType === 'daily' || orderType === 'daily_order'
  const title = isDaily ? t('manual_order.title_daily') : t('manual_order.title_exceptional')
  const showBranchSelector = isAdmin && !user?.branch_id

  React.useEffect(() => {
    import('./services/api').then(({ dashboardApi, masterApi }) => {
      const effectiveBranchId = selectedBranchId || user?.branch_id
      if (showBranchSelector && !effectiveBranchId) {
        setAllItems([])
        setFetching(false)
        setBranches([])
        masterApi.listBranches({ active_only: true }).then((r) => {
          const list = Array.isArray(r.data) ? r.data : (r.data?.items || [])
          setBranches(list)
        }).catch(() => {})
        return
      }
      const itemParams = {
        page_size: 200,
        active_only: true,
        visible_in_branch_ui_only: true,
        requestable_only: true,
      }
      if (effectiveBranchId) itemParams.branch_id = effectiveBranchId
      masterApi.listItems(itemParams)
        .then((r) => {
          const raw = r.data
          const list = Array.isArray(raw) ? raw : (raw?.items || raw?.data || [])
          const finalList = Array.isArray(list) ? list : []
          setAllItems(finalList)
        })
        .finally(() => setFetching(false))

      if (effectiveBranchId) {
        dashboardApi.branchStock(effectiveBranchId)
          .then((r) => {
            const rows = Array.isArray(r.data) ? r.data : []
            setBranchStockByItem(Object.fromEntries(rows.map((row) => [row.item_id, row])))
          })
          .catch(() => setBranchStockByItem({}))
      } else {
        setBranchStockByItem({})
      }

      // ط§ظ„ط£ط¯ظ…ظ†: ط­ظ…ظ‘ظ„ ظ‚ط§ط¦ظ…ط© ط§ظ„ظپط±ظˆط¹ ظ„ظٹط®طھط§ط± ظ…ظ†ظ‡ط§
      if (isAdmin && !user?.branch_id) {
        masterApi.listBranches({ active_only: true }).then((r) => {
          const list = Array.isArray(r.data) ? r.data : (r.data?.items || [])
          setBranches(list)
        }).catch(() => { /* طھط¬ط§ظ‡ظ„ ط¨ظ‡ط¯ظˆط، â€” ط§ظ„ط£ط®ط·ط§ط، ط³طھط¸ظ‡ط± ط¹ظ†ط¯ ط§ظ„ظ€ submit */ })
      }
    })
  }, [isAdmin, selectedBranchId, user?.branch_id])

  React.useEffect(() => {
    let cancelled = false

    const loadStable = async () => {
      try {
        const effectiveBranchId = selectedBranchId || user?.branch_id

        if (showBranchSelector) {
          try {
            const branchesResp = await masterApi.listBranches({ active_only: true })
            if (!cancelled) {
              const list = Array.isArray(branchesResp.data) ? branchesResp.data : (branchesResp.data?.items || [])
              setBranches(list)
            }
          } catch (_e) {
            if (!cancelled) setBranches([])
          }
        }

        if (showBranchSelector && !effectiveBranchId) {
          if (!cancelled) {
            setAllItems([])
            setFetching(false)
          }
          return
        }

        const itemParams = {
          page_size: 200,
          active_only: true,
          visible_in_branch_ui_only: true,
          requestable_only: true,
        }
        if (effectiveBranchId) itemParams.branch_id = effectiveBranchId

        const [itemsResp, stockResp] = await Promise.all([
          masterApi.listItems(itemParams),
          dashboardApi.branchStock(effectiveBranchId).catch(() => ({ data: [] })),
        ])
        if (cancelled) return
        const raw = itemsResp.data
        const list = Array.isArray(raw) ? raw : (raw?.items || raw?.data || [])
        setAllItems(Array.isArray(list) ? list : [])
        const stockRows = Array.isArray(stockResp.data) ? stockResp.data : []
        setBranchStockByItem(Object.fromEntries(stockRows.map((row) => [row.item_id, row])))
      } catch (_e) {
        if (!cancelled) setAllItems([])
      } finally {
        if (!cancelled) setFetching(false)
      }
    }

    loadStable()
    return () => { cancelled = true }
  }, [showBranchSelector, selectedBranchId, user?.branch_id])

  const filteredItems = allItems.filter((i) => {
    const code = String(i.item_code || '').toLowerCase()
    if (!search) return true
    const q = search.toLowerCase()
    return (i.item_name_ar || '').includes(search) || (i.item_name_en || '').toLowerCase().includes(q) || code.includes(q)
  })

  const handleSubmit = async () => {
    const toastMod = await import('react-hot-toast')
    const toast = toastMod.default

    const effectiveBranchId = selectedBranchId || user?.branch_id
    if (!effectiveBranchId) {
      toast.error(t('manual_order.toast_branch_required'))
      return
    }

    const selectedItems = allItems
      .filter((i) => quantities[i.id] && parseFloat(quantities[i.id]) > 0)
      .map((i) => ({
        item_id: i.id,
        branch_requested_qty: parseFloat(quantities[i.id]),
        notes: lineNotes[i.id] || null,
      }))

    if (selectedItems.length === 0) {
      toast.error(t('manual_order.toast_qty_required'))
      return
    }

    setLoading(true)
    try {
      const payload = {
        branch_id: effectiveBranchId,
        items: selectedItems,
        notes: orderNotes,
      }
      if (isDaily) {
        await ordersApi.createDaily(payload)
      } else {
        await ordersApi.createExceptional(payload)
      }
      toast.success(isDaily ? t('manual_order.toast_created_daily') : t('manual_order.toast_created_exceptional'))
      window.history.back()
    } catch (err) {
      // ط§ظ„ظ€ backend ط¨ظٹط±ط¬ظ‘ط¹ {error_code, message, detail}. ظ†ظپط¶ظ‘ظ„ ط§ظ„ظ€ messageطŒ
      // ظˆظ„ظˆ ظ…ط´ ظ…ظˆط¬ظˆط¯ ظ†ط±ط¬ط¹ ظ„ظ„ظ€ detail (ظ‚ط¯ ظٹظƒظˆظ† array ظ…ظ† pydantic ط£ظˆ dict ط£ظˆ string).
      const data = err?.response?.data
      const det = data?.detail
      const detMsg = Array.isArray(det)
        ? det.map((e) => (typeof e === 'object' && e != null ? (e.msg || JSON.stringify(e)) : String(e))).join(' â€” ')
        : (typeof det === 'object' && det != null && Object.keys(det).length > 0
            ? JSON.stringify(det)
            : (typeof det === 'string' ? det : ''))
      const msg = data?.message || detMsg || err?.message || t('manual_order.toast_generic_error')
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }

  if (fetching) return <div className="p-6"><PageLoader /></div>

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{title}</h1>
        <button type="button" onClick={() => window.history.back()} className="btn-secondary text-sm">{t('common.back')}</button>
      </div>

      {showBranchSelector && (
        <div className="mb-4 bg-blue-50 border border-blue-200 rounded-xl p-4">
          <label className="label text-blue-900 font-medium mb-2 block">
            {t('manual_order.admin_branch_label')}
          </label>
          {branches.length === 0 ? (
            <p className="text-sm text-blue-700">{t('manual_order.admin_branch_loading')}</p>
          ) : (
            <select
              id="daily-order-branch"
              aria-label="Branch"
              value={selectedBranchId || ''}
              onChange={(e) => setSelectedBranchId(e.target.value ? parseInt(e.target.value, 10) : null)}
              className="input-field w-full md:w-96"
            >
              <option value="">{t('manual_order.admin_branch_select_placeholder')}</option>
              {branches.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.branch_name} ({b.branch_code})
                </option>
              ))}
            </select>
          )}
          <p className="text-xs text-blue-700 mt-2">
            {t('manual_order.admin_branch_note')}
          </p>
        </div>
      )}

      {showBranchSelector && !selectedBranchId && (
        <div className="mb-4 bg-yellow-50 border border-yellow-200 rounded-xl p-4 text-sm text-yellow-800">
          {t('manual_order.toast_branch_required') || 'ط§ط®طھط± ط§ظ„ظپط±ط¹ ط£ظˆظ„ظ‹ط§ ظ„طھط­ظ…ظٹظ„ ط£طµظ†ط§ظپ ط§ظ„ط·ظ„ط¨.'}
        </div>
      )}

      <div className="mb-4">
        <input
          type="text"
          placeholder={t('manual_order.search_placeholder')}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="input-field w-full md:w-80"
        />
      </div>

      <div className="card table-container mb-4 overflow-x-auto">
        <table className="table w-full text-sm border-collapse">
          <thead>
            <tr>
              <th>{t('manual_order.col_name')}</th>
              <th>{t('manual_order.col_code')}</th>
              <th className="w-32 text-center">مخزون الفرع</th>
              <th className="w-32 text-center">{t('manual_order.col_qty')}</th>
              <th className="w-48">{t('manual_order.col_note')}</th>
            </tr>
          </thead>
          <tbody>
            {filteredItems.map((item) => {
              const stock = branchStockByItem[item.id]
              const stockQty = stock ? Number(stock.current_qty || 0) : 0
              return (
                <tr key={item.id} className={parseFloat(quantities[item.id] || 0) > 0 ? 'bg-blue-50' : ''}>
                  <td className="font-medium">{nameOf(item) || item.item_code}</td>
                  <td className="font-mono text-xs text-gray-600">{safeItemText(item.item_code)}</td>
                  <td className={`text-center font-semibold ${stockQty <= 0 ? 'text-red-600' : stockQty <= Number(stock?.reorder_point || 0) ? 'text-amber-600' : 'text-gray-900'}`}>
                    {stock ? stockQty.toLocaleString(undefined, { maximumFractionDigits: 2 }) : '0'}
                  </td>
                  <td>
                    <input
                      type="number"
                      min="0"
                      step="0.5"
                      value={quantities[item.id] || ''}
                      onChange={(e) => setQuantities((p) => ({
                        ...p, [item.id]: e.target.value,
                      }))}
                      className="border rounded px-2 py-1 w-full text-center text-sm focus:ring-2 focus:ring-blue-300"
                      placeholder="0"
                    />
                  </td>
                  <td>
                    <input
                      type="text"
                      value={lineNotes[item.id] || ''}
                      onChange={(e) => setLineNotes((p) => ({
                        ...p, [item.id]: e.target.value,
                      }))}
                      className="border rounded px-2 py-1 w-full text-sm focus:ring-2 focus:ring-blue-300"
                      placeholder={t('manual_order.note_placeholder')}
                    />
                  </td>
                </tr>
              )
            })}
            {filteredItems.length === 0 && (
              <tr>
                <td colSpan={5} className="text-center text-gray-400 py-8">
                  {showBranchSelector && !selectedBranchId
                    ? (t('manual_order.admin_branch_select_placeholder') || 'ط§ط®طھط± ط§ظ„ظپط±ط¹ ط£ظˆظ„ظ‹ط§')
                    : (t('branch_stock.empty') || 'ظ„ط§ طھظˆط¬ط¯ ط¨ظٹط§ظ†ط§طھ')}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="mb-6">
        <label className="label">{t('manual_order.order_notes_label')}</label>
        <textarea
          value={orderNotes}
          onChange={(e) => setOrderNotes(e.target.value)}
          className="input-field min-h-20 w-full"
          placeholder={t('manual_order.order_notes_placeholder')}
        />
      </div>

      <div className="flex items-center justify-between">
        <span className="text-sm text-gray-500">
          {t('manual_order.selected_count', { count: Object.values(quantities).filter((v) => parseFloat(v || 0) > 0).length })}
        </span>
        <div className="flex gap-3">
          <button type="button" onClick={() => window.history.back()} className="btn-secondary">{t('common.cancel')}</button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={loading}
            className="btn-primary"
          >
            {loading
              ? t('manual_order.submitting')
              : (isDaily ? t('manual_order.submit_daily') : t('manual_order.submit_exceptional'))}
          </button>
        </div>
      </div>
    </div>
  )
}

// â”€â”€â”€ Inter-branch stock transfer page â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// طھط­ظˆظٹظ„ ظ…ط®ط²ظˆظ† ظ…ط¨ط§ط´ط± (ظپظˆط±ظٹطŒ ط¨ط¯ظˆظ† workflow ظ…ظˆط§ظپظ‚ط©) ظ…ظ† ظپط±ط¹ ظ„ظپط±ط¹.
// ط§ظ„طµظ„ط§ط­ظٹط© (backend): area_manager / operations_manager / admin / super_admin.
// ط§ظ„ظ€ API: POST /api/v1/orders/inter-branch (ط·ظ„ط¨ طھط­ظˆظٹظ„ ط¨ط§ظ†طھط¸ط§ط± ظ…ظˆط§ظپظ‚ط© ظ…ط¯ظٹط± ط§ظ„ظ…ظ†ط·ظ‚ط©ط› ظ„ظٹط³ طھط­ظˆظٹظ„ ط§ظ„ظ…ط®ط²ظˆظ† ط§ظ„ظ…ط¨ط§ط´ط±)
function InterBranchTransferPage() {
  const t = useT()
  const { lang } = useLanguage()
  const roles = useSelector(selectUserRoles)
  const user = useSelector(selectUser)
  const allowed = roles.some((r) =>
    ['branch_manager', 'operations_manager', 'admin', 'super_admin'].includes(r)
  )
  const isElevated = roles.some((r) => ['admin', 'super_admin', 'operations_manager'].includes(r))
  const nameOf = (obj, base = 'item_name') =>
    obj?.[`${base}_${lang}`] || obj?.[`${base}_ar`] || obj?.[base] || ''

  const [branches, setBranches] = React.useState([])
  // branch_manager ظ…ظ‚ظپظ„ ط¹ظ„ظ‰ ظپط±ط¹ظ‡ط› ط§ظ„ط¥ط¯ط§ط±ظٹظˆظ† ظٹط®طھط§ط±ظˆظ† ظپط±ط¹ ط§ظ„ظ…طµط¯ط±
  const [sourceBranchId, setSourceBranchId] = React.useState('')
  const [destBranchId, setDestBranchId] = React.useState('')
  const [sourceStock, setSourceStock] = React.useState([])
  const [loadingStock, setLoadingStock] = React.useState(false)
  // ظƒظ„ طµظ†ظپ = { item_id, qty }
  const [lines, setLines] = React.useState([{ item_id: '', qty: '' }])
  const [reason, setReason] = React.useState('')
  const [referenceNo, setReferenceNo] = React.useState('')
  const [notes, setNotes] = React.useState('')
  const [submitting, setSubmitting] = React.useState(false)
  const [history, setHistory] = React.useState([]) // ط·ظ„ط¨ط§طھ ط£ظڈظ†ط´ط¦طھ ظپظٹ ظ‡ط°ظ‡ ط§ظ„ط¬ظ„ط³ط©

  // ط­ظ…ظ‘ظ„ ط§ظ„ظپط±ظˆط¹ + ط¥ط°ط§ ظƒط§ظ† branch_manager ط§ط³طھط®ط¯ظ… ظپط±ط¹ظ‡ ظƒظ…طµط¯ط±
  React.useEffect(() => {
    import('./services/api').then(({ masterApi }) => {
      masterApi.listBranches({ active_only: true }).then((r) => {
        const list = Array.isArray(r.data) ? r.data : (r.data?.items || [])
        setBranches(list)
      }).catch(() => { /* ط±ط³ط§ط¦ظ„ ط§ظ„ط®ط·ط£ ط³طھط¸ظ‡ط± ط¹ظ†ط¯ ط§ظ„ظ€ submit */ })
    })

    // branch_manager: ظپط±ط¹ ط§ظ„ظ…طµط¯ط± = ظپط±ط¹ظ‡ (ظ…ظ‚ظپظ„)
    if (!isElevated && user?.branch_id) {
      setSourceBranchId(String(user.branch_id))
    }
  }, [isElevated, user?.branch_id])

  // ظ„ظ…ط§ ظٹطھط­ط¯ط¯ ظپط±ط¹ ط§ظ„ظ…طµط¯ط±طŒ ط­ظ…ظ‘ظ„ ظ…ط®ط²ظˆظ†ظ‡
  React.useEffect(() => {
    if (!sourceBranchId) {
      setSourceStock([])
      return
    }
    setLoadingStock(true)
    import('./services/api').then(({ dashboardApi }) => {
      dashboardApi.branchStock(sourceBranchId)
        .then((r) => {
          const list = Array.isArray(r.data) ? r.data : []
          setSourceStock(list.filter((s) => parseFloat(s.current_qty) > 0))
        })
        .catch(() => setSourceStock([]))
        .finally(() => setLoadingStock(false))
    })
  }, [sourceBranchId])

  // â€” Helpers ظ„ظ„ظ€ lines â€”
  const updateLine = (idx, patch) => {
    setLines((arr) => arr.map((l, i) => (i === idx ? { ...l, ...patch } : l)))
  }
  const addLine = () => setLines((arr) => [...arr, { item_id: '', qty: '' }])
  const removeLine = (idx) => setLines((arr) => (arr.length > 1 ? arr.filter((_, i) => i !== idx) : arr))

  const getAvailableQty = (itemId) => {
    const row = sourceStock.find((s) => String(s.item_id) === String(itemId))
    return row ? parseFloat(row.current_qty) : 0
  }

  // validation: ط³ط·ط± طµط§ظ„ط­ = طµظ†ظپ ظ…ط®طھط§ط± + ظƒظ…ظٹط© > 0 + <= ط§ظ„ظ…طھط§ط­
  const validLines = lines.filter((l) => l.item_id && parseFloat(l.qty) > 0)
  const anyOverStock = lines.some(
    (l) => l.item_id && parseFloat(l.qty) > 0 && parseFloat(l.qty) > getAvailableQty(l.item_id)
  )
  const duplicateItem = (() => {
    const seen = new Set()
    for (const l of lines) {
      if (!l.item_id) continue
      if (seen.has(String(l.item_id))) return true
      seen.add(String(l.item_id))
    }
    return false
  })()

  const canSubmit =
    sourceBranchId &&
    destBranchId &&
    sourceBranchId !== destBranchId &&
    validLines.length > 0 &&
    !anyOverStock &&
    !duplicateItem &&
    reason.trim().length >= 3 &&
    !submitting

  const resetForm = () => {
    setLines([{ item_id: '', qty: '' }])
    setReason('')
    setReferenceNo('')
    setNotes('')
  }

  const handleSubmit = async () => {
    const { default: toast } = await import('react-hot-toast')

    if (sourceBranchId === destBranchId) {
      toast.error(t('inter_branch.tx_same_branch_error'))
      return
    }
    if (validLines.length === 0) {
      toast.error(t('inter_branch.tx_empty_lines_toast'))
      return
    }
    if (duplicateItem) {
      toast.error(t('inter_branch.tx_duplicate_item'))
      return
    }
    if (anyOverStock) {
      toast.error(t('inter_branch.tx_over_available'))
      return
    }
    if (reason.trim().length < 3) {
      toast.error(t('inter_branch.tx_reason_required_toast'))
      return
    }

    setSubmitting(true)
    try {
      const { ordersApi } = await import('./services/api')
      const payload = {
        destination_branch_id: parseInt(destBranchId, 10),
        items: validLines.map((l) => ({
          item_id: parseInt(l.item_id, 10),
          qty: parseFloat(l.qty),
        })),
        reason: reason.trim(),
        reference_no: referenceNo.trim() || null,
        notes: notes.trim() || null,
      }
      // ط§ظ„ط¥ط¯ط§ط±ظٹظˆظ† ظ…ظ…ظƒظ† ظٹط­ط¯ط¯ظˆط§ ظ…طµط¯ط± ظ…ط®طھظ„ظپ ط¹ظ† ظپط±ط¹ظ‡ظ…
      if (isElevated) {
        payload.source_branch_id = parseInt(sourceBranchId, 10)
      }
      const { data } = await ordersApi.createInterBranch(payload)

      const dst = branches.find((b) => b.id === parseInt(destBranchId, 10))
      toast.success(t('inter_branch.tx_submitted_toast'))
      setHistory((h) => [
        {
          at: new Date().toLocaleTimeString(lang === 'en' ? 'en-US' : 'ar-EG'),
          order_no: data?.order_no || 'â€”',
          dst: dst?.branch_name || destBranchId,
          lines_count: validLines.length,
          status: data?.status || 'area_manager_review',
        },
        ...h.slice(0, 9),
      ])
      resetForm()
    } catch (err) {
      const data = err?.response?.data
      const det = data?.detail
      const detMsg = Array.isArray(det)
        ? det.map((e) => (typeof e === 'object' && e != null ? (e.msg || JSON.stringify(e)) : String(e))).join(' â€” ')
        : (typeof det === 'object' && det != null && Object.keys(det).length > 0
            ? JSON.stringify(det)
            : (typeof det === 'string' ? det : ''))
      const msg = data?.message || detMsg || err?.message || t('common.error_generic')
      toast.error(msg)
    } finally {
      setSubmitting(false)
    }
  }

  if (!allowed) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded-xl p-6">
          <h1 className="text-xl font-bold text-red-900 mb-2">{t('inter_branch.tx_unauthorized_title')}</h1>
          <p className="text-sm text-red-700">
            {t('inter_branch.tx_unauthorized_body')}
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{t('inter_branch.tx_title')}</h1>
        <button type="button" onClick={() => window.history.back()} className="btn-secondary text-sm">
          {t('common.back')}
        </button>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 mb-6 text-sm text-blue-800">
        {t('inter_branch.tx_banner')}
      </div>

      <div className="card p-6 space-y-5">
        {/* ط§ظ„ظ…طµط¯ط± ظˆط§ظ„ظ…ظ‚طµط¯ */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="label">{t('inter_branch.tx_source_label')} <span className="text-red-600">*</span></label>
            {isElevated ? (
              <select
                value={sourceBranchId}
                onChange={(e) => setSourceBranchId(e.target.value)}
                className="input-field w-full"
              >
                <option value="">{t('inter_branch.tx_source_placeholder')}</option>
                {branches.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.branch_name} ({b.branch_code})
                  </option>
                ))}
              </select>
            ) : (
              <input
                type="text"
                readOnly
                value={
                  branches.find((b) => String(b.id) === String(sourceBranchId))?.branch_name || 'â€”'
                }
                className="input-field w-full bg-gray-50"
              />
            )}
          </div>
          <div>
            <label className="label">{t('inter_branch.tx_dest_label')} <span className="text-red-600">*</span></label>
            <select
              value={destBranchId}
              onChange={(e) => setDestBranchId(e.target.value)}
              className="input-field w-full"
            >
              <option value="">{t('inter_branch.tx_dest_placeholder')}</option>
              {branches
                .filter((b) => String(b.id) !== String(sourceBranchId))
                .map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.branch_name} ({b.branch_code})
                  </option>
                ))}
            </select>
            {sourceBranchId && destBranchId && sourceBranchId === destBranchId && (
              <p className="text-xs text-red-600 mt-1">{t('inter_branch.tx_same_branch_error')}</p>
            )}
          </div>
        </div>

        {/* ط§ظ„ط£طµظ†ط§ظپ (ظ…طھط¹ط¯ط¯) */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="label m-0">{t('inter_branch.tx_items_label')} <span className="text-red-600">*</span></label>
            <button
              type="button"
              onClick={addLine}
              className="text-xs text-primary-600 hover:underline"
              disabled={!sourceBranchId}
            >
              + {t('inter_branch.tx_add_item')}
            </button>
          </div>

          {!sourceBranchId ? (
            <p className="text-sm text-gray-400">{t('inter_branch.tx_pick_source_first')}</p>
          ) : loadingStock ? (
            <p className="text-sm text-gray-500">{t('inter_branch.tx_loading_source_stock')}</p>
          ) : sourceStock.length === 0 ? (
            <p className="text-sm text-orange-600">{t('inter_branch.tx_no_stock_at_source')}</p>
          ) : (
            <div className="space-y-2">
              {lines.map((line, idx) => {
                const available = line.item_id ? getAvailableQty(line.item_id) : 0
                const qtyNum = parseFloat(line.qty) || 0
                const overStock = line.item_id && qtyNum > 0 && qtyNum > available
                return (
                  <div key={idx} className="grid grid-cols-[1fr_140px_auto] gap-2 items-start">
                    <select
                      value={line.item_id}
                      onChange={(e) => updateLine(idx, { item_id: e.target.value, qty: '' })}
                      className="input-field w-full"
                    >
                      <option value="">{t('inter_branch.tx_select_item')}</option>
                      {sourceStock
                        .filter((s) => {
                          // ط§ط³طھط¨ط¹ط¯ ط§ظ„ط£طµظ†ط§ظپ ط§ظ„ظ…ط®طھط§ط±ط© ظپظٹ ط§ظ„ط£ط³ط·ط± ط§ظ„ط£ط®ط±ظ‰
                          const pickedElsewhere = lines.some(
                            (l, i) => i !== idx && String(l.item_id) === String(s.item_id)
                          )
                          return !pickedElsewhere
                        })
                        .map((s) => (
                          <option key={s.item_id} value={s.item_id}>
                            {nameOf(s) || s.item_code} â€” {t('inter_branch.tx_available')}: {parseFloat(s.current_qty)}
                          </option>
                        ))}
                    </select>
                    <div>
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={line.qty}
                        onChange={(e) => updateLine(idx, { qty: e.target.value })}
                        disabled={!line.item_id}
                        className={`input-field w-full ${overStock ? 'border-red-500' : ''}`}
                        placeholder={t('inter_branch.tx_qty_placeholder')}
                      />
                      {line.item_id && (
                        <p className={`text-xs mt-1 ${overStock ? 'text-red-600' : 'text-gray-500'}`}>
                          {overStock ? `${t('inter_branch.tx_over_available')} (${available})` : `${t('inter_branch.tx_available')}: ${available}`}
                        </p>
                      )}
                    </div>
                    <button
                      type="button"
                      onClick={() => removeLine(idx)}
                      disabled={lines.length <= 1}
                      className="p-2 text-red-600 hover:bg-red-50 rounded disabled:opacity-30 disabled:cursor-not-allowed"
                      title={t('common.delete')}
                    >
                      أ—
                    </button>
                  </div>
                )
              })}
            </div>
          )}
          {duplicateItem && (
            <p className="text-xs text-red-600 mt-2">{t('inter_branch.tx_duplicate_item')}</p>
          )}
        </div>

        {/* ط§ظ„ط³ط¨ط¨ ظˆط§ظ„ظ…ط±ط¬ط¹ ظˆط§ظ„ظ…ظ„ط§ط­ط¸ط§طھ */}
        <div>
          <label className="label">{t('inter_branch.tx_reason_label')} <span className="text-red-600">*</span></label>
          <input
            type="text"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className="input-field w-full"
            placeholder={t('inter_branch.tx_reason_placeholder')}
            minLength={3}
          />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="label">{t('inter_branch.tx_reference_label')}</label>
            <input
              type="text"
              value={referenceNo}
              onChange={(e) => setReferenceNo(e.target.value)}
              className="input-field w-full"
              placeholder={t('inter_branch.tx_reference_placeholder')}
            />
          </div>
          <div>
            <label className="label">{t('inter_branch.tx_notes_label')}</label>
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="input-field w-full"
              placeholder={t('inter_branch.tx_notes_placeholder')}
            />
          </div>
        </div>

        <div className="flex items-center justify-between pt-2 border-t border-gray-100">
          <span className="text-xs text-gray-500">
            {!canSubmit && t('inter_branch.tx_validation_hint')}
          </span>
          <div className="flex gap-3">
            <button type="button" onClick={resetForm} className="btn-secondary" disabled={submitting}>
              {t('inter_branch.tx_clear')}
            </button>
            <button
              type="button"
              onClick={handleSubmit}
              disabled={!canSubmit}
              className="btn-primary"
            >
              {submitting ? t('inter_branch.tx_submitting') : t('inter_branch.tx_submit')}
            </button>
          </div>
        </div>
      </div>

      {/* ط·ظ„ط¨ط§طھ طھظ… ط¥ط±ط³ط§ظ„ظ‡ط§ ظپظٹ ظ‡ط°ظ‡ ط§ظ„ط¬ظ„ط³ط© */}
      {history.length > 0 && (
        <div className="mt-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-2">{t('inter_branch.tx_history_title')}</h2>
          <div className="card table-container">
            <table className="table text-sm">
              <thead>
                <tr>
                  <th>{t('inter_branch.tx_col_time')}</th>
                  <th>{t('inter_branch.tx_col_order')}</th>
                  <th>{t('inter_branch.tx_col_to')}</th>
                  <th className="text-center">{t('inter_branch.tx_col_lines')}</th>
                  <th>{t('inter_branch.tx_col_status')}</th>
                </tr>
              </thead>
              <tbody>
                {history.map((h, i) => (
                  <tr key={i}>
                    <td className="text-gray-500">{h.at}</td>
                    <td className="font-mono text-xs">{h.order_no}</td>
                    <td>{h.dst}</td>
                    <td className="text-center font-bold">{h.lines_count}</td>
                    <td>
                      <span className="inline-block px-2 py-0.5 rounded bg-amber-50 text-amber-700 text-xs">
                        {t('inter_branch.tx_awaiting_approval')}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}


// طµظپط­ط© ظ…ط¯ظٹط± ط§ظ„ظ…ظ†ط·ظ‚ط© ظ„ظ…ط±ط§ط¬ط¹ط© ط·ظ„ط¨ط§طھ ط§ظ„طھط­ظˆظٹظ„ ظˆطھظپط¹ظٹظ„ظ‡ط§/ط±ظپط¶ظ‡ط§
function InterBranchPendingApprovalsPage() {
  const t = useT()
  const { lang } = useLanguage()
  const roles = useSelector(selectUserRoles)
  const allowed = roles.some((r) =>
    ['area_manager', 'operations_manager', 'admin', 'super_admin'].includes(r)
  )
  const nameOf = (obj, base = 'item_name') =>
    obj?.[`${base}_${lang}`] || obj?.[`${base}_ar`] || obj?.[base] || ''

  const [orders, setOrders] = React.useState([])
  const [loading, setLoading] = React.useState(true)
  const [workingId, setWorkingId] = React.useState(null)
  const [rejectingId, setRejectingId] = React.useState(null)
  const [rejectReason, setRejectReason] = React.useState('')

  const load = React.useCallback(async () => {
    setLoading(true)
    try {
      const { ordersApi } = await import('./services/api')
      const { data } = await ordersApi.listPendingInterBranch()
      setOrders(Array.isArray(data) ? data : [])
    } catch {
      setOrders([])
    } finally {
      setLoading(false)
    }
  }, [])

  React.useEffect(() => { load() }, [load])

  const handleApprove = async (id) => {
    const { default: toast } = await import('react-hot-toast')
    if (!window.confirm(t('inter_branch.approvals_confirm_approve'))) return
    setWorkingId(id)
    try {
      const { ordersApi } = await import('./services/api')
      await ordersApi.approveInterBranch(id, {})
      toast.success(t('inter_branch.approvals_approved_toast'))
      await load()
    } catch (err) {
      const data = err?.response?.data
      toast.error(data?.message || err?.message || t('inter_branch.approvals_approve_error'))
    } finally {
      setWorkingId(null)
    }
  }

  const handleReject = async (id) => {
    const { default: toast } = await import('react-hot-toast')
    if (rejectReason.trim().length < 3) {
      toast.error(t('inter_branch.approvals_reject_required'))
      return
    }
    setWorkingId(id)
    try {
      const { ordersApi } = await import('./services/api')
      await ordersApi.rejectInterBranch(id, rejectReason.trim())
      toast.success(t('inter_branch.approvals_rejected_toast'))
      setRejectingId(null)
      setRejectReason('')
      await load()
    } catch (err) {
      const data = err?.response?.data
      toast.error(data?.message || err?.message || t('inter_branch.approvals_reject_error'))
    } finally {
      setWorkingId(null)
    }
  }

  if (!allowed) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded-xl p-6">
          <h1 className="text-xl font-bold text-red-900 mb-2">{t('inter_branch.tx_unauthorized_title')}</h1>
          <p className="text-sm text-red-700">
            {t('inter_branch.approvals_unauthorized_body')}
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{t('inter_branch.approvals_title')}</h1>
        <button type="button" onClick={load} className="btn-secondary text-sm">{t('inter_branch.approvals_refresh')}</button>
      </div>

      {loading ? (
        <p className="text-gray-500">{t('inter_branch.approvals_loading')}</p>
      ) : orders.length === 0 ? (
        <div className="card p-8 text-center text-gray-500">
          {t('inter_branch.approvals_empty')}
        </div>
      ) : (
        <div className="space-y-3">
          {orders.map((o) => (
            <div key={o.id} className="card p-4">
              <div className="flex items-start justify-between flex-wrap gap-3">
                <div>
                  <div className="flex items-center gap-3 mb-1">
                    <span className="font-mono text-xs text-gray-500">{o.order_no}</span>
                    <span className="text-xs bg-amber-50 text-amber-700 px-2 py-0.5 rounded">
                      {t('inter_branch.tx_awaiting_approval')}
                    </span>
                  </div>
                  <div className="text-sm text-gray-900">
                    <b>{t('inter_branch.approvals_from')}:</b> {o.source_branch_name || o.source_branch_id}
                    <span className="mx-2 text-gray-400">â†گ</span>
                    <b>{t('inter_branch.approvals_to')}:</b> {o.destination_branch_name || o.destination_branch_id}
                  </div>
                  {o.reason && (
                    <p className="text-sm text-gray-600 mt-1"><b>{t('inter_branch.approvals_reason')}:</b> {o.reason}</p>
                  )}
                  {o.reference_no && (
                    <p className="text-xs text-gray-500 mt-0.5">{t('inter_branch.approvals_reference')}: {o.reference_no}</p>
                  )}
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => handleApprove(o.id)}
                    disabled={workingId === o.id}
                    className="btn-primary text-sm"
                  >
                    {workingId === o.id ? t('inter_branch.approvals_working') : t('inter_branch.approvals_approve_execute')}
                  </button>
                  <button
                    type="button"
                    onClick={() => { setRejectingId(o.id); setRejectReason('') }}
                    disabled={workingId === o.id}
                    className="btn-secondary text-sm text-red-600"
                  >
                    {t('inter_branch.approvals_reject')}
                  </button>
                </div>
              </div>

              {o.lines && o.lines.length > 0 && (
                <div className="mt-3 border-t border-gray-100 pt-3">
                  <table className="w-full text-sm">
                    <thead className="text-gray-500 text-xs">
                      <tr>
                        <th className="font-normal">{t('inter_branch.approvals_col_code')}</th>
                        <th className="font-normal">{t('inter_branch.approvals_col_item')}</th>
                        <th className="font-normal">{t('inter_branch.approvals_col_qty')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {o.lines.map((l) => (
                        <tr key={l.id}>
                          <td className="font-mono text-xs text-gray-500">{l.item_code}</td>
                          <td>{nameOf(l)}</td>
                          <td className="font-semibold">{l.qty}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {rejectingId === o.id && (
                <div className="mt-3 border-t border-gray-100 pt-3">
                  <label className="label">{t('inter_branch.approvals_reject_reason_label')} <span className="text-red-600">*</span></label>
                  <textarea
                    value={rejectReason}
                    onChange={(e) => setRejectReason(e.target.value)}
                    className="input-field w-full"
                    rows={2}
                    placeholder={t('inter_branch.approvals_reject_reason_placeholder')}
                  />
                  <div className="flex justify-end gap-2 mt-2">
                    <button
                      type="button"
                      onClick={() => { setRejectingId(null); setRejectReason('') }}
                      className="btn-secondary text-sm"
                    >
                      {t('inter_branch.approvals_reject_cancel')}
                    </button>
                    <button
                      type="button"
                      onClick={() => handleReject(o.id)}
                      disabled={workingId === o.id || rejectReason.trim().length < 3}
                      className="btn-primary text-sm bg-red-600 hover:bg-red-700"
                    >
                      {t('inter_branch.approvals_reject_confirm')}
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}


// â”€â”€â”€ Notifications full-page view â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function NotificationsPage() {
  const t = useT()
  const [data, setData] = React.useState({ total: 0, sections: [] })
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState(null)

  const load = React.useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const r = await notificationsApi.list({ limit: 50 })
      setData(r.data || { total: 0, sections: [] })
    } catch (_e) {
      setError(t('common.error_generic'))
    } finally {
      setLoading(false)
    }
  }, [t])

  React.useEffect(() => { load() }, [load])

  const nonEmpty = (data.sections || []).filter((s) => (s.count || 0) > 0)

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-gray-900">{t('notifications.details_title')}</h1>
        <button
          onClick={load}
          className="text-sm px-3 py-1.5 rounded-lg bg-gray-100 hover:bg-gray-200"
        >
          {t('common.refresh')}
        </button>
      </div>

      {loading && <p className="text-sm text-gray-500">{t('common.loading')}</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {!loading && !error && nonEmpty.length === 0 && (
        <div className="p-10 text-center text-gray-500 bg-white rounded-xl border border-gray-100">
          {t('notifications.empty')}
        </div>
      )}

      <div className="space-y-5">
        {nonEmpty.map((section) => (
          <div key={section.key} className="bg-white rounded-xl border border-gray-100 overflow-hidden">
            <div className="flex items-center justify-between px-5 py-3 border-b border-gray-50">
              <Link
                to={section.target_url || '#'}
                className="font-semibold text-gray-900 hover:text-primary-700"
              >
                {t(`notifications.${section.key}`)}
              </Link>
              <span className="text-xs font-bold bg-primary-100 text-primary-700 rounded-full px-2.5 py-0.5">
                {section.count}
              </span>
            </div>
            <ul className="divide-y divide-gray-50">
              {(section.items || []).map((it, idx) => (
                <li key={`${section.key}-${idx}`} className="px-5 py-2 hover:bg-gray-50">
                  <Link
                    to={it.target_url || section.target_url || '#'}
                    className="flex items-center justify-between text-sm"
                  >
                    <span className="text-gray-800">
                      {it.order_no || it.inventory_date || it.visit_date || it.assessment_date || `#${it.id ?? ''}`}
                    </span>
                    {it.status && (
                      <span className="text-xs text-gray-500">
                        {t(`order_status.${it.status}`)}
                      </span>
                    )}
                  </Link>
                </li>
              ))}
              {section.count > (section.items?.length || 0) && (
                <li className="px-5 py-2 text-center text-xs text-gray-400">
                  â€¦
                </li>
              )}
            </ul>
          </div>
        ))}
      </div>
    </div>
  )
}


// Protected route wrapper
function ProtectedRoute({ children }) {
  const isAuth = useSelector(selectIsAuthenticated)
  if (!isAuth) return <Navigate to="/login" replace />
  return children
}

// Smart dashboard selector based on role
function SmartDashboard() {
  const roles = useSelector(selectUserRoles)
  if (roles.includes('super_admin')) return <Navigate to="/supply-chain/control" replace />
  if (roles.includes('internal_auditor')) return <Navigate to="/audit/dashboard" replace />
  if (roles.includes('branch_user') || roles.includes('branch_manager')) return <BranchDashboard />
  if (roles.includes('warehouse_user') || roles.includes('warehouse_manager')) return <WarehouseDashboard />
  if (roles.includes('operations_manager')) return <OperationsDashboard />
  if (roles.includes('admin')) return <OperationsDashboard />
  return <BranchDashboard />
}

function AppRoutes() {
  const isAuth = useSelector(selectIsAuthenticated)

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={isAuth ? <Navigate to="/dashboard" /> : <LoginPage />} />
        <Route path="/" element={<Navigate to="/dashboard" />} />

        <Route element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
          <Route path="/dashboard" element={<SmartDashboard />} />

          {/* Branch */}
          <Route path="/inventory" element={<InventoryListPage />} />
          <Route path="/inventory/new" element={<InventoryEntryPage />} />
          <Route path="/inventory/:id" element={<InventoryEntryPage />} />
          <Route path="/orders" element={<OrdersListPage />} />
          <Route path="/orders/exceptional" element={<ManualOrderPage orderType="exceptional" />} />
          <Route
            path="/orders/daily"
            element={(
              <RouteRoleGuard allowed={['branch_manager', 'admin', 'super_admin']}>
                <ManualOrderPage orderType="daily_order" />
              </RouteRoleGuard>
            )}
          />
          <Route path="/orders/:id" element={<OrderDetailPage />} />
          <Route path="/receiving" element={<OrdersListPage receiveView />} />
          <Route path="/receiving/:id" element={<ReceivingPage />} />
          <Route path="/branch-stock" element={<BranchStockPage />} />
          <Route path="/branch-employees" element={<RouteRoleGuard allowed={['branch_manager', 'admin', 'super_admin']}><BranchEmployeesPage /></RouteRoleGuard>} />

          {/* Warehouse */}
          <Route path="/warehouse/orders" element={<OrdersListPage warehouseView />} />
          <Route path="/warehouse/orders/:id" element={<OrderDetailPage warehouseView />} />
          <Route path="/warehouse/picking" element={<OrdersListPage warehouseView pickingView />} />
          <Route path="/warehouse/dispatch" element={<OrdersListPage warehouseView dispatchView />} />
          <Route path="/warehouse/stock" element={<WarehouseStockPage />} />
          <Route path="/warehouse/reports" element={<WarehouseDashboard />} />

          {/* Inter-branch transfer â€” ط·ظ„ط¨ ظ…ظ† ظ…ط¯ظٹط± ط§ظ„ظپط±ط¹طŒ ط¨ط§ظ†طھط¸ط§ط± ظ…ظˆط§ظپظ‚ط© ظ…ط¯ظٹط± ط§ظ„ظ…ظ†ط·ظ‚ط© */}
          <Route path="/stock/inter-branch-transfer" element={<RouteRoleGuard allowed={['branch_manager', 'area_manager', 'operations_manager', 'admin', 'super_admin']}><InterBranchTransferPage /></RouteRoleGuard>} />

          {/* Operations */}
          <Route
            path="/operations"
            element={(
              <RouteRoleGuard allowed={['operations_manager', 'admin', 'super_admin']}>
                <OperationsDashboard />
              </RouteRoleGuard>
            )}
          />
          <Route
            path="/operations/inter-branch-approvals"
            element={(
              <RouteRoleGuard allowed={['area_manager', 'operations_manager', 'admin', 'super_admin']}>
                <InterBranchPendingApprovalsPage />
              </RouteRoleGuard>
            )}
          />
          <Route path="/operations/branch-items" element={<RouteRoleGuard allowed={['area_manager', 'admin', 'super_admin']}><AreaBranchItemsPage /></RouteRoleGuard>} />
          {/* Notifications â€” ظ„ظƒظ„ ط§ظ„ط£ط¯ظˆط§ط± */}
          <Route path="/notifications" element={<NotificationsPage />} />
          <Route
            path="/reports/inventory"
            element={(
              <RouteRoleGuard allowed={['operations_manager', 'warehouse_manager', 'area_manager', 'admin', 'super_admin']}>
                <InventoryListPage />
              </RouteRoleGuard>
            )}
          />
          <Route
            path="/reports/orders"
            element={(
              <RouteRoleGuard allowed={['operations_manager', 'admin', 'super_admin']}>
                <OrdersListPage />
              </RouteRoleGuard>
            )}
          />

          {/* Delivery Analytics â€” ط£ط¯ظˆط§ط± ظ…طھظˆط§ظپظ‚ط© ظ…ط¹ AppLayoutV2 */}
          <Route path="/delivery" element={<RouteRoleGuard allowed={['sales_manager', 'operations_manager', 'area_manager', 'admin', 'super_admin']}><DeliveryDashboardPage /></RouteRoleGuard>} />
          <Route path="/delivery/daily-entry" element={<RouteRoleGuard allowed={['branch_manager', 'sales_manager', 'area_manager', 'admin', 'super_admin']}><SalesChannelsDailyEntryPage /></RouteRoleGuard>} />
          <Route path="/delivery/statements" element={<RouteRoleGuard allowed={['sales_manager', 'admin', 'super_admin']}><SalesChannelsStatementsPage /></RouteRoleGuard>} />
          <Route path="/delivery/reconciliation" element={<RouteRoleGuard allowed={['branch_manager', 'area_manager', 'operations_manager', 'sales_manager', 'internal_auditor', 'admin', 'super_admin']}><SalesChannelsReconciliationPage /></RouteRoleGuard>} />
          <Route path="/delivery/closures" element={<RouteRoleGuard allowed={['sales_manager', 'admin', 'super_admin']}><SalesChannelsClosuresPage /></RouteRoleGuard>} />
          <Route path="/delivery/compliance" element={<RouteRoleGuard allowed={['branch_manager', 'area_manager', 'operations_manager', 'sales_manager', 'internal_auditor', 'admin', 'super_admin']}><SalesChannelsCompliancePage /></RouteRoleGuard>} />
          <Route path="/delivery/import" element={<RouteRoleGuard allowed={['sales_manager', 'admin', 'super_admin']}><DeliveryImportPage /></RouteRoleGuard>} />
          <Route path="/delivery/branches" element={<RouteRoleGuard allowed={['sales_manager', 'admin', 'super_admin']}><DeliveryBranchesManagementPage /></RouteRoleGuard>} />
          <Route path="/delivery/branch-stats" element={<RouteRoleGuard allowed={['sales_manager', 'operations_manager', 'area_manager', 'internal_auditor', 'admin', 'super_admin']}><DeliveryBranchStatsPage /></RouteRoleGuard>} />
          <Route path="/delivery/brands" element={<RouteRoleGuard allowed={['sales_manager', 'operations_manager', 'area_manager', 'internal_auditor', 'admin', 'super_admin']}><DeliveryBrandStatsPage /></RouteRoleGuard>} />
          <Route path="/delivery/unmatched" element={<RouteRoleGuard allowed={['sales_manager', 'admin', 'super_admin']}><DeliveryUnmatchedPage /></RouteRoleGuard>} />
          {/* Redirect ظ…ظ† ط§ظ„ظ…ط³ط§ط±ط§طھ ط§ظ„ظ‚ط¯ظٹظ…ط© */}
          <Route path="/delivery-analytics" element={<RouteRoleGuard allowed={['sales_manager', 'operations_manager', 'area_manager', 'admin', 'super_admin']}><DeliveryDashboardPage /></RouteRoleGuard>} />
          <Route path="/delivery-analytics/branches" element={<RouteRoleGuard allowed={['sales_manager', 'admin', 'super_admin']}><DeliveryBranchesManagementPage /></RouteRoleGuard>} />
          <Route path="/delivery-analytics/imports" element={<RouteRoleGuard allowed={['sales_manager', 'admin', 'super_admin']}><DeliveryImportPage /></RouteRoleGuard>} />

          {/* Quality */}
          <Route path="/quality" element={<RouteRoleGuard allowed={['quality_visitor', 'quality_manager', 'branch_manager', 'area_manager', 'internal_auditor', 'admin', 'super_admin']}><QualityVisitListPage /></RouteRoleGuard>} />
          <Route path="/quality/new" element={<RouteRoleGuard allowed={['quality_visitor', 'quality_manager', 'admin', 'super_admin']}><QualityVisitFormPage /></RouteRoleGuard>} />
          <Route path="/quality/open-actions" element={<RouteRoleGuard allowed={['quality_manager', 'branch_manager', 'area_manager', 'internal_auditor', 'admin', 'super_admin']}><QualityOpenActionsPage /></RouteRoleGuard>} />
          <Route path="/quality/analytics" element={<RouteRoleGuard allowed={['quality_manager', 'branch_manager', 'area_manager', 'internal_auditor', 'admin', 'super_admin']}><QualityAnalyticsPage /></RouteRoleGuard>} />
          <Route path="/quality/:id" element={<RouteRoleGuard allowed={['quality_visitor', 'quality_manager', 'branch_manager', 'area_manager', 'internal_auditor', 'admin', 'super_admin']}><QualityVisitDetailPage /></RouteRoleGuard>} />

          {/* Training */}
          <Route path="/training" element={<RouteRoleGuard allowed={['area_manager', 'branch_manager', 'quality_manager', 'operations_manager', 'internal_auditor', 'admin', 'super_admin']}><TrainingAssessmentListPage /></RouteRoleGuard>} />
          <Route path="/training/new" element={<RouteRoleGuard allowed={['area_manager', 'admin', 'super_admin']}><TrainingAssessmentFormPage /></RouteRoleGuard>} />
          <Route path="/training/analytics" element={<RouteRoleGuard allowed={['quality_manager', 'operations_manager', 'internal_auditor', 'admin', 'super_admin']}><TrainingAnalyticsPage /></RouteRoleGuard>} />
          <Route path="/training/:id" element={<RouteRoleGuard allowed={['area_manager', 'branch_manager', 'quality_manager', 'operations_manager', 'internal_auditor', 'admin', 'super_admin']}><TrainingAssessmentDetailPage /></RouteRoleGuard>} />

          {/* Internal audit */}
          <Route path="/audit/dashboard" element={<RouteRoleGuard allowed={['internal_auditor', 'admin', 'super_admin']}><AuditDashboardPage /></RouteRoleGuard>} />
          <Route path="/audit/daily-orders" element={<RouteRoleGuard allowed={['internal_auditor', 'admin', 'super_admin']}><OrdersListPage scopeAll showBranchColumn readOnly todayOnly orderType="daily_order" title="طلبيات اليوم لكل الفروع" subtitle="طلبات اليوم فقط مع حالة كل فرع." /></RouteRoleGuard>} />
          <Route path="/audit/order-history" element={<RouteRoleGuard allowed={['internal_auditor', 'admin', 'super_admin']}><OrdersListPage scopeAll showBranchColumn readOnly title="سجل الطلبيات" subtitle="أرشيف كل الطلبيات بكل الأنواع والتواريخ." /></RouteRoleGuard>} />
          <Route path="/audit/warehouse-stock" element={<RouteRoleGuard allowed={['internal_auditor', 'admin', 'super_admin']}><WarehouseStockPage readOnly title="مخزون مستودعات الرياض والدمام" subtitle="عرض قراءة فقط للمراجع الداخلي" /></RouteRoleGuard>} />
          <Route path="/audit/item-change-requests" element={<RouteRoleGuard allowed={['internal_auditor', 'admin', 'super_admin']}><ItemChangeRequestsPage /></RouteRoleGuard>} />
          <Route path="/audit/findings" element={<RouteRoleGuard allowed={['internal_auditor', 'admin', 'super_admin', 'area_manager', 'operations_manager']}><AuditFindingsPage /></RouteRoleGuard>} />
          <Route path="/audit/trail" element={<RouteRoleGuard allowed={['internal_auditor', 'admin', 'super_admin']}><AuditTrailPage /></RouteRoleGuard>} />

          {/* Supply Chain V1 demo screens */}
          <Route path="/supply-chain" element={<Navigate to="/supply-chain/control" replace />} />
          <Route path="/supply-chain/control" element={<RouteRoleGuard allowed={['branch_user', 'branch_manager', 'area_manager', 'kitchen_section_manager', 'warehouse_user', 'warehouse_manager', 'delivery_user', 'operations_manager', 'internal_auditor', 'admin', 'super_admin']}><SupplyChainControlDashboard /></RouteRoleGuard>} />
          <Route path="/supply-chain/branch-requests" element={<RouteRoleGuard allowed={['branch_user', 'branch_manager', 'area_manager', 'internal_auditor', 'admin', 'super_admin']}><SupplyChainBranchRequestsPage /></RouteRoleGuard>} />
          <Route path="/supply-chain/approvals" element={<RouteRoleGuard allowed={['area_manager', 'internal_auditor', 'admin', 'super_admin']}><SupplyChainApprovalsPage /></RouteRoleGuard>} />
          <Route path="/supply-chain/kitchen" element={<RouteRoleGuard allowed={['kitchen_section_manager', 'internal_auditor', 'admin', 'super_admin']}><SupplyChainKitchenPage /></RouteRoleGuard>} />
          <Route path="/supply-chain/warehouse" element={<RouteRoleGuard allowed={['warehouse_user', 'warehouse_manager', 'internal_auditor', 'admin', 'super_admin']}><SupplyChainWarehousePage /></RouteRoleGuard>} />
          <Route path="/supply-chain/delivery" element={<RouteRoleGuard allowed={['delivery_user', 'internal_auditor', 'admin', 'super_admin']}><SupplyChainDeliveryPage /></RouteRoleGuard>} />

          {/* Documents (Phase F3) */}
          <Route path="/documents" element={<RouteRoleGuard allowed={['admin', 'super_admin', 'area_manager', 'branch_manager', 'quality_manager', 'warehouse_manager', 'internal_auditor']}><DocumentsListPage /></RouteRoleGuard>} />
          <Route path="/documents/expiring" element={<RouteRoleGuard allowed={['admin', 'super_admin', 'area_manager', 'branch_manager', 'quality_manager', 'warehouse_manager', 'internal_auditor']}><DocumentsExpiringPage /></RouteRoleGuard>} />
          <Route path="/documents/new" element={<RouteRoleGuard allowed={['admin', 'super_admin', 'area_manager', 'branch_manager', 'quality_manager']}><DocumentFormPage /></RouteRoleGuard>} />
          <Route path="/documents/:id" element={<RouteRoleGuard allowed={['admin', 'super_admin', 'area_manager', 'branch_manager', 'quality_manager', 'warehouse_manager', 'internal_auditor']}><DocumentFormPage /></RouteRoleGuard>} />

          {/* Admin â€” طµظ„ط§ط­ظٹط§طھ ظ…ط³ط§ط±ط§طھ (ظٹطھظ… طھط¬ط§ظˆط²ظ‡ط§ ظ„ظ€ admin/super_admin ط¯ط§ط®ظ„ RouteRoleGuard) */}
          <Route path="/admin/users" element={<RouteRoleGuard allowed={['admin', 'super_admin']}><UsersManagementPage /></RouteRoleGuard>} />
          <Route path="/admin/items" element={<RouteRoleGuard allowed={['admin', 'super_admin']}><ItemsManagementPage /></RouteRoleGuard>} />
          <Route path="/admin/branches" element={<RouteRoleGuard allowed={['admin', 'super_admin']}><BranchesAdminPage /></RouteRoleGuard>} />
          <Route path="/admin/warehouses" element={<RouteRoleGuard allowed={['admin', 'super_admin']}><WarehousesAdminPage /></RouteRoleGuard>} />
          <Route path="/admin/kitchens" element={<RouteRoleGuard allowed={['admin', 'super_admin']}><KitchensAdminPage /></RouteRoleGuard>} />
          <Route path="/admin/suggestions" element={<RouteRoleGuard allowed={['admin', 'super_admin']}><AssistantSuggestionsPage /></RouteRoleGuard>} />
          <Route path="/admin/sales-channels" element={<RouteRoleGuard allowed={['sales_manager', 'admin', 'super_admin']}><SalesChannelsAdminPage /></RouteRoleGuard>} />
          <Route path="/admin/settings" element={<RouteRoleGuard allowed={['admin', 'super_admin']}><SettingsPage /></RouteRoleGuard>} />

          {/* Analytics (G5/G6/G7) */}
          <Route path="/analytics/consumption-trend" element={<RouteRoleGuard allowed={['branch_manager', 'warehouse_manager', 'area_manager', 'operations_manager', 'admin', 'super_admin']}><ConsumptionTrendPage /></RouteRoleGuard>} />
          <Route path="/analytics/order-delay" element={<RouteRoleGuard allowed={['operations_manager', 'warehouse_manager', 'area_manager', 'internal_auditor', 'admin', 'super_admin']}><OrderDelayAnalyticsPage /></RouteRoleGuard>} />
          <Route path="/analytics/branches-open-actions" element={<RouteRoleGuard allowed={['quality_manager', 'area_manager', 'operations_manager', 'internal_auditor', 'admin', 'super_admin']}><BranchesOpenActionsPage /></RouteRoleGuard>} />
        </Route>

        <Route path="*" element={<Navigate to="/dashboard" />} />
      </Routes>
    </BrowserRouter>
  )
}

// Inline simple admin pages
function BranchesAdminPage() {
  const t = useT()
  const [items, setItems] = React.useState([])
  const [warehouses, setWarehouses] = React.useState([])
  const [form, setForm] = React.useState({ branch_code:'', branch_name:'', city:'', area:'', warehouse_id:'', active:true })
  const [modal, setModal] = React.useState(false)
  const [editing, setEditing] = React.useState(null)

  React.useEffect(() => {
    import('./services/api').then(({ masterApi }) => {
      masterApi.listBranches().then((r) => {
        const d = r.data
        setItems(Array.isArray(d) ? d : (d?.items || []))
      })
      masterApi.listWarehouses().then((r) => {
        const d = r.data
        setWarehouses(Array.isArray(d) ? d : (d?.items || []))
      })
    })
  }, [])

  const reload = () => import('./services/api').then(({ masterApi }) => masterApi.listBranches().then((r) => {
    const d = r.data
    setItems(Array.isArray(d) ? d : (d?.items || []))
  }))

  const handleSave = async () => {
    const { masterApi } = await import('./services/api')
    const { default: toast } = await import('react-hot-toast')
    try {
      if (editing) { await masterApi.updateBranch(editing.id, form) }
      else { await masterApi.createBranch(form) }
      toast.success(t('admin.saved_toast')); setModal(false); reload()
    } catch (e) { toast.error(e?.response?.data?.detail || t('admin.error_generic')) }
  }

  const handleDelete = async (branch) => {
    const msg = t('admin.branches_confirm_delete', { name: branch.branch_name })
      || `ظ‡ظ„ ط£ظ†طھ ظ…طھط£ظƒط¯ ظ…ظ† ط­ط°ظپ ط§ظ„ظپط±ط¹ "${branch.branch_name}"طں`
    if (!window.confirm(msg)) return
    const { masterApi } = await import('./services/api')
    const { default: toast } = await import('react-hot-toast')
    try {
      await masterApi.deleteBranch(branch.id)
      toast.success(t('admin.branches_deleted_toast') || 'طھظ… ط­ط°ظپ ط§ظ„ظپط±ط¹')
      reload()
    } catch (e) {
      toast.error(e?.response?.data?.detail || e?.response?.data?.message || t('admin.branches_delete_error') || 'ظپط´ظ„ ط§ظ„ط­ط°ظپ')
    }
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">{t('admin.branches_title')}</h1>
        <button onClick={() => { setEditing(null); setForm({ branch_code:'', branch_name:'', city:'', area:'', warehouse_id: warehouses[0]?.id||'', active:true }); setModal(true) }} className="btn-primary">
          <span className="text-lg leading-none">+</span> {t('admin.branches_new')}
        </button>
      </div>
      <div className="card table-container">
        <table className="table">
          <thead><tr>
            <th>{t('admin.branches_col_code')}</th>
            <th>{t('admin.branches_col_name')}</th>
            <th>{t('admin.branches_col_city')}</th>
            <th>{t('admin.branches_col_area')}</th>
            <th>{t('admin.branches_col_warehouse')}</th>
            <th>{t('admin.branches_col_status')}</th>
            <th></th>
          </tr></thead>
          <tbody>
            {items.map((b) => (
              <tr key={b.id}>
                <td className="font-mono text-xs">{b.branch_code}</td>
                <td className="font-medium">{b.branch_name}</td>
                <td>{b.city}</td><td>{b.area}</td>
                <td>{warehouses.find((w) => w.id === b.warehouse_id)?.warehouse_name || b.warehouse_id}</td>
                <td><span className={`status-badge ${b.active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>{b.active ? t('admin.branches_status_active') : t('admin.branches_status_inactive')}</span></td>
                <td>
                  <div className="flex gap-1">
                    <button onClick={() => { setEditing(b); setForm({ branch_code:b.branch_code, branch_name:b.branch_name, city:b.city||'', area:b.area||'', warehouse_id:b.warehouse_id, active:b.active }); setModal(true) }} className="p-1.5 hover:bg-gray-100 rounded" title={t('common.edit')}>âœڈï¸ڈ</button>
                    <button onClick={() => handleDelete(b)} className="p-1.5 hover:bg-red-50 rounded text-red-500" title={t('common.delete')}>ًں—‘ï¸ڈ</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {modal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-white rounded-xl p-6 w-full max-w-md space-y-4">
            <h2 className="font-semibold text-lg">{editing ? t('admin.branches_edit_title') : t('admin.branches_create_title')}</h2>
            {[['branch_code', t('admin.branch_code')], ['branch_name', t('admin.branch_name')], ['city', t('admin.city')], ['area', t('admin.area')]].map(([k,l]) => (
              <div key={k}>
                <label className="label">{l}</label>
                <input type="text" value={form[k]} onChange={(e) => setForm((p) => ({...p,[k]:e.target.value}))} className="input-field" disabled={!!editing && k==='branch_code'} />
              </div>
            ))}
            <div>
              <label className="label">{t('admin.warehouse')}</label>
              <select value={form.warehouse_id} onChange={(e) => setForm((p) => ({...p, warehouse_id: parseInt(e.target.value)}))} className="input-field">
                {warehouses.map((w) => <option key={w.id} value={w.id}>{w.warehouse_name}</option>)}
              </select>
            </div>
            <label className="flex items-center gap-2"><input type="checkbox" checked={form.active} onChange={(e) => setForm((p) => ({...p, active: e.target.checked}))} /><span className="text-sm">{t('admin.active')}</span></label>
            <div className="flex justify-end gap-3"><button onClick={() => setModal(false)} className="btn-secondary">{t('common.cancel')}</button><button onClick={handleSave} className="btn-primary">{t('admin.save')}</button></div>
          </div>
        </div>
      )}
    </div>
  )
}

function WarehousesAdminPage() {
  const t = useT()
  const [items, setItems] = React.useState([])
  const [form, setForm] = React.useState({ warehouse_code:'', warehouse_name:'', location:'', active:true })
  const [modal, setModal] = React.useState(false)
  const [editing, setEditing] = React.useState(null)

  const reload = () => import('./services/api').then(({ masterApi }) => masterApi.listWarehouses().then((r) => {
    const d = r.data
    setItems(Array.isArray(d) ? d : (d?.items || []))
  }))
  React.useEffect(() => { reload() }, [])

  const handleSave = async () => {
    const { masterApi } = await import('./services/api')
    const { default: toast } = await import('react-hot-toast')
    try {
      if (editing) { await masterApi.updateWarehouse(editing.id, form) }
      else { await masterApi.createWarehouse(form) }
      toast.success(t('admin.saved_toast')); setModal(false); reload()
    } catch (e) { toast.error(e?.response?.data?.detail || t('admin.error_generic')) }
  }

  const handleDelete = async (w) => {
    const { masterApi } = await import('./services/api')
    const { default: toast } = await import('react-hot-toast')
    const msg = t('admin.warehouses_confirm_delete', { name: w.warehouse_name })
      || `ظ‡ظ„ ط£ظ†طھ ظ…طھط£ظƒط¯ ظ…ظ† ط­ط°ظپ ط§ظ„ظ…ط³طھظˆط¯ط¹ "${w.warehouse_name}"طں`
    if (!window.confirm(msg)) return
    try {
      await masterApi.deleteWarehouse(w.id)
      toast.success(t('admin.warehouses_toast_deleted') || 'طھظ… ط­ط°ظپ ط§ظ„ظ…ط³طھظˆط¯ط¹')
      reload()
    } catch (e) {
      toast.error(e?.response?.data?.detail || t('admin.warehouses_toast_delete_error') || 'ظپط´ظ„ ط§ظ„ط­ط°ظپ')
    }
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">{t('admin.warehouses_title')}</h1>
        <button onClick={() => { setEditing(null); setForm({ warehouse_code:'', warehouse_name:'', location:'', active:true }); setModal(true) }} className="btn-primary">
          <span>+</span> {t('admin.warehouses_new')}
        </button>
      </div>
      <div className="card table-container">
        <table className="table">
          <thead><tr>
            <th>{t('admin.warehouses_col_code')}</th>
            <th>{t('admin.warehouses_col_name')}</th>
            <th>{t('admin.warehouses_col_location')}</th>
            <th>{t('admin.warehouses_col_status')}</th>
            <th></th>
          </tr></thead>
          <tbody>
            {items.map((w) => (
              <tr key={w.id}>
                <td className="font-mono text-xs">{w.warehouse_code}</td>
                <td className="font-medium">{w.warehouse_name}</td>
                <td>{w.location}</td>
                <td><span className={`status-badge ${w.active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>{w.active ? t('admin.warehouses_status_active') : t('admin.warehouses_status_inactive')}</span></td>
                <td>
                  <div className="flex gap-2">
                    <button onClick={() => { setEditing(w); setForm({ warehouse_code:w.warehouse_code, warehouse_name:w.warehouse_name, location:w.location||'', active:w.active }); setModal(true) }} className="p-1.5 hover:bg-gray-100 rounded" title={t('common.edit')}>âœڈï¸ڈ</button>
                    <button onClick={() => handleDelete(w)} className="p-1.5 hover:bg-red-100 rounded" title={t('common.delete') || 'ط­ط°ظپ'}>ًں—‘ï¸ڈ</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {modal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-white rounded-xl p-6 w-full max-w-md space-y-4">
            <h2 className="font-semibold text-lg">{editing ? t('admin.warehouses_edit_title') : t('admin.warehouses_create_title')}</h2>
            {[['warehouse_code', t('admin.warehouse_code')], ['warehouse_name', t('admin.warehouse_name')], ['location', t('admin.location')]].map(([k,l]) => (
              <div key={k}><label className="label">{l}</label><input type="text" value={form[k]} onChange={(e) => setForm((p) => ({...p,[k]:e.target.value}))} className="input-field" disabled={!!editing && k==='warehouse_code'} /></div>
            ))}
            <div className="flex justify-end gap-3"><button onClick={() => setModal(false)} className="btn-secondary">{t('common.cancel')}</button><button onClick={handleSave} className="btn-primary">{t('admin.save')}</button></div>
          </div>
        </div>
      )}
    </div>
  )
}

// Boolean / enum / time / numeric settings â€” metadata drives the UI
const SETTING_META = {
  days_of_cover_target:                { kind: 'int', min: 1, max: 30 },
  max_exceptional_order_per_day:       { kind: 'int', min: 1, max: 20 },
  variance_warning_threshold_pct:      { kind: 'float', min: 0, max: 100 },
  variance_critical_threshold_pct:     { kind: 'float', min: 0, max: 100 },
  auto_generate_order_on_approval:     { kind: 'bool' },
  require_variance_reason:             { kind: 'bool' },
  avg_consumption_mode:                { kind: 'enum', options: ['last_7_days', 'last_14_days', 'last_30_days'] },
  inventory_reminder_time:             { kind: 'time' },
}

function SettingsPage() {
  const t = useT()
  const [rows, setRows] = React.useState([])    // [{key, value, description, updated_at, updated_by_name}]
  const [draft, setDraft] = React.useState({})   // {key: new_value}
  const [loading, setLoading] = React.useState(true)
  const [saving, setSaving] = React.useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const { settingsApi } = await import('./services/api')
      const res = await settingsApi.list()
      setRows(res.data || [])
      const d = {}
      for (const r of res.data || []) d[r.key] = r.value
      setDraft(d)
    } catch (e) {
      const { default: toast } = await import('react-hot-toast')
      toast.error(e?.response?.data?.detail || t('admin.error_generic'))
    } finally {
      setLoading(false)
    }
  }

  React.useEffect(() => { load() }, [])

  const changed = rows.filter(r => draft[r.key] !== r.value)
  const hasChanges = changed.length > 0

  const handleSave = async () => {
    if (!hasChanges) return
    const { settingsApi } = await import('./services/api')
    const { default: toast } = await import('react-hot-toast')
    setSaving(true)
    try {
      const payload = {}
      for (const c of changed) payload[c.key] = draft[c.key]
      await settingsApi.bulkUpdate(payload)
      toast.success(t('admin.settings_saved_toast') || 'طھظ… ط­ظپط¸ ط§ظ„ط¥ط¹ط¯ط§ط¯ط§طھ')
      await load()
    } catch (e) {
      toast.error(e?.response?.data?.detail || t('admin.error_generic'))
    } finally {
      setSaving(false)
    }
  }

  const handleReset = () => {
    const d = {}
    for (const r of rows) d[r.key] = r.value
    setDraft(d)
  }

  const renderInput = (row) => {
    const meta = SETTING_META[row.key] || { kind: 'text' }
    const val = draft[row.key] ?? ''
    const setVal = (v) => setDraft(p => ({ ...p, [row.key]: v }))
    if (meta.kind === 'bool') {
      return (
        <label className="inline-flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={val === 'true'}
            onChange={(e) => setVal(e.target.checked ? 'true' : 'false')}
          />
          <span className="text-sm">{val === 'true' ? t('common.yes') : t('common.no')}</span>
        </label>
      )
    }
    if (meta.kind === 'enum') {
      return (
        <select className="input-field w-48" value={val} onChange={(e) => setVal(e.target.value)}>
          {meta.options.map(o => (
            <option key={o} value={o}>{t(`admin.settings_opt_${o}`) || o}</option>
          ))}
        </select>
      )
    }
    if (meta.kind === 'time') {
      return <input type="time" className="input-field w-32" value={val} onChange={(e) => setVal(e.target.value)} />
    }
    if (meta.kind === 'int') {
      return (
        <input
          type="number"
          min={meta.min}
          max={meta.max}
          step="1"
          className="input-field w-32"
          value={val}
          onChange={(e) => setVal(e.target.value)}
        />
      )
    }
    if (meta.kind === 'float') {
      return (
        <input
          type="number"
          min={meta.min}
          max={meta.max}
          step="0.01"
          className="input-field w-32"
          value={val}
          onChange={(e) => setVal(e.target.value)}
        />
      )
    }
    return <input type="text" className="input-field w-48" value={val} onChange={(e) => setVal(e.target.value)} />
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{t('admin.settings_title')}</h1>
        <div className="flex gap-2">
          <button
            onClick={handleReset}
            disabled={!hasChanges || saving}
            className="btn-secondary disabled:opacity-50"
          >
            {t('admin.settings_reset') || 'ط¥ظ„ط؛ط§ط، ط§ظ„طھط؛ظٹظٹط±ط§طھ'}
          </button>
          <button
            onClick={handleSave}
            disabled={!hasChanges || saving}
            className="btn-primary disabled:opacity-50"
          >
            {saving ? t('common.saving') : (t('admin.settings_save_all') || t('admin.save'))}
          </button>
        </div>
      </div>

      <div className="card p-6">
        <p className="text-gray-500 text-sm mb-6">{t('admin.settings_intro')}</p>

        {loading ? (
          <div className="py-8 text-center text-gray-500">{t('common.loading')}</div>
        ) : rows.length === 0 ? (
          <div className="py-8 text-center text-gray-500">{t('common.no_data')}</div>
        ) : (
          <div className="space-y-4">
            {rows.map((r) => {
              const label = t(`admin.settings_${r.key}`) || r.key
              const hint = r.description
              const isDirty = draft[r.key] !== r.value
              return (
                <div
                  key={r.key}
                  className={`flex items-center justify-between py-3 border-b border-gray-100 ${isDirty ? 'bg-yellow-50 -mx-4 px-4 rounded' : ''}`}
                >
                  <div className="flex-1">
                    <div className="text-sm font-medium text-gray-800">
                      {label}
                      {isDirty && <span className="mr-2 text-xs text-yellow-700">â—ڈ {t('admin.settings_dirty') || 'ط؛ظٹط± ظ…ط­ظپظˆط¸'}</span>}
                    </div>
                    {hint && <div className="text-xs text-gray-500 mt-0.5">{hint}</div>}
                  </div>
                  <div>{renderInput(r)}</div>
                </div>
              )
            })}
          </div>
        )}

        {rows.length > 0 && rows.some(r => r.updated_by_name) && (
          <div className="mt-4 pt-4 border-t border-gray-100 text-xs text-gray-500">
            {t('admin.settings_last_updated_footer') || 'ط¢ط®ط± طھط­ط¯ظٹط«:'}{' '}
            {(() => {
              const latest = rows.reduce((acc, r) => (!acc || new Date(r.updated_at) > new Date(acc.updated_at) ? r : acc), null)
              if (!latest) return 'â€”'
              const d = new Date(latest.updated_at)
              return `${d.toLocaleString()} ${latest.updated_by_name ? 'â€” ' + latest.updated_by_name : ''}`
            })()}
          </div>
        )}
      </div>
    </div>
  )
}

function AreaBranchItemsPage() {
  const { lang } = useLanguage()
  const [branches, setBranches] = React.useState([])
  const [items, setItems] = React.useState([])
  const [branchItems, setBranchItems] = React.useState([])
  const [branchId, setBranchId] = React.useState('')
  const [itemId, setItemId] = React.useState('')
  const [loading, setLoading] = React.useState(false)
  const [newItem, setNewItem] = React.useState({ proposed_item_name_ar: '', proposed_unit: '', proposed_source_type: 'WAREHOUSE', reason: '' })
  const nameOf = (obj, base = 'item_name') => obj?.[`${base}_${lang}`] || obj?.[`${base}_ar`] || obj?.[base] || obj?.item_name || ''

  const loadBranchItems = React.useCallback(async (id) => {
    if (!id) {
      setBranchItems([])
      return
    }
    setLoading(true)
    try {
      const res = await masterApi.listItems({ page_size: 200, active_only: true, branch_id: id, visible_in_branch_ui_only: true, requestable_only: true })
      setBranchItems(res?.data?.items || [])
    } catch {
      setBranchItems([])
    } finally {
      setLoading(false)
    }
  }, [])

  React.useEffect(() => {
    ;(async () => {
      try {
        const [branchesRes, itemsRes] = await Promise.all([
          masterApi.listBranches({ active_only: true }),
          masterApi.listItems({ page_size: 200, active_only: true }),
        ])
        const branchList = Array.isArray(branchesRes.data) ? branchesRes.data : (branchesRes.data?.items || [])
        setBranches(branchList)
        setItems(itemsRes.data?.items || [])
        if (branchList[0]?.id) {
          setBranchId(String(branchList[0].id))
          loadBranchItems(branchList[0].id)
        }
      } catch (err) {
        toast.error('فشل تحميل البيانات')
      }
    })()
  }, [loadBranchItems])

  const addItem = async () => {
    if (!branchId || !itemId) {
      toast.error('اختر الفرع والصنف')
      return
    }
    try {
      await itemChangeRequestsApi.addBranchItem({ branch_id: Number(branchId), item_id: Number(itemId), reason: 'Area manager branch item add' })
      toast.success('تمت إضافة الصنف للفرع')
      setItemId('')
      loadBranchItems(branchId)
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'فشل إضافة الصنف')
    }
  }

  const requestRemove = async (row) => {
    const reason = window.prompt(`سبب طلب إزالة الصنف من الفرع: ${nameOf(row) || row.item_code}`) || ''
    if (!reason.trim()) return
    try {
      await itemChangeRequestsApi.requestBranchRemove({ branch_id: Number(branchId), item_id: Number(row.id || row.item_id), reason: reason.trim() })
      toast.success('تم إرسال طلب الإزالة للمراجعة')
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'فشل إرسال طلب الإزالة')
    }
  }

  const requestNewItem = async () => {
    if (!newItem.proposed_item_name_ar.trim()) {
      toast.error('اكتب اسم الصنف الجديد')
      return
    }
    try {
      await itemChangeRequestsApi.requestNewItem({ ...newItem, target_type: 'branch', branch_id: branchId ? Number(branchId) : null })
      toast.success('تم إرسال طلب إنشاء الصنف للمراجعة')
      setNewItem({ proposed_item_name_ar: '', proposed_unit: '', proposed_source_type: 'WAREHOUSE', reason: '' })
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'فشل إرسال طلب الصنف الجديد')
    }
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">أصناف الفروع</h1>
        <p className="text-sm text-gray-500 mt-1">إضافة صنف موجود للفرع مباشرة، وطلب إزالة الصنف يذهب للمراجعة.</p>
      </div>
      <div className="card p-5 grid grid-cols-1 lg:grid-cols-4 gap-3 items-end">
        <div>
          <label className="label">الفرع</label>
          <select className="input-field" value={branchId} onChange={(e) => { setBranchId(e.target.value); loadBranchItems(e.target.value) }}>
            <option value="">اختر الفرع</option>
            {branches.map((b) => <option key={b.id} value={b.id}>{b.branch_name || b.branch_name_ar || b.branch_code}</option>)}
          </select>
        </div>
        <div className="lg:col-span-2">
          <label className="label">صنف موجود</label>
          <select className="input-field" value={itemId} onChange={(e) => setItemId(e.target.value)}>
            <option value="">اختر صنف</option>
            {items.map((item) => <option key={item.id} value={item.id}>{nameOf(item)} ({item.item_code})</option>)}
          </select>
        </div>
        <button type="button" className="btn-primary" onClick={addItem}>إضافة للفرع</button>
      </div>
      <div className="card p-5 space-y-3">
        <h2 className="font-semibold text-gray-900">طلب صنف جديد غير موجود</h2>
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-3">
          <input className="input-field" placeholder="اسم الصنف" value={newItem.proposed_item_name_ar} onChange={(e) => setNewItem((p) => ({ ...p, proposed_item_name_ar: e.target.value }))} />
          <input className="input-field" placeholder="الوحدة" value={newItem.proposed_unit} onChange={(e) => setNewItem((p) => ({ ...p, proposed_unit: e.target.value }))} />
          <select className="input-field" value={newItem.proposed_source_type} onChange={(e) => setNewItem((p) => ({ ...p, proposed_source_type: e.target.value }))}>
            <option value="WAREHOUSE">من المستودع</option>
            <option value="KITCHEN">من المطبخ</option>
          </select>
          <input className="input-field" placeholder="سبب الطلب" value={newItem.reason} onChange={(e) => setNewItem((p) => ({ ...p, reason: e.target.value }))} />
        </div>
        <button type="button" className="btn-secondary" onClick={requestNewItem}>إرسال للمراجعة</button>
      </div>
      <div className="card table-container">
        <table className="table">
          <thead><tr><th>الصنف</th><th>الكود</th><th>المصدر</th><th>إجراء</th></tr></thead>
          <tbody>
            {loading ? <tr><td colSpan={4} className="text-center py-8 text-gray-500">جاري التحميل...</td></tr> : branchItems.length === 0 ? (
              <tr><td colSpan={4} className="text-center py-8 text-gray-400">لا توجد أصناف ظاهرة لهذا الفرع</td></tr>
            ) : branchItems.map((item) => (
              <tr key={item.id}>
                <td className="font-medium">{nameOf(item)}</td>
                <td className="font-mono text-xs text-gray-500">{item.item_code}</td>
                <td>{item.source_type === 'KITCHEN' ? 'مطبخ' : 'مستودع'}</td>
                <td><button type="button" className="btn-secondary text-xs" onClick={() => requestRemove(item)}>طلب إزالة</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function ItemChangeRequestsPage() {
  const [rows, setRows] = React.useState([])
  const [status, setStatus] = React.useState('pending')
  const [loading, setLoading] = React.useState(false)

  const load = React.useCallback(async () => {
    setLoading(true)
    try {
      const res = await itemChangeRequestsApi.list({ status: status || undefined })
      setRows(Array.isArray(res.data) ? res.data : [])
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'فشل تحميل طلبات الأصناف')
    } finally {
      setLoading(false)
    }
  }, [status])

  React.useEffect(() => { load() }, [load])

  const typeLabel = (type) => ({
    warehouse_remove: 'إزالة من مستودع',
    branch_remove: 'إزالة من فرع',
    new_item: 'صنف جديد',
  }[type] || type)

  const approve = async (row) => {
    const review_note = window.prompt('ملاحظة الموافقة') || ''
    try {
      await itemChangeRequestsApi.approve(row.id, { review_note })
      toast.success('تمت مراجعة الطلب')
      load()
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'فشل اعتماد الطلب')
    }
  }

  const reject = async (row) => {
    const review_note = window.prompt('سبب الرفض') || ''
    if (!review_note.trim()) return
    try {
      await itemChangeRequestsApi.reject(row.id, { review_note })
      toast.success('تم رفض الطلب')
      load()
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'فشل رفض الطلب')
    }
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">طلبات تغييرات الأصناف</h1>
          <p className="text-sm text-gray-500 mt-1">مراجعة حذف الأصناف وطلبات إنشاء الأصناف الجديدة.</p>
        </div>
        <select className="input-field w-48" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="pending">قيد المراجعة</option>
          <option value="">كل الحالات</option>
          <option value="executed">منفذ</option>
          <option value="approved">معتمد</option>
          <option value="rejected">مرفوض</option>
          <option value="failed">فشل التنفيذ</option>
        </select>
      </div>
      <div className="card table-container">
        <table className="table">
          <thead><tr><th>رقم الطلب</th><th>النوع</th><th>الفرع/المستودع</th><th>الصنف</th><th>الحالة</th><th>السبب</th><th>الإجراءات</th></tr></thead>
          <tbody>
            {loading ? <tr><td colSpan={7} className="text-center py-8 text-gray-500">جاري التحميل...</td></tr> : rows.length === 0 ? (
              <tr><td colSpan={7} className="text-center py-8 text-gray-400">لا توجد طلبات</td></tr>
            ) : rows.map((row) => (
              <tr key={row.id}>
                <td className="font-mono text-xs">{row.request_no}</td>
                <td>{typeLabel(row.request_type)}</td>
                <td>{row.branch_name || row.warehouse_name || '-'}</td>
                <td>{row.item_name || row.proposed_item_name_ar || '-'}</td>
                <td><span className="status-badge bg-blue-100 text-blue-700">{row.status}</span></td>
                <td className="text-sm text-gray-600">{row.failure_reason || row.reason || '-'}</td>
                <td>
                  {row.status === 'pending' ? (
                    <div className="flex gap-2">
                      <button type="button" className="btn-primary text-xs" onClick={() => approve(row)}>موافقة</button>
                      <button type="button" className="btn-secondary text-xs" onClick={() => reject(row)}>رفض</button>
                    </div>
                  ) : <span className="text-xs text-gray-400">{row.review_note || '-'}</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// â”€â”€â”€ Root App â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// ErrorBoundary ظٹظ…ط³ظƒ ط£ظٹ crash ظپظٹ ط§ظ„ط´ط¬ط±ط© ط¨ط¯ظ„ط§ظ‹ ظ…ظ† Whitescreen
export default function App() {
  return (
    <ErrorBoundary>
      <LanguageProvider>
        <Provider store={store}>
          <Toaster position="top-center" toastOptions={{ duration: 3500 }} />
          <Suspense fallback={<PageLoader />}>
            <AppRoutes />
          </Suspense>
        </Provider>
      </LanguageProvider>
    </ErrorBoundary>
  )
}
     


