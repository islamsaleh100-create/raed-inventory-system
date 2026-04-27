/**
 * DeliveryAnalyticsPages.jsx
 * داشبورد تحليل تطبيقات التوصيل — قسم مستقل
 */
import React, { useState, useEffect, useCallback } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import { deliveryApi } from '../../services/api'
import * as XLSX from 'xlsx'
import { useT, useLanguage } from '../../i18n'

// ─── Helpers ─────────────────────────────────────────────────────────────────

const COLORS = ['#3B82F6','#10B981','#F59E0B','#EF4444','#8B5CF6','#EC4899','#14B8A6']

function fmt(n, dec = 0) {
  if (n == null) return '—'
  return Number(n).toLocaleString('en-SA', { maximumFractionDigits: dec })
}

function fmtSAR(n) {
  if (n == null) return '—'
  return `${fmt(n, 2)} ﷼`
}

function useMonthName() {
  const t = useT()
  return (m) => {
    const n = parseInt(m) || 1
    return t(`delivery.month_${n}`)
  }
}

// ─── Shared UI ────────────────────────────────────────────────────────────────

function PageHeader({ title, subtitle, children }) {
  return (
    <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{title}</h1>
        {subtitle && <p className="text-sm text-gray-500 mt-1">{subtitle}</p>}
      </div>
      <div className="flex gap-2 flex-wrap">{children}</div>
    </div>
  )
}

function KpiCard({ label, value, sub, color = 'blue' }) {
  const colorMap = {
    blue:   'bg-blue-50   border-blue-200   text-blue-700',
    green:  'bg-green-50  border-green-200  text-green-700',
    amber:  'bg-amber-50  border-amber-200  text-amber-700',
    purple: 'bg-purple-50 border-purple-200 text-purple-700',
  }
  return (
    <div className={`rounded-xl border p-5 ${colorMap[color] || colorMap.blue}`}>
      <div className="text-xs font-medium mb-1 opacity-70">{label}</div>
      <div className="text-2xl font-bold">{value}</div>
      {sub && <div className="text-xs mt-2 opacity-60">{sub}</div>}
    </div>
  )
}

function Card({ title, children, className = '' }) {
  return (
    <div className={`bg-white rounded-xl border border-gray-200 shadow-sm p-5 ${className}`}>
      {title && <h3 className="text-base font-semibold text-gray-800 mb-4">{title}</h3>}
      {children}
    </div>
  )
}

function FilterBar({ filters, setFilters, brands = [], apps = [], periods = [] }) {
  const t = useT()
  const monthName = useMonthName()
  const years  = [...new Set(periods.map(p => p.year))].sort((a, b) => b - a)
  const months = filters.year
    ? [...new Set(periods.filter(p => p.year === +filters.year).map(p => p.month))].sort((a, b) => a - b)
    : []

  return (
    <div className="flex flex-wrap gap-3 mb-6">
      <select
        className="input text-sm"
        value={filters.year || ''}
        onChange={e => setFilters(f => ({ ...f, year: e.target.value || undefined, month: undefined }))}
      >
        <option value="">{t('delivery.filter_all_years')}</option>
        {years.map(y => <option key={y} value={y}>{y}</option>)}
      </select>

      <select
        className="input text-sm"
        value={filters.month || ''}
        onChange={e => setFilters(f => ({ ...f, month: e.target.value || undefined }))}
        disabled={!filters.year}
      >
        <option value="">{t('delivery.filter_all_months')}</option>
        {months.map(m => <option key={m} value={m}>{monthName(m)}</option>)}
      </select>

      {brands.length > 0 && (
        <select
          className="input text-sm"
          value={filters.brand_id || ''}
          onChange={e => setFilters(f => ({ ...f, brand_id: e.target.value || undefined }))}
        >
          <option value="">{t('delivery.filter_all_brands')}</option>
          {brands.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
        </select>
      )}

      {apps.length > 0 && (
        <select
          className="input text-sm"
          value={filters.app_id || ''}
          onChange={e => setFilters(f => ({ ...f, app_id: e.target.value || undefined }))}
        >
          <option value="">{t('delivery.filter_all_apps')}</option>
          {apps.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
      )}

      <button className="btn btn-ghost text-sm" onClick={() => setFilters({})}>
        {t('delivery.filter_clear')}
      </button>
    </div>
  )
}

function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center py-20">
      <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
    </div>
  )
}

function ErrorMsg({ msg }) {
  return (
    <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">{msg}</div>
  )
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null
  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3 text-sm">
      <p className="font-semibold mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color }}>
          {p.name}: {typeof p.value === 'number' && p.value > 10000 ? fmtSAR(p.value) : fmt(p.value)}
        </p>
      ))}
    </div>
  )
}

// ─── 1. Dashboard (Main) ──────────────────────────────────────────────────────

export function DeliveryDashboardPage() {
  const t = useT()
  const { lang } = useLanguage()
  const monthName = useMonthName()
  const [kpis,    setKpis]    = useState(null)
  const [appStats,setAppStats]= useState([])
  const [trend,   setTrend]   = useState([])
  const [brands,  setBrands]  = useState([])
  const [apps,    setApps]    = useState([])
  const [periods, setPeriods] = useState([])
  const [filters, setFilters] = useState({})
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const [kR, aR, tR, bR, apR, pR] = await Promise.all([
        deliveryApi.getKPIs(filters),
        deliveryApi.getAppStats(filters),
        deliveryApi.getTrend(filters),
        deliveryApi.getBrands(),
        deliveryApi.getApps(),
        deliveryApi.getPeriods(),
      ])
      setKpis(kR.data);  setAppStats(aR.data)
      setTrend(tR.data); setBrands(bR.data)
      setApps(apR.data); setPeriods(pR.data)
    } catch (e) {
      setError(e?.response?.data?.detail || t('delivery.load_data_failed'))
    } finally { setLoading(false) }
  }, [filters, t])

  useEffect(() => { load() }, [load])

  const ordersKey = t('delivery.series_orders')
  const revenueKey = t('delivery.series_revenue_sar')

  const trendData = trend.map(tr => ({
    name: `${monthName(tr.month)} ${tr.year}`,
    [ordersKey]: tr.orders,
    [revenueKey]: Number(tr.revenue || 0),
  }))

  const pieData = appStats.map((a, i) => ({
    name: a.app_name,
    value: a.orders,
    fill: COLORS[i % COLORS.length],
  }))

  return (
    <div dir={lang === 'ar' ? 'rtl' : 'ltr'} className="p-6">
      <PageHeader title={t('delivery.dashboard_main_title')} subtitle={t('delivery.dashboard_subtitle')}>
        <Link to="/delivery/import" className="btn btn-primary text-sm">{t('delivery.btn_import')}</Link>
        <Link to="/delivery/branches" className="btn btn-ghost text-sm">{t('delivery.btn_manage_branches')}</Link>
        <Link to="/delivery/brands" className="btn btn-ghost text-sm">{t('delivery.btn_brands')}</Link>
        <Link to="/delivery/branch-stats" className="btn btn-ghost text-sm">{t('delivery.btn_branches')}</Link>
      </PageHeader>

      <FilterBar filters={filters} setFilters={setFilters} brands={brands} apps={apps} periods={periods} />

      {loading && <LoadingSpinner />}
      {error   && <ErrorMsg msg={error} />}

      {!loading && !error && kpis && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <KpiCard label={t('delivery.kpi_total_orders')}  value={fmt(kpis.total_orders)}    color="blue"   />
            <KpiCard label={t('delivery.kpi_total_revenue')} value={fmtSAR(kpis.total_revenue)} color="green" />
            <KpiCard label={t('delivery.kpi_avg_aov')}        value={fmtSAR(kpis.avg_aov)}      color="amber"  />
            <KpiCard
              label={t('delivery.kpi_top_app')}
              value={kpis.top_app || '—'}
              sub={kpis.top_app_orders ? t('delivery.kpi_top_app_orders', { count: fmt(kpis.top_app_orders) }) : null}
              color="purple"
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 mb-6">
            <Card title={t('delivery.monthly_trend_title')} className="lg:col-span-2">
              {trendData.length === 0
                ? <p className="text-gray-400 text-center py-8">{t('delivery.no_data_import_first')}</p>
                : (
                  <ResponsiveContainer width="100%" height={250}>
                    <LineChart data={trendData} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                      <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                      <YAxis tick={{ fontSize: 10 }} />
                      <Tooltip content={<CustomTooltip />} />
                      <Legend />
                      <Line type="monotone" dataKey={ordersKey} stroke="#3B82F6" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                )
              }
            </Card>

            <Card title={t('delivery.orders_by_app_title')}>
              {pieData.length === 0
                ? <p className="text-gray-400 text-center py-8">{t('delivery.no_data')}</p>
                : (
                  <ResponsiveContainer width="100%" height={250}>
                    <PieChart>
                      <Pie
                        data={pieData} dataKey="value" nameKey="name"
                        cx="50%" cy="50%" outerRadius={80}
                        label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                        labelLine={true}
                      >
                        {pieData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
                      </Pie>
                      <Tooltip formatter={v => fmt(v)} />
                    </PieChart>
                  </ResponsiveContainer>
                )
              }
            </Card>
          </div>

          <Card title={t('delivery.app_detail_title')}>
            {appStats.length === 0
              ? <p className="text-gray-400 text-center py-8">{t('delivery.no_data')}</p>
              : (
                <div className="overflow-x-auto">
                  <table className="table w-full text-sm">
                    <thead>
                      <tr>
                        <th>{t('delivery.col_app')}</th>
                        <th>{t('delivery.col_orders')}</th>
                        <th>{t('delivery.col_revenue_sar')}</th>
                        <th>{t('delivery.col_avg_aov')}</th>
                        <th>{t('delivery.col_share')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {appStats.map(a => (
                        <tr key={a.app_id}>
                          <td className="font-medium">{a.app_name}</td>
                          <td>{fmt(a.orders)}</td>
                          <td>{fmtSAR(a.revenue)}</td>
                          <td>{fmtSAR(a.avg_aov)}</td>
                          <td>
                            <div className="flex items-center gap-2">
                              <div className="w-24 h-2 bg-gray-100 rounded-full overflow-hidden">
                                <div
                                  className="h-full bg-blue-500 rounded-full"
                                  style={{ width: `${Math.min(a.share_pct || 0, 100)}%` }}
                                />
                              </div>
                              <span className="text-xs text-gray-500">{fmt(a.share_pct, 1)}%</span>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
            }
          </Card>
        </>
      )}

      {!loading && !error && !kpis && (
        <Card>
          <div className="text-center py-16 text-gray-400">
            <div className="text-6xl mb-4">📊</div>
            <div className="text-lg font-medium text-gray-600 mb-2">{t('delivery.empty_state_title')}</div>
            <div className="text-sm mb-4">{t('delivery.empty_state_subtitle')}</div>
            <Link to="/delivery/import" className="btn btn-primary">{t('delivery.btn_import')}</Link>
          </div>
        </Card>
      )}
    </div>
  )
}

// ─── 2. Branch Stats Page ─────────────────────────────────────────────────────

export function DeliveryBranchStatsPage() {
  const t = useT()
  const { lang } = useLanguage()
  const [data,    setData]    = useState([])
  const [brands,  setBrands]  = useState([])
  const [apps,    setApps]    = useState([])
  const [periods, setPeriods] = useState([])
  const [filters, setFilters] = useState({})
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const [dR, bR, aR, pR] = await Promise.all([
        deliveryApi.getBranchStats(filters),
        deliveryApi.getBrands(),
        deliveryApi.getApps(),
        deliveryApi.getPeriods(),
      ])
      setData(dR.data); setBrands(bR.data); setApps(aR.data); setPeriods(pR.data)
    } catch (e) { setError(e?.response?.data?.detail || t('delivery.load_failed')) }
    finally { setLoading(false) }
  }, [filters, t])

  useEffect(() => { load() }, [load])

  const ordersLabel = t('delivery.series_orders')

  return (
    <div dir={lang === 'ar' ? 'rtl' : 'ltr'} className="p-6">
      <PageHeader title={t('delivery.branches_page_title')} subtitle={t('delivery.branches_page_subtitle')}>
        <Link to="/delivery" className="btn btn-ghost text-sm">← {t('delivery.back_dashboard')}</Link>
      </PageHeader>
      <FilterBar filters={filters} setFilters={setFilters} brands={brands} apps={apps} periods={periods} />
      {loading && <LoadingSpinner />}
      {error   && <ErrorMsg msg={error} />}

      {!loading && !error && data.length > 0 && (
        <>
          <Card title={t('delivery.top10_branches_title')} className="mb-5">
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={data.slice(0, 10)} layout="vertical" margin={{ right: 30, left: 120 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis type="number" tick={{ fontSize: 10 }} />
                <YAxis type="category" dataKey="branch_name" tick={{ fontSize: 10 }} width={110} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="orders" name={ordersLabel} fill="#3B82F6" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>

          <Card title={t('delivery.branches_table_title')}>
            <div className="overflow-x-auto">
              <table className="table w-full text-sm">
                <thead>
                  <tr>
                    <th>{t('delivery.col_num')}</th>
                    <th>{t('delivery.col_branch')}</th>
                    <th>{t('delivery.col_brand')}</th>
                    <th>{t('delivery.col_orders')}</th>
                    <th>{t('delivery.col_revenue_sar')}</th>
                    <th>{t('delivery.col_avg_aov')}</th>
                    <th>{t('delivery.col_map')}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((b, i) => (
                    <tr key={b.branch_id || i}>
                      <td className="text-gray-400">{i + 1}</td>
                      <td className="font-medium">{b.branch_name || '—'}</td>
                      <td className="text-gray-500">{b.brand_name || '—'}</td>
                      <td>{fmt(b.orders)}</td>
                      <td>{fmtSAR(b.revenue)}</td>
                      <td>{fmtSAR(b.avg_aov)}</td>
                      <td>
                        {b.google_maps_url
                          ? <a href={b.google_maps_url} target="_blank" rel="noopener noreferrer"
                              className="text-blue-500 hover:underline text-xs">📍 {t('delivery.map_link')}</a>
                          : <span className="text-gray-300 text-xs">—</span>
                        }
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
      {!loading && !error && data.length === 0 && (
        <Card><p className="text-center text-gray-400 py-10">{t('delivery.no_data')}</p></Card>
      )}
    </div>
  )
}

// ─── 3. Brand Stats Page ──────────────────────────────────────────────────────

export function DeliveryBrandStatsPage() {
  const t = useT()
  const { lang } = useLanguage()
  const [data,    setData]    = useState([])
  const [apps,    setApps]    = useState([])
  const [periods, setPeriods] = useState([])
  const [filters, setFilters] = useState({})
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const [dR, aR, pR] = await Promise.all([
        deliveryApi.getBrandStats(filters),
        deliveryApi.getApps(),
        deliveryApi.getPeriods(),
      ])
      setData(dR.data); setApps(aR.data); setPeriods(pR.data)
    } catch (e) { setError(e?.response?.data?.detail || t('delivery.load_failed')) }
    finally { setLoading(false) }
  }, [filters, t])

  useEffect(() => { load() }, [load])

  const ordersLabel = t('delivery.series_orders')
  const revenueLabel = t('delivery.series_revenue_sar')

  return (
    <div dir={lang === 'ar' ? 'rtl' : 'ltr'} className="p-6">
      <PageHeader title={t('delivery.brands_page_title')} subtitle={t('delivery.brands_page_subtitle')}>
        <Link to="/delivery" className="btn btn-ghost text-sm">← {t('delivery.back_dashboard')}</Link>
      </PageHeader>
      <FilterBar filters={filters} setFilters={setFilters} brands={[]} apps={apps} periods={periods} />
      {loading && <LoadingSpinner />}
      {error   && <ErrorMsg msg={error} />}

      {!loading && !error && data.length > 0 && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mb-5">
            <Card title={t('delivery.orders_by_brand_title')}>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={data}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="brand_name" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="orders" name={ordersLabel} fill="#3B82F6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </Card>
            <Card title={t('delivery.revenue_by_brand_title')}>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={data}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="brand_name" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="revenue" name={revenueLabel} fill="#10B981" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          </div>

          <Card title={t('delivery.brands_table_title')}>
            <div className="overflow-x-auto">
              <table className="table w-full text-sm">
                <thead>
                  <tr>
                    <th>{t('delivery.col_brand')}</th>
                    <th>{t('delivery.col_orders')}</th>
                    <th>{t('delivery.col_revenue_sar')}</th>
                    <th>{t('delivery.col_avg_aov')}</th>
                    <th>{t('delivery.col_share')}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map(b => (
                    <tr key={b.brand_id}>
                      <td className="font-medium">{b.brand_name}</td>
                      <td>{fmt(b.orders)}</td>
                      <td>{fmtSAR(b.revenue)}</td>
                      <td>{fmtSAR(b.avg_aov)}</td>
                      <td>
                        <div className="flex items-center gap-2">
                          <div className="w-20 h-2 bg-gray-100 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-green-500 rounded-full"
                              style={{ width: `${Math.min(b.share_pct || 0, 100)}%` }}
                            />
                          </div>
                          <span className="text-xs text-gray-500">{fmt(b.share_pct, 1)}%</span>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
      {!loading && !error && data.length === 0 && (
        <Card><p className="text-center text-gray-400 py-10">{t('delivery.no_data')}</p></Card>
      )}
    </div>
  )
}

// ─── 4. Import Page ───────────────────────────────────────────────────────────

export function DeliveryImportPage() {
  const t = useT()
  const { lang } = useLanguage()
  const monthName = useMonthName()
  const [rows,      setRows]      = useState([])
  const [preview,   setPreview]   = useState([])
  const [loading,   setLoading]   = useState(false)
  const [importing, setImporting] = useState(false)
  const [result,    setResult]    = useState(null)
  const [error,     setError]     = useState(null)
  const [exporting, setExporting] = useState(false)

  // H11: download a blank Excel template with the expected columns + sample rows
  const handleDownloadTemplate = () => {
    const year = new Date().getFullYear()
    const sample = [
      { year, month: 1, brand: 'ONDA', branch: 'فرع الملقا', app: 'Jahez',      orders: 320, revenue: 18400, aov: 57.5 },
      { year, month: 1, brand: 'ONDA', branch: 'فرع الملقا', app: 'HungerStation', orders: 210, revenue: 12800, aov: 60.95 },
      { year, month: 1, brand: 'ONDA', branch: 'فرع العليا', app: 'Jahez',      orders: 180, revenue: 11250, aov: 62.5 },
    ]
    const ws = XLSX.utils.json_to_sheet(sample, {
      header: ['year', 'month', 'brand', 'branch', 'app', 'orders', 'revenue', 'aov'],
    })
    // Column widths for readability
    ws['!cols'] = [
      { wch: 8 }, { wch: 8 }, { wch: 14 }, { wch: 20 },
      { wch: 16 }, { wch: 10 }, { wch: 12 }, { wch: 10 },
    ]
    // Build instructions sheet
    const instructions = [
      { key: 'year',    desc_ar: 'سنة البيانات (مثال: 2026)',             required: 'نعم' },
      { key: 'month',   desc_ar: 'رقم الشهر 1-12',                         required: 'نعم' },
      { key: 'brand',   desc_ar: 'اسم البراند (ONDA مثلاً)',               required: 'نعم' },
      { key: 'branch',  desc_ar: 'اسم الفرع كما يظهر في تطبيق التوصيل',    required: 'نعم' },
      { key: 'app',     desc_ar: 'اسم التطبيق (Jahez, HungerStation…)',    required: 'نعم' },
      { key: 'orders',  desc_ar: 'إجمالي عدد الطلبات في الشهر',            required: 'نعم' },
      { key: 'revenue', desc_ar: 'إجمالي الإيراد بالريال',                 required: 'نعم' },
      { key: 'aov',     desc_ar: 'متوسط قيمة الطلب (يُحسب تلقائياً لو فاضي)', required: 'لا' },
    ]
    const ws2 = XLSX.utils.json_to_sheet(instructions, {
      header: ['key', 'desc_ar', 'required'],
    })
    ws2['!cols'] = [{ wch: 14 }, { wch: 48 }, { wch: 10 }]

    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws,  'Delivery Data')
    XLSX.utils.book_append_sheet(wb, ws2, 'Instructions')
    XLSX.writeFile(wb, `delivery_template_${year}.xlsx`)
  }

  // H11: export existing delivery records as Excel (per-branch, per-app breakdown)
  const handleExport = async () => {
    setExporting(true); setError(null)
    try {
      const now = new Date()
      const [brandStatsRes, appStatsRes, branchStatsRes, trendRes] = await Promise.all([
        deliveryApi.getBrandStats({}),
        deliveryApi.getAppStats({}),
        deliveryApi.getBranchStats({}),
        deliveryApi.getTrend({}),
      ])
      const wb = XLSX.utils.book_new()

      const brandSheet = XLSX.utils.json_to_sheet(
        (brandStatsRes.data || []).map(b => ({
          brand:        b.brand_name,
          orders:       b.orders,
          revenue:      b.revenue,
          aov:          b.avg_aov,
          market_share: b.share_pct,
        }))
      )
      XLSX.utils.book_append_sheet(wb, brandSheet, 'Brands')

      const appSheet = XLSX.utils.json_to_sheet(
        (appStatsRes.data || []).map(a => ({
          app:          a.app_name,
          orders:       a.orders,
          revenue:      a.revenue,
          aov:          a.avg_aov,
          market_share: a.share_pct,
        }))
      )
      XLSX.utils.book_append_sheet(wb, appSheet, 'Apps')

      const branchSheet = XLSX.utils.json_to_sheet(
        (branchStatsRes.data || []).map(br => ({
          branch:  br.branch_name,
          brand:   br.brand_name || '',
          orders:  br.orders,
          revenue: br.revenue,
          aov:     br.avg_aov,
        }))
      )
      XLSX.utils.book_append_sheet(wb, branchSheet, 'Branches')

      const trendSheet = XLSX.utils.json_to_sheet(
        (trendRes.data || []).map(tr => ({
          year:    tr.year,
          month:   tr.month,
          orders:  tr.orders,
          revenue: tr.revenue,
        }))
      )
      XLSX.utils.book_append_sheet(wb, trendSheet, 'Monthly Trend')

      const ts = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}`
      XLSX.writeFile(wb, `delivery_export_${ts}.xlsx`)
    } catch (e) {
      setError(e?.response?.data?.detail || t('delivery.export_failed') || 'فشل التصدير')
    } finally {
      setExporting(false)
    }
  }

  const handleFile = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    setLoading(true); setError(null); setRows([]); setPreview([]); setResult(null)

    try {
      const ab  = await file.arrayBuffer()
      const wb  = XLSX.read(ab)
      const ws  = wb.Sheets[wb.SheetNames[0]]
      const raw = XLSX.utils.sheet_to_json(ws, { defval: '' })

      if (!raw.length) { setError(t('delivery.file_empty')); setLoading(false); return }

      const cleaned = raw.map(r => {
        const get = (...variants) => {
          for (const v of variants) {
            for (const k of Object.keys(r)) {
              if (k.trim().toLowerCase().includes(v)) return String(r[k]).trim()
            }
          }
          return ''
        }
        const ordersRaw  = get('order', 'طلب', 'orders', 'count')
        const revenueRaw = get('revenue', 'sales', 'إيراد', 'مبيعات', 'amount')
        const aovRaw     = get('aov', 'average')
        const orders     = parseInt(ordersRaw.replace(/,/g, ''))  || 0
        const revenue    = parseFloat(revenueRaw.replace(/,/g, '')) || 0
        const aov        = aovRaw ? parseFloat(aovRaw.replace(/,/g, '')) || null : null
        return {
          year:        parseInt(get('year', 'سنة'))  || new Date().getFullYear(),
          month:       parseInt(get('month', 'شهر')) || 1,
          brand_name:  get('brand', 'براند'),
          branch_name: get('branch', 'store', 'فرع', 'outlet'),
          app_name:    get('app', 'platform', 'تطبيق', 'channel'),
          orders, revenue, aov,
        }
      }).filter(r => r.orders > 0 || r.revenue > 0)

      setRows(cleaned)
      setPreview(cleaned.slice(0, 10))
    } catch (err) {
      setError(t('delivery.read_file_error') + ': ' + err.message)
    } finally { setLoading(false) }
  }

  const handleImport = async () => {
    if (!rows.length) return
    setImporting(true); setError(null); setResult(null)
    try {
      const res = await deliveryApi.importData({ rows })
      setResult(res.data)
      setRows([]); setPreview([])
    } catch (e) {
      setError(e?.response?.data?.detail || t('delivery.import_failed'))
    } finally { setImporting(false) }
  }

  return (
    <div dir={lang === 'ar' ? 'rtl' : 'ltr'} className="p-6">
      <PageHeader title={t('delivery.import_title')} subtitle={t('delivery.import_page_subtitle')}>
        <button className="btn btn-ghost text-sm" onClick={handleDownloadTemplate}>
          ⬇️ {t('delivery.btn_download_template') || 'تحميل القالب'}
        </button>
        <button className="btn btn-ghost text-sm" onClick={handleExport} disabled={exporting}>
          {exporting ? '⏳' : '📤'} {t('delivery.btn_export') || 'تصدير البيانات'}
        </button>
        <Link to="/delivery" className="btn btn-ghost text-sm">← {t('delivery.back_to_dashboard')}</Link>
      </PageHeader>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 mb-6">
        <Card title={t('delivery.required_fields_title')} className="lg:col-span-1">
          <ul className="text-sm text-gray-600 space-y-2">
            {[
              ['year',    t('delivery.field_year_desc')],
              ['month',   t('delivery.field_month_desc')],
              ['brand',   t('delivery.field_brand_desc')],
              ['branch',  t('delivery.field_branch_desc')],
              ['app',     t('delivery.field_app_desc')],
              ['orders',  t('delivery.field_orders_desc')],
              ['revenue', t('delivery.field_revenue_desc')],
            ].map(([key, desc]) => (
              <li key={key} className="flex items-start gap-2">
                <span className="text-green-500 mt-0.5">✓</span>
                <span><span className="font-mono text-blue-700">{key}</span> — {desc}</span>
              </li>
            ))}
            <li className="flex items-start gap-2 text-gray-400">
              <span className="mt-0.5">○</span>
              <span><span className="font-mono">aov</span> — {t('delivery.field_aov_desc')}</span>
            </li>
          </ul>
        </Card>

        <Card title={t('delivery.upload_file_title')} className="lg:col-span-2">
          <div
            className="border-2 border-dashed border-gray-300 rounded-lg p-10 text-center cursor-pointer hover:border-blue-400 hover:bg-blue-50 transition-colors"
            onClick={() => document.getElementById('xlsx-upload').click()}
          >
            <div className="text-5xl mb-3">📊</div>
            <div className="text-sm text-gray-600 mb-1 font-medium">{t('delivery.upload_click')}</div>
            <div className="text-xs text-gray-400">{t('delivery.upload_hint')}</div>
            <input id="xlsx-upload" type="file" accept=".xlsx,.xls" className="hidden" onChange={handleFile} />
          </div>
          {loading && <p className="text-center text-blue-500 mt-3 text-sm animate-pulse">{t('delivery.reading_file')}</p>}
        </Card>
      </div>

      {error && <div className="mb-4"><ErrorMsg msg={error} /></div>}

      {result && (
        <Card className="mb-5 border-green-200 bg-green-50">
          <div className="text-green-700 text-center py-4">
            <div className="text-4xl mb-2">✅</div>
            <div className="font-bold text-lg">{t('delivery.import_success')}</div>
            <div className="text-sm mt-2">
              {t('delivery.import_summary', {
                imported: fmt(result.imported),
                skipped: fmt(result.skipped),
                unmatched: fmt(result.unmatched),
              })}
            </div>
            {result.unmatched > 0 && (
              <Link to="/delivery/unmatched" className="text-xs underline mt-2 block">
                {t('delivery.fix_unmatched_link')} ←
              </Link>
            )}
            <Link to="/delivery" className="btn btn-primary mt-4 inline-block text-sm">
              {t('delivery.view_dashboard_link')} ←
            </Link>
          </div>
        </Card>
      )}

      {preview.length > 0 && (
        <Card title={t('delivery.preview_title', { shown: preview.length, total: rows.length })}>
          <div className="overflow-x-auto mb-4">
            <table className="table w-full text-xs">
              <thead>
                <tr>
                  <th>{t('delivery.col_year')}</th>
                  <th>{t('delivery.col_month')}</th>
                  <th>{t('delivery.col_brand')}</th>
                  <th>{t('delivery.col_branch_import')}</th>
                  <th>{t('delivery.col_app_import')}</th>
                  <th>{t('delivery.col_orders')}</th>
                  <th>{t('delivery.col_revenue')}</th>
                </tr>
              </thead>
              <tbody>
                {preview.map((r, i) => (
                  <tr key={i}>
                    <td>{r.year}</td>
                    <td>{monthName(r.month || 1)}</td>
                    <td>{r.brand_name}</td>
                    <td>{r.branch_name}</td>
                    <td>{r.app_name}</td>
                    <td>{fmt(r.orders)}</td>
                    <td>{fmtSAR(r.revenue)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <button
            className="btn btn-primary w-full"
            onClick={handleImport}
            disabled={importing}
          >
            {importing
              ? `⏳ ${t('delivery.importing_label')}`
              : `⬆️ ${t('delivery.import_button', { count: fmt(rows.length) })}`
            }
          </button>
        </Card>
      )}
    </div>
  )
}

// ─── 5. Branches Management Page ─────────────────────────────────────────────

export function DeliveryBranchesManagementPage() {
  const t = useT()
  const { lang } = useLanguage()
  const [branches,  setBranches]  = useState([])
  const [brands,    setBrands]    = useState([])
  const [loading,   setLoading]   = useState(true)
  const [error,     setError]     = useState(null)
  const [aliasInput,setAliasInput]= useState({})
  const [search,    setSearch]    = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [bR, brR] = await Promise.all([deliveryApi.getBranches(), deliveryApi.getBrands()])
      setBranches(bR.data); setBrands(brR.data)
    } catch (e) { setError(t('delivery.load_failed')) }
    finally { setLoading(false) }
  }, [t])

  useEffect(() => { load() }, [load])

  const handleAddAlias = async (branchId) => {
    const alias = (aliasInput[branchId] || '').trim()
    if (!alias) return
    try {
      await deliveryApi.addAlias(branchId, alias)
      setAliasInput(p => ({ ...p, [branchId]: '' }))
      await load()
    } catch (e) { alert(t('delivery.alias_add_failed') + ': ' + (e?.response?.data?.detail || e.message)) }
  }

  const handleDeleteAlias = async (branchId, aliasId) => {
    if (!confirm(t('delivery.confirm_delete_alias'))) return
    try { await deliveryApi.deleteAlias(branchId, aliasId); await load() }
    catch (e) { alert(t('delivery.alias_delete_failed')) }
  }

  const filtered = branches.filter(b => {
    if (!search) return true
    const q = search.toLowerCase()
    return b.name.toLowerCase().includes(q) ||
      brands.find(br => br.id === b.brand_id)?.name.toLowerCase().includes(q)
  })

  return (
    <div dir={lang === 'ar' ? 'rtl' : 'ltr'} className="p-6">
      <PageHeader title={t('delivery.branches_mgmt_title')} subtitle={t('delivery.branches_mgmt_subtitle')}>
        <Link to="/delivery/unmatched" className="btn btn-ghost text-sm text-amber-600">⚠️ {t('delivery.btn_unmatched')}</Link>
        <Link to="/delivery" className="btn btn-ghost text-sm">← {t('delivery.back_dashboard')}</Link>
      </PageHeader>

      <div className="mb-4">
        <input
          className="input w-full md:w-80"
          placeholder={t('delivery.search_branches_placeholder')}
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>

      {loading && <LoadingSpinner />}
      {error   && <ErrorMsg msg={error} />}

      {!loading && !error && (
        <div className="space-y-3">
          {filtered.length === 0
            ? <Card><p className="text-center text-gray-400 py-10">{t('delivery.no_matching_branches')}</p></Card>
            : filtered.map(branch => {
              const brand = brands.find(b => b.id === branch.brand_id)
              return (
                <Card key={branch.id}>
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <span className="font-semibold text-gray-900">{branch.name}</span>
                        <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">
                          {brand?.name || '—'}
                        </span>
                        {branch.region && (
                          <span className="text-xs text-gray-400">📍 {branch.region}</span>
                        )}
                      </div>

                      {/* Aliases */}
                      {branch.aliases?.length > 0 && (
                        <div className="flex flex-wrap gap-1.5 mt-2">
                          {branch.aliases.map(a => (
                            <span key={a.id} className="inline-flex items-center gap-1 bg-gray-100 text-gray-700 text-xs px-2 py-0.5 rounded-full">
                              {a.alias}
                              <button
                                onClick={() => handleDeleteAlias(branch.id, a.id)}
                                className="text-red-400 hover:text-red-600 font-bold leading-none"
                              >×</button>
                            </span>
                          ))}
                        </div>
                      )}

                      {/* Add alias */}
                      <div className="flex gap-2 mt-3">
                        <input
                          className="input text-sm flex-1 max-w-xs"
                          placeholder={t('delivery.add_alias_placeholder')}
                          value={aliasInput[branch.id] || ''}
                          onChange={e => setAliasInput(p => ({ ...p, [branch.id]: e.target.value }))}
                          onKeyDown={e => e.key === 'Enter' && handleAddAlias(branch.id)}
                        />
                        <button className="btn btn-sm btn-primary" onClick={() => handleAddAlias(branch.id)}>
                          + {t('delivery.btn_add')}
                        </button>
                      </div>
                    </div>

                    {branch.google_maps_url && (
                      <a href={branch.google_maps_url} target="_blank" rel="noopener noreferrer"
                        className="text-blue-500 hover:text-blue-700 text-sm shrink-0">
                        📍 {t('delivery.map_link')}
                      </a>
                    )}
                  </div>
                </Card>
              )
            })
          }
        </div>
      )}
    </div>
  )
}

// ─── 6. Unmatched Branches ────────────────────────────────────────────────────

export function DeliveryUnmatchedPage() {
  const t = useT()
  const { lang } = useLanguage()
  const [data,    setData]    = useState([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    deliveryApi.getUnmatched()
      .then(r => setData(r.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return (
    <div dir={lang === 'ar' ? 'rtl' : 'ltr'} className="p-6">
      <PageHeader title={t('delivery.unmatched_page_title')} subtitle={t('delivery.unmatched_page_subtitle')}>
        <Link to="/delivery/branches" className="btn btn-primary text-sm">{t('delivery.btn_manage_link')} ←</Link>
        <Link to="/delivery" className="btn btn-ghost text-sm">{t('delivery.dashboard_title')}</Link>
      </PageHeader>

      {loading && <LoadingSpinner />}

      {!loading && (
        data.length === 0
          ? (
            <Card>
              <div className="text-center py-12">
                <div className="text-5xl mb-3">✅</div>
                <div className="text-gray-700 font-semibold text-lg">{t('delivery.all_matched_title')}</div>
                <div className="text-gray-400 text-sm mt-2">{t('delivery.all_matched_subtitle')}</div>
              </div>
            </Card>
          )
          : (
            <Card title={t('delivery.unmatched_count_title', { count: data.length })}>
              <p className="text-sm text-gray-500 mb-4">
                {t('delivery.unmatched_hint')}
              </p>
              <div className="overflow-x-auto">
                <table className="table w-full text-sm">
                  <thead>
                    <tr>
                      <th>{t('delivery.col_raw_name')}</th>
                      <th>{t('delivery.col_record_count')}</th>
                      <th>{t('delivery.col_action')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.map((b, i) => (
                      <tr key={i}>
                        <td className="font-mono text-gray-800 text-xs">{b.raw_name}</td>
                        <td className="text-gray-600">{fmt(b.count)}</td>
                        <td>
                          <button
                            className="text-blue-600 hover:underline text-xs"
                            onClick={() => navigate('/delivery/branches')}
                          >{t('delivery.btn_link_to_branch')} ←</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )
      )}
    </div>
  )
}

// ─── Default export ───────────────────────────────────────────────────────────

export default DeliveryDashboardPage
