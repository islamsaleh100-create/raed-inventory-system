import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { CheckCircle, ArrowLeft } from 'lucide-react'
import toast from 'react-hot-toast'
import { ordersApi, masterApi } from '../../services/api'
import { selectUser } from '../../store'
import { PageLoader, StatusBadge } from '../../components/common'
import { formatQty, formatDate } from '../../utils/helpers'
import { useT, useLanguage } from '../../i18n'

export default function ReceivingPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const user = useSelector(selectUser)
  const t = useT()
  const { lang } = useLanguage()
  const nameOf = (obj, base) => obj?.[`${base}_${lang}`] || obj?.[`${base}_ar`] || obj?.[base] || ''
  const [order, setOrder] = useState(null)
  const [loading, setLoading] = useState(true)
  const [receiveData, setReceiveData] = useState({}) // { line_id: {received_qty, damaged_qty, missing_qty, notes} }
  const [reasons, setReasons] = useState([])
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    Promise.all([
      ordersApi.get(id),
      masterApi.listReceivingVarianceReasons(),
    ]).then(([o, r]) => {
      setOrder(o.data)
      setReasons(r.data || [])
      const data = {}
      o.data.lines?.forEach((l) => {
        data[l.id] = {
          received_qty: l.dispatched_qty,
          damaged_qty: 0,
          missing_qty: 0,
          notes: '',
          receiving_variance_reason_id: '',
        }
      })
      setReceiveData(data)
    }).finally(() => setLoading(false))
  }, [id])

  const updateLine = (lineId, field, value) => {
    setReceiveData((prev) => ({
      ...prev,
      [lineId]: { ...prev[lineId], [field]: value }
    }))
  }

  const handleConfirm = async () => {
    setSubmitting(true)
    try {
      await ordersApi.receive(id, {
        lines: order.lines.map((l) => {
          const d = receiveData[l.id] || {}
          return {
            line_id: l.id,
            received_qty: parseFloat(d.received_qty) || 0,
            damaged_qty: parseFloat(d.damaged_qty) || 0,
            missing_qty: parseFloat(d.missing_qty) || 0,
            receiving_variance_reason_id: d.receiving_variance_reason_id || null,
            notes: d.notes || null,
          }
        }),
        notes: t('receiving.confirmation_note', { name: user?.full_name || '' }),
      })
      toast.success(t('receiving.confirmed_toast'))
      navigate('/orders')
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('receiving.confirm_error_toast'))
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <PageLoader />
  if (!order) return <div className="p-6 text-red-600">{t('receiving.order_not_found')}</div>
  if (order.status !== 'dispatched') {
    return (
      <div className="p-6">
        <div className="card p-8 text-center">
          <p className="text-gray-500">
            {t('receiving.order_in_status')} <StatusBadge status={order.status} />
          </p>
          <p className="text-sm text-gray-400 mt-2">{t('receiving.cannot_receive_unless_dispatched')}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6">
      <div className="flex items-center gap-4 mb-6">
        <button onClick={() => navigate(-1)} className="p-2 hover:bg-gray-100 rounded-lg">
          <ArrowLeft className="w-5 h-5 text-gray-600" />
        </button>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            {t('receiving.page_title')}
          </h1>
          <p className="text-gray-500 text-sm mt-1">
            {order.order_no} — {formatDate(order.order_date)}
          </p>
        </div>
      </div>

      <div className="card mb-6">
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>{t('receiving.col_item')}</th>
                <th>{t('receiving.col_dispatched')}</th>
                <th className="w-28">{t('receiving.col_received')}</th>
                <th className="w-24">{t('receiving.col_damaged')}</th>
                <th className="w-24">{t('receiving.col_missing')}</th>
                <th className="w-40">{t('receiving.col_variance_reason')}</th>
                <th>{t('common.notes')}</th>
              </tr>
            </thead>
            <tbody>
              {order.lines?.map((line) => {
                const d = receiveData[line.id] || {}
                const received = parseFloat(d.received_qty) || 0
                const dispatched = parseFloat(line.dispatched_qty) || 0
                const hasVariance = received !== dispatched

                return (
                  <tr key={line.id} className={hasVariance ? 'bg-yellow-50' : ''}>
                    <td>
                      <p className="font-medium text-sm">{nameOf(line, 'item_name')}</p>
                      <p className="text-xs text-gray-400">{line.item_code}</p>
                    </td>
                    <td className="text-center font-semibold">{formatQty(line.dispatched_qty)}</td>
                    <td>
                      <input
                        type="number" min="0" step="0.01"
                        value={d.received_qty ?? line.dispatched_qty}
                        onChange={(e) => updateLine(line.id, 'received_qty', e.target.value)}
                        className={`w-full border rounded px-2 py-1 text-sm text-center
                          ${hasVariance ? 'border-yellow-400 bg-yellow-50' : 'border-gray-300'}`}
                      />
                    </td>
                    <td>
                      <input
                        type="number" min="0" step="0.01"
                        value={d.damaged_qty || 0}
                        onChange={(e) => updateLine(line.id, 'damaged_qty', e.target.value)}
                        className="w-full border border-gray-300 rounded px-2 py-1 text-sm text-center"
                      />
                    </td>
                    <td>
                      <input
                        type="number" min="0" step="0.01"
                        value={d.missing_qty || 0}
                        onChange={(e) => updateLine(line.id, 'missing_qty', e.target.value)}
                        className="w-full border border-gray-300 rounded px-2 py-1 text-sm text-center"
                      />
                    </td>
                    <td>
                      <select
                        value={d.receiving_variance_reason_id || ''}
                        onChange={(e) => updateLine(line.id, 'receiving_variance_reason_id', e.target.value)}
                        className="input-field text-xs py-1"
                      >
                        <option value="">—</option>
                        {reasons.map((r) => (
                          <option key={r.id} value={r.id}>{nameOf(r, 'reason')}</option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <input
                        type="text"
                        value={d.notes || ''}
                        onChange={(e) => updateLine(line.id, 'notes', e.target.value)}
                        className="input-field text-xs py-1"
                        placeholder={t('receiving.note_placeholder')}
                      />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div className="flex justify-end">
        <button
          onClick={handleConfirm}
          disabled={submitting}
          className="btn-success text-base px-8 py-3"
        >
          <CheckCircle className="w-5 h-5" />
          {submitting ? t('receiving.confirming') : t('receiving.confirm_cta')}
        </button>
      </div>
    </div>
  )
}
