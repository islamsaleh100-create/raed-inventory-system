/**
 * G5 / G6 / G7 Analytics Dashboards.
 *   G5 — Daily consumption trend per branch
 *   G6 — Order-to-receive delay analytics
 *   G7 — Branches with most open corrective actions
 *
 * All three are read-only dashboards; data comes from the backend.
 */
import React from 'react'
import toast from 'react-hot-toast'
import { dashboardApi, masterApi } from '../../services/api'
import { useT, useLanguage } from '../../i18n'
import { PageLoader } from '../../components/common'


// ══════════════════════════════════════════════════════════════════════════
// G5 — Daily consumption trend per branch
// ══════════════════════════════════════════════════════════════════════════
export function ConsumptionTrendPage() {
  const t = useT()
  const { lang } = useLanguage()
  const [branches, setBranches] = React.useState([])
  const [branchId, setBranchId] = React.useState('')
  const [days, setDays] = React.useState(30)
  const [data, setData] = React.useState(null)
  const [loading, setLoading] = React.useState(false)

  React.useEffect(() => {
    masterApi.listBranches({ active_only: true })
      .then((r) => {
        setBranches(r.data || [])
        if ((r.data || []).length > 0 && !branchId) setBranchId(r.data[0].id)
      })
      .catch(() => toast.error(t('common.error_generic')))
  }, [])

  const load = React.useCallback(async () => {
    if (!branchId) return
    setLoading(true)
    try {
      const r = await dashboardApi.branchConsumptionTrend(branchId, days)
      setData(r.data)
    } catch (e) {
      toast.error(e?.response?.data?.detail || t('common.error_generic'))
      setData(null)
    } finally {
      setLoading(false)
    }
  }, [branchId, days, t])

  React.useEffect(() => { load() }, [load])

  // Simple SVG bar chart (no external chart lib dependency)
  const renderChart = () => {
    if (!data?.trend?.length) return null
    const max = Math.max(...data.trend.map(p => p.consumed_qty), 1)
    const barW = 100 / data.trend.length
    return (
      <svg viewBox="0 0 100 40" preserveAspectRatio="none" className="w-full h-48 bg-gray-50 rounded">
        {data.trend.map((p, i) => {
          const h = (p.consumed_qty / max) * 38
          return (
            <rect
              key={p.date}
              x={i * barW + 0.2}
              y={40 - h}
              width={Math.max(barW - 0.4, 0.1)}
              height={h}
              fill="#3b82f6"
            >
              <title>{p.date}: {p.consumed_qty}</title>
            </rect>
          )
        })}
      </svg>
    )
  }

  const branchName = (b) => b[`branch_name_${lang}`] || b.branch_name || b.branch_code

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-gray-900 mb-4">
        {t('analytics.consumption_trend_title') || 'اتجاه الاستهلاك اليومي'}
      </h1>
      <p className="text-sm text-gray-500 mb-4">
        {t('analytics.consumption_trend_desc') ||
          'الكمية المستهلكة يومياً في الفرع (من تسويات الجرد). اختر الفرع والفترة.'}
      </p>

      <div className="card p-4 mb-4 flex gap-3 items-end flex-wrap">
        <div>
          <label className="label">{t('common.branch') || 'الفرع'}</label>
          <select className="input-field" value={branchId} onChange={(e) => setBranchId(e.target.value)}>
            {branches.map(b => <option key={b.id} value={b.id}>{branchName(b)}</option>)}
          </select>
        </div>
        <div>
          <label className="label">{t('analytics.days_window') || 'عدد الأيام'}</label>
          <select className="input-field" value={days} onChange={(e) => setDays(Number(e.target.value))}>
            <option value={7}>7</option>
            <option value={14}>14</option>
            <option value={30}>30</option>
            <option value={60}>60</option>
            <option value={90}>90</option>
          </select>
        </div>
      </div>

      {loading ? (
        <PageLoader />
      ) : !data ? (
        <div className="card p-8 text-center text-gray-500">{t('common.no_data')}</div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            <div className="card p-4">
              <div className="text-xs text-gray-500">{t('analytics.total_consumed') || 'إجمالي المستهلك'}</div>
              <div className="text-2xl font-bold text-blue-600">{data.total_consumed}</div>
            </div>
            <div className="card p-4">
              <div className="text-xs text-gray-500">{t('analytics.avg_daily') || 'المعدل اليومي'}</div>
              <div className="text-2xl font-bold text-green-600">{data.avg_daily}</div>
            </div>
            <div className="card p-4">
              <div className="text-xs text-gray-500">{t('analytics.days_measured') || 'عدد الأيام'}</div>
              <div className="text-2xl font-bold text-gray-700">{data.days}</div>
            </div>
          </div>

          <div className="card p-4">
            <h3 className="font-semibold mb-2">{t('analytics.daily_chart') || 'الاستهلاك اليومي'}</h3>
            {renderChart()}
          </div>

          <div className="card table-container mt-4">
            <table className="table">
              <thead>
                <tr>
                  <th>{t('common.date')}</th>
                  <th>{t('analytics.consumed_qty') || 'الكمية المستهلكة'}</th>
                </tr>
              </thead>
              <tbody>
                {data.trend.slice().reverse().map(p => (
                  <tr key={p.date}>
                    <td>{p.date}</td>
                    <td className={p.consumed_qty > 0 ? 'font-semibold' : 'text-gray-400'}>
                      {p.consumed_qty}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}


// ══════════════════════════════════════════════════════════════════════════
// G6 — Order-to-receive delay analytics
// ══════════════════════════════════════════════════════════════════════════
export function OrderDelayAnalyticsPage() {
  const t = useT()
  const [days, setDays] = React.useState(30)
  const [data, setData] = React.useState(null)
  const [loading, setLoading] = React.useState(true)

  React.useEffect(() => {
    setLoading(true)
    dashboardApi.orderDelayAnalytics({ days })
      .then(r => setData(r.data))
      .catch(e => toast.error(e?.response?.data?.detail || t('common.error_generic')))
      .finally(() => setLoading(false))
  }, [days])

  const kpiCard = (label, value, hint, colour = 'text-blue-600') => (
    <div className="card p-4">
      <div className="text-xs text-gray-500">{label}</div>
      <div className={`text-2xl font-bold ${colour}`}>
        {value}
        {hint && <span className="text-xs font-normal text-gray-400 ms-1">{hint}</span>}
      </div>
    </div>
  )

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-gray-900 mb-4">
        {t('analytics.order_delay_title') || 'تحليل تأخير الطلبيات'}
      </h1>
      <p className="text-sm text-gray-500 mb-4">
        {t('analytics.order_delay_desc') ||
          'متوسط الزمن من تقديم الطلبية للمستودع حتى الاستلام، مع تحديد أكثر الفروع تأخيراً.'}
      </p>

      <div className="card p-4 mb-4 flex gap-3 items-end">
        <div>
          <label className="label">{t('analytics.days_window') || 'عدد الأيام'}</label>
          <select className="input-field" value={days} onChange={(e) => setDays(Number(e.target.value))}>
            <option value={7}>7</option>
            <option value={30}>30</option>
            <option value={60}>60</option>
            <option value={90}>90</option>
            <option value={180}>180</option>
          </select>
        </div>
      </div>

      {loading ? (
        <PageLoader />
      ) : !data || data.total_orders_measured === 0 ? (
        <div className="card p-8 text-center text-gray-500">
          {t('analytics.no_measured_orders') || 'لا توجد طلبيات مكتملة في هذه الفترة'}
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            {kpiCard(
              t('analytics.orders_measured') || 'طلبيات مقاسة',
              data.total_orders_measured,
              null, 'text-gray-700'
            )}
            {kpiCard(
              t('analytics.avg_approval_hours') || 'متوسط الاعتماد',
              data.avg_approval_hours,
              t('analytics.hours') || 'ساعة',
              'text-orange-600'
            )}
            {kpiCard(
              t('analytics.avg_transit_hours') || 'متوسط النقل',
              data.avg_transit_hours,
              t('analytics.hours') || 'ساعة',
              'text-blue-600'
            )}
            {kpiCard(
              t('analytics.avg_total_hours') || 'المتوسط الكلي',
              data.avg_total_hours,
              t('analytics.hours') || 'ساعة',
              'text-red-600'
            )}
          </div>

          <div className="card p-0">
            <h3 className="font-semibold p-4 border-b">
              {t('analytics.top_delayed_branches') || 'أكثر الفروع تأخيراً'}
            </h3>
            <table className="table">
              <thead>
                <tr>
                  <th>{t('admin.branch_code')}</th>
                  <th>{t('admin.branch_name')}</th>
                  <th>{t('analytics.orders_count') || 'عدد الطلبيات'}</th>
                  <th>{t('analytics.avg_total_hours') || 'المتوسط (ساعة)'}</th>
                  <th>{t('analytics.max_total_hours') || 'الأقصى (ساعة)'}</th>
                </tr>
              </thead>
              <tbody>
                {data.top_delayed_branches.length === 0 ? (
                  <tr><td colSpan={5} className="text-center py-4 text-gray-400">
                    {t('common.no_data')}
                  </td></tr>
                ) : data.top_delayed_branches.map(b => (
                  <tr key={b.branch_id}>
                    <td className="font-mono text-xs">{b.branch_code}</td>
                    <td>{b.branch_name}</td>
                    <td>{b.orders_count}</td>
                    <td className={b.avg_total_hours > 48 ? 'text-red-600 font-bold' : 'font-semibold'}>
                      {b.avg_total_hours}
                    </td>
                    <td className="text-gray-500">{b.max_total_hours}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}


// ══════════════════════════════════════════════════════════════════════════
// G7 — Branches with most open corrective actions
// ══════════════════════════════════════════════════════════════════════════
export function BranchesOpenActionsPage() {
  const t = useT()
  const [limit, setLimit] = React.useState(10)
  const [data, setData] = React.useState(null)
  const [loading, setLoading] = React.useState(true)

  React.useEffect(() => {
    setLoading(true)
    dashboardApi.branchesOpenActions(limit)
      .then(r => setData(r.data))
      .catch(e => toast.error(e?.response?.data?.detail || t('common.error_generic')))
      .finally(() => setLoading(false))
  }, [limit])

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-gray-900 mb-4">
        {t('analytics.branches_open_actions_title') || 'الفروع الأكثر إجراءات تصحيحية مفتوحة'}
      </h1>
      <p className="text-sm text-gray-500 mb-4">
        {t('analytics.branches_open_actions_desc') ||
          'عدد الإجراءات التصحيحية غير المنجزة لكل فرع، والمتأخر منها.'}
      </p>

      <div className="card p-4 mb-4 flex gap-3 items-end">
        <div>
          <label className="label">{t('analytics.top_n') || 'أول'}</label>
          <select className="input-field" value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
            <option value={5}>5</option>
            <option value={10}>10</option>
            <option value={20}>20</option>
            <option value={50}>50</option>
          </select>
        </div>
      </div>

      {loading ? (
        <PageLoader />
      ) : !data || data.branches.length === 0 ? (
        <div className="card p-8 text-center text-gray-500">
          {t('analytics.no_open_actions') || 'لا توجد إجراءات مفتوحة'}
        </div>
      ) : (
        <div className="card table-container">
          <table className="table">
            <thead>
              <tr>
                <th>#</th>
                <th>{t('admin.branch_code')}</th>
                <th>{t('admin.branch_name')}</th>
                <th>{t('admin.city')}</th>
                <th>{t('analytics.open_actions') || 'مفتوحة'}</th>
                <th>{t('analytics.overdue_actions') || 'متأخرة'}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.branches.map((b, i) => {
                const pct = b.open_actions > 0 ? (b.overdue_actions / b.open_actions) * 100 : 0
                return (
                  <tr key={b.branch_id}>
                    <td className="text-gray-400">{i + 1}</td>
                    <td className="font-mono text-xs">{b.branch_code}</td>
                    <td className="font-medium">{b.branch_name}</td>
                    <td className="text-gray-500">{b.city}</td>
                    <td className="font-semibold">{b.open_actions}</td>
                    <td className={b.overdue_actions > 0 ? 'text-red-600 font-bold' : 'text-gray-400'}>
                      {b.overdue_actions}
                    </td>
                    <td>
                      <div className="w-24 h-2 bg-gray-200 rounded">
                        <div
                          className={`h-2 rounded ${pct > 50 ? 'bg-red-500' : pct > 20 ? 'bg-orange-500' : 'bg-green-500'}`}
                          style={{ width: `${Math.min(pct, 100)}%` }}
                          title={`${Math.round(pct)}% overdue`}
                        />
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
