import React from 'react'
import { Link, useParams } from 'react-router-dom'
import toast from 'react-hot-toast'
import { supplyChainApi } from '../../services/api'

const STATUS_BADGE = {
  DRAFT: 'bg-gray-100 text-gray-700',
  SUBMITTED: 'bg-blue-100 text-blue-700',
  SPLIT: 'bg-indigo-100 text-indigo-700',
  IN_EXECUTION: 'bg-amber-100 text-amber-700',
  DELIVERED: 'bg-green-100 text-green-700',
  AREA_REJECTED: 'bg-red-100 text-red-700',
}

const STATUS_LABEL = {
  DRAFT: 'مسودة',
  SUBMITTED: 'مرسل',
  AREA_APPROVED: 'معتمد',
  AREA_REJECTED: 'مرفوض',
  SPLIT: 'تم التقسيم',
  IN_EXECUTION: 'قيد التنفيذ',
  DELIVERED: 'تم التسليم',
}

function StatusBadge({ status }) {
  return (
    <span className={`status-badge text-xs ${STATUS_BADGE[status] || 'bg-gray-100 text-gray-700'}`}>
      {STATUS_LABEL[status] || status}
    </span>
  )
}

function formatDate(value) {
  if (!value) return '—'
  try {
    return new Date(value).toLocaleString('ar-SA')
  } catch {
    return value
  }
}

export function FulfillmentTable({ lines, compact = false }) {
  if (!lines?.length) {
    return <p className="text-sm text-gray-500">لا توجد بيانات تنفيذ بعد.</p>
  }
  return (
    <div className="overflow-x-auto">
      <table className="table text-sm">
        <thead>
          <tr>
            <th>الصنف</th>
            <th>المطلوب</th>
            <th>المصروف</th>
            <th>المُسلّم</th>
            <th>المتبقي</th>
            {!compact && <th>المسار</th>}
            {!compact && <th>سبب التأخير</th>}
          </tr>
        </thead>
        <tbody>
          {lines.map((line) => (
            <tr key={line.request_line_id || line.item_id}>
              <td>{line.item_name}</td>
              <td>{line.requested_qty}</td>
              <td>{line.issued_qty}</td>
              <td>{line.delivered_qty}</td>
              <td className={Number(line.remaining_qty) > 0 ? 'text-amber-700 font-medium' : ''}>{line.remaining_qty}</td>
              {!compact && <td>{line.route_ar || '—'}</td>}
              {!compact && <td>{line.delay_reason || '—'}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function BranchRequestDetailPage() {
  const { id: requestId } = useParams()
  const [loading, setLoading] = React.useState(true)
  const [detail, setDetail] = React.useState(null)

  React.useEffect(() => {
    let mounted = true
    ;(async () => {
      try {
        const res = await supplyChainApi.getBranchRequestDetail(requestId)
        if (mounted) setDetail(res.data)
      } catch (error) {
        toast.error(error?.response?.data?.message || 'تعذر تحميل تفاصيل الطلب')
      } finally {
        if (mounted) setLoading(false)
      }
    })()
    return () => { mounted = false }
  }, [requestId])

  if (loading) {
    return <div className="p-6 text-center text-gray-400">جارٍ التحميل...</div>
  }

  if (!detail) {
    return (
      <div className="p-6 space-y-4">
        <p className="text-red-600">تعذر عرض الطلب.</p>
        <Link to="/supply-chain/branch-requests" className="btn-secondary inline-block">رجوع</Link>
      </div>
    )
  }

  const { request, branch_name, timeline, fulfillment_lines, status_summary, timeline_gaps } = detail

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{request.request_no}</h1>
          <p className="text-sm text-gray-500 mt-1">{branch_name} — {request.brand_name_snapshot || ''}</p>
        </div>
        <div className="flex gap-2 items-center">
          <StatusBadge status={request.status} />
          <Link to="/supply-chain/branch-requests" className="btn-secondary">رجوع للقائمة</Link>
        </div>
      </div>

      <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-4">
        <div className="card p-4">
          <div className="text-xs text-gray-500">الحالة الحالية</div>
          <div className="font-semibold mt-1">{status_summary.current_status_ar}</div>
        </div>
        <div className="card p-4">
          <div className="text-xs text-gray-500">المسؤول الآن</div>
          <div className="font-semibold mt-1">{status_summary.current_owner_ar}</div>
        </div>
        <div className="card p-4">
          <div className="text-xs text-gray-500">الإجراء التالي</div>
          <div className="font-semibold mt-1">{status_summary.next_action_ar}</div>
        </div>
        <div className="card p-4">
          <div className="text-xs text-gray-500">آخر تحديث</div>
          <div className="font-semibold mt-1">{formatDate(status_summary.last_updated_at)}</div>
        </div>
      </div>

      <div className="card p-5 space-y-3">
        <h2 className="font-semibold text-gray-900">أين الكمية المتبقية؟</h2>
        <FulfillmentTable lines={fulfillment_lines} />
      </div>

      <div className="card p-5 space-y-4">
        <h2 className="font-semibold text-gray-900">سجل مسار الطلب</h2>
        {timeline?.length ? (
          <ol className="space-y-3 border-r-2 border-blue-100 pr-4">
            {timeline.map((ev, idx) => (
              <li key={`${ev.key}-${idx}`} className="relative">
                <div className="font-medium text-gray-900">{ev.label_ar}</div>
                <div className="text-xs text-gray-500 mt-0.5">{formatDate(ev.at)}{ev.owner_role_ar ? ` — ${ev.owner_role_ar}` : ''}</div>
                {ev.detail && <div className="text-sm text-gray-600 mt-1">{ev.detail}</div>}
              </li>
            ))}
          </ol>
        ) : (
          <p className="text-sm text-gray-500">لا توجد أحداث مسجلة بعد.</p>
        )}
        {timeline_gaps?.length > 0 && (
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
            <div className="font-medium mb-1">فجوات في السجل:</div>
            <ul className="list-disc list-inside">
              {timeline_gaps.map((gap) => <li key={gap}>{gap}</li>)}
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}

export default BranchRequestDetailPage
