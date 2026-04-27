import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useSelector } from 'react-redux'
import {
  ClipboardList, Package, Truck, AlertTriangle,
  CheckCircle, XCircle,
} from 'lucide-react'
import { dashboardApi, ordersApi } from '../../services/api'
import { KpiCard, PageLoader, StatusBadge, StockStatusBadge } from '../../components/common'
import { formatDate, todayString, formatQty } from '../../utils/helpers'
import { selectUser } from '../../store'
import { useT, useLanguage } from '../../i18n'

export default function BranchDashboard() {
  const user = useSelector(selectUser)
  const branchId = user?.branch_id
  const t = useT()
  const { lang } = useLanguage()
  const nameOf = (row, base = 'item_name') =>
    row?.[`${base}_${lang}`] || row?.[`${base}_ar`] || row?.[base] || ''
  const [data, setData] = useState(null)
  const [stock, setStock] = useState([])
  const [recentOrders, setRecentOrders] = useState([])
  const [loading, setLoading] = useState(true)
  const today = todayString()

  useEffect(() => {
    if (!branchId) {
      setLoading(false)
      return
    }
    setLoading(true)
    Promise.all([
      dashboardApi.branch(branchId),
      dashboardApi.branchStock(branchId),
      ordersApi.list({ branch_id: branchId, page_size: 5 }),
    ]).then(([d, s, o]) => {
      setData(d.data)
      setStock(s.data.filter(i => i.status !== 'ok').slice(0, 10))
      setRecentOrders(o.data.items || [])
    }).finally(() => setLoading(false))
  }, [branchId])

  if (loading) return <PageLoader />

  if (!branchId) {
    return (
      <div className="p-6">
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-6 text-center">
          <p className="text-yellow-800 font-medium">{t('branch_stock.no_branch')}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            {t('dashboard.greeting', { name: user?.full_name })}
          </h1>
          <p className="text-gray-500 text-sm mt-1">{data?.branch_name} — {formatDate(today)}</p>
        </div>
        <div className="flex gap-2">
          {!data?.today_inventory_status || data.today_inventory_status === 'rejected' ? (
            <Link to="/inventory/new" className="btn-primary text-sm">
              <ClipboardList className="w-4 h-4" /> {t('dashboard.enter_daily_inventory')}
            </Link>
          ) : (
            <div className="flex items-center gap-2 bg-green-50 border border-green-200 rounded-lg px-3 py-2">
              <CheckCircle className="w-4 h-4 text-green-600" />
              <span className="text-sm text-green-700 font-medium">
                {t('dashboard.today_inventory_label')} <StatusBadge status={data.today_inventory_status} />
              </span>
            </div>
          )}
          <Link to="/orders/exceptional" className="btn-secondary text-sm">
            <Package className="w-4 h-4" /> {t('dashboard.exceptional_order')}
          </Link>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Link to="/branch-stock" className="block">
          <KpiCard
            title={t('dashboard.items_below_min')}
            value={data?.items_below_min || 0}
            icon={AlertTriangle}
            iconBg="bg-orange-100"
            iconColor="text-orange-600"
          />
        </Link>
        <KpiCard
          title={t('dashboard.items_out_of_stock')}
          value={data?.items_out_of_stock || 0}
          icon={XCircle}
          iconBg="bg-red-100"
          iconColor="text-red-600"
        />
        <KpiCard
          title={t('dashboard.open_orders')}
          value={data?.open_orders || 0}
          icon={Package}
          iconBg="bg-blue-100"
          iconColor="text-blue-600"
        />
        <KpiCard
          title={t('dashboard.pending_receipt')}
          value={data?.pending_receiving || 0}
          icon={Truck}
          iconBg="bg-purple-100"
          iconColor="text-purple-600"
        />
      </div>

      {/* Compliance rate */}
      <div className="card p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold text-gray-900">{t('dashboard.weekly_compliance')}</h2>
          <span className="text-2xl font-bold text-primary-600">
            {data?.weekly_compliance_rate || 0}%
          </span>
        </div>
        <div className="w-full bg-gray-100 rounded-full h-2.5">
          <div
            className="bg-primary-600 h-2.5 rounded-full transition-all duration-500"
            style={{ width: `${data?.weekly_compliance_rate || 0}%` }}
          />
        </div>
        {data?.critical_items_alert > 0 && (
          <div className="mt-3 flex items-center gap-2 text-sm text-red-600">
            <AlertTriangle className="w-4 h-4" />
            <span>{t('dashboard.critical_items_alert', { n: data.critical_items_alert })}</span>
          </div>
        )}
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        {/* Stock alerts */}
        <div className="card">
          <div className="card-header flex items-center justify-between">
            <h2 className="font-semibold text-gray-900">{t('dashboard.stock_alerts')}</h2>
            <Link to="/branch-stock" className="text-sm text-primary-600 hover:underline">
              {t('common.view_all')}
            </Link>
          </div>
          <div className="divide-y divide-gray-50">
            {stock.length === 0 ? (
              <div className="py-8 text-center text-gray-400 text-sm">{t('dashboard.no_alerts')}</div>
            ) : stock.map((item) => (
              <div key={item.item_id} className="px-5 py-3 flex items-center justify-between">
                <div>
                  <p className="font-medium text-gray-900 text-sm">{nameOf(item)}</p>
                  <p className="text-xs text-gray-400">{item.item_code}</p>
                </div>
                <div className="text-left flex items-center gap-3">
                  <div className="text-left">
                    <p className="text-sm font-semibold text-gray-900">{formatQty(item.current_qty)}</p>
                    <p className="text-xs text-gray-400">{t('dashboard.minimum_label', { qty: formatQty(item.min_qty) })}</p>
                  </div>
                  <StockStatusBadge status={item.status} />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Recent orders */}
        <div className="card">
          <div className="card-header flex items-center justify-between">
            <h2 className="font-semibold text-gray-900">{t('dashboard.recent_orders')}</h2>
            <Link to="/orders" className="text-sm text-primary-600 hover:underline">
              {t('common.view_all')}
            </Link>
          </div>
          <div className="divide-y divide-gray-50">
            {recentOrders.length === 0 ? (
              <div className="py-8 text-center text-gray-400 text-sm">{t('orders.empty')}</div>
            ) : recentOrders.map((order) => (
              <Link
                key={order.id}
                to={`/orders/${order.id}`}
                className="px-5 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors"
              >
                <div>
                  <p className="font-medium text-gray-900 text-sm">{order.order_no}</p>
                  <p className="text-xs text-gray-400">{formatDate(order.order_date)}</p>
                </div>
                <StatusBadge status={order.status} />
              </Link>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
