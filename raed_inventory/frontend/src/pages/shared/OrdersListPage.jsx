import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { Plus, Eye, CheckCircle, XCircle, Truck, Package } from 'lucide-react'
import toast from 'react-hot-toast'
import { ordersApi } from '../../services/api'
import { selectUser, selectUserRoles } from '../../store'
import { StatusBadge, PageLoader, Pagination } from '../../components/common'
import { formatDate } from '../../utils/helpers'
import { useT } from '../../i18n'

export default function OrdersListPage({
  warehouseView = false,
  receiveView = false,
  pickingView = false,
  dispatchView = false,
  defaultStatus = null,
  scopeAll = false,
  showBranchColumn = false,
  readOnly = false,
  orderType = null,
  title = null,
  subtitle = null,
  todayOnly = false,
}) {
  const user = useSelector(selectUser)
  const roles = useSelector(selectUserRoles)
  const t = useT()
  const branchId = user?.branch_id
  const warehouseId = user?.warehouse_id

  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState(defaultStatus || '')
  const [loading, setLoading] = useState(true)

  // عرض "خانة الاستلام" يرى طلبيات الفرع التي في حالة dispatched فقط
  // عرض "التجهيز" يرى التي في حالة approved — عرض "الصرف" يرى picking
  // ويجبر الفلتر — لا يمكن للمستخدم تغييره
  const forcedStatus =
    receiveView ? 'dispatched'
    : pickingView ? 'approved'
    : dispatchView ? 'picking'
    : defaultStatus

  const isWhMgr = roles.includes('warehouse_manager') || roles.includes('admin') || roles.includes('super_admin')
  const isBrMgr = roles.includes('branch_manager') || roles.includes('admin') || roles.includes('super_admin')

  const load = (p = 1) => {
    setLoading(true)
    const effectiveStatus = forcedStatus || status
    const today = new Date().toISOString().slice(0, 10)
    const params = {
      page: p, page_size: 20,
      ...(warehouseView && warehouseId && !scopeAll ? { warehouse_id: warehouseId } : {}),
      ...(!warehouseView && branchId && !scopeAll ? { branch_id: branchId } : {}),
      ...(effectiveStatus ? { status: effectiveStatus } : {}),
      ...(orderType ? { order_type: orderType } : {}),
      ...(todayOnly ? { date_from: today, date_to: today } : {}),
    }
    ordersApi.list(params)
      .then((r) => {
        const data = r?.data || {}
        setItems(Array.isArray(data.items) ? data.items : [])
        setTotal(data.total || 0)
      })
      .catch(() => {
        setItems([])
        setTotal(0)
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    setPage(1)
    load(1)
  }, [status, forcedStatus, warehouseView, scopeAll, orderType, todayOnly, branchId, warehouseId])

  const handleApprove = async (id) => {
    try {
      await ordersApi.approve(id)
      toast.success(t('orders.toast_approved'))
      load()
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('orders.toast_generic_error'))
    }
  }

  const handleSubmitToWH = async (id) => {
    try {
      await ordersApi.submitToWarehouse(id)
      toast.success(t('orders.toast_submitted_to_warehouse'))
      load()
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('orders.toast_generic_error'))
    }
  }

  const handleStartPicking = async (id) => {
    try {
      await ordersApi.startPicking(id)
      toast.success(t('orders.toast_picking_started'))
      load()
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('orders.toast_generic_error'))
    }
  }

  const STATUS_OPTIONS = warehouseView
    ? ['submitted_to_warehouse', 'under_review', 'approved', 'partially_approved', 'picking', 'dispatched']
    : ['system_generated', 'branch_reviewed', 'submitted_to_warehouse', 'under_review', 'approved', 'dispatched', 'received', 'closed']

  if (loading && items.length === 0) return <PageLoader />

  const shouldShowBranch = warehouseView || showBranchColumn
  const colCount = 6 + (shouldShowBranch ? 1 : 0)

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">
          {title || (receiveView ? (t('orders.receive_list_title') || t('nav.receiving'))
            : pickingView ? (t('orders.picking_list_title') || t('nav.warehouse_picking'))
            : dispatchView ? (t('orders.dispatch_list_title') || t('nav.warehouse_dispatch'))
            : warehouseView ? t('orders.warehouse_list_title')
            : t('orders.branch_list_title'))}
        </h1>
        {subtitle && <p className="text-sm text-gray-500 mt-1">{subtitle}</p>}
        {!readOnly && !warehouseView && !receiveView && !pickingView && !dispatchView && (
          <Link to="/orders/exceptional" className="btn-primary">
            <Plus className="w-4 h-4" /> {t('orders.new_exceptional')}
          </Link>
        )}
      </div>

      {/* Filter — في صفحات الاستلام/التجهيز الفلتر مثبت */}
      {!forcedStatus && (
        <div className="flex gap-3 mb-4 flex-wrap">
          <select
            value={status}
            onChange={(e) => { setStatus(e.target.value); setPage(1) }}
            className="input-field w-48"
          >
            <option value="">{t('orders.all_statuses')}</option>
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>{t(`order_status.${s}`)}</option>
            ))}
          </select>
        </div>
      )}

      <div className="card">
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>{t('orders.col_order_no')}</th>
                <th>{t('orders.col_date')}</th>
                {shouldShowBranch && <th>{t('orders.col_branch')}</th>}
                <th>{t('orders.col_type')}</th>
                <th>{t('orders.col_status')}</th>
                <th>{t('orders.col_items_count')}</th>
                <th>{t('orders.col_actions')}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((order) => (
                <tr key={order.id}>
                  <td className="font-mono text-sm font-semibold">{order.order_no}</td>
                  <td>{formatDate(order.order_date)}</td>
                  {shouldShowBranch && (
                    <td className="text-sm">
                      {order.branch_name || order.branch_name_ar || order.branch_id}
                    </td>
                  )}
                  <td>
                    <span className={`status-badge text-xs ${
                      order.order_type === 'exceptional'
                        ? 'bg-orange-100 text-orange-700'
                        : 'bg-blue-100 text-blue-700'
                    }`}>
                      {t(`order_type.${order.order_type}`)}
                    </span>
                  </td>
                  <td><StatusBadge status={order.status} /></td>
                  <td>{order.lines?.length || 0}</td>
                  <td>
                    <div className="flex items-center gap-1.5">
                      <Link
                        to={warehouseView ? `/warehouse/orders/${order.id}` : `/orders/${order.id}`}
                        className="p-1.5 hover:bg-gray-100 rounded-lg"
                        title={t('orders.action_view')}
                      >
                        <Eye className="w-4 h-4 text-gray-500" />
                      </Link>

                      {/* Branch: submit to warehouse */}
                      {!readOnly && !warehouseView && isBrMgr &&
                        ['system_generated', 'branch_reviewed', 'draft'].includes(order.status) && (
                        <button
                          onClick={() => handleSubmitToWH(order.id)}
                          className="p-1.5 hover:bg-blue-50 rounded-lg"
                          title={t('orders.action_submit_to_warehouse')}
                        >
                          <Truck className="w-4 h-4 text-blue-600" />
                        </button>
                      )}

                      {/* Warehouse: approve */}
                      {!readOnly && warehouseView && isWhMgr &&
                        ['under_review', 'submitted_to_warehouse'].includes(order.status) && (
                        <button
                          onClick={() => handleApprove(order.id)}
                          className="p-1.5 hover:bg-green-50 rounded-lg"
                          title={t('orders.action_approve')}
                        >
                          <CheckCircle className="w-4 h-4 text-green-600" />
                        </button>
                      )}

                      {/* Warehouse: start picking */}
                      {!readOnly && warehouseView &&
                        ['approved', 'partially_approved'].includes(order.status) && (
                        <button
                          onClick={() => handleStartPicking(order.id)}
                          className="p-1.5 hover:bg-teal-50 rounded-lg"
                          title={t('orders.action_start_picking')}
                        >
                          <Package className="w-4 h-4 text-teal-600" />
                        </button>
                      )}

                      {/* Branch: receive */}
                      {!readOnly && !warehouseView && order.status === 'dispatched' && (
                        <Link
                          to={`/receiving/${order.id}`}
                          className="p-1.5 hover:bg-purple-50 rounded-lg"
                          title={t('orders.action_receive')}
                        >
                          <Truck className="w-4 h-4 text-purple-600" />
                        </Link>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr>
                  <td colSpan={colCount} className="text-center py-12 text-gray-400">
                    {t('orders.empty')}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <Pagination
          total={total} page={page} pageSize={20}
          onChange={(p) => { setPage(p); load(p) }}
        />
      </div>
    </div>
  )
}
