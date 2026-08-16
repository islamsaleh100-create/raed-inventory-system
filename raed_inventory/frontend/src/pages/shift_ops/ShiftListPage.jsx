// ShiftListPage.jsx — عمليات الشفت: قائمة الشفتات ونقطة الدخول
import React, { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { Plus, ClipboardList, Wallet, AlertTriangle, Unlock, CalendarOff } from 'lucide-react'
import toast from 'react-hot-toast'
import { shiftOpsApi } from '../../services/shiftOpsApi'
import { selectUser, selectUserRoles } from '../../store'
import { PageLoader } from '../../components/common'
import { todayString } from '../../utils/helpers'
import { useT } from '../../i18n'

const MANAGER_ROLES = ['area_manager', 'operations_manager', 'admin', 'super_admin']

function SectionBadge({ label, status, t }) {
  const map = {
    submitted: 'bg-green-100 text-green-800',
    draft: 'bg-amber-100 text-amber-800',
  }
  const cls = map[status] || 'bg-gray-100 text-gray-600'
  const text = status ? t(`shift_ops.section_status.${status}`) : t('shift_ops.section_status.none')
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs ${cls}`}>
      {label}: {text}
    </span>
  )
}

export function ShiftListPage() {
  const t = useT()
  const user = useSelector(selectUser)
  const roles = useSelector(selectUserRoles) || []
  const isManager = roles.some((r) => MANAGER_ROLES.includes(r))

  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [partialOnly, setPartialOnly] = useState(false)
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  const [openForm, setOpenForm] = useState(false)
  const [shiftDate, setShiftDate] = useState(todayString())
  const [shiftNumber, setShiftNumber] = useState(1)
  // Never hardcoded: comes from the backend (available_shift_numbers).
  const [availableShiftNumbers, setAvailableShiftNumbers] = useState(null)
  const [overrideReason, setOverrideReason] = useState('')
  const [needsOverride, setNeedsOverride] = useState(false)
  const [saving, setSaving] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    const params = {}
    if (partialOnly) params.partial_only = true
    if (dateFrom) params.date_from = dateFrom
    if (dateTo) params.date_to = dateTo
    shiftOpsApi
      .listShifts(params)
      .then((r) => {
        const items = r.data?.items || []
        setRows(items)
        // مستوى الرد أولًا: يصل حتى مع صفر شفتات، ويخصّ الفرع المطلوب لا أول عنصر صادفناه.
        // القراءة من العناصر تبقى احتياطًا لو خدم قديم لم يُنشر بعد.
        const top = r.data?.available_shift_numbers
        if (Array.isArray(top)) {
          setAvailableShiftNumbers(top)
        } else {
          const known = items.find((i) => Array.isArray(i.available_shift_numbers))
          if (known) setAvailableShiftNumbers(known.available_shift_numbers)
        }
      })
      .catch(() => toast.error(t('common.load_failed')))
      .finally(() => setLoading(false))
  }, [partialOnly, dateFrom, dateTo, t])

  useEffect(() => { load() }, [load])

  const singleShiftBranch = Array.isArray(availableShiftNumbers) && availableShiftNumbers.length === 1
  useEffect(() => {
    if (singleShiftBranch) setShiftNumber(availableShiftNumbers[0])
  }, [singleShiftBranch, availableShiftNumbers])

  const submitOpen = async (withOverride = false) => {
    setSaving(true)
    try {
      const payload = { shift_date: shiftDate, shift_number: Number(shiftNumber) }
      if (withOverride) {
        payload.override = true
        payload.override_reason = overrideReason
      }
      await shiftOpsApi.openShift(payload)
      toast.success(t('shift_ops.opened'))
      setOpenForm(false)
      setNeedsOverride(false)
      setOverrideReason('')
      load()
    } catch (err) {
      const code = err?.response?.data?.error_code
      if (code === 'PREVIOUS_SHIFT_NOT_CLOSED') {
        // Never auto-override: the previous shift gets force-closed, so the
        // manager must see and accept that consequence explicitly.
        setNeedsOverride(true)
      } else {
        toast.error(err?.response?.data?.message || t('common.save_failed'))
      }
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <PageLoader />

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-xl font-bold">{t('shift_ops.title')}</h1>
        <button
          type="button"
          onClick={() => setOpenForm((v) => !v)}
          className="inline-flex items-center gap-2 bg-primary-600 text-white px-4 py-2 rounded-lg text-sm font-semibold"
        >
          <Plus size={16} /> {t('shift_ops.open_shift')}
        </button>
      </div>

      {/* ── filters ── */}
      <div className="bg-white border rounded-xl p-3 flex flex-wrap gap-3 items-end text-sm">
        <label className="flex flex-col gap-1">
          <span className="text-gray-500 text-xs">{t('common.date_from')}</span>
          <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)}
                 className="border rounded-lg px-2 py-1.5" />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-gray-500 text-xs">{t('common.date_to')}</span>
          <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)}
                 className="border rounded-lg px-2 py-1.5" />
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={partialOnly} onChange={(e) => setPartialOnly(e.target.checked)} />
          <span>{t('shift_ops.filter_partial_only')}</span>
        </label>
      </div>

      {/* ── open shift form ── */}
      {openForm && (
        <div className="bg-white border rounded-xl p-4 space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-gray-500 text-xs">{t('shift_ops.shift_date')}</span>
              <input type="date" value={shiftDate} onChange={(e) => setShiftDate(e.target.value)}
                     className="border rounded-lg px-3 py-2" />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-gray-500 text-xs">{t('shift_ops.shift_number')}</span>
              {availableShiftNumbers === null || availableShiftNumbers.length === 0 ? (
                <span className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                  {availableShiftNumbers === null
                    ? t('shift_ops.shift_config_unavailable')
                    : t('shift_ops.no_shift_config')}
                </span>
              ) : (
                <select
                  value={shiftNumber}
                  disabled={singleShiftBranch}
                  onChange={(e) => setShiftNumber(e.target.value)}
                  className="border rounded-lg px-3 py-2 disabled:bg-gray-100"
                >
                  {availableShiftNumbers.map((n) => (
                    <option key={n} value={n}>{t('shift_ops.shift_n', { n })}</option>
                  ))}
                </select>
              )}
            </label>
          </div>

          {needsOverride && (
            <div className="border border-red-300 bg-red-50 rounded-lg p-3 space-y-2">
              <p className="text-sm text-red-800 font-semibold flex items-center gap-2">
                <AlertTriangle size={16} /> {t('shift_ops.override_warning')}
              </p>
              <input
                type="text"
                value={overrideReason}
                onChange={(e) => setOverrideReason(e.target.value)}
                placeholder={t('shift_ops.override_reason_placeholder')}
                className="w-full border rounded-lg px-3 py-2 text-sm"
              />
              <button
                type="button"
                disabled={saving || overrideReason.trim().length < 5}
                onClick={() => submitOpen(true)}
                className="bg-red-600 text-white px-4 py-2 rounded-lg text-sm font-semibold disabled:bg-gray-300"
              >
                {t('shift_ops.confirm_override')}
              </button>
            </div>
          )}

          {!needsOverride && (
            <button
              type="button"
              disabled={saving || !availableShiftNumbers?.length}
              onClick={() => submitOpen(false)}
              className="bg-primary-600 text-white px-4 py-2 rounded-lg text-sm font-semibold disabled:bg-gray-300"
            >
              {t('common.save')}
            </button>
          )}
        </div>
      )}

      {/* ── list ── */}
      <div className="space-y-2">
        {rows.length === 0 && (
          <p className="text-sm text-gray-500 bg-white border rounded-xl p-6 text-center">
            {t('common.no_data')}
          </p>
        )}

        {rows.map((row) => (
          <div key={row.id} className="bg-white border rounded-xl p-3 space-y-2">
            <div className="flex items-start justify-between gap-2 flex-wrap">
              <div>
                <div className="font-semibold text-sm">
                  {row.shift_date} · {t('shift_ops.shift_n', { n: row.shift_number })}
                </div>
                <div className="text-xs text-gray-500">
                  {t(`shift_ops.status.${row.status}`)}
                  {row.exception_type ? ` · ${t(`shift_ops.exception_type.${row.exception_type}`)}` : ''}
                </div>
              </div>
              {row.is_partial && (
                <span className="inline-flex items-center gap-1 bg-red-100 text-red-800 px-2 py-1 rounded text-xs font-bold">
                  <AlertTriangle size={13} /> {t('shift_ops.partial')}
                </span>
              )}
            </div>

            {/* count and cash are never merged into one status */}
            <div className="flex flex-wrap gap-2">
              <SectionBadge label={t('shift_ops.count')} status={row.count_status} t={t} />
              <SectionBadge label={t('shift_ops.cash')} status={row.cash_status} t={t} />
            </div>

            <div className="flex flex-wrap gap-2 pt-1">
              <Link to={`/shift-ops/${row.id}/count`}
                    className="inline-flex items-center gap-1 border rounded-lg px-3 py-1.5 text-xs">
                <ClipboardList size={14} /> {t('shift_ops.count')}
              </Link>
              <Link to={`/shift-ops/${row.id}/cash`}
                    className="inline-flex items-center gap-1 border rounded-lg px-3 py-1.5 text-xs">
                <Wallet size={14} /> {t('shift_ops.cash')}
              </Link>
              {isManager && (
                <>
                  <Link to={`/shift-ops/${row.id}/count?manage=1`}
                        className="inline-flex items-center gap-1 border border-amber-300 text-amber-800 rounded-lg px-3 py-1.5 text-xs">
                    <Unlock size={14} /> {t('shift_ops.reopen')}
                  </Link>
                  <Link to={`/shift-ops/${row.id}/count?closeNoActivity=1`}
                        className="inline-flex items-center gap-1 border border-gray-300 rounded-lg px-3 py-1.5 text-xs">
                    <CalendarOff size={14} /> {t('shift_ops.close_no_activity')}
                  </Link>
                </>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default ShiftListPage
