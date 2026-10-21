// ShiftTodayRedirect.jsx — محوّل إلى شفت اليوم (جرد أو كاش) بلا فتح ضمني
import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { shiftOpsApi } from '../../services/shiftOpsApi'
import { PageLoader } from '../../components/common'
import { isValidServerDate } from '../../utils/serverDate'
import { useT } from '../../i18n'

export function ShiftTodayRedirect({ target }) {
  const navigate = useNavigate()
  const t = useT()

  useEffect(() => {
    let cancelled = false
    shiftOpsApi
      .listShifts({})
      .then((r) => {
        if (cancelled) return
        const serverToday = r.data?.server_today
        if (!isValidServerDate(serverToday)) {
          toast.error(t('shift_ops.server_today_missing_error'))
          navigate('/shift-ops', { replace: true })
          return
        }
        const items = r.data?.items || []
        const todayShift = items.find((i) => String(i.shift_date).slice(0, 10) === serverToday)
        if (todayShift) {
          navigate(`/shift-ops/${todayShift.id}/${target}`, { replace: true })
        } else {
          navigate('/shift-ops?open=1&reason=no_shift_today', { replace: true })
        }
      })
      .catch(() => {
        if (cancelled) return
        toast.error(t('common.load_failed'))
        navigate('/shift-ops', { replace: true })
      })
    return () => { cancelled = true }
  }, [navigate, t, target])

  return <PageLoader />
}

export default ShiftTodayRedirect
