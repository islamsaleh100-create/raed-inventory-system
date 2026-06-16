/**
 * Single source of truth — LAN Trial quick-login cards (development only).
 * Usernames must match seed_phase2_official_users.py on raed_lan_trial.
 */

export const LAN_TRIAL_LOGIN_TITLE_KEY = 'auth.lan_accounts_title'
export const LAN_TRIAL_LOGIN_NOTICE_KEY = 'auth.lan_accounts_notice'

/** Usernames that must never appear on the LAN login helper. */
export const FORBIDDEN_LAN_LOGIN_USERNAMES = [
  'am_riyadh',
  'branch.mgr1',
  'wh.mgr1',
  'branch.user1',
  'qa.mgr',
  'ops.mgr',
  'branch_pizza_3_arkan',
  'branch_shawarma_4_arkan',
  'area_riyadh_all',
  'branch_onda_5_muowasat',
  'branch_onda_4_sefarat',
]

export const LAN_TRIAL_LOGIN_GROUPS = [
  {
    groupKey: 'auth.lan_group_system',
    accounts: [
      { labelKey: 'auth.lan_super_admin', username: 'super.admin', passwordKind: 'trial' },
      { labelKey: 'auth.lan_admin', username: 'admin', passwordKind: 'admin' },
      { labelKey: 'auth.lan_auditor', username: 'audit.officer', passwordKind: 'auditor' },
    ],
  },
  {
    groupKey: 'auth.lan_group_area_managers',
    accounts: [
      { labelKey: 'auth.lan_area_dammam_onda', username: 'area_dammam_onda', passwordKind: 'trial' },
      { labelKey: 'auth.lan_area_dammam_restaurants', username: 'area_dammam_restaurants', passwordKind: 'trial' },
    ],
  },
  {
    groupKey: 'auth.lan_group_trial_branches',
    accounts: [
      { labelKey: 'auth.lan_branch_onda_arkan', username: 'branch_onda_1_arkan', passwordKind: 'trial' },
      { labelKey: 'auth.lan_branch_pizza_khobar', username: 'branch_pizza_1_al_khobar', passwordKind: 'trial' },
      { labelKey: 'auth.lan_branch_shawarma_khobar', username: 'branch_shawarma_1_khobar', passwordKind: 'trial' },
    ],
  },
  {
    groupKey: 'auth.lan_group_kitchen',
    accounts: [
      { labelKey: 'auth.lan_kitchen_meat', username: 'kitchen_dammam_meat_and_chicken_mgr', passwordKind: 'trial' },
      { labelKey: 'auth.lan_kitchen_bakery', username: 'kitchen_dammam_bakery_and_sweets_mgr', passwordKind: 'trial' },
      { labelKey: 'auth.lan_kitchen_pizza', username: 'kitchen_dammam_pizza_mgr', passwordKind: 'trial' },
    ],
  },
  {
    groupKey: 'auth.lan_group_warehouse',
    accounts: [
      { labelKey: 'auth.lan_warehouse_manager', username: 'warehouse_dammam_manager', passwordKind: 'trial' },
      { labelKey: 'auth.lan_warehouse_user', username: 'warehouse_dammam_user', passwordKind: 'trial' },
    ],
  },
  {
    groupKey: 'auth.lan_group_delivery',
    accounts: [
      { labelKey: 'auth.lan_delivery_dammam', username: 'delivery_dammam', passwordKind: 'trial' },
    ],
  },
]

export const LAN_TRIAL_LOGIN_USERNAMES = LAN_TRIAL_LOGIN_GROUPS.flatMap((group) =>
  group.accounts.map((account) => account.username),
)

export function resolveLanTrialPassword(passwordKind = 'trial') {
  if (passwordKind === 'admin') {
    return import.meta.env.VITE_LAN_TRIAL_ADMIN_PASSWORD || 'Admin@2025'
  }
  if (passwordKind === 'auditor') {
    return import.meta.env.VITE_INTERNAL_AUDITOR_PASSWORD || 'Raed@2025'
  }
  return import.meta.env.VITE_LAN_TRIAL_DEMO_PASSWORD || 'LanTrial@2026Temp'
}
