import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { CheckCircle, XCircle, Truck, Package, ArrowLeft, MessageSquare, AlertTriangle, ClipboardCheck, PackageCheck } from 'lucide-react'
import toast from 'react-hot-toast'
import { ordersApi } from '../../services/api'
import { selectUserRoles } from '../../store'
import { StatusBadge, PageLoader, Modal } from '../../components/common'
import { formatDate, formatQty, ORDER_TYPE_LABELS } from '../../utils/helpers'
import { useT, useLanguage } from '../../i18n'
import InlineAuditFindingsPanel from '../../components/audit/InlineAuditFindingsPanel'

export default function OrderDetailPage({ warehouseView = false }) {
  const { id } = useParams()
  const navigate = useNavigate()
  const roles = useSelector(selectUserRoles)
  const t = useT()
  const { lang } = useLanguage()
  const tf = (key, fallback) => {
    const value = t(key)
    return value === key ? fallback : value
  }
  const apiErrorMessage = (err, fallback) => {
    const data = err?.response?.data
    if (data?.message) return data.message
    if (typeof data?.detail === 'string') return data.detail
    return fallback
  }
  const nameOf = (obj, base) => obj?.[`${base}_${lang}`] || obj?.[`${base}_ar`] || obj?.[base] || ''
  const [order, setOrder] = useState(null)
  const [loading, setLoading] = useState(true)
  const [lineEdits, setLineEdits] = useState({}) // line_id -> wh_approved_qty
  const [branchQtyEdits, setBranchQtyEdits] = useState({})
  const [dispatchQtys, setDispatchQtys] = useState({})
  const [rejectReason, setRejectReason] = useState('')
  const [showRejectModal, setShowRejectModal] = useState(false)
  const [saving, setSaving] = useState(false)
  // H13: area manager review state
  const [showAreaReviewModal, setShowAreaReviewModal] = useState(false)
  const [areaReviewNotes, setAreaReviewNotes] = useState('')

  const isWhMgr = roles.includes('warehouse_manager') || roles.includes('admin') || roles.includes('super_admin')
  const isWhUser = roles.includes('warehouse_user') || isWhMgr
  const isBrMgr = roles.includes('branch_manager') || roles.includes('admin') || roles.includes('super_admin')
  // H13: split workflow by role — area manager and branch user need their own permissions
  const isAreaMgr = roles.includes('area_manager') || roles.includes('admin') || roles.includes('super_admin')
  const isBrUser = roles.includes('branch_user') || isBrMgr

  const load = () => {
    ordersApi.get(id).then((r) => {
      setOrder(r.data)
      // init line edits
      const edits = {}
      const branchEdits = {}
      const dispatches = {}
      r.data.lines?.forEach((l) => {
        edits[l.id] = l.wh_approved_qty
        branchEdits[l.id] = l.branch_requested_qty
        dispatches[l.id] = l.wh_approved_qty
      })
      setLineEdits(edits)
      setBranchQtyEdits(branchEdits)
      setDispatchQtys(dispatches)
    }).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [id])

  const handleWarehouseReview = async () => {
    setSaving(true)
    try {
      await ordersApi.warehouseReview(id, {
        lines: order.lines.map((l) => ({
          line_id: l.id,
          wh_approved_qty: parseFloat(lineEdits[l.id]) || 0,
        }))
      })
      toast.success(t('orders.toast_review_saved'))
      load()
    } catch (err) {
      toast.error(apiErrorMessage(err, t('orders.toast_generic_error')))
    } finally {
      setSaving(false)
    }
  }

  const handleBranchReview = async () => {
    setSaving(true)
    try {
      await ordersApi.branchReview(id, {
        lines: order.lines.map((l) => ({
          line_id: l.id,
          branch_requested_qty: parseFloat(branchQtyEdits[l.id]) || 0,
        })),
      })
      toast.success('تم حفظ كميات الفرع')
      load()
    } catch (err) {
      toast.error(apiErrorMessage(err, t('orders.toast_generic_error')))
    } finally {
      setSaving(false)
    }
  }

  const handleApprove = async () => {
    try {
      await ordersApi.approve(id)
      toast.success(t('orders.toast_approved'))
      load()
    } catch (err) {
      toast.error(apiErrorMessage(err, t('orders.toast_generic_error')))
    }
  }

  const handleStartPicking = async () => {
    try {
      await ordersApi.startPicking(id)
      toast.success(t('orders.toast_picking_started'))
      load()
    } catch (err) {
      toast.error(apiErrorMessage(err, t('orders.toast_generic_error')))
    }
  }

  const handleDispatch = async () => {
    setSaving(true)
    try {
      await ordersApi.dispatch(id, {
        lines: order.lines.map((l) => ({
          line_id: l.id,
          dispatched_qty: parseFloat(dispatchQtys[l.id]) || 0,
        })),
        dispatch_note_no: `DN-${order.order_no}`,
      })
      toast.success(t('orders.toast_order_dispatched'))
      load()
    } catch (err) {
      toast.error(apiErrorMessage(err, t('orders.toast_generic_error')))
    } finally {
      setSaving(false)
    }
  }

  const handleReject = async () => {
    if (!rejectReason) { toast.error(t('orders.reject_reason_required')); return }
    try {
      await ordersApi.reject(id, rejectReason)
      toast.success(t('orders.toast_order_rejected'))
      setShowRejectModal(false)
      load()
    } catch (err) {
      toast.error(apiErrorMessage(err, t('orders.toast_generic_error')))
    }
  }

  const handleSubmitToWarehouse = async () => {
    try {
      if (canBranchEdit) {
        await ordersApi.branchReview(id, {
          lines: order.lines.map((l) => ({
            line_id: l.id,
            branch_requested_qty: parseFloat(branchQtyEdits[l.id]) || 0,
          })),
        })
      }
      await ordersApi.submitToWarehouse(id)
      toast.success(t('orders.toast_submitted_to_warehouse'))
      load()
    } catch (err) {
      toast.error(apiErrorMessage(err, t('orders.toast_generic_error')))
    }
  }

  // H13: area manager reviews the order (system_generated / branch_reviewed → area_manager_review)
  const handleAreaReview = async () => {
    setSaving(true)
    try {
      const line_notes = {}
      order.lines?.forEach((l) => {
        if (l.notes) line_notes[l.id] = l.notes
      })
      await ordersApi.areaReview(id, {
        notes: areaReviewNotes || undefined,
        line_notes,
      })
      toast.success(t('orders.toast_area_reviewed') || 'تمت مراجعة الطلبية')
      setShowAreaReviewModal(false)
      setAreaReviewNotes('')
      load()
    } catch (err) {
      toast.error(apiErrorMessage(err, t('orders.toast_generic_error')))
    } finally {
      setSaving(false)
    }
  }

  // H13: branch user/manager receives dispatched order — navigate to dedicated receiving page
  const handleGoToReceive = () => {
    navigate(`/receiving/${id}`)
  }

  if (loading) return <PageLoader />
  if (!order) return <div className="p-6 text-red-600">{t('orders.order_not_found')}</div>

  const canWHReview = isWhUser && ['submitted_to_warehouse', 'under_review'].includes(order.status)
  const canApprove = isWhMgr && ['under_review', 'submitted_to_warehouse'].includes(order.status)
  const canPick = isWhUser && ['approved', 'partially_approved'].includes(order.status)
  const canDispatch = isWhUser && order.status === 'picking'
  // H13: submit-to-warehouse now also available to area managers after area_manager_review
  const canSubmitToWH = (isBrMgr || isAreaMgr) && ['system_generated', 'branch_reviewed', 'area_manager_review', 'draft'].includes(order.status)
  const canBranchEdit = !warehouseView && isBrMgr && ['system_generated', 'branch_reviewed', 'area_manager_review', 'draft'].includes(order.status)
  // H13: area manager gets a review action on system_generated / branch_reviewed orders
  const canAreaReview = isAreaMgr && ['system_generated', 'branch_reviewed'].includes(order.status)
  // H13: branch user/manager can confirm receipt of a dispatched order
  const canReceive = (isBrUser || isBrMgr) && order.status === 'dispatched'
  const showWHQtyEdit = canWHReview
  const showDispatchQtyEdit = canDispatch
  const hasActions = canBranchEdit || canAreaReview || canSubmitToWH || canReceive || canWHReview || canApprove || canPick || canDispatch
  const warehouseWaitingForBranchReceipt = warehouseView && isWhUser && order.status === 'dispatched'

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center gap-4 mb-6">
        <button
          onClick={() => navigate(-1)}
          className="p-2 hover:bg-gray-100 rounded-lg"
        >
          <ArrowLeft className="w-5 h-5 text-gray-600" />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-900">{order.order_no}</h1>
            <StatusBadge status={order.status} />
            <span className={`status-badge text-xs ${
              order.order_type === 'exceptional' ? 'bg-orange-100 text-orange-700' : 'bg-blue-100 text-blue-700'
            }`}>
              {t(`order_type.${order.order_type}`)}
            </span>
          </div>
          <p className="text-gray-500 text-sm mt-1">{formatDate(order.order_date)}</p>
        </div>

        {/* Action buttons */}
        <div className="flex gap-2 flex-wrap">
          {canAreaReview && (
            <button onClick={() => setShowAreaReviewModal(true)} className="btn-primary">
              <ClipboardCheck className="w-4 h-4" /> {t('orders.action_area_review') || 'مراجعة مدير المنطقة'}
            </button>
          )}
          {canSubmitToWH && (
            <button onClick={handleSubmitToWarehouse} className="btn-primary">
              <Truck className="w-4 h-4" /> {t('orders.action_submit_to_warehouse')}
            </button>
          )}
          {canBranchEdit && (
            <button onClick={handleBranchReview} disabled={saving} className="btn-secondary">
              {saving ? t('orders.action_saving') : 'حفظ تعديل الكميات'}
            </button>
          )}
          {canReceive && (
            <button onClick={handleGoToReceive} className="btn-success">
              <PackageCheck className="w-4 h-4" /> {t('orders.action_receive') || 'استلام الطلبية'}
            </button>
          )}
          {canWHReview && (
            <button onClick={handleWarehouseReview} disabled={saving} className="btn-secondary">
              {saving ? t('orders.action_saving') : t('orders.action_save_review')}
            </button>
          )}
          {canApprove && (
            <button onClick={handleApprove} className="btn-success">
              <CheckCircle className="w-4 h-4" /> {t('orders.action_approve_short')}
            </button>
          )}
          {canApprove && (
            <button onClick={() => setShowRejectModal(true)} className="btn-danger">
              <XCircle className="w-4 h-4" /> {t('orders.action_reject_short')}
            </button>
          )}
          {canPick && (
            <button onClick={handleStartPicking} className="btn-primary">
              <Package className="w-4 h-4" /> {t('orders.action_start_picking_short')}
            </button>
          )}
          {canDispatch && (
            <button onClick={handleDispatch} disabled={saving} className="btn-primary">
              <Truck className="w-4 h-4" /> {saving ? t('orders.action_dispatching') : t('orders.action_dispatch_cta')}
            </button>
          )}
          {!hasActions && warehouseWaitingForBranchReceipt && (
            <div className="flex items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-800">
              <PackageCheck className="w-4 h-4" />
              <span>{tf('orders.waiting_branch_receipt', 'تم الصرف، والطلب الآن بانتظار استلام الفرع')}</span>
            </div>
          )}
        </div>
      </div>

      {/* Order-level notes & rejection reason — مهم لمدير المنطقة والمستودع يشوفوها */}
      {(order.notes || order.rejection_reason) && (
        <div className="mb-4 space-y-3">
          {order.notes && (
            <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 flex gap-3">
              <MessageSquare className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="text-sm font-semibold text-blue-900 mb-1">
                  {t('orders.notes_from_branch') || 'ملاحظات من الفرع'}
                </p>
                <p className="text-sm text-blue-800 whitespace-pre-wrap">{order.notes}</p>
              </div>
            </div>
          )}
          {order.rejection_reason && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex gap-3">
              <AlertTriangle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="text-sm font-semibold text-red-900 mb-1">
                  {t('orders.rejection_reason_label') || 'سبب الرفض'}
                </p>
                <p className="text-sm text-red-800 whitespace-pre-wrap">{order.rejection_reason}</p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Lines table */}
      <div className="card">
        <div className="card-header">
          <h2 className="font-semibold">{t('orders.lines_header', { count: order.lines?.length || 0 })}</h2>
        </div>
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>{t('orders.col_item')}</th>
                <th>{t('orders.col_unit')}</th>
                <th>{t('orders.col_suggested')}</th>
                <th>{t('orders.col_branch_requested')}</th>
                {warehouseView && <th>{t('orders.col_wh_approved')}</th>}
                {warehouseView && <th>{t('orders.col_dispatched')}</th>}
                {!warehouseView && <th>{t('orders.col_approved')}</th>}
                {!warehouseView && <th>{t('orders.col_dispatched')}</th>}
                {!warehouseView && <th>{t('orders.col_received')}</th>}
                <th>{t('orders.col_line_status')}</th>
                {order.status === 'picking' && <th>{t('orders.col_dispatch_qty')}</th>}
                {canWHReview && <th>{t('orders.col_approval_qty')}</th>}
              </tr>
            </thead>
            <tbody>
              {order.lines?.map((line) => (
                <tr key={line.id} className={line.shortage_flag ? 'bg-red-50' : ''}>
                  <td>
                    <div>
                      <p className="font-medium text-sm">{nameOf(line, 'item_name')}</p>
                      <p className="text-xs text-gray-400">{line.item_code}</p>
                      {line.notes && (
                        <div className="mt-1.5 flex items-start gap-1.5 text-xs text-blue-700 bg-blue-50 border border-blue-100 rounded px-2 py-1">
                          <MessageSquare className="w-3 h-3 flex-shrink-0 mt-0.5" />
                          <span className="whitespace-pre-wrap break-words">{line.notes}</span>
                        </div>
                      )}
                      {line.rejection_reason && (
                        <div className="mt-1.5 flex items-start gap-1.5 text-xs text-red-700 bg-red-50 border border-red-100 rounded px-2 py-1">
                          <AlertTriangle className="w-3 h-3 flex-shrink-0 mt-0.5" />
                          <span className="whitespace-pre-wrap break-words">{line.rejection_reason}</span>
                        </div>
                      )}
                    </div>
                  </td>
                  <td className="text-xs text-gray-500">{line.unit}</td>
                  <td className="text-center">{formatQty(line.suggested_qty)}</td>
                  <td className="text-center font-medium">
                    {canBranchEdit ? (
                      <input
                        type="number"
                        min="0"
                        step="0.5"
                        value={branchQtyEdits[line.id] ?? line.branch_requested_qty}
                        onChange={(e) => setBranchQtyEdits((p) => ({ ...p, [line.id]: e.target.value }))}
                        className="w-20 border border-gray-300 rounded px-2 py-1 text-sm text-center"
                      />
                    ) : (
                      formatQty(line.branch_requested_qty)
                    )}
                  </td>

                  {warehouseView && (
                    <td className="text-center">
                      {showWHQtyEdit ? (
                        <input
                          type="number" min="0"
                          value={lineEdits[line.id] ?? line.wh_approved_qty}
                          onChange={(e) => setLineEdits((p) => ({ ...p, [line.id]: e.target.value }))}
                          className="w-20 border border-gray-300 rounded px-2 py-1 text-sm text-center"
                        />
                      ) : (
                        <span className={line.wh_approved_qty < line.branch_requested_qty ? 'text-orange-600 font-semibold' : ''}>
                          {formatQty(line.wh_approved_qty)}
                        </span>
                      )}
                    </td>
                  )}
                  {warehouseView && (
                    <td className="text-center">
                      {showDispatchQtyEdit ? (
                        <input
                          type="number" min="0"
                          value={dispatchQtys[line.id] ?? line.wh_approved_qty}
                          onChange={(e) => setDispatchQtys((p) => ({ ...p, [line.id]: e.target.value }))}
                          className="w-20 border border-gray-300 rounded px-2 py-1 text-sm text-center"
                        />
                      ) : (
                        <span>{formatQty(line.dispatched_qty)}</span>
                      )}
                    </td>
                  )}

                  {!warehouseView && <td className="text-center">{formatQty(line.wh_approved_qty)}</td>}
                  {!warehouseView && <td className="text-center">{formatQty(line.dispatched_qty)}</td>}
                  {!warehouseView && <td className="text-center">{formatQty(line.received_qty)}</td>}

                  <td>
                    <span className={`status-badge text-xs ${
                      line.line_status === 'rejected' ? 'bg-red-100 text-red-700' :
                      line.line_status === 'received' ? 'bg-green-100 text-green-700' :
                      line.line_status === 'dispatched' ? 'bg-blue-100 text-blue-700' :
                      line.shortage_flag ? 'bg-orange-100 text-orange-700' :
                      'bg-gray-100 text-gray-600'
                    }`}>
                      {t(`orders.line_status_${line.line_status}`) || line.line_status}
                    </span>
                  </td>

                  {(order.status === 'picking' || canWHReview) && (
                    <td />
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <InlineAuditFindingsPanel
        entityType="replenishment_order"
        entityId={order.id}
        title="ملاحظات المراجعة على الطلبية"
      />

      {/* Reject modal */}
      <Modal open={showRejectModal} onClose={() => setShowRejectModal(false)} title={t('orders.reject_modal_title')}>
        <textarea
          value={rejectReason}
          onChange={(e) => setRejectReason(e.target.value)}
          className="input-field min-h-24"
          placeholder={t('orders.reject_reason_placeholder')}
        />
        <div className="flex gap-3 mt-4 justify-end">
          <button onClick={() => setShowRejectModal(false)} className="btn-secondary">{t('common.cancel')}</button>
          <button onClick={handleReject} className="btn-danger">{t('orders.action_reject_short')}</button>
        </div>
      </Modal>

      {/* H13: area-review modal */}
      <Modal open={showAreaReviewModal} onClose={() => setShowAreaReviewModal(false)} title={t('orders.area_review_modal_title') || 'مراجعة مدير المنطقة'}>
        <p className="text-sm text-gray-600 mb-3">
          {t('orders.area_review_modal_hint') || 'أضف ملاحظات على الطلبية قبل إرسالها للمستودع (اختياري).'}
        </p>
        <textarea
          value={areaReviewNotes}
          onChange={(e) => setAreaReviewNotes(e.target.value)}
          className="input-field min-h-24"
          placeholder={t('orders.area_review_notes_placeholder') || 'ملاحظات المراجعة...'}
        />
        <div className="flex gap-3 mt-4 justify-end">
          <button onClick={() => setShowAreaReviewModal(false)} className="btn-secondary">{t('common.cancel')}</button>
          <button onClick={handleAreaReview} disabled={saving} className="btn-primary">
            {saving ? (t('orders.action_saving') || 'جاري الحفظ...') : (t('orders.action_area_review_confirm') || 'تأكيد المراجعة')}
          </button>
        </div>
      </Modal>
    </div>
  )
}
