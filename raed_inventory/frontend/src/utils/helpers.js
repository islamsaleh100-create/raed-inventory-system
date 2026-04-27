import { format, parseISO } from 'date-fns'
import { ar } from 'date-fns/locale'

// ─── Date helpers ──────────────────────────────────────────────────────
export const formatDate = (d) => {
  if (!d) return '-'
  const date = typeof d === 'string' ? parseISO(d) : d
  return format(date, 'dd/MM/yyyy')
}

export const formatDateTime = (d) => {
  if (!d) return '-'
  const date = typeof d === 'string' ? parseISO(d) : d
  return format(date, 'dd/MM/yyyy HH:mm')
}

export const todayString = () => format(new Date(), 'yyyy-MM-dd')

// ─── Number helpers ────────────────────────────────────────────────────
export const formatQty = (n) => {
  if (n === null || n === undefined) return '-'
  const num = parseFloat(n)
  return Number.isInteger(num) ? num.toString() : num.toFixed(2)
}

export const formatPct = (n) => {
  if (n === null || n === undefined) return '-'
  return `${parseFloat(n).toFixed(1)}%`
}

// ─── Status labels (Arabic) ────────────────────────────────────────────
export const STATUS_LABELS = {
  // Inventory
  draft: 'مسودة',
  submitted: 'مرسل للاعتماد',
  approved: 'معتمد',
  rejected: 'مرفوض',

  // Orders
  system_generated: 'نظام تلقائي',
  branch_reviewed: 'مراجعة الفرع',
  submitted_to_warehouse: 'مرسل للمستودع',
  under_review: 'قيد المراجعة',
  partially_approved: 'اعتماد جزئي',
  picking: 'قيد التجهيز',
  dispatched: 'تم الصرف',
  received: 'تم الاستلام',
  closed: 'مغلق',

  // Stock
  ok: 'مناسب',
  reorder: 'نقطة الطلب',
  below_min: 'تحت الحد الأدنى',
  out_of_stock: 'نفد من المخزون',

  // Variance
  warning: 'تحذير',
  critical: 'حرج',

  // User
  active: 'نشط',
  inactive: 'غير نشط',
  suspended: 'موقوف',
}

export const getStatusLabel = (status) => STATUS_LABELS[status] || status

// ─── Order type labels ─────────────────────────────────────────────────
export const ORDER_TYPE_LABELS = {
  auto_replenishment: 'تلقائي',
  exceptional: 'استثنائي',
}

// ─── Role labels ───────────────────────────────────────────────────────
export const ROLE_LABELS = {
  super_admin: 'مدير النظام',
  admin: 'مشرف',
  branch_manager: 'مدير فرع',
  branch_user: 'موظف فرع',
  warehouse_manager: 'مدير مستودع',
  warehouse_user: 'موظف مستودع',
  operations_manager: 'مدير عمليات',
}

// ─── Status CSS classes ────────────────────────────────────────────────
export const getStatusClass = (status) => `status-badge status-${status}`

export const getStockStatusClass = (status) => `stock-${status}`

// ─── Variance status helpers ───────────────────────────────────────────
export const getVarianceBadge = (variance_status) => {
  const map = {
    ok: 'bg-green-100 text-green-700',
    warning: 'bg-yellow-100 text-yellow-700',
    critical: 'bg-red-100 text-red-700',
  }
  return map[variance_status] || 'bg-gray-100 text-gray-700'
}

// ─── Error message extract ─────────────────────────────────────────────
export const getErrorMessage = (error) => {
  return error?.response?.data?.detail ||
    error?.message ||
    'حدث خطأ غير متوقع'
}

// ─── Stock status derive ───────────────────────────────────────────────
export const deriveStockStatus = (current_qty, min_qty, reorder_point) => {
  const q = parseFloat(current_qty)
  const min = parseFloat(min_qty)
  const rp = parseFloat(reorder_point)
  if (q <= 0) return 'out_of_stock'
  if (q < min) return 'below_min'
  if (q <= rp) return 'reorder'
  return 'ok'
}

// ─── Display helpers ───────────────────────────────────────────────────
/**
 * عرض اسم الصنف بطريقة آمنة (Arabic first, then English, then code, then id).
 * يمنع طباعة كائن React children عن طريق الخطأ.
 */
export const displayItemName = (item) => {
  if (!item || typeof item !== 'object') return String(item ?? '')
  return (
    item.item_name_ar ||
    item.item_name_en ||
    item.name_ar ||
    item.name_en ||
    item.name ||
    item.item_code ||
    (item.id != null ? `#${item.id}` : '')
  )
}

export const displayBranchName = (branch) => {
  if (!branch || typeof branch !== 'object') return String(branch ?? '')
  return (
    branch.branch_name_ar ||
    branch.branch_name ||
    branch.name ||
    branch.branch_code ||
    (branch.id != null ? `#${branch.id}` : '')
  )
}

export const displayWarehouseName = (warehouse) => {
  if (!warehouse || typeof warehouse !== 'object') return String(warehouse ?? '')
  return (
    warehouse.warehouse_name ||
    warehouse.name ||
    warehouse.warehouse_code ||
    (warehouse.id != null ? `#${warehouse.id}` : '')
  )
}

/**
 * آمن لعرض أي قيمة داخل JSX (أرقام/نصوص كـ String، كائنات كـ JSON).
 * يستخدم كـ خط دفاع أخير لتجنب `Objects are not valid as a React child`.
 */
export const safeText = (v) => {
  if (v === null || v === undefined) return ''
  if (typeof v === 'object') {
    try {
      return JSON.stringify(v)
    } catch {
      return '[object]'
    }
  }
  return String(v)
}
