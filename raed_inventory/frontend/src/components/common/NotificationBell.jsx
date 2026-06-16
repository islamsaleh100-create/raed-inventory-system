import React, { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bell } from 'lucide-react'
import { notificationsApi } from '../../services/api'
import { notificationSectionLabel } from '../../utils/operationalLabels'

const POLL_INTERVAL_MS = 60_000

/**
 * Notification bell — fetches summary every 60s and on dropdown open.
 * Each section carries an i18n key (notifications.<key>) so the label
 * renders in the active language.
 */
export default function NotificationBell() {
  const t = useT()
  const { dir } = useLanguage()
  const [open, setOpen] = useState(false)
  const [summary, setSummary] = useState({ total: 0, sections: [] })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const wrapRef = useRef(null)

  const fetchSummary = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await notificationsApi.summary()
      setSummary(res.data || { total: 0, sections: [] })
    } catch (e) {
      setError(t('common.error_generic'))
    } finally {
      setLoading(false)
    }
  }

  // Initial load + polling
  useEffect(() => {
    fetchSummary()
    const id = setInterval(fetchSummary, POLL_INTERVAL_MS)
    return () => clearInterval(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Refresh when dropdown is opened
  useEffect(() => {
    if (open) fetchSummary()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  // Close on outside click
  useEffect(() => {
    if (!open) return
    const onDocClick = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [open])

  const total = summary?.total || 0
  const nonEmptySections = (summary?.sections || []).filter((s) => (s.count || 0) > 0)
  const anchorSide = dir === 'rtl' ? 'left-0' : 'right-0'

  return (
    <div className="relative" ref={wrapRef}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="relative p-2 hover:bg-gray-100 rounded-lg transition-colors"
        title={t('notifications.title')}
        aria-label={t('notifications.title')}
      >
        <Bell className="w-5 h-5 text-gray-600" />
        {total > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] px-1 bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center">
            {total > 99 ? '99+' : total}
          </span>
        )}
      </button>

      {open && (
        <div
          className={`absolute ${anchorSide} mt-2 w-80 max-h-[70vh] overflow-y-auto bg-white border border-gray-200 rounded-xl shadow-lg z-50`}
          style={{ top: '100%' }}
        >
          <div className="flex items-center justify-between p-3 border-b border-gray-100">
            <p className="font-semibold text-sm text-gray-900">{t('notifications.title')}</p>
            {loading && <span className="text-xs text-gray-400">{t('common.loading')}</span>}
          </div>

          {error && (
            <div className="p-4 text-sm text-red-600">{error}</div>
          )}

          {!error && nonEmptySections.length === 0 && !loading && (
            <div className="p-6 text-sm text-gray-500 text-center">
              {t('notifications.empty')}
            </div>
          )}

          {!error && nonEmptySections.map((section) => (
            <div key={section.key} className="border-b border-gray-50 last:border-b-0">
              <Link
                to={section.target_url || '/notifications'}
                onClick={() => setOpen(false)}
                className="flex items-center justify-between px-3 py-2 hover:bg-gray-50"
              >
                <span className="text-sm font-medium text-gray-800 truncate">
                  {notificationSectionLabel(t, section.key)}
                </span>
                <span className="text-xs font-semibold text-white bg-primary-600 rounded-full px-2 py-0.5 flex-shrink-0">
                  {section.count}
                </span>
              </Link>
              {(section.items || []).slice(0, 3).map((it, idx) => (
                <Link
                  key={`${section.key}-${idx}`}
                  to={it.target_url || section.target_url || '/notifications'}
                  onClick={() => setOpen(false)}
                  className="block px-5 py-1.5 text-xs text-gray-500 hover:bg-gray-50 truncate"
                >
                  {it.order_no || it.inventory_date || it.visit_date || it.assessment_date || `#${it.id ?? ''}`}
                </Link>
              ))}
            </div>
          ))}

          <div className="p-2 border-t border-gray-100">
            <Link
              to="/notifications"
              onClick={() => setOpen(false)}
              className="block text-center text-sm font-medium text-primary-700 hover:bg-gray-50 py-2 rounded-lg"
            >
              {t('notifications.view_all')}
            </Link>
          </div>
        </div>
      )}
    </div>
  )
}
