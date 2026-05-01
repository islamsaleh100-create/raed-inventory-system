import React, { useCallback, useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { Lightbulb, AlertTriangle, Bug, Wrench, MoreHorizontal, Save, X, Pencil } from 'lucide-react'
import { assistantApi } from '../../services/api'
import { PageLoader } from '../../components/common'
import { useT, useLanguage } from '../../i18n'

const STATUSES = ['pending', 'reviewed', 'approved', 'rejected', 'implemented']
const CATEGORIES = ['ui', 'workflow', 'bug', 'feature', 'other']
const PRIORITIES = ['low', 'medium', 'high']

const CATEGORY_ICON = {
  ui: Wrench,
  workflow: MoreHorizontal,
  bug: Bug,
  feature: Lightbulb,
  other: AlertTriangle,
}

const PRIORITY_BADGE = {
  high: 'bg-red-100 text-red-700 border border-red-200',
  medium: 'bg-amber-100 text-amber-700 border border-amber-200',
  low: 'bg-gray-100 text-gray-700 border border-gray-200',
}

const STATUS_BADGE = {
  pending: 'bg-amber-50 text-amber-700 border border-amber-200',
  reviewed: 'bg-blue-50 text-blue-700 border border-blue-200',
  approved: 'bg-emerald-50 text-emerald-700 border border-emerald-200',
  rejected: 'bg-red-50 text-red-700 border border-red-200',
  implemented: 'bg-purple-50 text-purple-700 border border-purple-200',
}

export default function AssistantSuggestionsPage() {
  const t = useT()
  const { dir } = useLanguage()

  const [loading, setLoading] = useState(true)
  const [stats, setStats] = useState(null)
  const [rows, setRows] = useState([])
  const [filters, setFilters] = useState({ status: '', category: '', priority: '' })
  const [editingId, setEditingId] = useState(null)
  const [editDraft, setEditDraft] = useState({ status: '', admin_note: '' })

  const loadAll = useCallback(async () => {
    setLoading(true)
    try {
      const params = {}
      if (filters.status) params.status = filters.status
      if (filters.category) params.category = filters.category
      if (filters.priority) params.priority = filters.priority

      const [statsRes, listRes] = await Promise.all([
        assistantApi.suggestionsStats(),
        assistantApi.listSuggestions(params),
      ])
      setStats(statsRes?.data || null)
      setRows(Array.isArray(listRes?.data) ? listRes.data : [])
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('assistant.suggestions.load_error'))
    } finally {
      setLoading(false)
    }
  }, [filters.status, filters.category, filters.priority, t])

  useEffect(() => {
    loadAll()
  }, [loadAll])

  const startEdit = (row) => {
    setEditingId(row.id)
    setEditDraft({ status: row.status, admin_note: row.admin_note || '' })
  }

  const cancelEdit = () => {
    setEditingId(null)
    setEditDraft({ status: '', admin_note: '' })
  }

  const saveEdit = async (id) => {
    try {
      await assistantApi.updateSuggestion(id, {
        status: editDraft.status,
        admin_note: editDraft.admin_note || null,
      })
      toast.success(t('assistant.suggestions.saved'))
      cancelEdit()
      await loadAll()
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('assistant.suggestions.save_error'))
    }
  }

  if (loading && !stats) return <PageLoader />

  return (
    <div className="p-6 space-y-6 max-w-7xl" dir={dir}>
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{t('assistant.suggestions.page_title')}</h1>
        <p className="text-sm text-gray-500 mt-1">{t('assistant.suggestions.page_subtitle')}</p>
      </div>

      {stats && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard label={t('assistant.suggestions.stats_total')} value={stats.total} accent="emerald" />
          <StatCard label={t('assistant.suggestions.stats_pending')} value={stats.pending} accent="amber" />
          <BreakdownCard
            label={t('assistant.suggestions.stats_by_category')}
            entries={stats.by_category}
            translateKey={(k) => t(`assistant.suggestions.category.${k}`)}
          />
          <BreakdownCard
            label={t('assistant.suggestions.stats_by_priority')}
            entries={stats.by_priority}
            translateKey={(k) => t(`assistant.suggestions.priority.${k}`)}
          />
        </div>
      )}

      <div className="card p-4 flex flex-wrap gap-3 items-end">
        <FilterSelect
          label={t('assistant.suggestions.filter_status')}
          value={filters.status}
          onChange={(v) => setFilters({ ...filters, status: v })}
          options={STATUSES}
          translateKey={(k) => t(`assistant.suggestions.status_label.${k}`)}
          allLabel={t('assistant.suggestions.filter_all')}
        />
        <FilterSelect
          label={t('assistant.suggestions.filter_category')}
          value={filters.category}
          onChange={(v) => setFilters({ ...filters, category: v })}
          options={CATEGORIES}
          translateKey={(k) => t(`assistant.suggestions.category.${k}`)}
          allLabel={t('assistant.suggestions.filter_all')}
        />
        <FilterSelect
          label={t('assistant.suggestions.filter_priority')}
          value={filters.priority}
          onChange={(v) => setFilters({ ...filters, priority: v })}
          options={PRIORITIES}
          translateKey={(k) => t(`assistant.suggestions.priority.${k}`)}
          allLabel={t('assistant.suggestions.filter_all')}
        />
      </div>

      <div className="card overflow-hidden">
        {rows.length === 0 ? (
          <div className="p-8 text-center text-gray-500">{t('assistant.suggestions.empty')}</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <Th>{t('assistant.suggestions.col_id')}</Th>
                  <Th>{t('assistant.suggestions.col_user')}</Th>
                  <Th>{t('assistant.suggestions.col_branch')}</Th>
                  <Th className="min-w-[260px]">{t('assistant.suggestions.col_text')}</Th>
                  <Th>{t('assistant.suggestions.col_category')}</Th>
                  <Th>{t('assistant.suggestions.col_priority')}</Th>
                  <Th>{t('assistant.suggestions.col_status')}</Th>
                  <Th>{t('assistant.suggestions.col_date')}</Th>
                  <Th>{t('assistant.suggestions.col_actions')}</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 bg-white">
                {rows.map((r) => {
                  const Icon = CATEGORY_ICON[r.category] || Lightbulb
                  const isEditing = editingId === r.id
                  return (
                    <tr key={r.id} className="hover:bg-gray-50">
                      <Td className="font-mono text-xs text-gray-500">#{r.id}</Td>
                      <Td>
                        <div className="text-sm text-gray-900">{r.user_username || `#${r.user_id}`}</div>
                        <div className="text-xs text-gray-500">{r.role_at_creation}</div>
                      </Td>
                      <Td className="text-sm text-gray-700">{r.branch_name || '-'}</Td>
                      <Td>
                        <div className="text-sm text-gray-900 whitespace-pre-wrap break-words max-w-xl">
                          {r.suggestion_text}
                        </div>
                        {(r.admin_note || isEditing) && (
                          <div className="mt-2">
                            {isEditing ? (
                              <textarea
                                className="input-field text-xs"
                                rows={2}
                                value={editDraft.admin_note}
                                onChange={(e) => setEditDraft({ ...editDraft, admin_note: e.target.value })}
                                placeholder={t('assistant.suggestions.admin_note_placeholder')}
                              />
                            ) : (
                              <div className="text-xs text-gray-600 bg-gray-50 rounded px-2 py-1">
                                <span className="font-medium">{t('assistant.suggestions.admin_note')}:</span>{' '}
                                {r.admin_note}
                              </div>
                            )}
                          </div>
                        )}
                      </Td>
                      <Td>
                        <div className="inline-flex items-center gap-1.5 text-xs text-gray-700">
                          <Icon size={14} />
                          {t(`assistant.suggestions.category.${r.category}`)}
                        </div>
                      </Td>
                      <Td>
                        <span className={`inline-block px-2 py-0.5 rounded-full text-xs ${PRIORITY_BADGE[r.priority] || 'bg-gray-100 text-gray-700'}`}>
                          {t(`assistant.suggestions.priority.${r.priority}`)}
                        </span>
                      </Td>
                      <Td>
                        {isEditing ? (
                          <select
                            className="input-field text-xs py-1"
                            value={editDraft.status}
                            onChange={(e) => setEditDraft({ ...editDraft, status: e.target.value })}
                          >
                            {STATUSES.map((s) => (
                              <option key={s} value={s}>
                                {t(`assistant.suggestions.status_label.${s}`)}
                              </option>
                            ))}
                          </select>
                        ) : (
                          <span className={`inline-block px-2 py-0.5 rounded-full text-xs ${STATUS_BADGE[r.status] || 'bg-gray-100 text-gray-700'}`}>
                            {t(`assistant.suggestions.status_label.${r.status}`)}
                          </span>
                        )}
                      </Td>
                      <Td className="text-xs text-gray-500 whitespace-nowrap">
                        {r.created_at ? new Date(r.created_at).toLocaleString() : '-'}
                      </Td>
                      <Td>
                        {isEditing ? (
                          <div className="flex items-center gap-1">
                            <button
                              type="button"
                              onClick={() => saveEdit(r.id)}
                              className="p-1.5 rounded-md text-emerald-700 hover:bg-emerald-50"
                              title={t('assistant.suggestions.save')}
                            >
                              <Save size={16} />
                            </button>
                            <button
                              type="button"
                              onClick={cancelEdit}
                              className="p-1.5 rounded-md text-gray-600 hover:bg-gray-100"
                              title={t('assistant.suggestions.cancel')}
                            >
                              <X size={16} />
                            </button>
                          </div>
                        ) : (
                          <button
                            type="button"
                            onClick={() => startEdit(r)}
                            className="p-1.5 rounded-md text-gray-700 hover:bg-gray-100"
                            title={t('assistant.suggestions.edit')}
                          >
                            <Pencil size={16} />
                          </button>
                        )}
                      </Td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

function StatCard({ label, value, accent }) {
  const accentMap = {
    emerald: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    amber: 'bg-amber-50 text-amber-700 border-amber-200',
  }
  const cls = accentMap[accent] || 'bg-gray-50 text-gray-700 border-gray-200'
  return (
    <div className={`rounded-xl border p-4 ${cls}`}>
      <div className="text-xs uppercase tracking-wide opacity-70">{label}</div>
      <div className="text-3xl font-bold mt-1">{value ?? 0}</div>
    </div>
  )
}

function BreakdownCard({ label, entries, translateKey }) {
  const items = Object.entries(entries || {})
  return (
    <div className="rounded-xl border bg-white border-gray-200 p-4">
      <div className="text-xs uppercase tracking-wide text-gray-500">{label}</div>
      <div className="mt-2 space-y-1">
        {items.length === 0 ? (
          <div className="text-sm text-gray-400">-</div>
        ) : (
          items.map(([k, v]) => (
            <div key={k} className="flex justify-between items-center text-sm">
              <span className="text-gray-700">{translateKey ? translateKey(k) : k}</span>
              <span className="font-semibold text-gray-900">{v}</span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

function FilterSelect({ label, value, onChange, options, translateKey, allLabel }) {
  return (
    <div>
      <label className="label">{label}</label>
      <select className="input-field" value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">{allLabel}</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {translateKey ? translateKey(o) : o}
          </option>
        ))}
      </select>
    </div>
  )
}

function Th({ children, className = '' }) {
  return (
    <th className={`px-3 py-2 text-start text-xs font-semibold text-gray-600 uppercase tracking-wide ${className}`}>
      {children}
    </th>
  )
}

function Td({ children, className = '' }) {
  return <td className={`px-3 py-3 align-top ${className}`}>{children}</td>
}
