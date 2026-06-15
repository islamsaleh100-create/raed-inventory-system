import React, { useState, useEffect } from 'react'
import { useSelector } from 'react-redux'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend
} from 'recharts'
import { dashboardApi, masterApi, qualityApi } from '../../services/api'
import { selectUser, selectUserRoles } from '../../store'
import { KpiCard, PageLoader } from '../../components/common'
import { Link } from 'react-router-dom'
import {
  Building2, Package, AlertTriangle, TrendingUp,
  CheckCircle, Clock, Truck, XCircle, BarChart3, AlertCircle
} from 'lucide-react'
import { useT, useLanguage } from '../../i18n'

// ─── Operations Dashboard ──────────────────────────────────────────────
export function OperationsDashboard() {
  const t = useT()
  const { lang } = useLanguage()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [qualityKpis, setQualityKpis] = useState({ open: 0, overdue: 0 })

  useEffect(() => {
    dashboardApi.operations()
      .then((r) => setData(r.data))
      .finally(() => setLoading(false))
    // Quality KPIs — best-effort, tolerated failure for non-viewers
    Promise.all([
      qualityApi.listOpenActions().catch(() => ({ data: [] })),
      qualityApi.listOpenActions({ overdue_only: true }).catch(() => ({ data: [] })),
    ]).then(([all, overdue]) => {
      setQualityKpis({
        open: (all.data || []).length,
        overdue: (overdue.data || []).length,
      })
    })
  }, [])

  if (loading) return <PageLoader />

  const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{t('dashboard.ops_title')}</h1>
        <p className="text-gray-500 text-sm mt-1">{t('dashboard.ops_subtitle')}</p>
      </div>

      {/* Main KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          title={t('dashboard.ops_compliance_title')}
          value={`${data?.compliance_rate || 0}%`}
          subtitle={t('dashboard.ops_compliance_sub', { done: data?.branches_with_inventory_today || 0, total: data?.total_branches || 0 })}
          icon={CheckCircle}
          iconBg="bg-green-100"
          iconColor="text-green-600"
        />
        <KpiCard
          title={t('dashboard.ops_out_of_stock_title')}
          value={data?.total_out_of_stock_items || 0}
          subtitle={t('dashboard.ops_out_of_stock_sub')}
          icon={XCircle}
          iconBg="bg-red-100"
          iconColor="text-red-600"
        />
        <KpiCard
          title={t('dashboard.ops_below_min_title')}
          value={data?.total_below_min_items || 0}
          subtitle={t('dashboard.ops_below_min_sub')}
          icon={AlertTriangle}
          iconBg="bg-orange-100"
          iconColor="text-orange-600"
        />
        <KpiCard
          title={t('dashboard.ops_orders_today_title')}
          value={data?.total_orders_today || 0}
          subtitle={t('dashboard.ops_orders_today_sub', { rejected: data?.rejected_orders_today || 0 })}
          icon={Package}
          iconBg="bg-blue-100"
          iconColor="text-blue-600"
        />
      </div>

      {/* Quality KPIs row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Link to="/quality/open-actions" className="block">
          <KpiCard
            title={t('dashboard.quality_open_actions_title')}
            value={qualityKpis.open}
            subtitle={t('dashboard.quality_open_actions_sub')}
            icon={AlertCircle}
            iconBg="bg-orange-100"
            iconColor="text-orange-600"
          />
        </Link>
        <Link to="/quality/open-actions" className="block">
          <KpiCard
            title={t('dashboard.quality_overdue_title')}
            value={qualityKpis.overdue}
            subtitle={t('dashboard.quality_overdue_sub')}
            icon={AlertTriangle}
            iconBg="bg-red-100"
            iconColor="text-red-600"
          />
        </Link>
        <Link to="/quality/analytics" className="block">
          <KpiCard
            title={t('dashboard.quality_analytics_title')}
            value={t('dashboard.quality_analytics_value')}
            subtitle={t('dashboard.quality_analytics_sub')}
            icon={TrendingUp}
            iconBg="bg-indigo-100"
            iconColor="text-indigo-600"
          />
        </Link>
        <Link to="/training/analytics" className="block">
          <KpiCard
            title={t('dashboard.training_analytics_title')}
            value={t('dashboard.training_analytics_value')}
            subtitle={t('dashboard.training_analytics_sub')}
            icon={BarChart3}
            iconBg="bg-purple-100"
            iconColor="text-purple-600"
          />
        </Link>
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        {/* Top requested items */}
        <div className="card">
          <div className="card-header">
            <h2 className="font-semibold text-gray-900">{t('dashboard.ops_top_items_title')}</h2>
          </div>
          <div className="p-4" style={{ height: 280 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={data?.top_requested_items || []}
                layout="vertical"
                margin={{ left: 30, right: 30 }}
              >
                <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis
                  type="category"
                  dataKey={lang === 'en' ? 'item_name_en' : 'item_name_ar'}
                  width={100}
                  tick={{ fontSize: 10, textAnchor: 'end' }}
                />
                <Tooltip />
                <Bar dataKey="total_requested" fill="#3b82f6" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Top branches by shortages */}
        <div className="card">
          <div className="card-header">
            <h2 className="font-semibold text-gray-900">{t('dashboard.ops_top_branches_shortages')}</h2>
          </div>
          <div className="card-body">
            {data?.top_branches_by_shortages?.length > 0 ? (
              <div className="space-y-3">
                {data.top_branches_by_shortages.map((b, i) => (
                  <div key={b.branch_id} className="flex items-center gap-3">
                    <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white
                      ${i === 0 ? 'bg-red-500' : i === 1 ? 'bg-orange-500' : 'bg-yellow-500'}`}>
                      {i + 1}
                    </div>
                    <div className="flex-1">
                      <p className="text-sm font-medium text-gray-900">{b.branch_name}</p>
                    </div>
                    <span className="text-sm font-bold text-red-600">{b.shortage_count} {t('dashboard.ops_shortage_suffix')}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-400 text-sm text-center py-8">{t('dashboard.ops_no_data')}</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Warehouse Dashboard ───────────────────────────────────────────────
export function WarehouseDashboard() {
  const t = useT()
  const user = useSelector(selectUser)
  const roles = useSelector(selectUserRoles)
  const isAdmin = roles.includes('admin') || roles.includes('super_admin')

  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [warehouses, setWarehouses] = useState([])
  const [selectedWh, setSelectedWh] = useState(user?.warehouse_id || null)

  // admin بدون warehouse_id: قائمة المستودعات وتعيين افتراضي
  useEffect(() => {
    if (!isAdmin) return
    masterApi.listWarehouses().then((r) => {
      setWarehouses(r.data || [])
    })
  }, [isAdmin])

  // تحميل لوحة المستودع عند تحديد المستودع
  useEffect(() => {
    if (!selectedWh) return
    setLoading(true)
    dashboardApi.warehouse(selectedWh)
      .then((r) => setData(r.data))
      .finally(() => setLoading(false))
  }, [selectedWh])

  if (loading) return <PageLoader />

  if (!selectedWh) {
    return (
      <div className="p-6 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{t('dashboard.wh_title')}</h1>
            <p className="text-gray-500 text-sm mt-1">{t('dashboard.wh_subtitle_select')}</p>
          </div>
          {isAdmin && warehouses.length > 0 && (
            <select
              value={selectedWh || ''}
              onChange={(e) => setSelectedWh(e.target.value ? parseInt(e.target.value, 10) : null)}
              className="input-field w-full sm:w-64"
            >
              <option value="">{t('dashboard.wh_select_placeholder') || 'اختر المستودع'}</option>
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>{w.warehouse_name}</option>
              ))}
            </select>
          )}
        </div>
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-6 text-center">
          <p className="text-yellow-700 font-medium">
            {isAdmin ? t('dashboard.wh_select_warehouse_hint') : t('dashboard.wh_account_not_linked')}
          </p>
          {!isAdmin && (
            <p className="text-yellow-600 text-sm mt-1">{t('dashboard.wh_login_hint')}</p>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('dashboard.wh_title')}</h1>
          <p className="text-gray-500 text-sm mt-1">{data?.warehouse_name}</p>
        </div>
        {isAdmin && warehouses.length > 0 && (
          <select
            value={selectedWh || ''}
            onChange={(e) => setSelectedWh(e.target.value ? parseInt(e.target.value, 10) : null)}
            className="input-field w-full sm:w-64"
          >
            <option value="">{t('dashboard.wh_select_placeholder') || 'اختر المستودع'}</option>
            {warehouses.map((w) => (
              <option key={w.id} value={w.id}>{w.warehouse_name}</option>
            ))}
          </select>
        )}
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          title={t('dashboard.wh_kpi_pending')}
          value={data?.pending_orders || 0}
          icon={Clock}
          iconBg="bg-yellow-100"
          iconColor="text-yellow-600"
        />
        <KpiCard
          title={t('dashboard.wh_kpi_approved')}
          value={data?.approved_orders || 0}
          icon={CheckCircle}
          iconBg="bg-green-100"
          iconColor="text-green-600"
        />
        <KpiCard
          title={t('dashboard.wh_kpi_ready')}
          value={data?.ready_to_dispatch ?? data?.orders_in_picking ?? 0}
          icon={Truck}
          iconBg="bg-blue-100"
          iconColor="text-blue-600"
        />
        <KpiCard
          title={t('dashboard.wh_kpi_dispatched_today')}
          value={data?.dispatched_today || 0}
          icon={BarChart3}
          iconBg="bg-purple-100"
          iconColor="text-purple-600"
        />
      </div>
    </div>
  )
}
