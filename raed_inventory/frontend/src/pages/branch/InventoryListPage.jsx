// InventoryListPage.jsx
import React, { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { Plus, Eye, CheckCircle, XCircle } from 'lucide-react'
import toast from 'react-hot-toast'
import { inventoryApi } from '../../services/api'
import { selectUser, selectUserRoles } from '../../store'
import { StatusBadge, PageLoader, Pagination, ConfirmDialog } from '../../components/common'
import { formatDate, todayString } from '../../utils/helpers'
import { useT } from '../../i18n'

export function InventoryListPage() {
  const t = useT()
  const user = useSelector(selectUser)
  const roles = useSelector(selectUserRoles)
  const branchId = user?.branch_id
  const isMgr = roles.includes('branch_manager') || roles.includes('admin') || roles.includes('super_admin')

  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [rejectModal, setRejectModal] = useState(null)
  const [rejectReason, setRejectReason] = useState('')

  const load = (p = 1) => {
    setLoading(true)
    inventoryApi.list({ branch_id: branchId, page: p, page_size: 20 })
      .then((r) => { setItems(r.data.items); setTotal(r.data.total) })
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const handleApprove = async (id) => {
    try {
      await inventoryApi.approve(id)
      toast.success(t('inventory.approved_with_order_toast'))
      load()
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('common.error_generic'))
    }
  }

  const handleReject = async () => {
    if (!rejectReason) { toast.error(t('inventory.reason_required_toast')); return }
    try {
      await inventoryApi.reject(rejectModal, rejectReason)
      toast.success(t('inventory.rejected_success_toast'))
      setRejectModal(null); setRejectReason('')
      load()
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('common.error_generic'))
    }
  }

  if (loading && items.length === 0) return <PageLoader />

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{t('nav.daily_inventory')}</h1>
        <Link to="/inventory/new" className="btn-primary">
          <Plus className="w-4 h-4" /> {t('inventory.new')}
        </Link>
      </div>

      <div className="card">
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>{t('common.date')}</th>
                <th>{t('inventory.branch')}</th>
                <th>{t('inventory.col_type') || 'النوع'}</th>
                <th>{t('common.status')}</th>
                <th>{t('inventory.line_count')}</th>
                <th>{t('inventory.submitted_at')}</th>
                <th>{t('common.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((inv) => (
                <tr key={inv.id}>
                  <td className="font-medium">{formatDate(inv.inventory_date)}</td>
                  <td>{inv.branch?.branch_name || branchId}</td>
                  <td>
                    <span className="status-badge bg-gray-100 text-gray-700 text-xs">
                      {t(`inventory.type_${inv.inventory_type || 'daily'}`) || inv.inventory_type || 'daily'}
                    </span>
                  </td>
                  <td>
                    <div className="flex items-center gap-2 flex-wrap">
                      <StatusBadge status={inv.status} />
                      {/* H8: flag surplus inventories so warehouse can investigate */}
                      {inv.surplus_lines_count > 0 && (
                        <span
                          className="status-badge bg-purple-100 text-purple-700 text-[10px]"
                          title={t('inventory.surplus_hint') || ''}
                        >
                          {t('inventory.surplus_badge') || 'زيادة'} · {inv.surplus_lines_count}
                        </span>
                      )}
                    </div>
                  </td>
                  <td>{inv.line_count ?? inv.lines?.length ?? '-'}</td>
                  <td>{formatDate(inv.submitted_at)}</td>
                  <td>
                    <div className="flex items-center gap-2">
                      <Link to={`/inventory/${inv.id}`} className="p-1.5 hover:bg-gray-100 rounded-lg">
                        <Eye className="w-4 h-4 text-gray-500" />
                      </Link>
                      {isMgr && inv.status === 'submitted' && (
                        <>
                          <button
                            onClick={() => handleApprove(inv.id)}
                            className="p-1.5 hover:bg-green-50 rounded-lg"
                            title={t('common.approve')}
                          >
                            <CheckCircle className="w-4 h-4 text-green-600" />
                          </button>
                          <button
                            onClick={() => { setRejectModal(inv.id); setRejectReason('') }}
                            className="p-1.5 hover:bg-red-50 rounded-lg"
                            title={t('common.reject')}
                          >
                            <XCircle className="w-4 h-4 text-red-600" />
                          </button>
                        </>
                      )}
                      {inv.status === 'draft' && (
                        <Link to={`/inventory/new`} className="text-xs text-primary-600 hover:underline">
                          {t('common.edit')}
                        </Link>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Pagination total={total} page={page} pageSize={20} onChange={(p) => { setPage(p); load(p) }} />
      </div>

      {/* Reject modal */}
      {rejectModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/50" onClick={() => setRejectModal(null)} />
          <div className="relative bg-white rounded-xl p-6 w-full max-w-md">
            <h3 className="font-semibold text-gray-900 mb-3">{t('inventory.reject_title')}</h3>
            <textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              className="input-field min-h-24"
              placeholder={t('inventory.reject_placeholder')}
            />
            <div className="flex gap-3 mt-4 justify-end">
              <button onClick={() => setRejectModal(null)} className="btn-secondary">{t('common.cancel')}</button>
              <button onClick={handleReject} className="btn-danger">{t('inventory.reject_cta')}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
