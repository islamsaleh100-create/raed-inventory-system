import React, { useEffect, useMemo, useState } from 'react'
import toast from 'react-hot-toast'
import { useSelector } from 'react-redux'

import { selectUser, selectUserRoles } from '../../store'
import { masterApi, salesChannelsApi } from '../../services/api'
import { useLanguage, useT } from '../../i18n'

// TODO(P2): when a raw daily-sales list is added to this page family, surface a
// small badge for rows where `on_behalf_of === true` so substitute entries are
// visible in the UI. Current reconciliation/compliance screens aggregate rows
// and do not expose DailySaleOut records directly.

function todayMonth() {
  return new Date().toISOString().slice(0, 7)
}

function todayDate() {
  return new Date().toISOString().slice(0, 10)
}

function PageShell({ title, subtitle, actions, children }) {
  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{title}</h1>
          {subtitle ? <p className="text-sm text-gray-500 mt-1">{subtitle}</p> : null}
        </div>
        {actions ? <div className="flex gap-2 flex-wrap">{actions}</div> : null}
      </div>
      {children}
    </div>
  )
}

function LoadingState() {
  return (
    <div className="flex items-center justify-center py-16">
      <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
    </div>
  )
}

function EmptyState({ text }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-sm text-gray-400">
      {text}
    </div>
  )
}

function useBranches(enabled = true) {
  const [branches, setBranches] = useState([])
  useEffect(() => {
    if (!enabled) return
    masterApi.listBranches({ active_only: true })
      .then((res) => setBranches(Array.isArray(res.data) ? res.data : []))
      .catch(() => setBranches([]))
  }, [enabled])
  return branches
}

function statusClass(status) {
  if (status === 'major') return 'bg-red-50 text-red-700'
  if (status === 'minor') return 'bg-amber-50 text-amber-700'
  return 'bg-green-50 text-green-700'
}

function RoleGuard({ allowed, children }) {
  const roles = useSelector(selectUserRoles)
  const isAllowed = roles.includes('super_admin') || allowed.some((role) => roles.includes(role))
  const t = useT()
  if (!isAllowed) {
    return (
      <PageShell title={t('sales_channels.unauthorized_title')}>
        <EmptyState text={t('sales_channels.unauthorized_text')} />
      </PageShell>
    )
  }
  return children
}

export function SalesChannelsDailyEntryPage() {
  const t = useT()
  const { lang } = useLanguage()
  const user = useSelector(selectUser)
  const roles = useSelector(selectUserRoles)
  // Daily entry (Model C, 2026-04-24):
  //   - branch_manager enters own branch only (no branch selector)
  //   - area_manager enters for any branch in their region (selector shown)
  //   - admin/super_admin can choose any branch (selector shown)
  //   - sales_manager is NOT an entry role in Model C (blocked by RoleGuard above)
  const isElevated = roles.includes('area_manager') || roles.includes('super_admin') || roles.includes('admin')
  const branches = useBranches(isElevated)
  const [channels, setChannels] = useState([])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [salesDate, setSalesDate] = useState(todayDate())
  const [branchId, setBranchId] = useState(user?.branch_id || '')
  const [lines, setLines] = useState({})

  useEffect(() => {
    salesChannelsApi.listChannels()
      .then((res) => {
        const data = Array.isArray(res.data) ? res.data : []
        setChannels(data)
        const initial = {}
        data.forEach((channel) => {
          initial[channel.id] = { amount: '', orders_count: channel.type === 'delivery_app' ? '0' : '' }
        })
        setLines(initial)
      })
      .catch((err) => toast.error(err?.response?.data?.detail || t('sales_channels.load_failed')))
      .finally(() => setLoading(false))
  }, [t])

  const grouped = useMemo(() => ({
    delivery: channels.filter((c) => c.type === 'delivery_app'),
    payment: channels.filter((c) => c.type === 'payment_method'),
  }), [channels])

  const totals = useMemo(() => {
    return channels.reduce((acc, channel) => {
      const line = lines[channel.id] || {}
      acc.amount += Number(line.amount || 0)
      if (channel.type === 'delivery_app') acc.orders += Number(line.orders_count || 0)
      return acc
    }, { amount: 0, orders: 0 })
  }, [channels, lines])

  const updateLine = (channelId, key, value) => {
    setLines((prev) => ({
      ...prev,
      [channelId]: {
        ...prev[channelId],
        [key]: value,
      },
    }))
  }

  const handleSubmit = async () => {
    const effectiveBranchId = Number(branchId || user?.branch_id)
    if (!effectiveBranchId) {
      toast.error(t('sales_channels.branch_required'))
      return
    }
    setSubmitting(true)
    try {
      await salesChannelsApi.createDailySalesBatch({
        branch_id: effectiveBranchId,
        sales_date: salesDate,
        lines: channels.map((channel) => ({
          channel_id: channel.id,
          amount: lines[channel.id]?.amount === '' ? '0' : lines[channel.id]?.amount || '0',
          orders_count: channel.type === 'delivery_app'
            ? Number(lines[channel.id]?.orders_count || 0)
            : null,
        })),
      })
      toast.success(t('sales_channels.daily_saved'))
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('sales_channels.save_failed'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <RoleGuard allowed={['branch_manager', 'area_manager', 'admin', 'super_admin']}>
      <PageShell
        title={t('sales_channels.daily_entry_title')}
        subtitle={t('sales_channels.daily_entry_subtitle')}
        actions={(
          <>
            <input type="date" className="input-field" value={salesDate} onChange={(e) => setSalesDate(e.target.value)} />
            {isElevated ? (
              <select className="input-field min-w-56" value={branchId || ''} onChange={(e) => setBranchId(e.target.value)}>
                <option value="">{t('sales_channels.select_branch')}</option>
                {branches.map((branch) => (
                  <option key={branch.id} value={branch.id}>{branch.branch_name}</option>
                ))}
              </select>
            ) : null}
            <button className="btn-primary" onClick={handleSubmit} disabled={submitting}>
              {submitting ? t('sales_channels.saving') : t('sales_channels.save_day')}
            </button>
          </>
        )}
      >
        {loading ? <LoadingState /> : (
          <div dir={lang === 'ar' ? 'rtl' : 'ltr'} className="space-y-6">
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h2 className="text-base font-semibold text-gray-900 mb-4">{t('sales_channels.delivery_apps')}</h2>
              <div className="overflow-x-auto">
                <table className="table w-full">
                  <thead>
                    <tr>
                      <th>{t('sales_channels.channel')}</th>
                      <th>{t('sales_channels.orders_count')}</th>
                      <th>{t('sales_channels.amount')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {grouped.delivery.map((channel) => (
                      <tr key={channel.id}>
                        <td className="font-medium">{lang === 'ar' ? channel.name_ar : channel.name_en}</td>
                        <td>
                          <input
                            type="number"
                            min="0"
                            className="input-field"
                            value={lines[channel.id]?.orders_count ?? '0'}
                            onChange={(e) => updateLine(channel.id, 'orders_count', e.target.value)}
                          />
                        </td>
                        <td>
                          <input
                            type="number"
                            min="0"
                            step="0.01"
                            className="input-field"
                            value={lines[channel.id]?.amount ?? ''}
                            onChange={(e) => updateLine(channel.id, 'amount', e.target.value)}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h2 className="text-base font-semibold text-gray-900 mb-4">{t('sales_channels.payment_methods')}</h2>
              <div className="overflow-x-auto">
                <table className="table w-full">
                  <thead>
                    <tr>
                      <th>{t('sales_channels.channel')}</th>
                      <th>{t('sales_channels.amount')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {grouped.payment.map((channel) => (
                      <tr key={channel.id}>
                        <td className="font-medium">{lang === 'ar' ? channel.name_ar : channel.name_en}</td>
                        <td>
                          <input
                            type="number"
                            min="0"
                            step="0.01"
                            className="input-field"
                            value={lines[channel.id]?.amount ?? ''}
                            onChange={(e) => updateLine(channel.id, 'amount', e.target.value)}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-blue-50 rounded-xl border border-blue-100 p-4">
                <div className="text-sm text-blue-600">{t('sales_channels.total_orders')}</div>
                <div className="text-2xl font-bold text-blue-800">{totals.orders}</div>
              </div>
              <div className="bg-green-50 rounded-xl border border-green-100 p-4">
                <div className="text-sm text-green-600">{t('sales_channels.total_amount')}</div>
                <div className="text-2xl font-bold text-green-800">{totals.amount.toLocaleString(undefined, { maximumFractionDigits: 2 })}</div>
              </div>
            </div>
          </div>
        )}
      </PageShell>
    </RoleGuard>
  )
}

export function SalesChannelsStatementsPage() {
  const t = useT()
  const { lang } = useLanguage()
  const branches = useBranches(true)
  const [channels, setChannels] = useState([])
  const [month, setMonth] = useState(todayMonth())
  const [channelId, setChannelId] = useState('')
  const [rows, setRows] = useState({})
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    salesChannelsApi.listChannels()
      .then((res) => {
        const apps = (Array.isArray(res.data) ? res.data : []).filter((channel) => channel.type === 'delivery_app')
        setChannels(apps)
        if (apps[0]) setChannelId(String(apps[0].id))
      })
      .catch((err) => toast.error(err?.response?.data?.detail || t('sales_channels.load_failed')))
  }, [t])

  const selectedChannel = channels.find((channel) => String(channel.id) === String(channelId))

  const handleChange = (branchId, key, value) => {
    setRows((prev) => ({
      ...prev,
      [branchId]: { ...(prev[branchId] || {}), [key]: value },
    }))
  }

  const handleSave = async () => {
    if (!channelId) {
      toast.error(t('sales_channels.channel_required'))
      return
    }
    setSaving(true)
    try {
      const payloads = branches
        .map((branch) => ({
          branch_id: branch.id,
          app_reported_amount: rows[branch.id]?.amount,
          app_reported_count: rows[branch.id]?.count,
        }))
        .filter((row) => row.app_reported_amount !== undefined && row.app_reported_amount !== '')

      await Promise.all(payloads.map((row) => salesChannelsApi.createStatement({
        channel_id: Number(channelId),
        branch_id: row.branch_id,
        statement_month: month,
        app_reported_amount: row.app_reported_amount,
        app_reported_count: row.app_reported_count === '' || row.app_reported_count === undefined ? null : Number(row.app_reported_count),
        commission_rate: selectedChannel?.commission_rate || 0,
        import_source: 'manual',
      })))
      toast.success(t('sales_channels.statements_saved'))
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('sales_channels.save_failed'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <RoleGuard allowed={['sales_manager', 'admin', 'super_admin']}>
      <PageShell
        title={t('sales_channels.statements_title')}
        subtitle={t('sales_channels.statements_subtitle')}
        actions={(
          <>
            <input type="month" className="input-field" value={month} onChange={(e) => setMonth(e.target.value)} />
            <select className="input-field min-w-56" value={channelId} onChange={(e) => setChannelId(e.target.value)}>
              {channels.map((channel) => (
                <option key={channel.id} value={channel.id}>{lang === 'ar' ? channel.name_ar : channel.name_en}</option>
              ))}
            </select>
            <button className="btn-primary" onClick={handleSave} disabled={saving}>
              {saving ? t('sales_channels.saving') : t('sales_channels.save_statements')}
            </button>
          </>
        )}
      >
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="text-sm text-gray-500 mb-4">
            {t('sales_channels.current_commission')}: {selectedChannel?.commission_rate ?? '0'}%
          </div>
          <div className="overflow-x-auto">
            <table className="table w-full">
              <thead>
                <tr>
                  <th>{t('sales_channels.branch')}</th>
                  <th>{t('sales_channels.app_amount')}</th>
                  <th>{t('sales_channels.app_orders_count')}</th>
                </tr>
              </thead>
              <tbody>
                {branches.map((branch) => (
                  <tr key={branch.id}>
                    <td className="font-medium">{branch.branch_name}</td>
                    <td>
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        className="input-field"
                        value={rows[branch.id]?.amount ?? ''}
                        onChange={(e) => handleChange(branch.id, 'amount', e.target.value)}
                      />
                    </td>
                    <td>
                      <input
                        type="number"
                        min="0"
                        className="input-field"
                        value={rows[branch.id]?.count ?? ''}
                        onChange={(e) => handleChange(branch.id, 'count', e.target.value)}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </PageShell>
    </RoleGuard>
  )
}

export function SalesChannelsReconciliationPage() {
  const t = useT()
  const { lang } = useLanguage()
  const user = useSelector(selectUser)
  const roles = useSelector(selectUserRoles)
  const isManagerial = roles.includes('sales_manager') || roles.includes('operations_manager') || roles.includes('area_manager') || roles.includes('super_admin') || roles.includes('admin')
  const branches = useBranches(isManagerial)
  const [channels, setChannels] = useState([])
  const [month, setMonth] = useState(todayMonth())
  const [branchId, setBranchId] = useState(user?.branch_id || '')
  const [channelId, setChannelId] = useState('')
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    salesChannelsApi.listChannels()
      .then((res) => setChannels((Array.isArray(res.data) ? res.data : []).filter((channel) => channel.type === 'delivery_app')))
      .catch(() => {})
  }, [])

  const load = async () => {
    setLoading(true)
    try {
      const res = await salesChannelsApi.getReconciliation({
        month,
        branch_id: branchId || undefined,
        channel_id: channelId || undefined,
      })
      setReport(res.data)
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('sales_channels.load_failed'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  return (
    <RoleGuard allowed={['branch_manager', 'area_manager', 'operations_manager', 'sales_manager', 'admin', 'super_admin']}>
      <PageShell
        title={t('sales_channels.reconciliation_title')}
        subtitle={t('sales_channels.reconciliation_subtitle')}
        actions={(
          <>
            <input type="month" className="input-field" value={month} onChange={(e) => setMonth(e.target.value)} />
            {isManagerial ? (
              <select className="input-field min-w-56" value={branchId || ''} onChange={(e) => setBranchId(e.target.value)}>
                <option value="">{t('sales_channels.all_branches')}</option>
                {branches.map((branch) => (
                  <option key={branch.id} value={branch.id}>{branch.branch_name}</option>
                ))}
              </select>
            ) : null}
            <select className="input-field min-w-56" value={channelId || ''} onChange={(e) => setChannelId(e.target.value)}>
              <option value="">{t('sales_channels.all_apps')}</option>
              {channels.map((channel) => (
                <option key={channel.id} value={channel.id}>{lang === 'ar' ? channel.name_ar : channel.name_en}</option>
              ))}
            </select>
            <button className="btn-primary" onClick={load}>{t('sales_channels.refresh')}</button>
          </>
        )}
      >
        {loading ? <LoadingState /> : !report?.lines?.length ? <EmptyState text={t('sales_channels.no_data')} /> : (
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <div className="text-sm text-gray-500 mb-4">
              {report.is_locked ? t('sales_channels.month_locked') : t('sales_channels.month_open')}
            </div>
            <div className="overflow-x-auto">
              <table className="table w-full">
                <thead>
                  <tr>
                    <th>{t('sales_channels.branch')}</th>
                    <th>{t('sales_channels.channel')}</th>
                    <th>{t('sales_channels.branch_total')}</th>
                    <th>{t('sales_channels.app_total')}</th>
                    <th>{t('sales_channels.variance_amount')}</th>
                    <th>{t('sales_channels.variance_percent')}</th>
                    <th>{t('sales_channels.branch_count')}</th>
                    <th>{t('sales_channels.app_count')}</th>
                    <th>{t('sales_channels.count_variance')}</th>
                    <th>{t('sales_channels.status')}</th>
                  </tr>
                </thead>
                <tbody>
                  {report.lines.map((line) => (
                    <tr key={`${line.branch_id}-${line.channel_id}`}>
                      <td>{line.branch_name || line.branch_id}</td>
                      <td>{line.channel_name_ar || line.channel_code}</td>
                      <td>{line.branch_total}</td>
                      <td>{line.app_total}</td>
                      <td>{line.variance_amount}</td>
                      <td>{line.variance_percent ?? 'N/A'}</td>
                      <td>{line.branch_count ?? '-'}</td>
                      <td>{line.app_count ?? '-'}</td>
                      <td>{line.count_variance ?? '-'}</td>
                      <td>
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${statusClass(line.status)}`}>
                          {t(`sales_channels.status_${line.status}`)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </PageShell>
    </RoleGuard>
  )
}

export function SalesChannelsClosuresPage() {
  const t = useT()
  const branches = useBranches(true)
  const [month, setMonth] = useState(todayMonth())
  const [scopeType, setScopeType] = useState('all')
  const [branchId, setBranchId] = useState('')
  const [closures, setClosures] = useState([])
  const [reopenReason, setReopenReason] = useState({})

  const loadClosures = async (selectedMonth = month) => {
    try {
      const res = await salesChannelsApi.listClosures({ month: selectedMonth })
      setClosures(Array.isArray(res.data) ? res.data : [])
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('sales_channels.load_failed'))
    }
  }

  useEffect(() => {
    loadClosures()
  }, [])

  const handleCloseMonth = async () => {
    try {
      await salesChannelsApi.createClosure({
        month,
        scope_type: scopeType,
        branch_id: scopeType === 'branch' ? Number(branchId) : null,
      })
      toast.success(t('sales_channels.closure_saved'))
      loadClosures(month)
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('sales_channels.save_failed'))
    }
  }

  const handleReopen = async (closureId) => {
    try {
      await salesChannelsApi.reopenClosure(closureId, reopenReason[closureId] || '')
      toast.success(t('sales_channels.closure_reopened'))
      loadClosures(month)
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('sales_channels.save_failed'))
    }
  }

  return (
    <RoleGuard allowed={['sales_manager', 'admin', 'super_admin']}>
      <PageShell title={t('sales_channels.closures_title')} subtitle={t('sales_channels.closures_subtitle')}>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
            <div>
              <label className="label">{t('sales_channels.month')}</label>
              <input type="month" className="input-field" value={month} onChange={(e) => setMonth(e.target.value)} />
            </div>
            <div>
              <label className="label">{t('sales_channels.scope_type')}</label>
              <select className="input-field" value={scopeType} onChange={(e) => setScopeType(e.target.value)}>
                <option value="all">{t('sales_channels.scope_all')}</option>
                <option value="branch">{t('sales_channels.scope_branch')}</option>
              </select>
            </div>
            {scopeType === 'branch' ? (
              <div>
                <label className="label">{t('sales_channels.branch')}</label>
                <select className="input-field" value={branchId} onChange={(e) => setBranchId(e.target.value)}>
                  <option value="">{t('sales_channels.select_branch')}</option>
                  {branches.map((branch) => (
                    <option key={branch.id} value={branch.id}>{branch.branch_name}</option>
                  ))}
                </select>
              </div>
            ) : null}
            <div className="flex gap-2">
              <button className="btn-primary" onClick={handleCloseMonth}>{t('sales_channels.lock_month')}</button>
              <button className="btn-secondary" onClick={() => loadClosures(month)}>{t('sales_channels.refresh')}</button>
            </div>
          </div>

          <div className="lg:col-span-2 bg-white rounded-xl border border-gray-200 p-5">
            <div className="overflow-x-auto">
              <table className="table w-full">
                <thead>
                  <tr>
                    <th>{t('sales_channels.month')}</th>
                    <th>{t('sales_channels.scope_type')}</th>
                    <th>{t('sales_channels.branch')}</th>
                    <th>{t('sales_channels.status')}</th>
                    <th>{t('sales_channels.reopen_reason')}</th>
                    <th>{t('sales_channels.action')}</th>
                  </tr>
                </thead>
                <tbody>
                  {closures.map((closure) => (
                    <tr key={closure.id}>
                      <td>{closure.month}</td>
                      <td>{closure.scope_type === 'all' ? t('sales_channels.scope_all') : t('sales_channels.scope_branch')}</td>
                      <td>{closure.branch_id || '-'}</td>
                      <td>{closure.reopened_at ? t('sales_channels.status_reopened') : t('sales_channels.status_locked')}</td>
                      <td>
                        <input
                          type="text"
                          className="input-field"
                          value={reopenReason[closure.id] || ''}
                          onChange={(e) => setReopenReason((prev) => ({ ...prev, [closure.id]: e.target.value }))}
                          disabled={Boolean(closure.reopened_at)}
                        />
                      </td>
                      <td>
                        <button
                          className="btn-secondary"
                          disabled={Boolean(closure.reopened_at)}
                          onClick={() => handleReopen(closure.id)}
                        >
                          {t('sales_channels.reopen')}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </PageShell>
    </RoleGuard>
  )
}

export function SalesChannelsCompliancePage() {
  const t = useT()
  const [month, setMonth] = useState(todayMonth())
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)

  const load = async (selectedMonth = month) => {
    setLoading(true)
    try {
      const res = await salesChannelsApi.getCompliance({ month: selectedMonth })
      setReport(res.data)
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('sales_channels.load_failed'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  return (
    <RoleGuard allowed={['branch_manager', 'area_manager', 'operations_manager', 'sales_manager', 'admin', 'super_admin']}>
      <PageShell
        title={t('sales_channels.compliance_title')}
        subtitle={t('sales_channels.compliance_subtitle')}
        actions={(
          <>
            <input type="month" className="input-field" value={month} onChange={(e) => setMonth(e.target.value)} />
            <button className="btn-primary" onClick={() => load(month)}>{t('sales_channels.refresh')}</button>
          </>
        )}
      >
        {loading ? <LoadingState /> : !report?.rows?.length ? <EmptyState text={t('sales_channels.no_data')} /> : (
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <div className="overflow-x-auto">
              <table className="table w-full">
                <thead>
                  <tr>
                    <th>{t('sales_channels.branch')}</th>
                    <th>{t('sales_channels.expected_days')}</th>
                    <th>{t('sales_channels.submitted_days')}</th>
                    <th>{t('sales_channels.compliance_percent')}</th>
                    <th>{t('sales_channels.last_entry_date')}</th>
                    <th>{t('sales_channels.exceptional_entries')}</th>
                  </tr>
                </thead>
                <tbody>
                  {report.rows.map((row) => (
                    <tr key={row.branch_id}>
                      <td>{row.branch_name || row.branch_id}</td>
                      <td>{row.expected_days}</td>
                      <td>{row.submitted_days}</td>
                      <td>{row.compliance_percent}%</td>
                      <td>{row.last_entry_date || '-'}</td>
                      <td>{row.exceptional_entries}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </PageShell>
    </RoleGuard>
  )
}

export function SalesChannelsAdminPage() {
  const t = useT()
  const { lang } = useLanguage()
  const [channels, setChannels] = useState([])
  const [drafts, setDrafts] = useState({})

  const load = async () => {
    try {
      const res = await salesChannelsApi.listChannels()
      const apps = (Array.isArray(res.data) ? res.data : []).filter((channel) => channel.type === 'delivery_app')
      setChannels(apps)
      setDrafts(Object.fromEntries(apps.map((channel) => [channel.id, channel.commission_rate ?? '0'])))
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('sales_channels.load_failed'))
    }
  }

  useEffect(() => {
    load()
  }, [])

  const handleSave = async (channelId) => {
    try {
      await salesChannelsApi.updateCommissionRate(channelId, drafts[channelId])
      toast.success(t('sales_channels.commission_saved'))
      load()
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('sales_channels.save_failed'))
    }
  }

  return (
    <RoleGuard allowed={['sales_manager', 'admin', 'super_admin']}>
      <PageShell title={t('sales_channels.admin_title')} subtitle={t('sales_channels.admin_subtitle')}>
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="overflow-x-auto">
            <table className="table w-full">
              <thead>
                <tr>
                  <th>{t('sales_channels.channel')}</th>
                  <th>{t('sales_channels.commission_rate')}</th>
                  <th>{t('sales_channels.action')}</th>
                </tr>
              </thead>
              <tbody>
                {channels.map((channel) => (
                  <tr key={channel.id}>
                    <td className="font-medium">{lang === 'ar' ? channel.name_ar : channel.name_en}</td>
                    <td>
                      <input
                        type="number"
                        min="0"
                        max="100"
                        step="0.01"
                        className="input-field"
                        value={drafts[channel.id] ?? ''}
                        onChange={(e) => setDrafts((prev) => ({ ...prev, [channel.id]: e.target.value }))}
                      />
                    </td>
                    <td>
                      <button className="btn-primary" onClick={() => handleSave(channel.id)}>
                        {t('sales_channels.save')}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </PageShell>
    </RoleGuard>
  )
}
