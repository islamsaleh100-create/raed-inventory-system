import React from 'react'
import { useT } from '../../../i18n'

export default function Pagination({ page, pageSize, total, onPageChange }) {
  const t = useT()
  const totalPages = Math.max(1, Math.ceil((total || 0) / pageSize))
  if (totalPages <= 1) return null
  return (
    <div className="flex items-center justify-between gap-3 flex-wrap pt-3">
      <p className="text-sm text-gray-500">
        {t('count_audit.pagination_summary', { page, totalPages, total: total ?? 0 })}
      </p>
      <div className="flex gap-2">
        <button
          type="button"
          className="btn-secondary"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          {t('count_audit.prev_page')}
        </button>
        <button
          type="button"
          className="btn-secondary"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
        >
          {t('count_audit.next_page')}
        </button>
      </div>
    </div>
  )
}
