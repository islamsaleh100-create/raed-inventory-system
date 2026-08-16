// ShiftTodayRedirect.jsx — محوّل إلى شفت اليوم (جرد أو كاش) بلا فتح ضمني
import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { shiftOpsApi } from '../../services/shiftOpsApi'
import { PageLoader } from '../../components/common'
import { todayString } from '../../utils/helpers'
import { useT } from '../../i18n'

export function ShiftTodayRedirect({ target }) {
  const navigate = useNavigate()
  const t = useT()

  useEffect(() => {
    let cancelled = false
    const today = todayString()
    shiftOpsApi
      .listShifts({ date_from: today, date_to: today })
      .then((r) => {
        if (cancelled) return
        const items = r.data?.items || []
        if (items.length > 0) {
          navigate(`/shift-ops/${items[0].id}/${target}`, { replace: true })
        } else {
          navigate('/shift-ops?open=1', { replace: true })
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
