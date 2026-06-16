/** LAN trial operational roles — legacy order/inventory screens are hidden and blocked. */
export const TRIAL_SUPPLY_CHAIN_ROLES = [
  'branch_user',
  'branch_manager',
  'area_manager',
  'kitchen_section_manager',
  'warehouse_user',
  'warehouse_manager',
  'delivery_user',
]

export const LEGACY_TRIAL_BLOCKED_PATHS = new Set([
  '/orders',
  '/orders/daily',
  '/orders/exceptional',
  '/receiving',
  '/warehouse/orders',
  '/warehouse/picking',
  '/warehouse/dispatch',
  '/warehouse/stock',
  '/warehouse/reports',
  '/delivery',
  '/delivery/daily-entry',
  '/delivery/statements',
  '/delivery/reconciliation',
  '/delivery/closures',
  '/delivery/compliance',
  '/delivery/import',
  '/delivery/branches',
  '/delivery/branch-stats',
  '/delivery/brands',
  '/delivery/unmatched',
])

export function isTrialLegacyBlocked(roles = []) {
  if (roles.includes('admin') || roles.includes('super_admin')) return false
  return TRIAL_SUPPLY_CHAIN_ROLES.some((r) => roles.includes(r))
}

export function isLegacyPathBlockedForTrial(pathname = '', roles = []) {
  if (!isTrialLegacyBlocked(roles)) return false
  if (LEGACY_TRIAL_BLOCKED_PATHS.has(pathname)) return true
  if (pathname.startsWith('/orders/') && pathname !== '/orders/daily' && !pathname.startsWith('/orders/daily/')) {
    return true
  }
  if (pathname.startsWith('/receiving/')) return true
  if (pathname.startsWith('/warehouse/orders')) return true
  if (pathname.startsWith('/delivery-analytics')) return true
  return false
}
