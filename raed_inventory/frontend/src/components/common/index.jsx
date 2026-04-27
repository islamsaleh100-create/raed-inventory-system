import React from 'react'
import { X, AlertTriangle, Loader2 } from 'lucide-react'
import { getStatusLabel } from '../../utils/helpers'

// ─── Status Badge ──────────────────────────────────────────────────────
export function StatusBadge({ status, className = '' }) {
  return (
    <span className={`status-badge status-${status} ${className}`}>
      {getStatusLabel(status)}
    </span>
  )
}

// ─── Stock Status Badge ────────────────────────────────────────────────
export function StockStatusBadge({ status }) {
  const labels = {
    ok: 'مناسب', reorder: 'نقطة الطلب',
    below_min: 'تحت الحد الأدنى', out_of_stock: 'نفد',
  }
  const cls = {
    ok: 'bg-green-100 text-green-700',
    reorder: 'bg-yellow-100 text-yellow-700',
    below_min: 'bg-orange-100 text-orange-700',
    out_of_stock: 'bg-red-100 text-red-700',
  }
  return (
    <span className={`status-badge ${cls[status] || 'bg-gray-100 text-gray-600'}`}>
      {labels[status] || status}
    </span>
  )
}

// ─── Spinner ───────────────────────────────────────────────────────────
export function Spinner({ size = 'md', className = '' }) {
  const sizes = { sm: 'w-4 h-4', md: 'w-8 h-8', lg: 'w-12 h-12' }
  return (
    <Loader2 className={`animate-spin text-primary-600 ${sizes[size]} ${className}`} />
  )
}

export function PageLoader() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="text-center">
        <Spinner size="lg" className="mx-auto mb-3" />
        <p className="text-gray-500 text-sm">جاري التحميل...</p>
      </div>
    </div>
  )
}

// ─── Modal ─────────────────────────────────────────────────────────────
export function Modal({ open, onClose, title, children, size = 'md' }) {
  if (!open) return null
  const sizes = {
    sm: 'max-w-md', md: 'max-w-lg', lg: 'max-w-2xl', xl: 'max-w-4xl', full: 'max-w-6xl'
  }
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className={`relative bg-white rounded-xl shadow-xl w-full ${sizes[size]} max-h-[90vh] overflow-y-auto`}>
        <div className="flex items-center justify-between p-5 border-b border-gray-100">
          <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded-lg transition-colors">
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  )
}

// ─── Confirm Dialog ────────────────────────────────────────────────────
export function ConfirmDialog({ open, onClose, onConfirm, title, message, confirmText = 'تأكيد', danger = false }) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-white rounded-xl shadow-xl w-full max-w-sm p-6">
        <div className="flex gap-3 mb-4">
          <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0
            ${danger ? 'bg-red-100' : 'bg-yellow-100'}`}>
            <AlertTriangle className={`w-5 h-5 ${danger ? 'text-red-600' : 'text-yellow-600'}`} />
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">{title}</h3>
            <p className="text-sm text-gray-500 mt-1">{message}</p>
          </div>
        </div>
        <div className="flex gap-3 justify-end">
          <button onClick={onClose} className="btn-secondary text-sm px-3 py-1.5">إلغاء</button>
          <button
            onClick={() => { onConfirm(); onClose() }}
            className={`text-sm px-3 py-1.5 rounded-lg font-medium text-white transition-colors
              ${danger ? 'bg-red-600 hover:bg-red-700' : 'bg-primary-600 hover:bg-primary-700'}`}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Pagination ────────────────────────────────────────────────────────
export function Pagination({ total, page, pageSize, onChange }) {
  const totalPages = Math.ceil(total / pageSize)
  if (totalPages <= 1) return null

  return (
    <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100">
      <p className="text-sm text-gray-500">
        إجمالي: <span className="font-medium">{total}</span> سجل
      </p>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onChange(page - 1)}
          disabled={page === 1}
          className="px-3 py-1 text-sm border border-gray-200 rounded-lg disabled:opacity-40
            hover:bg-gray-50 transition-colors"
        >
          السابق
        </button>
        {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
          const p = i + 1
          return (
            <button
              key={p}
              onClick={() => onChange(p)}
              className={`px-3 py-1 text-sm rounded-lg transition-colors
                ${p === page ? 'bg-primary-600 text-white' : 'border border-gray-200 hover:bg-gray-50'}`}
            >
              {p}
            </button>
          )
        })}
        <button
          onClick={() => onChange(page + 1)}
          disabled={page === totalPages}
          className="px-3 py-1 text-sm border border-gray-200 rounded-lg disabled:opacity-40
            hover:bg-gray-50 transition-colors"
        >
          التالي
        </button>
      </div>
    </div>
  )
}

// ─── Empty State ───────────────────────────────────────────────────────
export function EmptyState({ icon: Icon, title, subtitle, action }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      {Icon && (
        <div className="w-16 h-16 bg-gray-100 rounded-2xl flex items-center justify-center mb-4">
          <Icon className="w-8 h-8 text-gray-400" />
        </div>
      )}
      <h3 className="text-base font-semibold text-gray-700 mb-1">{title}</h3>
      {subtitle && <p className="text-sm text-gray-400 mb-4">{subtitle}</p>}
      {action}
    </div>
  )
}

// ─── Alert Banner ──────────────────────────────────────────────────────
export function Alert({ type = 'info', message, className = '' }) {
  const styles = {
    info: 'bg-blue-50 border-blue-200 text-blue-800',
    success: 'bg-green-50 border-green-200 text-green-800',
    warning: 'bg-yellow-50 border-yellow-200 text-yellow-800',
    error: 'bg-red-50 border-red-200 text-red-800',
  }
  return (
    <div className={`border rounded-lg px-4 py-3 text-sm ${styles[type]} ${className}`}>
      {message}
    </div>
  )
}

export function ReadOnlyBanner({
  title = 'قراءة فقط',
  description = 'هذا المسار متاح للمراجعة فقط، ولا يسمح بإجراء تعديلات تشغيلية من هذا الحساب.',
  className = '',
}) {
  return (
    <div className={`mb-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 ${className}`}>
      <p className="text-sm font-semibold text-amber-800">{title}</p>
      {description ? <p className="mt-1 text-sm text-amber-700">{description}</p> : null}
    </div>
  )
}

// ─── KPI Card ──────────────────────────────────────────────────────────
export function KpiCard({ title, value, subtitle, icon: Icon, iconBg, iconColor, trend, onClick }) {
  return (
    <div
      className={`kpi-card ${onClick ? 'cursor-pointer hover:shadow-md transition-shadow' : ''}`}
      onClick={onClick}
    >
      <div className={`kpi-icon ${iconBg}`}>
        <Icon className={`w-6 h-6 ${iconColor}`} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs text-gray-500 mb-0.5">{title}</p>
        <p className="text-2xl font-bold text-gray-900">{value}</p>
        {subtitle && <p className="text-xs text-gray-400 mt-0.5 truncate">{subtitle}</p>}
      </div>
      {trend !== undefined && (
        <div className={`text-xs font-medium px-2 py-1 rounded-full
          ${trend >= 0 ? 'bg-green-50 text-green-600' : 'bg-red-50 text-red-600'}`}>
          {trend >= 0 ? '+' : ''}{trend}%
        </div>
      )}
    </div>
  )
}

// ─── Form Input Wrapper ────────────────────────────────────────────────
export function FormField({ label, error, children, required }) {
  return (
    <div>
      {label && (
        <label className="label">
          {label}
          {required && <span className="text-red-500 mr-1">*</span>}
        </label>
      )}
      {children}
      {error && <p className="text-xs text-red-600 mt-1">{error}</p>}
    </div>
  )
}

// ─── Error Boundary ────────────────────────────────────────────────────
export { default as ErrorBoundary } from './ErrorBoundary'

// ─── Search Input ──────────────────────────────────────────────────────
export function SearchInput({ value, onChange, placeholder = 'بحث...', className = '' }) {
  return (
    <div className={`relative ${className}`}>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="input-field pr-9"
      />
      <span className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400">🔍</span>
    </div>
  )
}
