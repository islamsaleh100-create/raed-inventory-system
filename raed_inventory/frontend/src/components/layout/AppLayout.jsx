import React, { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import {
  LayoutDashboard, ClipboardList, Package, Truck, BarChart3,
  Users, Settings, LogOut, Menu, X, ChevronDown, Bell,
  Warehouse, Building2, ShieldCheck, FileText, ArrowLeftRight,
  Star, GraduationCap, Bike
} from 'lucide-react'
import { logout, selectUser, selectUserRoles, selectSidebarOpen, toggleSidebar } from '../../store'
import { hasRole } from '../../store'

const NAVIGATION = [
  {
    section: 'رئيسي',
    items: [
      { to: '/dashboard', icon: LayoutDashboard, label: 'لوحة التحكم', roles: [] },
    ]
  },
  {
    section: 'الفرع',
    roles: ['branch_user', 'branch_manager'],
    items: [
      { to: '/shift-ops', icon: ClipboardList, label: 'عمليات الشفت', roles: ['branch_user', 'branch_manager', 'area_manager', 'operations_manager', 'admin', 'super_admin'] },
      { to: '/inventory', icon: ClipboardList, label: 'الجرد اليومي (قديم)', roles: ['admin', 'super_admin'] },
      { to: '/orders', icon: Package, label: 'الطلبيات', roles: ['branch_user', 'branch_manager'] },
      { to: '/receiving', icon: Truck, label: 'الاستلام', roles: ['branch_user', 'branch_manager'] },
      { to: '/branch-stock', icon: BarChart3, label: 'حالة المخزون', roles: ['branch_user', 'branch_manager'] },
    ]
  },
  {
    section: 'المستودع',
    roles: ['warehouse_user', 'warehouse_manager'],
    items: [
      { to: '/warehouse/orders', icon: Package, label: 'قائمة الطلبيات', roles: ['warehouse_user', 'warehouse_manager'] },
      { to: '/warehouse/picking', icon: ClipboardList, label: 'التجهيز والصرف', roles: ['warehouse_user', 'warehouse_manager'] },
      { to: '/warehouse/stock', icon: Warehouse, label: 'مخزون المستودع', roles: ['warehouse_user', 'warehouse_manager'] },
      { to: '/warehouse/reports', icon: FileText, label: 'تقارير المستودع', roles: ['warehouse_manager'] },
    ]
  },
  {
    section: 'العمليات',
    roles: ['operations_manager', 'admin', 'super_admin'],
    items: [
      { to: '/operations', icon: BarChart3, label: 'لوحة العمليات', roles: ['operations_manager', 'admin', 'super_admin'] },
      { to: '/reports/inventory', icon: FileText, label: 'تقارير الجرد', roles: ['operations_manager', 'admin', 'super_admin'] },
      { to: '/reports/orders', icon: FileText, label: 'تقارير الطلبيات', roles: ['operations_manager', 'admin', 'super_admin'] },
    ]
  },
  {
    section: 'الجودة والتدريب',
    roles: ['quality_visitor', 'quality_manager', 'area_manager', 'branch_manager', 'operations_manager', 'admin', 'super_admin'],
    items: [
      { to: '/quality', icon: Star, label: 'زيارات الجودة', roles: ['quality_visitor', 'quality_manager', 'branch_manager', 'admin', 'super_admin'] },
      { to: '/training', icon: GraduationCap, label: 'تقييمات مدير المنطقة', roles: ['area_manager', 'quality_manager', 'operations_manager', 'branch_manager', 'admin', 'super_admin'] },
    ]
  },
  {
    section: 'تحليل التوصيل',
    roles: ['super_admin'],
    items: [
      { to: '/delivery',             icon: Bike,      label: 'داشبورد التوصيل',   roles: ['super_admin'] },
      { to: '/delivery/branch-stats',icon: BarChart3, label: 'أداء الفروع',        roles: ['super_admin'] },
      { to: '/delivery/brands',      icon: ShieldCheck,label: 'أداء البراندات',   roles: ['super_admin'] },
      { to: '/delivery/import',      icon: ArrowLeftRight, label: 'استيراد بيانات', roles: ['super_admin'] },
      { to: '/delivery/branches',    icon: Building2, label: 'إدارة الفروع',       roles: ['super_admin'] },
    ]
  },
  {
    section: 'الإدارة',
    roles: ['admin', 'super_admin'],
    items: [
      { to: '/admin/users', icon: Users, label: 'المستخدمون', roles: ['admin', 'super_admin'] },
      { to: '/admin/branches', icon: Building2, label: 'الفروع', roles: ['admin', 'super_admin'] },
      { to: '/admin/warehouses', icon: Warehouse, label: 'المستودعات', roles: ['admin', 'super_admin'] },
      { to: '/admin/items', icon: Package, label: 'الأصناف', roles: ['admin', 'super_admin'] },
      { to: '/admin/settings', icon: Settings, label: 'الإعدادات', roles: ['admin', 'super_admin'] },
    ]
  },
]

function NavItem({ item, roles, onClick }) {
  const location = useLocation()
  const isActive = location.pathname === item.to ||
    (item.to !== '/dashboard' && location.pathname.startsWith(item.to))
  const isElevatedUser = roles.includes('admin') || roles.includes('super_admin')
  const visible = isElevatedUser || item.roles.length === 0 || item.roles.some(r => roles.includes(r))
  if (!visible) return null
  return (
    <Link to={item.to} onClick={onClick}>
      <div className={`sidebar-link ${isActive ? 'active' : ''}`}>
        <item.icon className="w-4 h-4 flex-shrink-0" />
        <span>{item.label}</span>
      </div>
    </Link>
  )
}

export default function AppLayout({ children }) {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const user = useSelector(selectUser)
  const roles = useSelector(selectUserRoles)
  const sidebarOpen = useSelector(selectSidebarOpen)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  const handleLogout = () => {
    dispatch(logout())
    navigate('/login')
  }

  const roleLabel = roles.includes('super_admin') ? 'مدير النظام' :
    roles.includes('admin') ? 'مشرف' :
    roles.includes('branch_manager') ? 'مدير فرع' :
    roles.includes('branch_user') ? 'موظف فرع' :
    roles.includes('warehouse_manager') ? 'مدير مستودع' :
    roles.includes('warehouse_user') ? 'موظف مستودع' :
    roles.includes('operations_manager') ? 'مدير عمليات' :
    roles.includes('area_manager') ? 'مدير المنطقة' :
    roles.includes('quality_manager') ? 'مدير الجودة' :
    roles.includes('quality_visitor') ? 'مفتش جودة' : ''

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      {/* Sidebar */}
      <aside className={`
        fixed inset-y-0 right-0 z-40 bg-white border-l border-gray-200 flex flex-col
        transition-all duration-300
        ${sidebarOpen ? 'w-64' : 'w-0 overflow-hidden'}
        lg:relative lg:flex
        ${mobileMenuOpen ? 'flex' : 'hidden lg:flex'}
      `}>
        {/* Logo */}
        <div className="flex items-center justify-between p-5 border-b border-gray-100">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-primary-600 rounded-xl flex items-center justify-center">
              <span className="text-white font-bold text-lg">ر</span>
            </div>
            <div>
              <p className="font-bold text-gray-900 text-sm leading-none">رائد</p>
              <p className="text-xs text-gray-400 mt-0.5">نظام الجرد</p>
            </div>
          </div>
          <button
            onClick={() => { dispatch(toggleSidebar()); setMobileMenuOpen(false) }}
            className="p-1 hover:bg-gray-100 rounded-lg lg:hidden"
          >
            <X className="w-4 h-4 text-gray-500" />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-3 px-3 space-y-4">
          {NAVIGATION.map((section) => {
            const isElevatedUser = roles.includes('admin') || roles.includes('super_admin')
            const sectionVisible = !section.roles ||
              section.roles.some(r => roles.includes(r)) ||
              isElevatedUser
            if (!sectionVisible) return null
            return (
              <div key={section.section}>
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider px-4 mb-1">
                  {section.section}
                </p>
                <div className="space-y-0.5">
                  {section.items.map((item) => (
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

        {/* User info */}
        <div className="p-4 border-t border-gray-100">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-primary-100 rounded-full flex items-center justify-center flex-shrink-0">
              <span className="text-primary-700 font-semibold text-sm">
                {user?.full_name?.[0] || 'U'}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-900 truncate">{user?.full_name}</p>
              <p className="text-xs text-gray-400 truncate">{roleLabel}</p>
            </div>
            <button
              onClick={handleLogout}
              className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors"
              title="تسجيل الخروج"
            >
              <LogOut className="w-4 h-4 text-gray-500" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Topbar */}
        <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-3">
            <button
              onClick={() => { dispatch(toggleSidebar()); setMobileMenuOpen(!mobileMenuOpen) }}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <Menu className="w-5 h-5 text-gray-600" />
            </button>
          </div>
          <div className="flex items-center gap-2">
            <button className="relative p-2 hover:bg-gray-100 rounded-lg transition-colors">
              <Bell className="w-5 h-5 text-gray-600" />
            </button>
            <div className="text-left">
              <p className="text-sm font-medium text-gray-900">{user?.full_name}</p>
              <p className="text-xs text-gray-400">{roleLabel}</p>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto">
          {children}
        </main>
      </div>

      {/* Mobile overlay */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/40 lg:hidden"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}
    </div>
  )
}
