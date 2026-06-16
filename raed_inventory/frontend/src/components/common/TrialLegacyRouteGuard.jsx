import React from 'react'
import { useSelector } from 'react-redux'
import { selectUserRoles } from '../../store'
import { useT } from '../../i18n'
import RouteRoleGuard from './RouteRoleGuard'
import { isTrialLegacyBlocked } from '../../utils/trialLegacy'

/**
 * Blocks LAN trial operational roles from legacy order/warehouse/delivery screens.
 * Admin and super_admin keep full access.
 */
export default function TrialLegacyRouteGuard({ allowed = [], children }) {
  const roles = useSelector(selectUserRoles)
  const t = useT()

  if (isTrialLegacyBlocked(roles)) {
    return (
      <div className="p-6">
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-6 max-w-xl">
          <h1 className="text-xl font-bold text-amber-900 mb-2">{t('common.lan_trial_legacy_blocked_title')}</h1>
          <p className="text-sm text-amber-800 leading-relaxed">{t('common.lan_trial_legacy_blocked_body')}</p>
        </div>
      </div>
    )
  }

  return <RouteRoleGuard allowed={allowed}>{children}</RouteRoleGuard>
}
