import React from 'react'
import toast from 'react-hot-toast'
import { Link } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { selectUser, selectUserRoles } from '../../store'
import { useT } from '../../i18n'
import { dashboardApi, masterApi, notificationsApi, supplyChainApi } from '../../services/api'
import ConfirmDialog from '../../components/common/ConfirmDialog'
import { FulfillmentTable } from './BranchRequestDetailPage'

const STATUS_BADGE = {
  DRAFT: 'bg-gray-100 text-gray-700',
  SUBMITTED: 'bg-blue-100 text-blue-700',
  AREA_APPROVED: 'bg-emerald-100 text-emerald-700',
  AREA_REJECTED: 'bg-red-100 text-red-700',
  SPLIT: 'bg-indigo-100 text-indigo-700',
  IN_EXECUTION: 'bg-amber-100 text-amber-700',
  DELIVERED: 'bg-green-100 text-green-700',
  PENDING: 'bg-gray-100 text-gray-700',
  IN_PROGRESS: 'bg-blue-100 text-blue-700',
  WAITING_FOR_MATERIALS: 'bg-orange-100 text-orange-700',
  PARTIAL_READY: 'bg-amber-100 text-amber-700',
  READY: 'bg-emerald-100 text-emerald-700',
  SENT_TO_WAREHOUSE: 'bg-indigo-100 text-indigo-700',
  AVAILABLE: 'bg-blue-100 text-blue-700',
  PARTIAL: 'bg-amber-100 text-amber-700',
  BACKORDER: 'bg-red-100 text-red-700',
  READY_FOR_DISPATCH: 'bg-emerald-100 text-emerald-700',
  OUT_FOR_DELIVERY: 'bg-sky-100 text-sky-700',
}

const STATUS_LABEL = {
  DRAFT: 'مسودة',
  SUBMITTED: 'مرسل',
  AREA_APPROVED: 'موافق عليه',
  AREA_REJECTED: 'مرفوض',
  SPLIT: 'تم التقسيم',
  IN_EXECUTION: 'قيد التنفيذ',
  DELIVERED: 'تم التسليم',
  APPROVED: 'معتمد',
  REJECTED: 'مرفوض',
  SPLIT_TO_WAREHOUSE: 'إلى المستودع',
  SPLIT_TO_PRODUCTION: 'إلى المطبخ',
  IN_PRODUCTION: 'في الإنتاج',
  READY_IN_WAREHOUSE: 'جاهز بالمستودع',
  PARTIAL_WAREHOUSE: 'جزئي بالمستودع',
  PENDING: 'بانتظار',
  IN_PROGRESS: 'قيد العمل',
  WAITING_FOR_MATERIALS: 'بانتظار خامات',
  PARTIAL_READY: 'جاهز جزئيًا',
  READY: 'جاهز',
  SENT_TO_WAREHOUSE: 'أرسل للمستودع',
  AVAILABLE: 'متاح',
  PARTIAL: 'صرف جزئي',
  BACKORDER: 'نقص',
  READY_FOR_DISPATCH: 'جاهز للتسليم',
  OUT_FOR_DELIVERY: 'خرج للتسليم',
}

function StatusBadge({ status }) {
  return (
    <span className={`status-badge text-xs ${STATUS_BADGE[status] || 'bg-gray-100 text-gray-700'}`}>
      {STATUS_LABEL[status] || status}
    </span>
  )
}

function PageShell({ title, subtitle, actions, children }) {
  return (
    <div className="p-6 space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{title}</h1>
          {subtitle && <p className="text-sm text-gray-500 mt-1">{subtitle}</p>}
        </div>
        {actions}
      </div>
      {children}
    </div>
  )
}

function ReadOnlyBanner({ message = 'عرض المراجع الداخلي للقراءة فقط. يمكن متابعة البيانات وإضافة ملاحظات المراجعة دون تنفيذ أي إجراء تشغيلي.' }) {
  return (
    <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
      {message}
    </div>
  )
}

function formatDate(value) {
  if (!value) return '—'
  try {
    return new Date(value).toLocaleString('en-GB')
  } catch {
    return value
  }
}

function branchDisplay(lineOrOrder) {
  return lineOrOrder?.branch_name
    || lineOrOrder?.branch?.branch_name
    || lineOrOrder?.branch?.branch_name_ar
    || '—'
}

function sourceRouteLabel(line) {
  const src = String(line?.resolved_source_type || line?.source_type || '').toUpperCase()
  if (src.includes('KITCHEN') && src.includes('WAREHOUSE')) return 'مطبخ / مستودع'
  if (src.includes('KITCHEN')) return 'مطبخ'
  if (src.includes('WAREHOUSE')) return 'مستودع'
  if (src.includes('BOTH')) return 'مطبخ / مستودع'
  return 'حسب إعداد الصنف'
}

function countApprovalRoutes(lines) {
  let kitchen = 0
  let warehouse = 0
  let mixed = 0
  lines.forEach((line) => {
    const label = sourceRouteLabel(line)
    if (label.includes('مطبخ') && label.includes('مستودع')) mixed += 1
    else if (label.includes('مطبخ')) kitchen += 1
    else if (label.includes('مستودع')) warehouse += 1
    else mixed += 1
  })
  return { kitchen, warehouse, mixed }
}

function itemLabel(item) {
  return item?.item_name_ar || item?.item_name_en || item?.item_name || `#${item?.id}`
}

function numberValue(value) {
  if (value === null || value === undefined || value === '') return ''
  return String(value)
}

const EMPTY_FILTERS = {
  search: '',
  status: '',
  branch_id: '',
  item_id: '',
  date_from: '',
  date_to: '',
}

const BRANCH_REQUEST_STATUS_OPTIONS = [
  ['', 'كل الحالات'],
  ['DRAFT', 'مسودة'],
  ['SUBMITTED', 'مرسل'],
  ['AREA_APPROVED', 'موافق عليه'],
  ['AREA_REJECTED', 'مرفوض'],
  ['SPLIT', 'تم التقسيم'],
  ['IN_EXECUTION', 'قيد التنفيذ'],
  ['DELIVERED', 'تم التسليم'],
]

const WAREHOUSE_LINE_STATUS_OPTIONS = [
  ['', 'كل الحالات'],
  ['PENDING', 'بانتظار'],
  ['AVAILABLE', 'متاح'],
  ['PARTIAL', 'صرف جزئي'],
  ['BACKORDER', 'نقص'],
  ['DELIVERED', 'تم التسليم'],
]

const DELIVERY_STATUS_OPTIONS = [
  ['', 'كل الحالات'],
  ['READY', 'جاهز للتسليم'],
  ['OUT_FOR_DELIVERY', 'خرج للتسليم'],
  ['DELIVERED', 'تم التسليم'],
  ['PARTIAL_DELIVERED', 'تسليم جزئي'],
]

function buildFilterParams(filters) {
  const params = {}
  if (filters.search?.trim()) params.search = filters.search.trim()
  if (filters.status) params.status = filters.status
  if (filters.branch_id) params.branch_id = Number(filters.branch_id)
  if (filters.item_id) params.item_id = Number(filters.item_id)
  if (filters.date_from) params.date_from = `${filters.date_from}T00:00:00`
  if (filters.date_to) params.date_to = `${filters.date_to}T23:59:59`
  return params
}

function SupplyChainFilterBar({
  filters,
  onChange,
  branches = [],
  items = [],
  statusOptions = [],
  showBranch = true,
  showItem = false,
  showStatus = true,
}) {
  const set = (key, value) => onChange((prev) => ({ ...prev, [key]: value }))
  return (
    <div className="card p-4 grid md:grid-cols-2 xl:grid-cols-6 gap-3">
      <div className="xl:col-span-2">
        <label className="label text-xs">بحث</label>
        <input
          className="input-field"
          value={filters.search}
          onChange={(e) => set('search', e.target.value)}
          placeholder="اسم الفرع، الصنف، أو رقم الطلب"
        />
      </div>
      {showStatus && (
        <div>
          <label className="label text-xs">الحالة</label>
          <select className="input-field" value={filters.status} onChange={(e) => set('status', e.target.value)}>
            {statusOptions.map(([value, label]) => (
              <option key={value || 'all'} value={value}>{label}</option>
            ))}
          </select>
        </div>
      )}
      {showBranch && (
        <div>
          <label className="label text-xs">الفرع</label>
          <select className="input-field" value={filters.branch_id} onChange={(e) => set('branch_id', e.target.value)}>
            <option value="">كل الفروع</option>
            {branches.map((branch) => (
              <option key={branch.id} value={branch.id}>{branch.branch_name}</option>
            ))}
          </select>
        </div>
      )}
      {showItem && (
        <div>
          <label className="label text-xs">الصنف</label>
          <select className="input-field" value={filters.item_id} onChange={(e) => set('item_id', e.target.value)}>
            <option value="">كل الأصناف</option>
            {items.map((item) => (
              <option key={item.id} value={item.id}>{itemLabel(item)}</option>
            ))}
          </select>
        </div>
      )}
      <div>
        <label className="label text-xs">من تاريخ</label>
        <input type="date" className="input-field" value={filters.date_from} onChange={(e) => set('date_from', e.target.value)} />
      </div>
      <div>
        <label className="label text-xs">إلى تاريخ</label>
        <input type="date" className="input-field" value={filters.date_to} onChange={(e) => set('date_to', e.target.value)} />
      </div>
    </div>
  )
}

const WAREHOUSE_ISSUE_STATUSES = new Set(['PENDING', 'AVAILABLE', 'PARTIAL'])

function canReceiveWarehouseLine(line) {
  return line?.source_type === 'BRANCH_REQUEST' && line?.status === 'PENDING'
}

function canIssueWarehouseLine(line) {
  return WAREHOUSE_ISSUE_STATUSES.has(line?.status) && Number(line?.pending_qty) > 0
}

function canCreateDeliveryFromLine(line) {
  return Number(line?.issued_qty) > 0 && ['READY_FOR_DISPATCH', 'PARTIAL'].includes(line?.status)
}

function productionCanStart(status) {
  return status === 'PENDING'
}

function productionCanMarkReady(status) {
  return ['IN_PROGRESS', 'WAITING_FOR_MATERIALS', 'PARTIAL_READY'].includes(status)
}

function productionCanPartialReady(status) {
  return ['IN_PROGRESS', 'WAITING_FOR_MATERIALS', 'PARTIAL_READY'].includes(status)
}

function productionCanSendToWarehouse(status) {
  return ['READY', 'PARTIAL_READY'].includes(status)
}

function productionIsClosed(status) {
  return status === 'SENT_TO_WAREHOUSE'
}

async function loadAllowedBrands(branchId, brands) {
  const checks = await Promise.all(brands.map(async (brand) => {
    try {
      const res = await supplyChainApi.listAllowedItems({ branch_id: branchId, brand_id: brand.id })
      const items = Array.isArray(res.data) ? res.data : []
      return items.length > 0 ? { brand, items } : null
    } catch {
      return null
    }
  }))
  return checks.filter(Boolean)
}

export function SupplyChainBranchRequestsPage() {
  const user = useSelector(selectUser)
  const roles = useSelector(selectUserRoles)
  const isAuditor = roles.includes('internal_auditor')
  const isAreaManager = roles.includes('area_manager') && !roles.includes('admin') && !roles.includes('super_admin')
  const canCreateRequest = (roles.includes('branch_user') || roles.includes('branch_manager')) && !isAuditor
  const canSelectBranch = roles.includes('admin') || roles.includes('super_admin') || isAuditor
  const usesScopedList = isAreaManager || (isAuditor && !user?.branch_id)
  const [loading, setLoading] = React.useState(true)
  const [saving, setSaving] = React.useState(false)
  const [requests, setRequests] = React.useState([])
  const [branches, setBranches] = React.useState([])
  const [allBrands, setAllBrands] = React.useState([])
  const [selectedBranchId, setSelectedBranchId] = React.useState(user?.branch_id || '')
  const [availableBrands, setAvailableBrands] = React.useState([])
  const [selectedBrandId, setSelectedBrandId] = React.useState('')
  const [allowedItems, setAllowedItems] = React.useState([])
  const [priority, setPriority] = React.useState('')
  const [lines, setLines] = React.useState([{ item_id: '', qty_requested: '', source_type: '', notes: '' }])
  const [listFilters, setListFilters] = React.useState({ ...EMPTY_FILTERS })

  const reloadRequests = React.useCallback(async (branchId = selectedBranchId, filters = listFilters) => {
    if (!branchId && !usesScopedList) {
      setRequests([])
      return
    }
    const params = {
      page_size: 100,
      ...buildFilterParams(filters),
    }
    if (branchId) params.branch_id = Number(branchId)
    const res = await supplyChainApi.listBranchRequests(params)
    setRequests(res.data?.items || [])
  }, [selectedBranchId, listFilters, usesScopedList])

  React.useEffect(() => {
    let mounted = true
    ;(async () => {
      try {
        const [brandsRes, branchesRes] = await Promise.all([
          supplyChainApi.listBrands(),
          canSelectBranch ? masterApi.listBranches({ active_only: true }) : Promise.resolve({ data: [] }),
        ])
        const brandRows = Array.isArray(brandsRes.data) ? brandsRes.data : []
        const branchRows = Array.isArray(branchesRes.data) ? branchesRes.data : []
        if (!mounted) return
        setAllBrands(brandRows)
        setBranches(branchRows)
        const effectiveBranchId = canSelectBranch ? (selectedBranchId || '') : user?.branch_id
        if (effectiveBranchId && effectiveBranchId !== selectedBranchId) {
          setSelectedBranchId(effectiveBranchId)
        }
        if (effectiveBranchId) {
          const allowed = await loadAllowedBrands(effectiveBranchId, brandRows)
          if (!mounted) return
          setAvailableBrands(allowed)
          const firstBrandId = allowed[0]?.brand?.id || ''
          setSelectedBrandId((prev) => prev || firstBrandId)
          setAllowedItems(allowed[0]?.items || [])
          await reloadRequests(effectiveBranchId)
        } else if (usesScopedList) {
          await reloadRequests(undefined, listFilters)
        }
      } catch (error) {
        toast.error(error?.response?.data?.message || error?.response?.data?.detail || 'تعذر تحميل بيانات طلبات الفروع')
      } finally {
        if (mounted) setLoading(false)
      }
    })()
    return () => { mounted = false }
  }, [])

  React.useEffect(() => {
    const hit = availableBrands.find((entry) => String(entry.brand.id) === String(selectedBrandId))
    setAllowedItems(hit?.items || [])
  }, [availableBrands, selectedBrandId])

  const selectedBrand = React.useMemo(
    () => availableBrands.find((entry) => String(entry.brand.id) === String(selectedBrandId))?.brand || null,
    [availableBrands, selectedBrandId]
  )

  const groupedAllowedItems = React.useMemo(() => {
    const grouped = new Map()
    allowedItems.forEach((item) => {
      const categoryName = item?.category?.name_ar || item?.category?.name_en || 'بدون تصنيف'
      if (!grouped.has(categoryName)) grouped.set(categoryName, [])
      grouped.get(categoryName).push(item)
    })
    return Array.from(grouped.entries())
  }, [allowedItems])

  React.useEffect(() => {
    if (usesScopedList) {
      reloadRequests(undefined, listFilters).catch(() => {})
      return
    }
    if (!selectedBranchId) {
      setAvailableBrands([])
      setSelectedBrandId('')
      setAllowedItems([])
      setRequests([])
      return
    }
    loadAllowedBrands(selectedBranchId, allBrands)
      .then((allowed) => {
        setAvailableBrands(allowed)
        if (!allowed.find((entry) => String(entry.brand.id) === String(selectedBrandId))) {
          setSelectedBrandId(allowed[0]?.brand?.id || '')
        }
      })
      .catch(() => {})
    reloadRequests(selectedBranchId).catch(() => {})
  }, [selectedBranchId, allBrands])

  React.useEffect(() => {
    if (usesScopedList) {
      reloadRequests(undefined, listFilters).catch(() => {})
      return
    }
    if (!selectedBranchId) return
    reloadRequests(selectedBranchId, listFilters).catch(() => {})
  }, [listFilters, selectedBranchId, reloadRequests, usesScopedList])

  const addLine = () => setLines((prev) => [...prev, { item_id: '', qty_requested: '', source_type: '', notes: '' }])

  const updateLine = (index, patch) => {
    setLines((prev) => prev.map((line, i) => (i === index ? { ...line, ...patch } : line)))
  }

  const removeLine = (index) => {
    setLines((prev) => (prev.length === 1 ? prev : prev.filter((_, i) => i !== index)))
  }

  const handleCreate = async (submitAfter = false) => {
    if (!selectedBranchId || !selectedBrandId) {
      toast.error('اختر الفرع والبراند أولًا')
      return
    }
    const normalized = lines
      .filter((line) => line.item_id && Number(line.qty_requested) > 0)
      .map((line) => ({
        item_id: Number(line.item_id),
        qty_requested: Number(line.qty_requested),
        source_type: line.source_type || null,
        notes: line.notes || null,
      }))
    if (normalized.length === 0) {
      toast.error('أضف صنفًا واحدًا على الأقل')
      return
    }
    setSaving(true)
    try {
      const created = await supplyChainApi.createBranchRequest({
        branch_id: Number(selectedBranchId),
        brand_id: Number(selectedBrandId),
        priority: priority || null,
        lines: normalized,
      })
      const requestId = created.data?.id
      if (submitAfter && requestId) {
        await supplyChainApi.submitBranchRequest(requestId)
      }
      toast.success(submitAfter ? 'تم إنشاء الطلب وإرساله' : 'تم حفظ الطلب كمسودة')
      setPriority('')
      setLines([{ item_id: '', qty_requested: '', source_type: '', notes: '' }])
      await reloadRequests(selectedBranchId)
    } catch (error) {
      toast.error(error?.response?.data?.message || error?.response?.data?.detail || 'فشل إنشاء الطلب')
    } finally {
      setSaving(false)
    }
  }

  return (
    <PageShell
      title="طلبات الفروع"
      subtitle={usesScopedList ? 'متابعة طلبات التوريد ضمن نطاقك' : 'إنشاء ومتابعة طلبات التوريد للفروع'}
    >
      {isAuditor && <ReadOnlyBanner message="المراجع الداخلي يستطيع استعراض الطلبات والأصناف القابلة للطلب لكل فرع، لكنه لا ينشئ أو يرسل طلبات جديدة من هذه الصفحة." />}
      <div className={`grid gap-6 ${canCreateRequest ? 'xl:grid-cols-[1.2fr,1fr]' : ''}`}>
        {canCreateRequest && (
        <div className="card p-5 space-y-4">
          <div className="grid md:grid-cols-3 gap-4">
            {canSelectBranch && (
              <div>
                <label className="label">الفرع</label>
                <select id="sc-branch-request-branch" aria-label="Branch" value={selectedBranchId} onChange={(e) => setSelectedBranchId(e.target.value)} className="input-field">
                  <option value="">اختر الفرع</option>
                  {branches.map((branch) => (
                    <option key={branch.id} value={branch.id}>{branch.branch_name || branch.branch_name_ar || branch.name}</option>
                  ))}
                </select>
              </div>
            )}
            <div>
              <label className="label">البراند</label>
              <select id="sc-branch-request-brand" aria-label="Brand" value={selectedBrandId} onChange={(e) => setSelectedBrandId(e.target.value)} className="input-field">
                <option value="">اختر البراند</option>
                {availableBrands.map(({ brand }) => (
                  <option key={brand.id} value={brand.id}>{brand.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">الأولوية</label>
              <input id="sc-branch-request-priority" aria-label="Priority" value={priority} onChange={(e) => setPriority(e.target.value)} className="input-field" placeholder="اختياري" disabled={isAuditor} />
            </div>
          </div>

          {canSelectBranch && !selectedBranchId && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-sm text-amber-800">
              اختر الفرع أولًا لعرض البراندات والأصناف المتاحة له.
            </div>
          )}

          <div className="space-y-3">
            {lines.map((line, index) => (
              <div key={index} className="border border-gray-200 rounded-xl p-4 space-y-3">
                <div className="grid md:grid-cols-4 gap-3">
                  <div>
                    <label className="label">الصنف</label>
                    <select id={`sc-branch-request-item-${index}`} aria-label={`Item ${index + 1}`} value={line.item_id} onChange={(e) => updateLine(index, { item_id: e.target.value, source_type: '' })} className="input-field" disabled={isAuditor}>
                      <option value="">اختر الصنف</option>
                      {groupedAllowedItems.map(([categoryName, items]) => (
                        <optgroup
                          key={`${selectedBrand?.id || 'brand'}-${categoryName}`}
                          label={`${selectedBrand?.name || 'البراند'} / ${categoryName}`}
                        >
                          {items.map((item) => (
                            <option key={item.id} value={item.id}>
                              {`${itemLabel(item)}${item?.item_code ? ` (${item.item_code})` : ''}`}
                            </option>
                          ))}
                        </optgroup>
                      ))}
                    </select>
                    {!allowedItems.length && (
                      <p className="text-xs text-amber-600 mt-2">لا توجد أصناف قابلة للطلب لهذا البراند حاليًا.</p>
                    )}
                  </div>
                  <div>
                    <label className="label">الكمية</label>
                    <input id={`sc-branch-request-qty-${index}`} aria-label={`Quantity ${index + 1}`} type="number" min="0" step="0.01" value={line.qty_requested} onChange={(e) => updateLine(index, { qty_requested: e.target.value })} className="input-field" disabled={isAuditor} />
                  </div>
                  <div>
                    <label className="label">المصدر</label>
                    <select id={`sc-branch-request-source-${index}`} aria-label={`Source ${index + 1}`} value={line.source_type} onChange={(e) => updateLine(index, { source_type: e.target.value })} className="input-field" disabled={isAuditor}>
                      <option value="">اتركه حسب إعداد الصنف</option>
                      <option value="WAREHOUSE">مستودع</option>
                      <option value="KITCHEN">مطبخ</option>
                      <option value="BOTH">كلاهما</option>
                    </select>
                  </div>
                  <div className="flex items-end">
                    <button type="button" onClick={() => removeLine(index)} className="btn-secondary w-full" disabled={isAuditor}>حذف السطر</button>
                  </div>
                </div>
                <div>
                  <label className="label">ملاحظة</label>
                  <input id={`sc-branch-request-notes-${index}`} aria-label={`Notes ${index + 1}`} value={line.notes} onChange={(e) => updateLine(index, { notes: e.target.value })} className="input-field" placeholder="اختياري" disabled={isAuditor} />
                </div>
              </div>
            ))}
          </div>

          <div className="flex gap-3 flex-wrap">
            {!isAuditor && <button type="button" onClick={addLine} className="btn-secondary">+ إضافة صنف</button>}
            {!isAuditor && <button type="button" onClick={() => handleCreate(false)} disabled={saving} className="btn-secondary">حفظ مسودة</button>}
            {!isAuditor && <button type="button" onClick={() => handleCreate(true)} disabled={saving} className="btn-primary">{saving ? 'جارٍ الحفظ...' : 'حفظ وإرسال'}</button>}
          </div>
        </div>
        )}

        <div className="card table-container">
          <div className="p-4 border-b border-gray-100 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold text-gray-900">{usesScopedList ? 'طلبات ضمن النطاق' : 'طلبات الفرع'}</h2>
              <button type="button" onClick={() => reloadRequests()} className="btn-secondary text-sm">تحديث</button>
            </div>
            <SupplyChainFilterBar
              filters={listFilters}
              onChange={setListFilters}
              statusOptions={BRANCH_REQUEST_STATUS_OPTIONS}
              showBranch={false}
              showItem={false}
            />
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>رقم الطلب</th>
                <th>البراند</th>
                <th>الحالة</th>
                <th>الإنشاء</th>
                <th>الإجراء</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={5} className="text-center py-8 text-gray-400">جارٍ التحميل...</td></tr>
              ) : requests.length === 0 ? (
                <tr><td colSpan={5} className="text-center py-8 text-gray-400">لا توجد طلبات بعد</td></tr>
              ) : requests.map((request) => {
                const brand = availableBrands.find((entry) => entry.brand.id === request.brand_id)?.brand
                return (
                  <tr key={request.id}>
                    <td className="font-medium">
                      <Link to={`/supply-chain/branch-requests/${request.id}`} className="text-blue-700 hover:underline">
                        {request.request_no}
                      </Link>
                    </td>
                    <td>{brand?.name || `#${request.brand_id}`}</td>
                    <td><StatusBadge status={request.status} /></td>
                    <td>{formatDate(request.created_at)}</td>
                    <td>
                      <Link to={`/supply-chain/branch-requests/${request.id}`} className="btn-secondary text-xs">تفاصيل</Link>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </PageShell>
  )
}

export function SupplyChainApprovalsPage() {
  const roles = useSelector(selectUserRoles)
  const isAuditor = roles.includes('internal_auditor')
  const [loading, setLoading] = React.useState(true)
  const [requests, setRequests] = React.useState([])
  const [selected, setSelected] = React.useState(null)
  const [approvalNote, setApprovalNote] = React.useState('')
  const [rejectNote, setRejectNote] = React.useState('')
  const [lineApprovals, setLineApprovals] = React.useState({})
  const [approveConfirmOpen, setApproveConfirmOpen] = React.useState(false)
  const [pendingApproveAction, setPendingApproveAction] = React.useState(null)
  const [rejectConfirmOpen, setRejectConfirmOpen] = React.useState(false)
  const [listFilters, setListFilters] = React.useState({ ...EMPTY_FILTERS, status: 'SUBMITTED' })

  const load = React.useCallback(async () => {
    setLoading(true)
    try {
      const res = await supplyChainApi.listBranchRequests({
        page_size: 100,
        ...buildFilterParams(listFilters),
      })
      const items = res.data?.items || []
      setRequests(items)
      if (items.length && !selected) {
        setSelected(items[0])
        setLineApprovals(Object.fromEntries(items[0].lines.map((line) => [line.id, numberValue(line.qty_requested)])))
      }
    } catch (error) {
      toast.error(error?.response?.data?.message || error?.response?.data?.detail || 'تعذر تحميل الطلبات')
    } finally {
      setLoading(false)
    }
  }, [selected, listFilters])

  React.useEffect(() => { load() }, [listFilters])

  const selectRequest = (request) => {
    setSelected(request)
    setApprovalNote('')
    setRejectNote('')
    setLineApprovals(Object.fromEntries(request.lines.map((line) => [line.id, numberValue(line.qty_requested)])))
  }

  const approve = async () => {
    if (!selected) return
    try {
      await supplyChainApi.approveBranchRequest(selected.id, { approval_note: approvalNote || null })
      toast.success('تمت الموافقة — سيتم إرسال الأسطر للمطبخ والمستودع')
      await load()
      setSelected(null)
    } catch (error) {
      toast.error(error?.response?.data?.message || error?.response?.data?.detail || 'تعذر اعتماد الطلب')
    }
  }

  const openApproveConfirm = (action) => {
    setPendingApproveAction(() => action)
    setApproveConfirmOpen(true)
  }

  const runApproveConfirm = async () => {
    setApproveConfirmOpen(false)
    if (pendingApproveAction) await pendingApproveAction()
    setPendingApproveAction(null)
  }

  const modifyApprove = async () => {
    if (!selected) return
    if (!approvalNote.trim()) {
      toast.error('ملاحظة التعديل مطلوبة')
      return
    }
    try {
      await supplyChainApi.modifyApproveBranchRequest(selected.id, {
        approval_note: approvalNote,
        lines: selected.lines.map((line) => ({
          line_id: line.id,
          qty_approved: Number(lineApprovals[line.id] || 0),
          approval_note: null,
        })),
      })
      toast.success('تم تعديل الكميات واعتماد الطلب')
      await load()
      setSelected(null)
    } catch (error) {
      toast.error(error?.response?.data?.message || error?.response?.data?.detail || 'تعذر تعديل واعتماد الطلب')
    }
  }

  const reject = async () => {
    if (!selected) return
    if (!rejectNote.trim()) {
      toast.error('سبب الرفض مطلوب')
      return
    }
    try {
      await supplyChainApi.rejectBranchRequest(selected.id, { rejection_note: rejectNote })
      toast.success('تم رفض الطلب')
      await load()
      setSelected(null)
    } catch (error) {
      toast.error(error?.response?.data?.message || error?.response?.data?.detail || 'تعذر رفض الطلب')
    }
  }

  const openRejectConfirm = () => {
    if (!rejectNote.trim()) {
      toast.error('سبب الرفض مطلوب')
      return
    }
    setRejectConfirmOpen(true)
  }

  return (
    <PageShell title="موافقات مدير المنطقة" subtitle="الاعتماد يرسل الأسطر تلقائيًا للمطبخ أو المستودع حسب نوع الصنف">
      <ConfirmDialog
        open={approveConfirmOpen && !!selected}
        title="تأكيد الاعتماد"
        onCancel={() => { setApproveConfirmOpen(false); setPendingApproveAction(null) }}
        onConfirm={runApproveConfirm}
      >
        {selected && (() => {
          const counts = countApprovalRoutes(selected.lines)
          return (
            <>
              <p>هذا الاعتماد سيرسل:</p>
              <ul className="list-disc list-inside">
                <li>{counts.kitchen} سطر/أسطر إلى المطبخ</li>
                <li>{counts.warehouse} سطر/أسطر إلى المستودع</li>
                {counts.mixed > 0 && <li>{counts.mixed} سطر/أسطر (مسار افتراضي / مختلط)</li>}
              </ul>
              <p className="font-medium pt-2">هل أنت متأكد؟</p>
            </>
          )
        })()}
      </ConfirmDialog>
      <ConfirmDialog
        open={rejectConfirmOpen && !!selected}
        title="تأكيد الرفض"
        confirmLabel="رفض الطلب"
        confirmClassName="btn-secondary !bg-red-50 !text-red-700 !border-red-200"
        onCancel={() => setRejectConfirmOpen(false)}
        onConfirm={() => { setRejectConfirmOpen(false); reject() }}
      >
        {selected && (
          <>
            <p><strong>رقم الطلب:</strong> {selected.request_no}</p>
            <p><strong>عدد الأسطر:</strong> {selected.lines.length}</p>
            <p><strong>سبب الرفض:</strong> {rejectNote}</p>
            <p className="font-medium pt-2 text-red-700">هل أنت متأكد من رفض هذا الطلب؟</p>
          </>
        )}
      </ConfirmDialog>
      <SupplyChainFilterBar
        filters={listFilters}
        onChange={setListFilters}
        statusOptions={BRANCH_REQUEST_STATUS_OPTIONS}
        showBranch={false}
        showItem={false}
      />
      <div className="grid xl:grid-cols-[380px,1fr] gap-6">
        <div className="card divide-y divide-gray-100">
          {loading ? (
            <div className="p-6 text-center text-gray-400">جارٍ التحميل...</div>
          ) : requests.length === 0 ? (
            <div className="p-6 text-center text-gray-400">لا توجد طلبات بانتظارك</div>
          ) : requests.map((request) => (
            <button key={request.id} type="button" onClick={() => selectRequest(request)} className={`p-4 text-right hover:bg-gray-50 w-full ${selected?.id === request.id ? 'bg-blue-50' : ''}`}>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="font-semibold text-gray-900">{request.request_no}</div>
                  <div className="text-xs text-gray-500 mt-1">{formatDate(request.submitted_at || request.created_at)}</div>
                </div>
                <StatusBadge status={request.status} />
              </div>
            </button>
          ))}
        </div>

        <div className="card p-5">
          {!selected ? (
            <div className="text-center text-gray-400 py-16">اختر طلبًا من القائمة</div>
          ) : (
            <div className="space-y-5">
              {isAuditor && <ReadOnlyBanner message="المراجع الداخلي يستطيع مراجعة الطلبات المرسلة والكميات المقترحة فقط، لكن لا يمكنه اعتماد أو رفض أو تعديل الطلب من هذه الصفحة." />}
              <div className="flex items-center justify-between gap-4">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">{selected.request_no}</h2>
                  <p className="text-sm text-gray-500">عدد الأسطر: {selected.lines.length}</p>
                  <Link to={`/supply-chain/branch-requests/${selected.id}`} className="text-sm text-blue-700 hover:underline">عرض التفاصيل والمسار</Link>
                </div>
                <StatusBadge status={selected.status} />
              </div>

              <div className="overflow-x-auto">
                <table className="table">
                  <thead>
                    <tr>
                      <th>الصنف</th>
                      <th>المطلوب</th>
                      <th>الكمية المعتمدة</th>
                      <th>المصدر</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selected.lines.map((line) => (
                      <tr key={line.id}>
                        <td>{itemLabel(line.item)}</td>
                        <td>{numberValue(line.qty_requested)}</td>
                        <td>
                          <input
                            type="number"
                            min="0"
                            step="0.01"
                            value={lineApprovals[line.id] || ''}
                            onChange={(e) => setLineApprovals((prev) => ({ ...prev, [line.id]: e.target.value }))}
                            className="input-field max-w-32"
                            disabled={isAuditor}
                          />
                        </td>
                        <td>{sourceRouteLabel(line)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {!isAuditor && (
                <>
                  <div className="grid md:grid-cols-2 gap-4">
                    <div>
                      <label className="label">ملاحظة الاعتماد / التعديل</label>
                      <textarea value={approvalNote} onChange={(e) => setApprovalNote(e.target.value)} className="input-field min-h-28" placeholder="اكتب ملاحظة إذا أردت، وتصبح مطلوبة عند التعديل" />
                    </div>
                    <div>
                      <label className="label">سبب الرفض</label>
                      <textarea value={rejectNote} onChange={(e) => setRejectNote(e.target.value)} className="input-field min-h-28" placeholder="مطلوب فقط عند الرفض" />
                    </div>
                  </div>

                  <div className="flex gap-3 flex-wrap">
                    <button type="button" onClick={() => openApproveConfirm(approve)} className="btn-primary">اعتماد</button>
                    <button type="button" onClick={() => openApproveConfirm(modifyApprove)} className="btn-secondary">تعديل واعتماد</button>
                    <button type="button" onClick={openRejectConfirm} className="btn-secondary !bg-red-50 !text-red-700 !border-red-200">رفض</button>
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </PageShell>
  )
}

export function SupplyChainKitchenPage() {
  const roles = useSelector(selectUserRoles)
  const isAuditor = roles.includes('internal_auditor')
  const [loading, setLoading] = React.useState(true)
  const [dailyOrders, setDailyOrders] = React.useState([])
  const [productionOrders, setProductionOrders] = React.useState([])
  const [selectedDaily, setSelectedDaily] = React.useState(null)
  const [partialQty, setPartialQty] = React.useState({})
  const [sendConfirm, setSendConfirm] = React.useState(null)

  const load = React.useCallback(async () => {
    setLoading(true)
    try {
      const [productionRes, dailyOrdersRes] = await Promise.all([
        supplyChainApi.listProductionOrders(),
        supplyChainApi.listDailyKitchenOrders(),
      ])
      setProductionOrders(Array.isArray(productionRes.data) ? productionRes.data : [])
      const nextDaily = Array.isArray(dailyOrdersRes.data) ? dailyOrdersRes.data : []
      setDailyOrders(nextDaily)
      setSelectedDaily((current) => current ? nextDaily.find((row) => row.id === current.id) || null : null)
    } catch (error) {
      toast.error(error?.response?.data?.message || error?.response?.data?.detail || 'تعذر تحميل أوامر المطبخ')
    } finally {
      setLoading(false)
    }
  }, [])

  React.useEffect(() => { load() }, [load])

  const action = async (runner, success) => {
    try {
      await runner()
      toast.success(success)
      await load()
    } catch (error) {
      toast.error(error?.response?.data?.message || error?.response?.data?.detail || 'تعذر تنفيذ الإجراء')
    }
  }

  const kitchenStatusLabel = {
    picking: 'بانتظار استلام المطبخ',
    approved: 'بانتظار استلام المطبخ',
    kitchen_received: 'استلم المطبخ',
    kitchen_in_progress: 'قيد التجهيز',
    kitchen_ready: 'جاهز للإرسال',
    kitchen_sent_to_warehouse: 'أرسل للمستودع',
  }

  const dailyStep = (status) => {
    if (status === 'kitchen_sent_to_warehouse') return 4
    if (status === 'kitchen_ready') return 3
    if (status === 'kitchen_in_progress') return 2
    if (status === 'kitchen_received') return 1
    return 0
  }

  const printDailyPdf = async (id) => {
    const win = window.open('', '_blank')
    try {
      const res = await supplyChainApi.dailyKitchenOrderPdf(id)
      if (win) {
        win.document.open()
        win.document.write(res.data)
        win.document.close()
      } else {
        toast.error('المتصفح منع فتح صفحة الطباعة')
      }
    } catch (error) {
      if (win) win.close()
      toast.error(error?.response?.data?.message || error?.response?.data?.detail || 'تعذر فتح ملف PDF')
    }
  }

  const dailyActions = (order) => (
    <div className="flex flex-wrap gap-2">
      <button type="button" className="btn-secondary text-xs" onClick={() => setSelectedDaily(order)}>عرض</button>
      <button type="button" className="btn-secondary text-xs" onClick={() => printDailyPdf(order.id)}>PDF</button>
      {!isAuditor && (
        <>
          <button
            type="button"
            disabled={dailyStep(order.kitchen_status) !== 0}
            className={`${dailyStep(order.kitchen_status) === 0 ? 'btn-primary' : 'btn-secondary opacity-50 cursor-not-allowed'} text-xs`}
            onClick={() => action(() => supplyChainApi.receiveDailyKitchenOrder(order.id), 'تم استلام الطلبية في المطبخ')}
          >
            استلام
          </button>
          <button
            type="button"
            disabled={dailyStep(order.kitchen_status) !== 1}
            className={`${dailyStep(order.kitchen_status) === 1 ? 'btn-primary' : 'btn-secondary opacity-50 cursor-not-allowed'} text-xs`}
            onClick={() => action(() => supplyChainApi.startDailyKitchenOrder(order.id), 'تم بدء التجهيز')}
          >
            بدء تجهيز
          </button>
          <button
            type="button"
            disabled={dailyStep(order.kitchen_status) !== 2}
            className={`${dailyStep(order.kitchen_status) === 2 ? 'btn-primary' : 'btn-secondary opacity-50 cursor-not-allowed'} text-xs`}
            onClick={() => action(() => supplyChainApi.markDailyKitchenOrderReady(order.id), 'تم تجهيز الطلبية')}
          >
            جاهز
          </button>
          <button
            type="button"
            disabled={dailyStep(order.kitchen_status) !== 3}
            className={`${dailyStep(order.kitchen_status) === 3 ? 'btn-primary' : 'btn-secondary opacity-50 cursor-not-allowed'} text-xs`}
            onClick={() => action(() => supplyChainApi.sendDailyKitchenOrderToWarehouse(order.id), 'تم إرسال الطلبية للمستودع')}
          >
            إرسال للمستودع
          </button>
        </>
      )}
    </div>
  )

  if (selectedDaily) {
    return (
      <PageShell
        title={`طلبية مطبخ - ${selectedDaily.order_no}`}
        subtitle={`الفرع: ${selectedDaily.branch_name}`}
        actions={<button type="button" className="btn-secondary" onClick={() => setSelectedDaily(null)}>رجوع</button>}
      >
        {isAuditor && <ReadOnlyBanner message="المراجع الداخلي يرى الطلبية فقط ولا يمكنه تنفيذ إجراءات تشغيلية." />}
        <div className="card p-4">
          <div className="flex items-center justify-between gap-3 flex-wrap mb-4">
            <div className="space-y-1">
              <div className="font-semibold">{selectedDaily.branch_name}</div>
              <div className="text-sm text-gray-500">{selectedDaily.order_no}</div>
              <StatusBadge status={selectedDaily.kitchen_status} />
            </div>
            {dailyActions(selectedDaily)}
        </div>
          <div className="mb-4 grid grid-cols-4 gap-2 text-center text-xs">
            {[
              ['استلام', 1],
              ['بدء تجهيز', 2],
              ['جاهز', 3],
              ['أرسل للمستودع', 4],
            ].map(([label, step]) => (
              <div
                key={label}
                className={`rounded border px-2 py-2 ${
                  dailyStep(selectedDaily.kitchen_status) >= step
                    ? 'border-blue-600 bg-blue-50 text-blue-700 font-semibold'
                    : 'border-gray-200 bg-gray-50 text-gray-400'
                }`}
              >
                {label}
              </div>
            ))}
          </div>
          <div className="table-container">
            <table className="table">
              <thead>
                <tr>
                  <th>الصنف</th>
                  <th>الكود</th>
                  <th>المطلوب</th>
                  <th>الجاهز</th>
                  <th>المرسل للمستودع</th>
                  <th>الحالة</th>
                </tr>
              </thead>
              <tbody>
                {selectedDaily.lines.map((line) => (
                  <tr key={line.id}>
                    <td>{itemLabel(line.item)}</td>
                    <td className="font-mono text-xs text-gray-500">{line.item?.item_code}</td>
                    <td>{numberValue(line.qty_requested)}</td>
                    <td>{numberValue(line.qty_ready)}</td>
                    <td>{numberValue(line.qty_sent_to_warehouse)}</td>
                    <td>{kitchenStatusLabel[line.line_status] || line.line_status || kitchenStatusLabel[selectedDaily.kitchen_status] || selectedDaily.kitchen_status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </PageShell>
    )
  }

  const confirmSendProduction = (order) => {
    setSendConfirm({
      title: 'تأكيد الإرسال للمستودع',
      body: (
        <>
          <p><strong>الصنف:</strong> {itemLabel(order.item)}</p>
          <p><strong>الكمية الجاهزة:</strong> {numberValue(order.qty_ready)}</p>
          <p><strong>الفرع:</strong> {branchDisplay(order)}</p>
          <p><strong>المستودع:</strong> {order.destination_warehouse_name || 'مستودع الفرع'}</p>
        </>
      ),
      onConfirm: () => action(() => supplyChainApi.sendProductionToWarehouse(order.id), 'تم إرسال الكمية للمستودع'),
    })
  }

  return (
    <PageShell title="أوامر أقسام المطبخ" subtitle="الطلبات مجمعة حسب الفرع ورقم الطلبية">
      <ConfirmDialog
        open={!!sendConfirm}
        title={sendConfirm?.title || ''}
        onCancel={() => setSendConfirm(null)}
        onConfirm={() => { sendConfirm?.onConfirm?.(); setSendConfirm(null) }}
      >
        {sendConfirm?.body}
      </ConfirmDialog>
      {isAuditor && <ReadOnlyBanner message="المراجع الداخلي يرى أوامر الإنتاج وحالاتها فقط." />}
      <div className="card table-container">
        <table className="table">
          <thead>
            <tr>
              <th>رقم الطلبية</th>
              <th>الفرع</th>
              <th>عدد الأصناف</th>
              <th>الجاهز</th>
              <th>المرسل للمستودع</th>
              <th>الحالة</th>
              <th>إجراءات</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={7} className="text-center py-8 text-gray-400">جاري التحميل...</td></tr>
            ) : dailyOrders.length === 0 && productionOrders.length === 0 ? (
              <tr><td colSpan={7} className="text-center py-8 text-gray-400">لا توجد أوامر لهذا القسم</td></tr>
            ) : (
              <>
                {dailyOrders.map((order) => (
                  <tr key={`daily-${order.id}`}>
                    <td className="font-mono text-sm font-semibold">{order.order_no}</td>
                    <td>{order.branch_name}</td>
                    <td>{order.items_count}</td>
                    <td>{numberValue(order.qty_ready_total)}</td>
                    <td>{numberValue(order.qty_sent_total)}</td>
                    <td><StatusBadge status={order.kitchen_status} /></td>
                    <td>{dailyActions(order)}</td>
                  </tr>
                ))}
                {productionOrders.map((order) => (
                  <tr key={`production-${order.id}`}>
                    <td className="font-medium">PO-{order.id}</td>
                    <td>{branchDisplay(order)}</td>
                    <td>1</td>
                    <td>{numberValue(order.qty_ready)}</td>
                    <td>{numberValue(order.qty_sent_to_warehouse || 0)}</td>
                    <td><StatusBadge status={order.status} /></td>
                    <td>
                      {isAuditor ? (
                        <span className="text-sm text-gray-500">قراءة فقط</span>
                      ) : productionIsClosed(order.status) ? (
                        <span className="text-sm text-gray-500">مكتمل</span>
                      ) : (
                        <div className="flex flex-wrap gap-2">
                          {productionCanStart(order.status) && (
                            <button type="button" className="btn-primary text-xs" onClick={() => action(() => supplyChainApi.startProductionOrder(order.id), 'تم بدء التنفيذ')}>بدء</button>
                          )}
                          {productionCanPartialReady(order.status) && (
                            <div className="flex gap-2">
                              <input
                                type="number"
                                min="0"
                                step="0.01"
                                value={partialQty[order.id] || ''}
                                onChange={(e) => setPartialQty((prev) => ({ ...prev, [order.id]: e.target.value }))}
                                className="input-field w-24 text-xs"
                                placeholder="جزئي"
                              />
                              <button
                                type="button"
                                className="btn-secondary text-xs"
                                onClick={() => action(
                                  () => supplyChainApi.markProductionPartialReady(order.id, { qty_ready: Number(partialQty[order.id] || 0) }),
                                  'تم تسجيل جاهزية جزئية',
                                )}
                              >
                                جاهز جزئيًا
                              </button>
                            </div>
                          )}
                          {productionCanMarkReady(order.status) && (
                            <button type="button" className="btn-secondary text-xs" onClick={() => action(() => supplyChainApi.markProductionReady(order.id), 'تم تعليم الأمر جاهزًا')}>جاهز</button>
                          )}
                          {productionCanSendToWarehouse(order.status) && (
                            <button type="button" className="btn-primary text-xs" onClick={() => confirmSendProduction(order)}>إرسال للمستودع</button>
                          )}
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </>
            )}
          </tbody>
        </table>
      </div>
    </PageShell>
  )
}

function LegacySupplyChainKitchenPage() {
  const roles = useSelector(selectUserRoles)
  const isAuditor = roles.includes('internal_auditor')
  const [loading, setLoading] = React.useState(true)
  const [orders, setOrders] = React.useState([])
  const [partialQty, setPartialQty] = React.useState({})

  const load = React.useCallback(async () => {
    setLoading(true)
    try {
      const [productionRes, dailyRes] = await Promise.all([
        supplyChainApi.listProductionOrders(),
        supplyChainApi.listDailyKitchenLines(),
      ])
      const productionOrders = Array.isArray(productionRes.data) ? productionRes.data : []
      const dailyKitchenLines = Array.isArray(dailyRes.data) ? dailyRes.data : []
      setOrders([...dailyKitchenLines, ...productionOrders])
    } catch (error) {
      toast.error(error?.response?.data?.message || error?.response?.data?.detail || 'تعذر تحميل أوامر الإنتاج')
    } finally {
      setLoading(false)
    }
  }, [])

  React.useEffect(() => { load() }, [])

  const action = async (runner, success) => {
    try {
      await runner()
      toast.success(success)
      await load()
    } catch (error) {
      toast.error(error?.response?.data?.message || error?.response?.data?.detail || 'تعذر تنفيذ الإجراء')
    }
  }

  return (
    <PageShell title="أوامر أقسام المطبخ" subtitle="هذه الصفحة scoped تلقائيًا حسب kitchen_section_assignment للمستخدم">
      {isAuditor && <ReadOnlyBanner message="المراجع الداخلي يرى أوامر الإنتاج وحالاتها وملاحظاتها فقط، ولا يمكنه بدء الإنتاج أو تسجيل جاهزية أو إرسال للمستودع." />}
      <div className="card table-container">
        <table className="table">
          <thead>
            <tr>
              <th>#</th>
              <th>الصنف</th>
              <th>الفرع الهدف</th>
              <th>المطلوب</th>
              <th>الجاهز</th>
              <th>الملاحظات</th>
              <th>الحالة</th>
              <th>إجراءات</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={8} className="text-center py-8 text-gray-400">جارٍ التحميل...</td></tr>
            ) : orders.length === 0 ? (
              <tr><td colSpan={8} className="text-center py-8 text-gray-400">لا توجد أوامر لهذا القسم</td></tr>
            ) : orders.map((order) => (
              <tr key={order.id}>
                <td className="font-medium">PO-{order.id}</td>
                <td>{itemLabel(order.item)}</td>
                <td>{order.destination_branch?.branch_name || order.destination_branch?.branch_name_ar || order.destination_branch_id}</td>
                <td>{numberValue(order.qty_requested)}</td>
                <td>{numberValue(order.qty_ready)}</td>
                <td className="max-w-56 whitespace-pre-wrap text-sm text-gray-600">
                  {order.legacy_daily ? `طلبية يومية: ${order.source_order_no}` : (order.notes || '—')}
                </td>
                <td><StatusBadge status={order.status} /></td>
                <td>
                  {isAuditor ? (
                    <span className="text-sm text-gray-500">قراءة فقط</span>
                  ) : order.legacy_daily ? (
                    <span className="text-sm text-gray-500">من طلبية يومية</span>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      <button type="button" className="btn-secondary text-xs" onClick={() => action(() => supplyChainApi.startProductionOrder(order.id), 'تم بدء التنفيذ')}>بدء</button>
                      <div className="flex gap-2">
                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          value={partialQty[order.id] || ''}
                          onChange={(e) => setPartialQty((prev) => ({ ...prev, [order.id]: e.target.value }))}
                          className="input-field w-24 text-xs"
                          placeholder="جزئي"
                        />
                        <button
                          type="button"
                          className="btn-secondary text-xs"
                          onClick={() => action(
                            () => supplyChainApi.markProductionPartialReady(order.id, { qty_ready: Number(partialQty[order.id] || 0) }),
                            'تم تسجيل جاهزية جزئية',
                          )}
                        >
                          جاهز جزئيًا
                        </button>
                      </div>
                      <button type="button" className="btn-secondary text-xs" onClick={() => action(() => supplyChainApi.markProductionReady(order.id), 'تم تعليم الأمر جاهزًا')}>جاهز</button>
                      <button type="button" className="btn-primary text-xs" onClick={() => action(() => supplyChainApi.sendProductionToWarehouse(order.id), 'تم إرسال الكمية للمستودع')}>إرسال للمستودع</button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </PageShell>
  )
}

export function SupplyChainWarehousePage() {
  const roles = useSelector(selectUserRoles)
  const isAuditor = roles.includes('internal_auditor')
  const [loading, setLoading] = React.useState(true)
  const [lines, setLines] = React.useState([])
  const [tab, setTab] = React.useState('ALL')
  const [issueQty, setIssueQty] = React.useState({})
  const [delayReason, setDelayReason] = React.useState({})
  const [issueConfirm, setIssueConfirm] = React.useState(null)
  const [deliveryConfirm, setDeliveryConfirm] = React.useState(null)
  const [listFilters, setListFilters] = React.useState({ ...EMPTY_FILTERS })
  const [branches, setBranches] = React.useState([])
  const [items, setItems] = React.useState([])

  const sourceTypeLabel = {
    BRANCH_REQUEST: 'طلب فرع',
    KITCHEN_OUTPUT: 'مخرجات مطبخ',
    KITCHEN_MATERIAL_REQUEST: 'طلب خامات',
  }

  const load = React.useCallback(async () => {
    setLoading(true)
    try {
      const res = await supplyChainApi.listWarehouseLines(buildFilterParams(listFilters))
      setLines(Array.isArray(res.data) ? res.data : [])
    } catch (error) {
      toast.error(error?.response?.data?.message || error?.response?.data?.detail || 'تعذر تحميل خطوط المستودع')
    } finally {
      setLoading(false)
    }
  }, [listFilters])

  React.useEffect(() => { load() }, [load])

  React.useEffect(() => {
    masterApi.listBranches({ active_only: true })
      .then((res) => setBranches(Array.isArray(res.data) ? res.data : []))
      .catch(() => {})
    masterApi.listItems({ active_only: true, page_size: 500 })
      .then((res) => setItems(res.data?.items || res.data || []))
      .catch(() => {})
  }, [])

  const filtered = lines.filter((line) => {
    if (tab === 'KITCHEN_OUTPUT') return line.source_type === 'KITCHEN_OUTPUT'
    if (tab === 'BACKORDER') return line.status === 'BACKORDER'
    if (tab === 'BRANCH_REQUEST') return line.source_type === 'BRANCH_REQUEST'
    return true
  })

  const run = async (runner, success) => {
    try {
      await runner()
      toast.success(success)
      await load()
    } catch (error) {
      toast.error(error?.response?.data?.message || error?.response?.data?.detail || 'تعذر تنفيذ الإجراء')
    }
  }

  const createDelivery = async (lineId) => {
    await run(() => supplyChainApi.createDeliveryOrder({ warehouse_line_ids: [lineId] }), 'تم إنشاء أمر تسليم')
  }

  const openCreateDeliveryConfirm = (line) => {
    setDeliveryConfirm({
      line,
      body: (
        <>
          <p><strong>الفرع:</strong> {branchDisplay(line)}</p>
          <p><strong>الصنف:</strong> {itemLabel(line.item)}</p>
          <p><strong>المصروف:</strong> {numberValue(line.issued_qty)}</p>
          <p><strong>المتبقي:</strong> {numberValue(line.pending_qty)}</p>
          <p className="font-medium pt-2">سيتم إنشاء أمر تسليم لهذا السطر.</p>
        </>
      ),
    })
  }

  const openFullIssueConfirm = (line) => {
    const issue = Number(line.pending_qty || line.requested_qty || 0)
    setIssueConfirm({
      title: 'تأكيد الصرف الكامل',
      body: (
        <>
          <p><strong>الفرع:</strong> {branchDisplay(line)}</p>
          <p><strong>الصنف:</strong> {itemLabel(line.item)}</p>
          <p><strong>المخزون المتاح:</strong> {numberValue(line.available_stock ?? '—')}</p>
          <p><strong>المطلوب:</strong> {numberValue(line.requested_qty)}</p>
          <p><strong>المصروف سابقًا:</strong> {numberValue(line.issued_qty)}</p>
          <p><strong>كمية الصرف:</strong> {issue}</p>
          <p><strong>المتبقي بعد الصرف:</strong> 0</p>
        </>
      ),
      onConfirm: () => run(() => supplyChainApi.issueWarehouseLine(line.id), 'تم الصرف بالكامل'),
    })
  }

  const openPartialIssueConfirm = (line) => {
    const qty = Number(issueQty[line.id] || 0)
    const pending = Number(line.pending_qty || 0)
    setIssueConfirm({
      title: 'تأكيد الصرف الجزئي',
      body: (
        <>
          <p><strong>الفرع:</strong> {branchDisplay(line)}</p>
          <p><strong>الصنف:</strong> {itemLabel(line.item)}</p>
          <p><strong>المخزون المتاح:</strong> {numberValue(line.available_stock ?? '—')}</p>
          <p><strong>المطلوب:</strong> {numberValue(line.requested_qty)}</p>
          <p><strong>المصروف سابقًا:</strong> {numberValue(line.issued_qty)}</p>
          <p><strong>كمية الصرف:</strong> {qty}</p>
          <p><strong>المتبقي:</strong> {Math.max(0, pending - qty)}</p>
          <p><strong>سبب التأخير:</strong> {delayReason[line.id] || '—'}</p>
        </>
      ),
      onConfirm: () => run(
        () => supplyChainApi.partialIssueWarehouseLine(line.id, {
          qty,
          delay_reason: delayReason[line.id] || '',
        }),
        'تم الصرف الجزئي',
      ),
    })
  }

  return (
    <PageShell title="تنفيذ المستودع" subtitle="يعرض فقط warehouse_lines الخاصة بمستودع المستخدم">
      <ConfirmDialog
        open={!!issueConfirm}
        title={issueConfirm?.title || ''}
        onCancel={() => setIssueConfirm(null)}
        onConfirm={() => { issueConfirm?.onConfirm?.(); setIssueConfirm(null) }}
      >
        {issueConfirm?.body}
      </ConfirmDialog>
      <ConfirmDialog
        open={!!deliveryConfirm}
        title="تأكيد إنشاء أمر تسليم"
        onCancel={() => setDeliveryConfirm(null)}
        onConfirm={() => {
          const lineId = deliveryConfirm?.line?.id
          setDeliveryConfirm(null)
          if (lineId) createDelivery(lineId)
        }}
      >
        {deliveryConfirm?.body}
      </ConfirmDialog>
      {isAuditor && <ReadOnlyBanner message="المراجع الداخلي يرى خطوط المستودع وحالات الصرف والتأخير فقط، ولا يمكنه الاستلام أو الصرف أو إنشاء أوامر تسليم من هذه الصفحة." />}
      <SupplyChainFilterBar
        filters={listFilters}
        onChange={setListFilters}
        branches={branches}
        items={items}
        statusOptions={WAREHOUSE_LINE_STATUS_OPTIONS}
        showBranch
        showItem
        showStatus
      />
      <div className="flex gap-2 flex-wrap">
        {[
          ['ALL', 'الكل'],
          ['BRANCH_REQUEST', 'طلبات الفروع'],
          ['KITCHEN_OUTPUT', 'إنتاج المطبخ'],
          ['BACKORDER', 'النواقص'],
        ].map(([value, label]) => (
          <button key={value} type="button" onClick={() => setTab(value)} className={tab === value ? 'btn-primary' : 'btn-secondary'}>{label}</button>
        ))}
      </div>

      <div className="card table-container">
        <table className="table">
          <thead>
            <tr>
              <th>#</th>
              <th>الصنف</th>
              <th>الفرع</th>
              <th>النوع</th>
              <th>المخزون المتاح</th>
              <th>المطلوب</th>
              <th>المصروف</th>
              <th>المتبقي</th>
              <th>الملاحظات / سبب التأخير</th>
              <th>الحالة</th>
              <th>إجراءات</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={11} className="text-center py-8 text-gray-400">جارٍ التحميل...</td></tr>
            ) : filtered.length === 0 ? (
              <tr><td colSpan={11} className="text-center py-8 text-gray-400">لا توجد بيانات لهذا التبويب</td></tr>
            ) : filtered.map((line) => (
              <tr key={line.id}>
                <td className="font-medium">WL-{line.id}</td>
                <td>{itemLabel(line.item)}</td>
                <td>{branchDisplay(line)}</td>
                <td>{sourceTypeLabel[line.source_type] || line.source_type}</td>
                <td className={Number(line.available_stock) <= 0 ? 'text-red-700 font-medium' : ''}>{numberValue(line.available_stock ?? '—')}</td>
                <td>{numberValue(line.requested_qty)}</td>
                <td>{numberValue(line.issued_qty)}</td>
                <td className={Number(line.pending_qty) > 0 ? 'text-amber-700 font-medium' : ''}>{numberValue(line.pending_qty)}</td>
                <td className="max-w-56 whitespace-pre-wrap text-sm text-gray-600">
                  {String(line.delay_reason || '').startsWith('daily_order:') ? 'من طلبية يومية' : (line.delay_reason || line.notes || '—')}
                </td>
                <td><StatusBadge status={line.status} /></td>
                <td>
                  {isAuditor ? (
                    <span className="text-sm text-gray-500">قراءة فقط</span>
                  ) : (
                    <div className="space-y-2">
                      <div className="flex gap-2 flex-wrap">
                        {canReceiveWarehouseLine(line) && (
                          <button type="button" className="btn-secondary text-xs" onClick={() => run(() => supplyChainApi.receiveWarehouseLine(line.id), 'تم الاستلام / الإقرار')}>استلام</button>
                        )}
                        {canIssueWarehouseLine(line) && (
                          <button type="button" className="btn-secondary text-xs" onClick={() => openFullIssueConfirm(line)}>صرف كامل</button>
                        )}
                        {canCreateDeliveryFromLine(line) && (
                          <button type="button" className="btn-secondary text-xs" onClick={() => openCreateDeliveryConfirm(line)}>إنشاء أمر تسليم</button>
                        )}
                        {!canReceiveWarehouseLine(line) && !canIssueWarehouseLine(line) && !canCreateDeliveryFromLine(line) && (
                          <span className="text-xs text-gray-500">لا إجراءات متاحة</span>
                        )}
                      </div>
                      {canIssueWarehouseLine(line) && (
                      <div className="flex gap-2 flex-wrap">
                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          value={issueQty[line.id] || ''}
                          onChange={(e) => setIssueQty((prev) => ({ ...prev, [line.id]: e.target.value }))}
                          className="input-field w-24 text-xs"
                          placeholder="كمية"
                        />
                        <input
                          value={delayReason[line.id] || ''}
                          onChange={(e) => setDelayReason((prev) => ({ ...prev, [line.id]: e.target.value }))}
                          className="input-field w-48 text-xs"
                          placeholder="سبب التأخير"
                        />
                        <button
                          type="button"
                          className="btn-secondary text-xs"
                          onClick={() => openPartialIssueConfirm(line)}
                        >
                          صرف جزئي
                        </button>
                        <button
                          type="button"
                          className="btn-secondary text-xs"
                          onClick={() => run(
                            () => supplyChainApi.addWarehouseDelayReason(line.id, { delay_reason: delayReason[line.id] || '' }),
                            'تم حفظ سبب التأخير',
                          )}
                        >
                          تسجيل تأخير
                        </button>
                      </div>
                      )}
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </PageShell>
  )
}

export function SupplyChainDeliveryPage() {
  const roles = useSelector(selectUserRoles)
  const isAuditor = roles.includes('internal_auditor')
  const [loading, setLoading] = React.useState(true)
  const [orders, setOrders] = React.useState([])
  const [receiverName, setReceiverName] = React.useState({})
  const [deliveryNote, setDeliveryNote] = React.useState({})
  const [deliverConfirm, setDeliverConfirm] = React.useState(null)
  const [outForDeliveryConfirm, setOutForDeliveryConfirm] = React.useState(null)
  const [expandedOrderId, setExpandedOrderId] = React.useState(null)
  const [listFilters, setListFilters] = React.useState({ ...EMPTY_FILTERS })
  const [branches, setBranches] = React.useState([])

  const load = React.useCallback(async () => {
    setLoading(true)
    try {
      const res = await supplyChainApi.listDeliveryOrders(buildFilterParams(listFilters))
      setOrders(Array.isArray(res.data) ? res.data : [])
    } catch (error) {
      toast.error(error?.response?.data?.message || error?.response?.data?.detail || 'تعذر تحميل أوامر التسليم')
    } finally {
      setLoading(false)
    }
  }, [listFilters])

  React.useEffect(() => { load() }, [load])

  React.useEffect(() => {
    masterApi.listBranches({ active_only: true })
      .then((res) => setBranches(Array.isArray(res.data) ? res.data : []))
      .catch(() => {})
  }, [])

  const run = async (runner, success) => {
    try {
      await runner()
      toast.success(success)
      await load()
    } catch (error) {
      toast.error(error?.response?.data?.message || error?.response?.data?.detail || 'تعذر تنفيذ الإجراء')
    }
  }

  const openDeliverConfirm = (order) => {
    const name = (receiverName[order.id] || '').trim()
    if (!name) {
      toast.error('اسم المستلم مطلوب')
      return
    }
    const dispatched = (order.lines || []).reduce((sum, line) => sum + Number(line.qty_dispatched || 0), 0)
    const delivered = (order.lines || []).reduce((sum, line) => sum + Number(line.qty_delivered || line.qty_dispatched || 0), 0)
    const shortage = (order.lines || []).reduce((sum, line) => sum + Number(line.shortage_qty || 0), 0)
    setDeliverConfirm({
      order,
      body: (
        <>
          <p><strong>الفرع:</strong> {branchDisplay(order)}</p>
          <p><strong>الكمية المخرجة:</strong> {dispatched}</p>
          <p><strong>الكمية المسلّمة:</strong> {delivered || dispatched}</p>
          <p><strong>اسم المستلم:</strong> {name}</p>
          {shortage > 0 && <p><strong>النقص:</strong> {shortage}</p>}
        </>
      ),
    })
  }

  const openOutForDeliveryConfirm = (order) => {
    const dispatched = (order.lines || []).reduce((sum, line) => sum + Number(line.qty_dispatched || line.qty_issued || 0), 0)
    setOutForDeliveryConfirm({
      order,
      body: (
        <>
          <p><strong>أمر التسليم:</strong> DO-{order.id}</p>
          <p><strong>الفرع:</strong> {branchDisplay(order)}</p>
          <p><strong>عدد الأسطر:</strong> {order.lines?.length || 0}</p>
          <p><strong>الكمية المخرجة:</strong> {dispatched}</p>
          <p className="font-medium pt-2">سيتم تغيير الحالة إلى «خرج للتسليم».</p>
        </>
      ),
    })
  }

  return (
    <PageShell title="أوامر التسليم" subtitle="إخراج أمر التسليم ثم إغلاقه كتسليم نهائي من نفس الصفحة">
      <ConfirmDialog
        open={!!outForDeliveryConfirm}
        title="تأكيد خروج للتسليم"
        onCancel={() => setOutForDeliveryConfirm(null)}
        onConfirm={() => {
          const order = outForDeliveryConfirm?.order
          setOutForDeliveryConfirm(null)
          if (order) run(() => supplyChainApi.markOutForDelivery(order.id), 'تم إخراج الطلب للتسليم')
        }}
      >
        {outForDeliveryConfirm?.body}
      </ConfirmDialog>
      <ConfirmDialog
        open={!!deliverConfirm}
        title="تأكيد التسليم"
        onCancel={() => setDeliverConfirm(null)}
        onConfirm={() => {
          const order = deliverConfirm.order
          run(
            () => supplyChainApi.deliverOrder(order.id, {
              receiver_name: receiverName[order.id],
              delivery_note: deliveryNote[order.id] || null,
            }),
            'تم تسجيل التسليم',
          )
          setDeliverConfirm(null)
        }}
      >
        {deliverConfirm?.body}
      </ConfirmDialog>
      {isAuditor && <ReadOnlyBanner message="المراجع الداخلي يرى أوامر التوصيل وبيانات التسليم فقط، ولا يمكنه إخراج الطلب للتسليم أو تأكيد التسليم من هذه الصفحة." />}
      <SupplyChainFilterBar
        filters={listFilters}
        onChange={setListFilters}
        branches={branches}
        statusOptions={DELIVERY_STATUS_OPTIONS}
        showBranch
        showItem={false}
        showStatus
      />
      <div className="card table-container">
        <table className="table">
          <thead>
            <tr>
              <th>#</th>
              <th>الفرع</th>
              <th>الحالة</th>
              <th>الأسطر</th>
              <th>الإجراءات</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={5} className="text-center py-8 text-gray-400">جارٍ التحميل...</td></tr>
            ) : orders.length === 0 ? (
              <tr><td colSpan={5} className="text-center py-8 text-gray-400">لا توجد أوامر تسليم</td></tr>
            ) : orders.map((order) => (
              <React.Fragment key={order.id}>
              <tr>
                <td className="font-medium">DO-{order.id}</td>
                <td>{branchDisplay(order)}</td>
                <td><StatusBadge status={order.status} /></td>
                <td>{order.lines?.length || 0}</td>
                <td>
                  {isAuditor ? (
                    <span className="text-sm text-gray-500">قراءة فقط</span>
                  ) : (
                    <div className="space-y-2">
                      <div className="flex gap-2 flex-wrap">
                        {order.status === 'READY' && (
                          <button type="button" className="btn-secondary text-xs" onClick={() => openOutForDeliveryConfirm(order)}>خرج للتسليم</button>
                        )}
                        <button type="button" className="btn-secondary text-xs" onClick={() => window.open(supplyChainApi.deliveryLabelsUrl(order.id), '_blank', 'noopener,noreferrer')}>طباعة Label</button>
                        <button type="button" className="btn-secondary text-xs" onClick={() => setExpandedOrderId(expandedOrderId === order.id ? null : order.id)}>تفاصيل</button>
                      </div>
                      {order.status === 'OUT_FOR_DELIVERY' && (
                      <div className="flex gap-2 flex-wrap">
                        <input
                          value={receiverName[order.id] || ''}
                          onChange={(e) => setReceiverName((prev) => ({ ...prev, [order.id]: e.target.value }))}
                          className="input-field w-40 text-xs"
                          placeholder="اسم المستلم *"
                        />
                        <input
                          value={deliveryNote[order.id] || ''}
                          onChange={(e) => setDeliveryNote((prev) => ({ ...prev, [order.id]: e.target.value }))}
                          className="input-field w-48 text-xs"
                          placeholder="ملاحظة"
                        />
                        <button
                          type="button"
                          className="btn-primary text-xs"
                          onClick={() => openDeliverConfirm(order)}
                        >
                          تم التسليم
                        </button>
                      </div>
                      )}
                      {order.status === 'DELIVERED' || order.status === 'PARTIAL_DELIVERED' ? (
                        <span className="text-xs text-gray-500">مكتمل</span>
                      ) : null}
                    </div>
                  )}
                </td>
              </tr>
              {expandedOrderId === order.id && (
                <tr>
                  <td colSpan={5} className="bg-gray-50 p-4">
                    <table className="table text-sm">
                      <thead>
                        <tr>
                          <th>الصنف</th>
                          <th>المخرج</th>
                          <th>المُسلّم</th>
                          <th>النقص</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(order.lines || []).map((line) => (
                          <tr key={line.id}>
                            <td>{itemLabel(line.item)}</td>
                            <td>{numberValue(line.qty_dispatched)}</td>
                            <td>{numberValue(line.qty_delivered)}</td>
                            <td>{numberValue(line.shortage_qty)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </td>
                </tr>
              )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </PageShell>
  )
}

function KpiCard({ title, value, to, linkLabel }) {
  return (
    <div className="card p-4 flex flex-col gap-2 min-h-[110px]">
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">{title}</p>
      <p className="text-3xl font-bold text-primary-700">{value === null || value === undefined ? '—' : value}</p>
      {to && (
        <Link to={to} className="text-sm text-primary-600 hover:underline mt-auto">
          {linkLabel}
        </Link>
      )}
    </div>
  )
}

function SummaryHeroCard({ title, value, subtitle, to, linkLabel, tone = 'primary' }) {
  const toneClasses = {
    primary: 'from-primary-50 border-primary-100 text-primary-700',
    amber: 'from-amber-50 border-amber-100 text-amber-700',
    emerald: 'from-emerald-50 border-emerald-100 text-emerald-700',
    red: 'from-red-50 border-red-100 text-red-700',
    slate: 'from-slate-50 border-slate-200 text-slate-700',
  }
  const toneClass = toneClasses[tone] || toneClasses.primary
  return (
    <div className={`rounded-2xl border bg-gradient-to-br ${toneClass} to-white p-4 flex flex-col gap-2 min-h-[132px]`}>
      <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">{title}</p>
      <p className="text-3xl font-bold">{value === null || value === undefined ? '—' : value}</p>
      {subtitle && <p className="text-sm text-gray-600">{subtitle}</p>}
      {to && (
        <Link to={to} className="text-sm text-primary-600 hover:underline mt-auto">
          {linkLabel}
        </Link>
      )}
    </div>
  )
}

function SeverityPill({ severity }) {
  const classes = {
    critical: 'bg-red-100 text-red-700',
    warning: 'bg-amber-100 text-amber-700',
    info: 'bg-sky-100 text-sky-700',
  }
  const labels = {
    critical: 'Critical',
    warning: 'Warning',
    info: 'Info',
  }
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-semibold ${classes[severity] || classes.info}`}>
      {labels[severity] || severity}
    </span>
  )
}

function SuperAdminAlertList({ alerts, openLabel }) {
  if (!alerts?.length) {
    return (
      <div className="card p-4">
        <div className="flex items-center justify-between gap-3 mb-2">
          <h3 className="text-base font-semibold text-gray-900">Critical alerts</h3>
          <span className="text-xs text-emerald-700 bg-emerald-100 rounded-full px-2 py-1">0</span>
        </div>
        <p className="text-sm text-gray-600">No critical operational alerts right now.</p>
      </div>
    )
  }
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between gap-3 mb-4">
        <h3 className="text-base font-semibold text-gray-900">Critical alerts</h3>
        <span className="text-xs text-red-700 bg-red-100 rounded-full px-2 py-1">{alerts.length}</span>
      </div>
      <div className="space-y-3">
        {alerts.map((alert) => (
          <div key={alert.key} className="rounded-xl border border-gray-200 p-3 bg-white">
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <h4 className="font-semibold text-gray-900">{alert.title}</h4>
                  <SeverityPill severity={alert.severity} />
                </div>
                {alert.description && <p className="text-sm text-gray-600">{alert.description}</p>}
              </div>
              <div className="text-right shrink-0">
                <div className="text-2xl font-bold text-gray-900">{alert.count}</div>
                {alert.to && (
                  <Link to={alert.to} className="text-xs text-primary-600 hover:underline">
                    {openLabel}
                  </Link>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function PipelineBlock({ label, count, delayedCount, partialCount, to, openLabel }) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 flex flex-col gap-3 min-h-[160px]">
      <div className="flex items-center justify-between gap-3">
        <h4 className="text-sm font-semibold text-gray-900">{label}</h4>
        {to && <Link to={to} className="text-xs text-primary-600 hover:underline">{openLabel}</Link>}
      </div>
      <div className="text-3xl font-bold text-gray-900">{count ?? '—'}</div>
      <div className="grid grid-cols-2 gap-3 text-sm">
        <div className="rounded-xl bg-red-50 p-3">
          <div className="text-gray-500">Delayed</div>
          <div className="font-semibold text-red-700">{delayedCount ?? 0}</div>
        </div>
        <div className="rounded-xl bg-amber-50 p-3">
          <div className="text-gray-500">Partial</div>
          <div className="font-semibold text-amber-700">{partialCount ?? 0}</div>
        </div>
      </div>
    </div>
  )
}

function OpsMiniTable({ title, rows, columns, emptyText, to, openLabel }) {
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between gap-3 mb-3">
        <h3 className="text-base font-semibold text-gray-900">{title}</h3>
        {to && <Link to={to} className="text-xs text-primary-600 hover:underline">{openLabel}</Link>}
      </div>
      {!rows?.length ? (
        <p className="text-sm text-gray-500">{emptyText}</p>
      ) : (
        <div className="space-y-2">
          {rows.map((row, index) => (
            <div key={`${row.id || row.label}-${index}`} className="rounded-xl border border-gray-100 bg-gray-50 p-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="font-semibold text-gray-900 truncate">{row.label}</div>
                  {row.city && <div className="text-xs text-gray-500 mt-1">{row.city}</div>}
                  {row.brand && <div className="text-xs text-gray-500 mt-1">{row.brand}</div>}
                </div>
                <div className="text-right text-sm space-y-1 shrink-0">
                  {columns.map((column) => (
                    <div key={column.key}>
                      <span className="text-gray-500">{column.label}</span>{' '}
                      <strong className="text-gray-900">{row[column.key] ?? 0}</strong>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function MetricListCard({ title, rows, to, openLabel, emptyText }) {
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between gap-3 mb-3">
        <h3 className="text-base font-semibold text-gray-900">{title}</h3>
        {to && <Link to={to} className="text-xs text-primary-600 hover:underline">{openLabel}</Link>}
      </div>
      {!rows?.length ? (
        <p className="text-sm text-gray-500">{emptyText}</p>
      ) : (
        <div className="space-y-2">
          {rows.map((row, index) => (
            <div key={`${row.label}-${index}`} className="flex items-center justify-between rounded-xl bg-gray-50 border border-gray-100 px-3 py-2">
              <span className="text-sm text-gray-700">{row.label}</span>
              <strong className="text-sm text-gray-900">{row.value}</strong>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function AuditListCard({ rows, to, openLabel }) {
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between gap-3 mb-3">
        <h3 className="text-base font-semibold text-gray-900">Recent admin audit</h3>
        {to && <Link to={to} className="text-xs text-primary-600 hover:underline">{openLabel}</Link>}
      </div>
      {!rows?.length ? (
        <p className="text-sm text-gray-500">No audit entries recorded yet.</p>
      ) : (
        <div className="space-y-2">
          {rows.map((row) => (
            <div key={row.id} className="rounded-xl border border-gray-100 bg-gray-50 p-3">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="font-semibold text-gray-900 truncate">{row.action || 'Action'}</div>
                  <div className="text-xs text-gray-500 mt-1">
                    {[row.module, row.entity_type, row.entity_id ? `#${row.entity_id}` : null].filter(Boolean).join(' · ')}
                  </div>
                </div>
                <div className="text-xs text-gray-500 shrink-0">{formatDate(row.created_at)}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function QueuePreviewBlock({ title, rows, to, emptyHint, emptyText }) {
  const isEmpty = !rows || rows.length === 0
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-gray-800">{title}</h3>
        {to && <Link to={to} className="text-xs text-primary-600 hover:underline">{emptyHint}</Link>}
      </div>
      {isEmpty ? (
        <p className="text-sm text-gray-500">{emptyText || 'No items.'}</p>
      ) : (
        <ul className="space-y-2 text-sm text-gray-700">
          {rows.map((row) => (
            <li key={row.id} className="flex justify-between gap-2 border-b border-gray-100 pb-1.5 last:border-0">
              <span className="truncate">{row.label}</span>
              {row.status && <StatusBadge status={row.status} />}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/** Step 2 — Supply Chain control center: KPIs, queue previews, auto-refresh. */
export function SupplyChainControlDashboard() {
  const t = useT()
  const roles = useSelector(selectUserRoles)
  const [loading, setLoading] = React.useState(true)
  const [autoRefresh, setAutoRefresh] = React.useState(true)
  const [refreshTick, setRefreshTick] = React.useState(0)
  const [lastUpdated, setLastUpdated] = React.useState(null)
  const [kpis, setKpis] = React.useState({
    pendingApprovals: null,
    branchRequestsTotal: null,
    productionPending: null,
    productionInProgress: null,
    warehousePending: null,
    warehouseAvailable: null,
    deliveryReady: null,
    opsAlerts: null,
    kitchenSites: null,
    requestsToday: null,
    inProduction: null,
    warehouseDelays: null,
    partialOrders: null,
    backorders: null,
    readyForDelivery: null,
    outForDelivery: null,
    deliveredToday: null,
    productionReady: null,
    sentToWarehouse: null,
    myRequests: null,
    shortages: null,
    partialWarehouse: null,
    notificationUnread: null,
  })
  const [queues, setQueues] = React.useState({
    submittedRequests: [],
    branchRequests: [],
    productionPending: [],
    productionInProgress: [],
    warehousePending: [],
    warehouseAvailable: [],
    deliveryReady: [],
  })
  const [alertsDetail, setAlertsDetail] = React.useState(null)
  const [superAdminOverview, setSuperAdminOverview] = React.useState(null)

  const isAdmin = roles.includes('admin') || roles.includes('super_admin')
  const isSuperAdmin = roles.includes('super_admin')
  const isOpsManager = roles.includes('operations_manager')
  const isAreaManager = roles.includes('area_manager')
  const isBranchOnly = (roles.includes('branch_user') || roles.includes('branch_manager')) && !isAreaManager && !isAdmin
  const isKitchen = roles.includes('kitchen_section_manager')
  const isWh = roles.includes('warehouse_user') || roles.includes('warehouse_manager')
  const isDel = roles.includes('delivery_user')
  const isOps = isOpsManager || isAdmin
  const showAdminKpis = isAdmin || isOpsManager
  const isArea = isAreaManager || isAdmin

  const loadAll = React.useCallback(async () => {
    setLoading(true)
    const nextKpis = {
      pendingApprovals: null,
      branchRequestsTotal: null,
      productionPending: null,
      productionInProgress: null,
      warehousePending: null,
      warehouseAvailable: null,
      deliveryReady: null,
      opsAlerts: null,
      kitchenSites: null,
      requestsToday: null,
      inProduction: null,
      warehouseDelays: null,
      partialOrders: null,
      backorders: null,
      readyForDelivery: null,
      outForDelivery: null,
      deliveredToday: null,
      productionReady: null,
      sentToWarehouse: null,
      myRequests: null,
      shortages: null,
      partialWarehouse: null,
      notificationUnread: null,
    }
    const nextQueues = {
      submittedRequests: [],
      branchRequests: [],
      productionPending: [],
      productionInProgress: [],
      warehousePending: [],
      warehouseAvailable: [],
      deliveryReady: [],
    }
    let alerts = null
    let adminOverview = null
    try {
      const tasks = []

      tasks.push(
        supplyChainApi.dashboard().then((r) => {
          const d = r.data || {}
          nextKpis.pendingApprovals = d.pending_approvals ?? 0
          nextKpis.inProduction = d.in_production ?? 0
          nextKpis.warehouseDelays = d.warehouse_delays ?? 0
          nextKpis.partialOrders = d.partial_orders ?? 0
          nextKpis.requestsToday = d.requests_today ?? 0
          nextKpis.warehousePending = d.warehouse_pending ?? 0
          nextKpis.backorders = d.backorders ?? 0
          nextKpis.readyForDelivery = d.ready_for_delivery ?? 0
          nextKpis.outForDelivery = d.out_for_delivery ?? 0
          nextKpis.deliveredToday = d.delivered_today ?? 0
          nextKpis.productionReady = d.production_ready ?? 0
          nextKpis.sentToWarehouse = d.sent_to_warehouse ?? 0
          nextKpis.myRequests = d.my_requests ?? 0
          nextKpis.shortages = d.shortages ?? 0
          nextKpis.partialWarehouse = d.partial_warehouse ?? 0
          nextKpis.deliveryReady = d.ready_for_delivery ?? 0
          nextKpis.branchRequestsTotal = d.my_requests ?? d.requests_today ?? 0
        }).catch(() => {}),
      )

      tasks.push(
        notificationsApi.summary().then((r) => {
          nextKpis.notificationUnread = r.data?.total ?? r.data?.unread_count ?? r.data?.unread ?? 0
        }).catch(() => {}),
      )

      if (isSuperAdmin) {
        tasks.push(
          dashboardApi.superAdminOverview().then((r) => {
            adminOverview = r.data || null
          }).catch(() => {}),
        )
      }
      if (isBranchOnly) {
        tasks.push(
          supplyChainApi.listBranchRequests({ page: 1, page_size: 5 }).then((r) => {
            nextQueues.branchRequests = (r.data?.items || []).map((x) => ({
              id: x.id,
              label: `${x.request_no || `BR-${x.id}`} · ${x.status}`,
              status: x.status,
            }))
          }).catch(() => {}),
        )
      }
      if (isArea) {
        tasks.push(
          supplyChainApi.listBranchRequests({ status: 'SUBMITTED', page: 1, page_size: 5 }).then((r) => {
            nextQueues.submittedRequests = (r.data?.items || []).map((x) => ({
              id: x.id,
              label: `${x.request_no || `BR-${x.id}`}`,
              status: x.status,
            }))
          }).catch(() => {}),
        )
      }
      if (isKitchen) {
        tasks.push(
          supplyChainApi.listProductionOrders({ status: 'PENDING' }).then((r) => {
            const arr = Array.isArray(r.data) ? r.data : []
            nextKpis.productionPending = arr.length
            nextQueues.productionPending = arr.slice(0, 5).map((o) => ({
              id: o.id,
              label: `PO-${o.id} · ${itemLabel(o.item)}`,
              status: o.status,
            }))
          }).catch(() => {}),
        )
        tasks.push(
          supplyChainApi.listProductionOrders({ status: 'IN_PROGRESS' }).then((r) => {
            const arr = Array.isArray(r.data) ? r.data : []
            nextKpis.productionInProgress = arr.length
            nextQueues.productionInProgress = arr.slice(0, 5).map((o) => ({
              id: o.id,
              label: `PO-${o.id} · ${itemLabel(o.item)}`,
              status: o.status,
            }))
          }).catch(() => {}),
        )
      }
      if (isWh) {
        tasks.push(
          supplyChainApi.listWarehouseLines({ status: 'AVAILABLE' }).then((r) => {
            const arr = Array.isArray(r.data) ? r.data : []
            nextKpis.warehouseAvailable = arr.length
            nextQueues.warehouseAvailable = arr.slice(0, 5).map((line) => ({
              id: line.id,
              label: `WL-${line.id} · ${itemLabel(line.item)}`,
              status: line.status,
            }))
          }).catch(() => {}),
        )
        tasks.push(
          supplyChainApi.listWarehouseLines({ status: 'PENDING' }).then((r) => {
            const arr = Array.isArray(r.data) ? r.data : []
            nextQueues.warehousePending = arr.slice(0, 5).map((line) => ({
              id: line.id,
              label: `WL-${line.id} · ${itemLabel(line.item)} · ${line.source_type}`,
              status: line.status,
            }))
          }).catch(() => {}),
        )
      }
      if (isDel) {
        tasks.push(
          supplyChainApi.listReadyDeliveryOrders().then((r) => {
            const arr = Array.isArray(r.data) ? r.data : []
            nextQueues.deliveryReady = arr.slice(0, 5).map((o) => ({
              id: o.id,
              label: `DO-${o.id} · فرع ${o.branch_id}`,
              status: o.status,
            }))
          }).catch(() => {}),
        )
      }
      if (isOps) {
        tasks.push(
          dashboardApi.alertsSummary().then((r) => {
            const d = r.data || {}
            nextKpis.opsAlerts = d.total_alerts ?? null
            alerts = d
          }).catch(() => {}),
        )
      }
      if (isAdmin || isKitchen || isWh || isArea) {
        tasks.push(
          masterApi.listKitchens({ active_only: true }).then((r) => {
            nextKpis.kitchenSites = Array.isArray(r.data) ? r.data.length : 0
          }).catch(() => {}),
        )
      }
      await Promise.all(tasks)
      setKpis(nextKpis)
      setQueues(nextQueues)
      setAlertsDetail(alerts)
      setSuperAdminOverview(adminOverview)
      setLastUpdated(new Date().toLocaleString())
    } finally {
      setLoading(false)
    }
  }, [isArea, isBranchOnly, isKitchen, isWh, isDel, isOps, isAdmin, isSuperAdmin])

  React.useEffect(() => {
    loadAll()
  }, [loadAll, refreshTick])

  React.useEffect(() => {
    if (!autoRefresh) return undefined
    const id = window.setInterval(() => setRefreshTick((x) => x + 1), 60000)
    return () => window.clearInterval(id)
  }, [autoRefresh])

  const open = t('supply_chain_control_page.open_action')

  const headerActions = (
    <div className="flex flex-wrap items-center gap-3">
      <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
        <input type="checkbox" checked={autoRefresh} onChange={(e) => setAutoRefresh(e.target.checked)} />
        {t('supply_chain_control_page.auto_refresh')}
      </label>
      <button type="button" className="btn-secondary text-sm" onClick={() => setRefreshTick((x) => x + 1)}>
        {t('supply_chain_control_page.refresh_now')}
      </button>
      {lastUpdated && (
        <span className="text-xs text-gray-600">{t('supply_chain_control_page.last_updated', { time: lastUpdated })}</span>
      )}
    </div>
  )

  return (
    <PageShell
      title={t('supply_chain_control_page.title')}
      subtitle={t('supply_chain_control_page.subtitle')}
      actions={headerActions}
    >
      {loading ? (
        <div className="text-center text-gray-500 py-12">…</div>
      ) : (
        <div className="space-y-8">
          {isSuperAdmin && superAdminOverview && (
            <div className="space-y-6">
              <div>
                <h2 className="text-lg font-bold text-gray-900">Super admin overview</h2>
                <p className="text-sm text-gray-600 mt-1">Executive summary, critical alerts, and end-to-end supply chain visibility.</p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-4">
                <SummaryHeroCard title="Total requests today" value={superAdminOverview.summary?.total_requests_today} subtitle="طلبات الفروع المنشأة اليوم" to="/supply-chain/branch-requests" linkLabel={open} tone="primary" />
                <SummaryHeroCard title="Pending approvals" value={superAdminOverview.summary?.pending_approvals} subtitle="طلبات تنتظر مدير المنطقة" to="/supply-chain/approvals" linkLabel={open} tone="amber" />
                <SummaryHeroCard title="In production" value={superAdminOverview.summary?.in_production} subtitle="أوامر إنتاج نشطة" to="/supply-chain/kitchen" linkLabel={open} tone="emerald" />
                <SummaryHeroCard title="Warehouse pending" value={superAdminOverview.summary?.warehouse_pending} subtitle="سطر مستودع مفتوح" to="/supply-chain/warehouse" linkLabel={open} tone="slate" />
                <SummaryHeroCard title="Out for delivery" value={superAdminOverview.summary?.out_for_delivery} subtitle="طلبات خرجت للتسليم" to="/supply-chain/delivery" linkLabel={open} tone="primary" />
                <SummaryHeroCard title="Delivered today" value={superAdminOverview.summary?.delivered} subtitle="طلبات أغلقت اليوم" to="/supply-chain/delivery" linkLabel={open} tone="emerald" />
                <SummaryHeroCard title="Delayed total" value={superAdminOverview.summary?.delayed} subtitle="عناصر متأخرة عبر السلسلة" to="/supply-chain/approvals" linkLabel={open} tone="red" />
                <SummaryHeroCard title="Partial total" value={superAdminOverview.summary?.partial} subtitle="حالات جزئية تحتاج متابعة" to="/supply-chain/warehouse" linkLabel={open} tone="amber" />
                <SummaryHeroCard title="Active branches" value={superAdminOverview.summary?.active_branches} subtitle="فروع تشغيلية فعّالة" to="/admin/branches" linkLabel={open} tone="slate" />
                <SummaryHeroCard title="Active users" value={superAdminOverview.summary?.active_users} subtitle="مستخدمون فعّالون بالنظام" to="/admin/users" linkLabel={open} tone="slate" />
              </div>

              <div className="grid xl:grid-cols-[1.1fr,1.4fr] gap-4">
                <SuperAdminAlertList alerts={superAdminOverview.alerts} openLabel={open} />
                <div className="card p-4">
                  <div className="flex items-center justify-between gap-3 mb-4">
                    <h3 className="text-base font-semibold text-gray-900">End-to-end pipeline</h3>
                    <span className="text-xs text-gray-500">Live operational counts</span>
                  </div>
                  <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
                    {(superAdminOverview.pipeline || []).map((stage) => (
                      <PipelineBlock
                        key={stage.key}
                        label={stage.label}
                        count={stage.count}
                        delayedCount={stage.delayed_count}
                        partialCount={stage.partial_count}
                        to={stage.to}
                        openLabel={open}
                      />
                    ))}
                  </div>
                </div>
              </div>

              <div className="space-y-4">
                <div>
                  <h3 className="text-base font-semibold text-gray-900">Operations visibility</h3>
                  <p className="text-sm text-gray-600 mt-1">Top operational pressure points across branches, approvals, kitchen, warehouse, and delivery.</p>
                </div>
                <div className="grid xl:grid-cols-2 gap-4">
                  <OpsMiniTable
                    title="Branch performance"
                    rows={superAdminOverview.operations?.branches?.top_requesting || []}
                    columns={[{ key: 'request_count', label: 'Requests' }]}
                    emptyText="No branch activity yet."
                    to="/supply-chain/branch-requests"
                    openLabel={open}
                  />
                  <OpsMiniTable
                    title="Delayed branches"
                    rows={superAdminOverview.operations?.branches?.delayed_branches || []}
                    columns={[{ key: 'delayed_count', label: 'Delayed' }]}
                    emptyText="No branch approval delays right now."
                    to="/supply-chain/approvals"
                    openLabel={open}
                  />
                  <OpsMiniTable
                    title="Area manager backlog"
                    rows={superAdminOverview.operations?.area_managers || []}
                    columns={[{ key: 'pending_count', label: 'Pending' }]}
                    emptyText="No area manager backlog right now."
                    to="/supply-chain/approvals"
                    openLabel={open}
                  />
                  <OpsMiniTable
                    title="Kitchen pressure"
                    rows={superAdminOverview.operations?.kitchen || []}
                    columns={[
                      { key: 'active_count', label: 'Active' },
                      { key: 'delayed_count', label: 'Delayed' },
                    ]}
                    emptyText="No kitchen orders right now."
                    to="/supply-chain/kitchen"
                    openLabel={open}
                  />
                  <OpsMiniTable
                    title="Warehouse pressure"
                    rows={superAdminOverview.operations?.warehouse || []}
                    columns={[
                      { key: 'active_count', label: 'Open lines' },
                      { key: 'backorder_count', label: 'Backorders' },
                    ]}
                    emptyText="No warehouse pressure right now."
                    to="/supply-chain/warehouse"
                    openLabel={open}
                  />
                  <OpsMiniTable
                    title="Delivery by city"
                    rows={superAdminOverview.operations?.delivery?.by_city || []}
                    columns={[
                      { key: 'active_count', label: 'Active' },
                      { key: 'out_count', label: 'Out' },
                    ]}
                    emptyText="No delivery activity right now."
                    to="/supply-chain/delivery"
                    openLabel={open}
                  />
                </div>
                <OpsMiniTable
                  title="Top delivery branches"
                  rows={superAdminOverview.operations?.delivery?.top_branches || []}
                  columns={[{ key: 'delivery_count', label: 'Deliveries' }]}
                  emptyText="No delivery branch history yet."
                  to="/supply-chain/delivery"
                  openLabel={open}
                />
              </div>

              <div className="space-y-4">
                <div>
                  <h3 className="text-base font-semibold text-gray-900">Analytics & governance</h3>
                  <p className="text-sm text-gray-600 mt-1">Performance indicators, data health checks, permission oversight, and recent sensitive actions.</p>
                </div>
                <div className="grid xl:grid-cols-2 gap-4">
                  <MetricListCard
                    title="Performance analytics"
                    rows={[
                      { label: 'Average approval hours', value: superAdminOverview.analytics?.performance?.avg_approval_hours ?? 0 },
                      { label: 'Average delivery hours', value: superAdminOverview.analytics?.performance?.avg_delivery_hours ?? 0 },
                      { label: 'Partial rate %', value: superAdminOverview.analytics?.performance?.partial_rate_pct ?? 0 },
                      { label: 'Delay rate %', value: superAdminOverview.analytics?.performance?.delay_rate_pct ?? 0 },
                    ]}
                    to="/operations"
                    openLabel={open}
                    emptyText="No performance metrics available yet."
                  />
                  <OpsMiniTable
                    title="Top requested items"
                    rows={superAdminOverview.analytics?.top_items || []}
                    columns={[
                      { key: 'request_count', label: 'Requests' },
                      { key: 'qty_requested', label: 'Qty' },
                    ]}
                    emptyText="No item demand data yet."
                    to="/admin/items"
                    openLabel={open}
                  />
                  <MetricListCard
                    title="Data health"
                    rows={[
                      { label: 'Users without scope', value: superAdminOverview.data_health?.users_without_scope ?? 0 },
                      { label: 'Users without roles', value: superAdminOverview.data_health?.users_without_roles ?? 0 },
                      { label: 'Inactive-branch users', value: superAdminOverview.data_health?.inactive_branch_users ?? 0 },
                      { label: 'Branches without brand links', value: superAdminOverview.data_health?.branches_without_brand_links ?? 0 },
                      { label: 'Items without brand links', value: superAdminOverview.data_health?.items_without_brand_links ?? 0 },
                      { label: 'Kitchen assignments without city', value: superAdminOverview.data_health?.kitchen_assignments_without_city ?? 0 },
                      { label: 'Branch UI visibility conflicts', value: superAdminOverview.data_health?.branch_requestable_hidden_conflicts ?? 0 },
                    ]}
                    to="/admin/users"
                    openLabel={open}
                    emptyText="No data health metrics available."
                  />
                  <MetricListCard
                    title="Role distribution"
                    rows={(superAdminOverview.governance?.role_distribution || []).map((row) => ({
                      label: row.role_display_name || row.role_name || `Role #${row.role_id}`,
                      value: row.user_count,
                    }))}
                    to="/admin/users"
                    openLabel={open}
                    emptyText="No role distribution data yet."
                  />
                </div>
                <AuditListCard rows={superAdminOverview.governance?.recent_audit || []} to="/audit/logs" openLabel={open} />
              </div>
            </div>
          )}

          {!isSuperAdmin && (
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
            {showAdminKpis && (
              <>
                <KpiCard title="Requests today" value={kpis.requestsToday} to="/supply-chain/branch-requests" linkLabel={open} />
                <KpiCard title="Pending approvals" value={kpis.pendingApprovals} to="/supply-chain/approvals" linkLabel={open} />
                <KpiCard title="In production" value={kpis.inProduction} to="/supply-chain/kitchen" linkLabel={open} />
                <KpiCard title="Warehouse pending" value={kpis.warehousePending} to="/supply-chain/warehouse" linkLabel={open} />
                <KpiCard title="Partial orders" value={kpis.partialOrders} to="/supply-chain/warehouse" linkLabel={open} />
                <KpiCard title="Backorders" value={kpis.backorders} to="/supply-chain/warehouse" linkLabel={open} />
                <KpiCard title="Ready for delivery" value={kpis.readyForDelivery} to="/supply-chain/delivery" linkLabel={open} />
                <KpiCard title="Delivered today" value={kpis.deliveredToday} to="/supply-chain/delivery" linkLabel={open} />
              </>
            )}
            {isBranchOnly && (
              <>
                <KpiCard title="My requests today" value={kpis.requestsToday} to="/supply-chain/branch-requests" linkLabel={open} />
                <KpiCard title="Pending approval" value={kpis.pendingApprovals} to="/supply-chain/branch-requests" linkLabel={open} />
                <KpiCard title="In production" value={kpis.inProduction} to="/supply-chain/branch-requests" linkLabel={open} />
                <KpiCard title="Warehouse processing" value={kpis.warehousePending} to="/supply-chain/branch-requests" linkLabel={open} />
                <KpiCard title="Out for delivery" value={kpis.outForDelivery} to="/supply-chain/branch-requests" linkLabel={open} />
                <KpiCard title="Delivered today" value={kpis.deliveredToday} to="/supply-chain/branch-requests" linkLabel={open} />
                <KpiCard title="Partial orders" value={kpis.partialOrders} to="/supply-chain/branch-requests" linkLabel={open} />
              </>
            )}
            {isAreaManager && !isAdmin && (
              <>
                <KpiCard title={t('supply_chain_control_page.pending_approvals')} value={kpis.pendingApprovals} to="/supply-chain/approvals" linkLabel={open} />
                <KpiCard title="Delayed requests" value={kpis.warehouseDelays} to="/supply-chain/approvals" linkLabel={open} />
                <KpiCard title="Partial orders" value={kpis.partialOrders} to="/supply-chain/warehouse" linkLabel={open} />
                <KpiCard title="Backorders" value={kpis.backorders} to="/supply-chain/warehouse" linkLabel={open} />
                <KpiCard title="Delivered today" value={kpis.deliveredToday} to="/supply-chain/delivery" linkLabel={open} />
              </>
            )}
            {isKitchen && !isAdmin && (
              <>
                <KpiCard title={t('supply_chain_control_page.production_pending')} value={kpis.productionPending} to="/supply-chain/kitchen" linkLabel={open} />
                <KpiCard title={t('supply_chain_control_page.production_in_progress')} value={kpis.productionInProgress} to="/supply-chain/kitchen" linkLabel={open} />
                <KpiCard title="Ready" value={kpis.productionReady} to="/supply-chain/kitchen" linkLabel={open} />
                <KpiCard title="Sent to warehouse" value={kpis.sentToWarehouse} to="/supply-chain/kitchen" linkLabel={open} />
                <KpiCard title="Waiting / delayed" value={kpis.warehouseDelays} to="/supply-chain/kitchen" linkLabel={open} />
              </>
            )}
            {isWh && !isAdmin && (
              <>
                <KpiCard title={t('supply_chain_control_page.warehouse_pending')} value={kpis.warehousePending} to="/supply-chain/warehouse" linkLabel={open} />
                <KpiCard title="Ready from kitchen" value={kpis.sentToWarehouse} to="/supply-chain/warehouse" linkLabel={open} />
                <KpiCard title="Partial orders" value={kpis.partialWarehouse} to="/supply-chain/warehouse" linkLabel={open} />
                <KpiCard title="Backorders" value={kpis.backorders} to="/supply-chain/warehouse" linkLabel={open} />
                <KpiCard title="Delay reasons" value={kpis.warehouseDelays} to="/supply-chain/warehouse" linkLabel={open} />
                <KpiCard title={t('supply_chain_control_page.warehouse_available')} value={kpis.warehouseAvailable} to="/supply-chain/warehouse" linkLabel={open} />
              </>
            )}
            {isDel && !isAdmin && (
              <>
                <KpiCard title="Ready for delivery" value={kpis.readyForDelivery} to="/supply-chain/delivery" linkLabel={open} />
                <KpiCard title="Out for delivery" value={kpis.outForDelivery} to="/supply-chain/delivery" linkLabel={open} />
                <KpiCard title="Delivered today" value={kpis.deliveredToday} to="/supply-chain/delivery" linkLabel={open} />
                <KpiCard title="Shortages" value={kpis.shortages} to="/supply-chain/delivery" linkLabel={open} />
              </>
            )}
            {isOpsManager && !isAdmin && (
              <KpiCard title={t('supply_chain_control_page.ops_alerts_total')} value={kpis.opsAlerts} to="/operations" linkLabel={open} />
            )}
            {(isAdmin || (isKitchen && !isAdmin) || (isWh && !isAdmin) || (isAreaManager && !isAdmin)) && (
              <KpiCard
                title={t('supply_chain_control_page.kitchen_sites')}
                value={kpis.kitchenSites}
                to={isAdmin ? '/admin/kitchens' : '/supply-chain/kitchen'}
                linkLabel={open}
              />
            )}
            <KpiCard title="Notifications" value={kpis.notificationUnread} to="/notifications" linkLabel={open} />
          </div>
          )}

          {!isSuperAdmin && (
          <div>
            <h2 className="text-sm font-semibold text-gray-700 mb-3">{t('supply_chain_control_page.queue_preview')}</h2>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {isAreaManager && !isAdmin && (
                <QueuePreviewBlock title={t('supply_chain_control_page.pending_approvals')} rows={queues.submittedRequests} to="/supply-chain/approvals" emptyHint={open} emptyText="No pending approvals." />
              )}
              {isBranchOnly && (
                <QueuePreviewBlock title={t('supply_chain_control_page.branch_requests_total')} rows={queues.branchRequests} to="/supply-chain/branch-requests" emptyHint={open} emptyText="No branch requests yet." />
              )}
              {isKitchen && !isAdmin && (
                <>
                  <QueuePreviewBlock title={t('supply_chain_control_page.production_pending')} rows={queues.productionPending} to="/supply-chain/kitchen" emptyHint={open} emptyText="No production orders pending." />
                  <QueuePreviewBlock title={t('supply_chain_control_page.production_in_progress')} rows={queues.productionInProgress} to="/supply-chain/kitchen" emptyHint={open} emptyText="No production orders in progress." />
                </>
              )}
              {isWh && !isAdmin && (
                <>
                  <QueuePreviewBlock title={t('supply_chain_control_page.warehouse_pending')} rows={queues.warehousePending} to="/supply-chain/warehouse" emptyHint={open} emptyText="No warehouse lines pending." />
                  <QueuePreviewBlock title={t('supply_chain_control_page.warehouse_available')} rows={queues.warehouseAvailable} to="/supply-chain/warehouse" emptyHint={open} emptyText="No warehouse lines ready to issue." />
                </>
              )}
              {isDel && !isAdmin && (
                <QueuePreviewBlock title={t('supply_chain_control_page.delivery_ready')} rows={queues.deliveryReady} to="/supply-chain/delivery" emptyHint={open} emptyText="No deliveries assigned." />
              )}
            </div>
          </div>
          )}

          {isOps && alertsDetail && (
            <div className="card p-4">
              <h3 className="text-sm font-semibold text-gray-800 mb-3">{t('supply_chain_control_page.alerts_breakdown')}</h3>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm text-gray-700">
                <div><span className="text-gray-500">{t('supply_chain_control_page.alerts_low_stock')}</span> — <strong>{alertsDetail.low_stock ?? 0}</strong></div>
                <div><span className="text-gray-500">{t('supply_chain_control_page.alerts_out_of_stock')}</span> — <strong>{alertsDetail.out_of_stock ?? 0}</strong></div>
                <div><span className="text-gray-500">{t('supply_chain_control_page.alerts_pending_inv')}</span> — <strong>{alertsDetail.pending_inventory_approvals ?? 0}</strong></div>
                <div><span className="text-gray-500">{t('supply_chain_control_page.alerts_missing_today')}</span> — <strong>{alertsDetail.missing_today ?? 0}</strong></div>
                <div><span className="text-gray-500">{t('supply_chain_control_page.alerts_overdue_orders')}</span> — <strong>{alertsDetail.overdue_orders ?? 0}</strong></div>
              </div>
              <Link to="/operations" className="text-xs text-primary-600 hover:underline mt-3 inline-block">{t('supply_chain_control_page.legacy_operations')}</Link>
            </div>
          )}

        </div>
      )}
    </PageShell>
  )
}
