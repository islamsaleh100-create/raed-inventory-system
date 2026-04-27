import React from 'react'
import { useSelector } from 'react-redux'
import { selectUserRoles } from '../../store'
import { useT } from '../../i18n'

/**
 * Blocks rendering when the user has none of `allowed` roles.
 * super_admin always passes.
 * admin must be listed explicitly in `allowed` to keep route access visible.
 */
export default function RouteRoleGuard({ allowed = [], children }) {
  const roles = useSelector(selectUserRoles)
  const t = useT()
  const elevated = roles.includes('super_admin')
  const ok = elevated || (Array.isArray(allowed) && allowed.some((r) => roles.includes(r)))

  if (!ok) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded-xl p-6 max-w-lg">
          <h1 className="text-xl font-bold text-red-900 mb-2">{t('common.forbidden_page_title')}</h1>
          <p className="text-sm text-red-700">{t('common.forbidden_page_body')}</p>
        </div>
      </div>
    )
  }
  return children
}
