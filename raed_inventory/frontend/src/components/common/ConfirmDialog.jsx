import React from 'react'

/**
 * Simple confirmation modal for dangerous supply-chain actions.
 */
export default function ConfirmDialog({
  open,
  title,
  children,
  confirmLabel = 'تأكيد',
  cancelLabel = 'إلغاء',
  confirmClassName = 'btn-primary',
  onConfirm,
  onCancel,
  confirmDisabled = false,
}) {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" role="dialog" aria-modal="true">
      <div className="bg-white rounded-2xl shadow-xl max-w-lg w-full p-6 space-y-4">
        <h2 className="text-lg font-bold text-gray-900">{title}</h2>
        <div className="text-sm text-gray-700 space-y-2">{children}</div>
        <div className="flex gap-3 justify-end flex-wrap pt-2">
          <button type="button" className="btn-secondary" onClick={onCancel}>{cancelLabel}</button>
          <button
            type="button"
            className={confirmClassName}
            disabled={confirmDisabled}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
