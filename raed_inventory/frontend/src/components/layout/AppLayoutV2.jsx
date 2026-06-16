import React, { useState } from 'react'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import {
  LayoutDashboard, ClipboardList, Package, Truck, BarChart3,
  Users, Settings, LogOut, Menu, X,
  Warehouse, Building2, FileText, ArrowLeftRight,
  Star, GraduationCap, Bike, Globe, AlertCircle, TrendingUp, ChefHat, ShieldCheck, Flag, History, Lightbulb
} from 'lucide-react'
import { logout, selectUser, selectUserRoles, selectSidebarOpen, toggleSidebar } from '../../store'
import NotificationBell from '../common/NotificationBell'
import { useT, useLanguage } from '../../i18n'
import AssistantWidget from '../assistant/AssistantWidget'

// Navigation uses i18n keys (sectionKey / labelKey) that are translated at render time.
const NAVIGATION = [
  {
    sectionKey: 'nav.section_main',
    items: [
      { to: '/dashboard', icon: LayoutDashboard, labelKey: 'nav.dashboard', roles: [] },
    ]
  },
  {
    sectionKey: 'nav.section_branch',
    roles: ['branch_user', 'branch_manager'],
    items: [
      { to: '/inventory', icon: ClipboardList, labelKey: 'nav.daily_inventory', roles: ['branch_user', 'branch_manager'] },
      { to: '/orders', icon: Package, labelKey: 'nav.orders', roles: ['branch_user', 'branch_manager'] },
      { to: '/orders/daily', icon: ClipboardList, labelKey: 'nav.daily_order', roles: ['branch_manager', 'admin', 'super_admin'] },
      { to: '/receiving', icon: Truck, labelKey: 'nav.receiving', roles: ['branch_user', 'branch_manager'] },
      { to: '/branch-stock', icon: BarChart3, labelKey: 'nav.branch_stock', roles: ['branch_user', 'branch_manager', 'admin', 'super_admin'] },
      { to: '/branch-employees', icon: Users, labelKey: 'nav.branch_employees', roles: ['branch_manager', 'admin', 'super_admin'] },
      { to: '/stock/inter-branch-transfer', icon: ArrowLeftRight, labelKey: 'nav.inter_branch_transfer', roles: ['branch_manager', 'admin', 'super_admin'] },
    ]
  },
  {
    sectionKey: 'nav.section_warehouse',
    roles: ['warehouse_user', 'warehouse_manager'],
    items: [
      { to: '/warehouse/orders', icon: Package, labelKey: 'nav.warehouse_orders', roles: ['warehouse_user', 'warehouse_manager'] },
      { to: '/warehouse/picking', icon: ClipboardList, labelKey: 'nav.warehouse_picking', roles: ['warehouse_user', 'warehouse_manager'] },
      { to: '/warehouse/dispatch', icon: Truck, labelKey: 'nav.warehouse_dispatch', roles: ['warehouse_user', 'warehouse_manager'] },
      { to: '/warehouse/stock', icon: Warehouse, labelKey: 'nav.warehouse_stock', roles: ['warehouse_user', 'warehouse_manager'] },
      { to: '/warehouse/reports', icon: FileText, labelKey: 'nav.warehouse_reports', roles: ['warehouse_manager'] },
    ]
  },
  {
    sectionKey: 'nav.section_operations',
    roles: ['operations_manager', 'admin', 'super_admin', 'area_manager', 'warehouse_manager'],
    items: [
      { to: '/operations', icon: BarChart3, labelKey: 'nav.operations_dashboard', roles: ['operations_manager', 'admin', 'super_admin'] },
      // /reports/inventory: added warehouse_manager (stock planning) + area_manager (regional oversight) — 2026-04-21
      { to: '/reports/inventory', icon: FileText, labelKey: 'nav.inventory_reports', roles: ['operations_manager', 'admin', 'super_admin', 'warehouse_manager', 'area_manager'] },
      { to: '/reports/orders', icon: FileText, labelKey: 'nav.order_reports', roles: ['operations_manager', 'admin', 'super_admin'] },
      { to: '/operations/inter-branch-approvals', icon: ArrowLeftRight, labelKey: 'nav.inter_branch_approvals', roles: ['area_manager', 'operations_manager', 'admin', 'super_admin'] },
      { to: '/operations/branch-items', icon: Package, label: 'أصناف الفروع', labelKey: 'nav.branch_items', roles: ['area_manager', 'admin', 'super_admin'] },
    ]
  },
    {
      sectionKey: 'nav.section_supply_chain',
      roles: ['branch_user', 'branch_manager', 'area_manager', 'kitchen_section_manager', 'warehouse_user', 'warehouse_manager', 'delivery_user', 'operations_manager', 'internal_auditor', 'admin', 'super_admin'],
      items: [
        { to: '/supply-chain/control', icon: LayoutDashboard, labelKey: 'nav.supply_chain_control', roles: ['branch_user', 'branch_manager', 'area_manager', 'kitchen_section_manager', 'warehouse_user', 'warehouse_manager', 'delivery_user', 'operations_manager', 'internal_auditor', 'admin', 'super_admin'] },
        { to: '/supply-chain/branch-requests', icon: ClipboardList, labelKey: 'nav.supply_chain_branch_requests', roles: ['branch_user', 'branch_manager', 'area_manager', 'internal_auditor', 'admin', 'super_admin'] },
        { to: '/supply-chain/approvals', icon: Users, labelKey: 'nav.supply_chain_approvals', roles: ['area_manager', 'internal_auditor', 'admin', 'super_admin'] },
        { to: '/supply-chain/kitchen', icon: Package, labelKey: 'nav.supply_chain_kitchen', roles: ['kitchen_section_manager', 'internal_auditor', 'admin', 'super_admin'] },
        { to: '/supply-chain/warehouse', icon: Warehouse, labelKey: 'nav.supply_chain_warehouse', roles: ['warehouse_user', 'warehouse_manager', 'internal_auditor', 'admin', 'super_admin'] },
        { to: '/supply-chain/delivery', icon: Truck, labelKey: 'nav.supply_chain_delivery', roles: ['delivery_user', 'internal_auditor', 'admin', 'super_admin'] },
      ]
    },
    {
      sectionKey: 'nav.section_delivery',
      // sales_manager: full access. operations_manager: read-only (backend enforces write block).
      roles: ['branch_manager', 'area_manager', 'sales_manager', 'operations_manager', 'admin', 'super_admin'],
      items: [
        { to: '/delivery',              icon: Bike,          labelKey: 'nav.delivery_dashboard',     roles: ['sales_manager', 'operations_manager', 'area_manager', 'admin', 'super_admin'] },
        { to: '/delivery/daily-entry',  icon: ClipboardList, labelKey: 'nav.sales_daily_entry',      roles: ['branch_manager', 'area_manager', 'admin', 'super_admin'] },
        { to: '/delivery/statements',   icon: FileText,      labelKey: 'nav.sales_statements',       roles: ['sales_manager', 'admin', 'super_admin'] },
        { to: '/delivery/reconciliation', icon: BarChart3,   labelKey: 'nav.sales_reconciliation',   roles: ['branch_manager', 'area_manager', 'operations_manager', 'sales_manager', 'admin', 'super_admin'] },
        { to: '/delivery/closures',     icon: Package,       labelKey: 'nav.sales_closures',         roles: ['sales_manager', 'admin', 'super_admin'] },
        { to: '/delivery/compliance',   icon: AlertCircle,   labelKey: 'nav.sales_compliance',       roles: ['branch_manager', 'area_manager', 'operations_manager', 'sales_manager', 'admin', 'super_admin'] },
        { to: '/delivery/branch-stats', icon: BarChart3,     labelKey: 'nav.delivery_branches_perf', roles: ['sales_manager', 'operations_manager', 'area_manager', 'admin', 'super_admin'] },
        { to: '/delivery/brands',       icon: FileText,      labelKey: 'nav.delivery_brands_perf',   roles: ['sales_manager', 'operations_manager', 'area_manager', 'admin', 'super_admin'] },
        { to: '/delivery/import',       icon: ArrowLeftRight,labelKey: 'nav.delivery_import',        roles: ['sales_manager', 'admin', 'super_admin'] },
        { to: '/delivery/branches',     icon: Building2,     labelKey: 'nav.delivery_branches_admin',roles: ['sales_manager', 'admin', 'super_admin'] },
        { to: '/admin/sales-channels',  icon: Settings,      labelKey: 'nav.sales_channels_admin',   roles: ['sales_manager', 'admin', 'super_admin'] },
      ]
    },
  {
    sectionKey: 'nav.section_audit',
    roles: ['internal_auditor', 'admin', 'super_admin'],
    items: [
      { to: '/audit/dashboard', icon: ShieldCheck, labelKey: 'nav.audit_dashboard', roles: ['internal_auditor', 'admin', 'super_admin'] },
      { to: '/audit/daily-orders', icon: ClipboardList, labelKey: 'nav.audit_daily_orders', roles: ['internal_auditor', 'admin', 'super_admin'] },
      { to: '/audit/order-history', icon: History, labelKey: 'nav.audit_order_history', roles: ['internal_auditor', 'admin', 'super_admin'] },
      { to: '/audit/warehouse-stock', icon: Warehouse, labelKey: 'nav.audit_warehouse_stock', roles: ['internal_auditor', 'admin', 'super_admin'] },
      { to: '/audit/item-change-requests', icon: Package, label: 'طلبات تغييرات الأصناف', labelKey: 'nav.item_change_requests', roles: ['internal_auditor', 'admin', 'super_admin'] },
      { to: '/audit/findings', icon: Flag, labelKey: 'nav.audit_findings', roles: ['internal_auditor', 'admin', 'super_admin'] },
      { to: '/audit/trail', icon: History, labelKey: 'nav.audit_trail', roles: ['internal_auditor', 'admin', 'super_admin'] },
    ]
  },
  {
    sectionKey: 'nav.section_quality_training',
    roles: ['quality_visitor', 'quality_manager', 'area_manager', 'branch_manager', 'operations_manager', 'admin', 'super_admin'],
    items: [
      { to: '/quality', icon: Star, labelKey: 'nav.quality_visits', roles: ['quality_visitor', 'quality_manager', 'branch_manager', 'admin', 'super_admin'] },
      { to: '/quality/open-actions', icon: AlertCircle, labelKey: 'nav.quality_open_actions', roles: ['quality_visitor', 'quality_manager', 'branch_manager', 'area_manager', 'admin', 'super_admin'] },
      { to: '/quality/analytics', icon: TrendingUp, labelKey: 'nav.quality_analytics', roles: ['quality_manager', 'area_manager', 'operations_manager', 'admin', 'super_admin'] },
      { to: '/training', icon: GraduationCap, labelKey: 'nav.area_manager_assessments', roles: ['area_manager', 'quality_manager', 'operations_manager', 'branch_manager', 'admin', 'super_admin'] },
      { to: '/training/analytics', icon: TrendingUp, labelKey: 'nav.training_analytics', roles: ['quality_manager', 'operations_manager', 'admin', 'super_admin'] },
    ]
  },
  {
    sectionKey: 'nav.section_documents',
    roles: ['admin', 'super_admin', 'area_manager', 'branch_manager', 'quality_manager', 'warehouse_manager'],
    items: [
      { to: '/documents', icon: FileText, labelKey: 'nav.documents', roles: ['admin', 'super_admin', 'area_manager', 'branch_manager', 'quality_manager', 'warehouse_manager'] },
      { to: '/documents/expiring', icon: AlertCircle, labelKey: 'nav.documents_expiring', roles: ['admin', 'super_admin', 'area_manager', 'branch_manager', 'quality_manager', 'warehouse_manager'] },
    ]
  },
  {
    sectionKey: 'nav.section_analytics',
    roles: ['admin', 'super_admin', 'operations_manager', 'area_manager', 'quality_manager', 'warehouse_manager'],
    items: [
      { to: '/analytics/consumption-trend', icon: TrendingUp, labelKey: 'nav.analytics_consumption',
        roles: ['admin', 'super_admin', 'operations_manager', 'area_manager', 'warehouse_manager', 'branch_manager'] },
      { to: '/analytics/order-delay', icon: BarChart3, labelKey: 'nav.analytics_order_delay',
        roles: ['admin', 'super_admin', 'operations_manager', 'warehouse_manager', 'area_manager'] },
      { to: '/analytics/branches-open-actions', icon: AlertCircle, labelKey: 'nav.analytics_branches_open_actions',
        roles: ['admin', 'super_admin', 'area_manager', 'quality_manager', 'operations_manager'] },
    ]
  },
  {
    sectionKey: 'nav.section_admin',
    roles: ['admin', 'super_admin'],
    items: [
      { to: '/admin/users', icon: Users, labelKey: 'nav.users', roles: ['admin', 'super_admin'] },
      { to: '/admin/branches', icon: Building2, labelKey: 'nav.branches', roles: ['admin', 'super_admin'] },
      { to: '/admin/warehouses', icon: Warehouse, labelKey: 'nav.warehouses', roles: ['admin', 'super_admin'] },
      { to: '/admin/kitchens', icon: ChefHat, labelKey: 'nav.kitchens', roles: ['admin', 'super_admin'] },
      { to: '/admin/items', icon: Package, labelKey: 'nav.items', roles: ['admin', 'super_admin'] },
      { to: '/admin/suggestions', icon: Lightbulb, labelKey: 'nav.assistant_suggestions', roles: ['admin', 'super_admin'] },
      { to: '/admin/settings', icon: Settings, labelKey: 'nav.settings', roles: ['admin', 'super_admin'] },
    ]
  },
]

const TRIAL_SUPPLY_CHAIN_ROLES = [
  'branch_user', 'branch_manager', 'area_manager', 'kitchen_section_manager',
  'warehouse_user', 'warehouse_manager', 'delivery_user',
]

/** Legacy paths hidden for LAN trial operational roles (admin/super_admin keep full nav). */
const LEGACY_TRIAL_HIDDEN_PATHS = new Set([
  '/orders', '/orders/daily', '/orders/exceptional', '/receiving',
  '/warehouse/orders', '/warehouse/picking', '/warehouse/dispatch', '/warehouse/stock', '/warehouse/reports',
  '/delivery', '/delivery/daily-entry', '/delivery/statements', '/delivery/reconciliation',
  '/delivery/closures', '/delivery/compliance', '/delivery/import', '/delivery/branches',
  '/delivery/branch-stats', '/delivery/brands', '/delivery/unmatched',
])

function isLegacyHiddenForTrial(item, roles) {
  if (roles.includes('admin') || roles.includes('super_admin')) return false
  if (!TRIAL_SUPPLY_CHAIN_ROLES.some((r) => roles.includes(r))) return false
  if (LEGACY_TRIAL_HIDDEN_PATHS.has(item.to)) return true
  if (item.to.startsWith('/delivery-analytics')) return true
  return false
}

function NavItem({ item, roles, onClick }) {
  const location = useLocation()
  const t = useT()
  const isActive =
    location.pathname === item.to
    || (item.to !== '/dashboard'
      && item.to !== '/supply-chain/control'
      && location.pathname.startsWith(item.to))
  const isElevatedUser = roles.includes('admin') || roles.includes('super_admin')
  const visible = !isLegacyHiddenForTrial(item, roles)
    && (isElevatedUser || item.roles.length === 0 || item.roles.some((r) => roles.includes(r)))
  if (!visible) return null

  return (
    <Link to={item.to} onClick={onClick}>
      <div className={`sidebar-link ${isActive ? 'active' : ''}`}>
        <item.icon className="w-4 h-4 flex-shrink-0" />
        <span>{item.label || t(item.labelKey)}</span>
      </div>
    </Link>
  )
}

export default function AppLayoutV2({ children }) {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const user = useSelector(selectUser)
  const roles = useSelector(selectUserRoles)
  const sidebarOpen = useSelector(selectSidebarOpen)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const t = useT()
  const { lang, toggle: toggleLang } = useLanguage()
  const closeLabel = lang === 'ar' ? 'إغلاق القائمة' : 'Close menu'
  const openLabel = lang === 'ar' ? 'فتح القائمة' : 'Open menu'

  const handleLogout = () => {
    dispatch(logout())
    navigate('/login')
  }

  // Pick the most specific role for display, then translate.
  const ROLE_PRIORITY = [
    'super_admin', 'admin', 'internal_auditor', 'operations_manager', 'area_manager',
    'delivery_user', 'kitchen_section_manager',
    'sales_manager',
    'branch_manager', 'branch_user',
    'warehouse_manager', 'warehouse_user',
    'quality_manager', 'quality_visitor', 'trainer',
  ]
  const primaryRole = ROLE_PRIORITY.find((r) => roles.includes(r))
  const roleLabel = primaryRole ? t(`roles.${primaryRole}`) : ''

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      <aside className={`
        fixed inset-y-0 right-0 z-40 bg-white border-l border-gray-200 flex flex-col
        transition-all duration-300
        ${sidebarOpen ? 'w-64' : 'w-0 overflow-hidden'}
        lg:relative lg:flex
        ${mobileMenuOpen ? 'flex' : 'hidden lg:flex'}
      `}>
        <div className="flex items-center justify-between p-5 border-b border-gray-100">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-primary-600 rounded-xl flex items-center justify-center">
              <span className="text-white font-bold text-lg">{lang === 'ar' ? 'ر' : 'R'}</span>
            </div>
            <div>
              <p className="font-bold text-gray-900 text-sm leading-none">{t('app.name')}</p>
              <p className="text-xs text-gray-600 mt-0.5">{t('app.tagline')}</p>
            </div>
          </div>
          <button
            onClick={() => { dispatch(toggleSidebar()); setMobileMenuOpen(false) }}
            className="p-1 hover:bg-gray-100 rounded-lg lg:hidden"
            title={closeLabel}
            aria-label={closeLabel}
          >
            <X className="w-4 h-4 text-gray-500" />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto py-3 px-3 space-y-4">
          {NAVIGATION.map((section) => {
            const isElevatedUser = roles.includes('admin') || roles.includes('super_admin')
            const sectionVisible = !section.roles || section.roles.some((r) => roles.includes(r)) || isElevatedUser
            if (!sectionVisible) return null

            const visibleItems = section.items.filter((item) => {
              if (isLegacyHiddenForTrial(item, roles)) return false
              return isElevatedUser || item.roles.length === 0 || item.roles.some((r) => roles.includes(r))
            })
            if (visibleItems.length === 0) return null

            return (
              <div key={section.sectionKey}>
                <p className="text-xs font-semibold text-gray-600 uppercase tracking-wider px-4 mb-1">
                  {t(section.sectionKey)}
                </p>
                <div className="space-y-0.5">
                  {visibleItems.map((item) => (
                    <NavItem
                      key={item.to}
                      item={item}
                      roles={roles}
                      onClick={() => setMobileMenuOpen(false)}
                    />
                  ))}
                </div>
              </div>
            )
          })}
        </nav>

        <div className="p-4 border-t border-gray-100">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-primary-100 rounded-full flex items-center justify-center flex-shrink-0">
              <span className="text-primary-700 font-semibold text-sm">
                {user?.full_name?.[0] || 'U'}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-900 truncate">{user?.full_name}</p>
              <p className="text-xs text-gray-600 truncate">{roleLabel}</p>
            </div>
            <button
              onClick={handleLogout}
              className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors"
              title={t('common.logout')}
              aria-label={t('common.logout')}
            >
              <LogOut className="w-4 h-4 text-gray-500" />
            </button>
          </div>
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-3">
            <button
              onClick={() => { dispatch(toggleSidebar()); setMobileMenuOpen(!mobileMenuOpen) }}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              title={sidebarOpen ? closeLabel : openLabel}
              aria-label={sidebarOpen ? closeLabel : openLabel}
            >
              <Menu className="w-5 h-5 text-gray-600" />
            </button>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={toggleLang}
              className="flex items-center gap-1 px-2.5 py-1.5 hover:bg-gray-100 rounded-lg transition-colors text-xs font-medium text-gray-700"
              title={t('lang.current')}
              aria-label={t('lang.current')}
            >
              <Globe className="w-4 h-4 text-gray-500" />
              <span>{lang === 'ar' ? t('lang.toggle_to_en') : t('lang.toggle_to_ar')}</span>
            </button>
            <NotificationBell />
            <div className="text-left">
              <p className="text-sm font-medium text-gray-900">{user?.full_name}</p>
              <p className="text-xs text-gray-600">{roleLabel}</p>
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto">
          {/* Outlet: where child routes render (React Router v6 layout pattern).
              children is kept as a fallback for any direct usage of AppLayout. */}
          {children ?? <Outlet />}
        </main>
      </div>

      {mobileMenuOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/40 lg:hidden"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}
      <AssistantWidget />
    </div>
  )
}
