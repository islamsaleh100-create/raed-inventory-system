import React from 'react'
import toast from 'react-hot-toast'
import { masterApi, getApiErrorMessage } from '../../services/api'
import { posTerminalsApi } from '../../services/posTerminalsApi'
import { useT } from '../../i18n'

const PROVIDERS = ['hala', 'nami', 'riyad_bank']
const STATUSES = ['active', 'disabled', 'withdrawn']

function emptyForm() {
  return {
    provider: 'hala',
    terminal_number: '',
    serial_number: '',
    branch_id: '',
    branch_label: '',
    status: 'active',
    notes: '',
  }
}

function renderBranchCell(row, t) {
  if (row.branch_name) {
    return row.branch_name
  }
  if (row.branch_label) {
    return (
      <span className="text-gray-500">
        {row.branch_label}
        <span className="mr-2 inline-block rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
          {t('pos_terminals.unlinked_badge')}
        </span>
      </span>
    )
  }
  return t('pos_terminals.branch_dash')
}

export function PosTerminalsPage() {
  const t = useT()
  const [search, setSearch] = React.useState('')
  const [providerFilter, setProviderFilter] = React.useState('')
  const [statusFilter, setStatusFilter] = React.useState('')
  const [items, setItems] = React.useState([])
  const [total, setTotal] = React.useState(0)
  const [loading, setLoading] = React.useState(true)
  const [branches, setBranches] = React.useState([])
  const [modalOpen, setModalOpen] = React.useState(false)
  const [editing, setEditing] = React.useState(null)
  const [form, setForm] = React.useState(emptyForm())
  const [saving, setSaving] = React.useState(false)

  const load = React.useCallback(async () => {
    setLoading(true)
    try {
      const params = { page: 1, page_size: 100 }
      if (search.trim()) params.search = search.trim()
      if (providerFilter) params.provider = providerFilter
      if (statusFilter) params.status = statusFilter
      const res = await posTerminalsApi.list(params)
      setItems(res.data.items || [])
      setTotal(res.data.total || 0)
    } catch (err) {
      toast.error(getApiErrorMessage(err, t('pos_terminals.load_error')))
    } finally {
      setLoading(false)
    }
  }, [search, providerFilter, statusFilter, t])

  React.useEffect(() => {
    masterApi.listBranches({ active_only: false }).then((res) => setBranches(res.data || [])).catch(() => {})
  }, [])

  React.useEffect(() => {
    const timer = setTimeout(load, 300)
    return () => clearTimeout(timer)
  }, [load])

  const openCreate = () => {
    setEditing(null)
    setForm(emptyForm())
    setModalOpen(true)
  }

  const openEdit = (row) => {
    setEditing(row)
    setForm({
      provider: row.provider,
      terminal_number: row.terminal_number,
      serial_number: row.serial_number || '',
      branch_id: row.branch_id != null ? String(row.branch_id) : '',
      branch_label: row.branch_label || '',
      status: row.status,
      notes: row.notes || '',
    })
    setModalOpen(true)
  }

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    const body = {
      provider: form.provider,
      terminal_number: form.terminal_number.trim(),
      serial_number: form.serial_number.trim() || null,
      branch_id: form.branch_id ? parseInt(form.branch_id, 10) : null,
      branch_label: form.branch_label.trim() || null,
      status: form.status,
      notes: form.notes.trim() || null,
    }
    try {
      if (editing) {
        await posTerminalsApi.update(editing.id, body)
        toast.success(t('pos_terminals.saved'))
      } else {
        await posTerminalsApi.create(body)
        toast.success(t('pos_terminals.created'))
      }
      setModalOpen(false)
      load()
    } catch (err) {
      const msg = getApiErrorMessage(err, t('pos_terminals.save_error'))
      const data = err?.response?.data
      const dupDetail = data?.detail
      if (data?.error_code === 'POS_TERMINAL_DUPLICATE_NUMBER' && dupDetail?.existing_branch_name) {
        toast.error(
          t('pos_terminals.errors.POS_TERMINAL_DUPLICATE_NUMBER', {
            branch: dupDetail.existing_branch_name,
          }),
        )
      } else {
        toast.error(msg)
      }
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="p-6 space-y-6" dir="rtl">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('pos_terminals.title')}</h1>
          <p className="text-sm text-gray-500 mt-1">{t('pos_terminals.subtitle')}</p>
        </div>
        <button type="button" className="btn-primary" onClick={openCreate}>
          {t('pos_terminals.add')}
        </button>
      </div>

      <div className="card p-4 space-y-4">
        <label className="block">
          <span className="text-sm font-medium text-gray-700">{t('pos_terminals.search_label')}</span>
          <input
            className="input-field w-full mt-1 text-lg py-3"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t('pos_terminals.search_placeholder')}
            autoComplete="off"
          />
        </label>
        <div className="flex flex-wrap gap-3">
          <select className="input-field" value={providerFilter} onChange={(e) => setProviderFilter(e.target.value)}>
            <option value="">{t('pos_terminals.filter_all_providers')}</option>
            {PROVIDERS.map((p) => (
              <option key={p} value={p}>{t(`pos_terminals.provider_${p}`)}</option>
            ))}
          </select>
          <select className="input-field" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">{t('pos_terminals.filter_all_statuses')}</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>{t(`pos_terminals.status_${s}`)}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="card overflow-x-auto">
        {loading ? (
          <p className="p-4 text-sm text-gray-500">{t('common.loading')}</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 border-b">
                <th className="p-3 text-right">{t('pos_terminals.col_provider')}</th>
                <th className="p-3 text-right">{t('pos_terminals.col_terminal_number')}</th>
                <th className="p-3 text-right">{t('pos_terminals.col_serial')}</th>
                <th className="p-3 text-right">{t('pos_terminals.col_branch')}</th>
                <th className="p-3 text-right">{t('pos_terminals.col_city')}</th>
                <th className="p-3 text-right">{t('pos_terminals.col_brand')}</th>
                <th className="p-3 text-right">{t('pos_terminals.col_status')}</th>
                <th className="p-3 text-right">{t('common.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={8} className="p-6 text-center text-gray-400">{t('pos_terminals.empty')}</td>
                </tr>
              ) : items.map((row) => (
                <tr key={row.id} className="border-b hover:bg-gray-50">
                  <td className="p-3">{t(`pos_terminals.provider_${row.provider}`)}</td>
                  <td className="p-3 font-mono" dir="ltr">{row.terminal_number}</td>
                  <td className="p-3 font-mono" dir="ltr">{row.serial_number || '—'}</td>
                  <td className="p-3">{renderBranchCell(row, t)}</td>
                  <td className="p-3">{row.city || '—'}</td>
                  <td className="p-3">{(row.brand_names || []).join('، ') || '—'}</td>
                  <td className="p-3">{t(`pos_terminals.status_${row.status}`)}</td>
                  <td className="p-3">
                    <button type="button" className="text-primary-600 hover:underline" onClick={() => openEdit(row)}>
                      {t('common.edit')}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {!loading ? (
          <p className="text-xs text-gray-500 p-3 border-t">{t('pos_terminals.total_rows', { n: total })}</p>
        ) : null}
      </div>

      {modalOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <form className="card w-full max-w-lg p-6 space-y-4" onSubmit={submit}>
            <h2 className="text-lg font-bold">{editing ? t('pos_terminals.edit_title') : t('pos_terminals.add_title')}</h2>
            <label className="block space-y-1">
              <span className="text-xs font-medium">{t('pos_terminals.col_provider')}</span>
              <select className="input-field w-full" value={form.provider} onChange={(e) => setForm((p) => ({ ...p, provider: e.target.value }))} required>
                {PROVIDERS.map((p) => (
                  <option key={p} value={p}>{t(`pos_terminals.provider_${p}`)}</option>
                ))}
              </select>
            </label>
            <label className="block space-y-1">
              <span className="text-xs font-medium">{t('pos_terminals.col_terminal_number')}</span>
              <input className="input-field w-full" value={form.terminal_number} onChange={(e) => setForm((p) => ({ ...p, terminal_number: e.target.value }))} required dir="ltr" />
            </label>
            <label className="block space-y-1">
              <span className="text-xs font-medium">{t('pos_terminals.col_serial')}</span>
              <input className="input-field w-full" value={form.serial_number} onChange={(e) => setForm((p) => ({ ...p, serial_number: e.target.value }))} dir="ltr" />
            </label>
            <label className="block space-y-1">
              <span className="text-xs font-medium">{t('pos_terminals.col_branch')}</span>
              <select className="input-field w-full" value={form.branch_id} onChange={(e) => setForm((p) => ({ ...p, branch_id: e.target.value }))}>
                <option value="">{t('pos_terminals.no_branch')}</option>
                {branches.map((b) => (
                  <option key={b.id} value={b.id}>{b.branch_name} — {b.city}</option>
                ))}
              </select>
            </label>
            <label className="block space-y-1">
              <span className="text-xs font-medium">{t('pos_terminals.branch_label')}</span>
              <input
                className="input-field w-full"
                value={form.branch_label}
                onChange={(e) => setForm((p) => ({ ...p, branch_label: e.target.value }))}
                placeholder={t('pos_terminals.branch_label_placeholder')}
                maxLength={128}
              />
            </label>
            <label className="block space-y-1">
              <span className="text-xs font-medium">{t('pos_terminals.col_status')}</span>
              <select className="input-field w-full" value={form.status} onChange={(e) => setForm((p) => ({ ...p, status: e.target.value }))}>
                {STATUSES.map((s) => (
                  <option key={s} value={s}>{t(`pos_terminals.status_${s}`)}</option>
                ))}
              </select>
            </label>
            <label className="block space-y-1">
              <span className="text-xs font-medium">{t('pos_terminals.col_notes')}</span>
              <textarea className="input-field w-full min-h-[80px]" value={form.notes} onChange={(e) => setForm((p) => ({ ...p, notes: e.target.value }))} />
            </label>
            <div className="flex gap-2 justify-end">
              <button type="button" className="btn-secondary" onClick={() => setModalOpen(false)}>{t('common.cancel')}</button>
              <button type="submit" className="btn-primary" disabled={saving}>{saving ? t('common.saving') : t('common.save')}</button>
            </div>
          </form>
        </div>
      ) : null}
    </div>
  )
}
