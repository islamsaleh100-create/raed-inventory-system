// ShiftManagerActions.jsx — إعادة الفتح والإغلاق بلا نشاط (مدير فقط)
// Shared by the count and cash screens so the permission rule lives in one place.
//
// branch_manager is deliberately absent: they are party to the cash float, so
// they must not reopen their own record.
import React, { useState } from 'react'
import { Unlock, CalendarOff } from 'lucide-react'
import toast from 'react-hot-toast'
import { shiftOpsApi } from '../../services/shiftOpsApi'
import { useT } from '../../i18n'

const REOPEN_ROLES = ['area_manager', 'operations_manager', 'admin', 'super_admin']
const TARGETS = ['count', 'cash', 'both']
const EXCEPTION_TYPES = ['branch_closed', 'manual_gap']

export default function ShiftManagerActions({
  shiftId, roles = [], shift, openReopen = false, openCloseNoActivity = false, onDone,
}) {
  const t = useT()
  const allowed = roles.some((r) => REOPEN_ROLES.includes(r))

  const [showReopen, setShowReopen] = useState(openReopen)
  const [showClose, setShowClose] = useState(openCloseNoActivity)
  const [target, setTarget] = useState('cash')
  const [reason, setReason] = useState('')
  const [exceptionType, setExceptionType] = useState('branch_closed')
  const [closeReason, setCloseReason] = useState('')
  const [busy, setBusy] = useState(false)

  // Hiding the buttons is not the control — the route guard and the backend are.
  // This only keeps the UI honest about who the action belongs to.
  if (!allowed) return null

  const doReopen = async () => {
    setBusy(true)
    try {
      await shiftOpsApi.reopenShift(shiftId, { target, reason })
      toast.success(t('shift_ops.reopened'))
      setShowReopen(false)
      setReason('')
      onDone?.()
    } catch (err) {
      toast.error(err?.response?.data?.message || t('common.save_failed'))
    } finally {
      setBusy(false)
    }
  }

  const doClose = async () => {
    setBusy(true)
    try {
      await shiftOpsApi.closeNoActivity(shiftId, {
        exception_type: exceptionType,
        reason: closeReason,
      })
      toast.success(t('shift_ops.closed_no_activity'))
      setShowClose(false)
      setCloseReason('')
      onDone?.()
    } catch (err) {
      toast.error(err?.response?.data?.message || t('common.save_failed'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="bg-white border rounded-xl p-3 space-y-3">
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={() => setShowReopen((v) => !v)}
                className="inline-flex items-center gap-1 border border-amber-300 text-amber-800 rounded-lg px-3 py-1.5 text-xs">
          <Unlock size={14} /> {t('shift_ops.reopen')}
        </button>
        <button type="button" onClick={() => setShowClose((v) => !v)}
                className="inline-flex items-center gap-1 border rounded-lg px-3 py-1.5 text-xs">
          <CalendarOff size={14} /> {t('shift_ops.close_no_activity')}
        </button>
      </div>

      {showReopen && (
        <div className="border rounded-lg p-3 space-y-2 bg-amber-50">
          <div className="flex flex-wrap gap-2">
            {TARGETS.map((v) => (
              <label key={v} className="inline-flex items-center gap-1 text-xs">
                <input type="radio" name="reopen-target" value={v}
                       checked={target === v} onChange={() => setTarget(v)} />
                {t(`shift_ops.reopen_target.${v}`)}
              </label>
            ))}
          </div>
          <input type="text" value={reason} onChange={(e) => setReason(e.target.value)}
                 placeholder={t('shift_ops.reopen_reason_placeholder')}
                 className="w-full border rounded-lg px-3 py-2 text-sm" />
          <button type="button" disabled={busy || reason.trim().length < 5} onClick={doReopen}
                  className="bg-amber-600 text-white rounded-lg px-4 py-2 text-sm font-semibold disabled:bg-gray-300">
            {t('shift_ops.confirm_reopen')}
          </button>
        </div>
      )}

      {showClose && (
        <div className="border rounded-lg p-3 space-y-2 bg-gray-50">
          <select value={exceptionType} onChange={(e) => setExceptionType(e.target.value)}
                  className="w-full border rounded-lg px-3 py-2 text-sm">
            {EXCEPTION_TYPES.map((v) => (
              <option key={v} value={v}>{t(`shift_ops.exception_type.${v}`)}</option>
            ))}
          </select>
          <input type="text" value={closeReason} onChange={(e) => setCloseReason(e.target.value)}
                 placeholder={t('shift_ops.close_reason_placeholder')}
                 className="w-full border rounded-lg px-3 py-2 text-sm" />
          <button type="button" disabled={busy || closeReason.trim().length < 5} onClick={doClose}
                  className="bg-gray-800 text-white rounded-lg px-4 py-2 text-sm font-semibold disabled:bg-gray-300">
            {t('shift_ops.confirm_close_no_activity')}
          </button>
        </div>
      )}
    </div>
  )
}
