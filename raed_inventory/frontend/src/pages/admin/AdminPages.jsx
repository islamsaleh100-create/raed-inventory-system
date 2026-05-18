import React, { useState, useEffect } from 'react'
import { Plus, Edit2, Trash2, Search } from 'lucide-react'
import toast from 'react-hot-toast'
import { masterApi, usersApi } from '../../services/api'
import { PageLoader, Modal, Pagination, SearchInput, FormField, StatusBadge } from '../../components/common'
import { ROLE_LABELS } from '../../utils/helpers'
import { useT, useLanguage } from '../../i18n'

// ─── Items Management ──────────────────────────────────────────────────
export function ItemsManagementPage() {
  const t = useT()
  const { lang } = useLanguage()
  const nameOf = (obj, base) => obj?.[`${base}_${lang}`] || obj?.[`${base}_ar`] || obj?.[base] || ''
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [categories, setCategories] = useState([])
  const [units, setUnits] = useState([])
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState({
    item_code: '', item_name_ar: '', item_name_en: '',
    category_id: '', unit_id: '', min_qty: 0, max_qty: 0,
    reorder_point: 0, safety_stock: 0, lead_time_days: 1,
    critical_item: false, branch_requestable: true, active: true,
    average_consumption_mode: 'last_7_days',
  })

  useEffect(() => {
    Promise.all([masterApi.listCategories(), masterApi.listUnits()])
      .then(([c, u]) => { setCategories(c.data); setUnits(u.data) })
  }, [])

  const load = (p = 1, q = search) => {
    setLoading(true)
    masterApi.listItems({ page: p, page_size: 20, search: q || undefined, active_only: false })
      .then((r) => { setItems(r.data.items); setTotal(r.data.total) })
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const openCreate = () => {
    setEditing(null)
    setForm({
      item_code: '', item_name_ar: '', item_name_en: '',
      category_id: categories[0]?.id || '', unit_id: units[0]?.id || '',
      min_qty: 0, max_qty: 0, reorder_point: 0, safety_stock: 0,
      lead_time_days: 1, critical_item: false, branch_requestable: true,
      active: true, average_consumption_mode: 'last_7_days',
    })
    setModalOpen(true)
  }

  const openEdit = (item) => {
    setEditing(item)
    setForm({
      item_code: item.item_code,
      item_name_ar: item.item_name_ar,
      item_name_en: item.item_name_en,
      category_id: item.category_id,
      unit_id: item.unit_id,
      min_qty: item.min_qty,
      max_qty: item.max_qty,
      reorder_point: item.reorder_point,
      safety_stock: item.safety_stock,
      lead_time_days: item.lead_time_days,
      critical_item: item.critical_item,
      branch_requestable: item.branch_requestable,
      active: item.active,
      average_consumption_mode: item.average_consumption_mode,
    })
    setModalOpen(true)
  }

  const handleSave = async () => {
    try {
      if (editing) {
        await masterApi.updateItem(editing.id, form)
        toast.success(t('admin.items_toast_updated'))
      } else {
        await masterApi.createItem(form)
        toast.success(t('admin.items_toast_created'))
      }
      setModalOpen(false)
      load()
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('admin.error_generic'))
    }
  }

  const handleDelete = async (id) => {
    if (!confirm(t('admin.items_confirm_delete'))) return
    try {
      await masterApi.deleteItem(id)
      toast.success(t('admin.items_toast_deleted'))
      load()
    } catch (err) {
      toast.error(t('admin.items_delete_error'))
    }
  }

  if (loading && items.length === 0) return <PageLoader />

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{t('admin.items_title')}</h1>
        <button onClick={openCreate} className="btn-primary">
          <Plus className="w-4 h-4" /> {t('admin.items_add')}
        </button>
      </div>

      <div className="flex gap-3 mb-4">
        <SearchInput
          value={search}
          onChange={(v) => { setSearch(v); load(1, v) }}
          placeholder={t('admin.items_search_placeholder')}
          className="w-64"
        />
      </div>

      <div className="card">
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>{t('admin.items_col_code')}</th>
                <th>{t('admin.items_col_name_ar')}</th>
                <th>{t('admin.items_col_category')}</th>
                <th>{t('admin.items_col_unit')}</th>
                <th>{t('admin.items_col_min_qty')}</th>
                <th>{t('admin.items_col_critical')}</th>
                <th>{t('admin.items_col_status')}</th>
                <th>{t('admin.items_col_actions')}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td className="font-mono text-xs">{item.item_code}</td>
                  <td className="font-medium">{nameOf(item, 'item_name')}</td>
                  <td className="text-xs text-gray-500">{nameOf(item.category, 'name')}</td>
                  <td className="text-xs">{nameOf(item.unit, 'name')}</td>
                  <td>{item.min_qty}</td>
                  <td>
                    {item.critical_item && (
                      <span className="status-badge bg-red-100 text-red-700 text-xs">{t('admin.items_critical_badge')}</span>
                    )}
                  </td>
                  <td>
                    <span className={`status-badge ${item.active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                      {item.active ? t('admin.active') : t('admin.items_status_inactive')}
                    </span>
                  </td>
                  <td>
                    <div className="flex gap-2">
                      <button onClick={() => openEdit(item)} className="p-1.5 hover:bg-gray-100 rounded" title={t('common.edit')}>
                        <Edit2 className="w-4 h-4 text-gray-500" />
                      </button>
                      <button onClick={() => handleDelete(item.id)} className="p-1.5 hover:bg-red-50 rounded" title={t('common.delete')}>
                        <Trash2 className="w-4 h-4 text-red-400" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Pagination total={total} page={page} pageSize={20}
          onChange={(p) => { setPage(p); load(p) }} />
      </div>

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editing ? t('admin.items_modal_edit_title') : t('admin.items_modal_create_title')}
        size="lg"
      >
        <div className="grid grid-cols-2 gap-4">
          <FormField label={t('admin.items_field_code')} required>
            <input type="text" value={form.item_code}
              onChange={(e) => setForm((p) => ({ ...p, item_code: e.target.value }))}
              className="input-field" placeholder={t('admin.items_code_placeholder')} disabled={!!editing} />
          </FormField>
          <FormField label={t('admin.items_field_unit')} required>
            <select value={form.unit_id}
              onChange={(e) => setForm((p) => ({ ...p, unit_id: e.target.value }))}
              className="input-field">
              {units.map((u) => <option key={u.id} value={u.id}>{nameOf(u, 'name')}</option>)}
            </select>
          </FormField>
          <FormField label={t('admin.items_field_name_ar')} required>
            <input type="text" value={form.item_name_ar}
              onChange={(e) => setForm((p) => ({ ...p, item_name_ar: e.target.value }))}
              className="input-field" placeholder={t('admin.items_name_ar_placeholder')} />
          </FormField>
          <FormField label={t('admin.items_field_name_en')}>
            <input type="text" value={form.item_name_en}
              onChange={(e) => setForm((p) => ({ ...p, item_name_en: e.target.value }))}
              className="input-field" placeholder={t('admin.items_name_en_placeholder')} />
          </FormField>
          <FormField label={t('admin.items_field_category')} required>
            <select value={form.category_id}
              onChange={(e) => setForm((p) => ({ ...p, category_id: e.target.value }))}
              className="input-field">
              {categories.map((c) => <option key={c.id} value={c.id}>{nameOf(c, 'name')}</option>)}
            </select>
          </FormField>
          <FormField label={t('admin.items_field_min_qty')}>
            <input type="number" min="0" value={form.min_qty}
              onChange={(e) => setForm((p) => ({ ...p, min_qty: e.target.value }))}
              className="input-field" />
          </FormField>
          <FormField label={t('admin.items_field_max_qty')}>
            <input type="number" min="0" value={form.max_qty}
              onChange={(e) => setForm((p) => ({ ...p, max_qty: e.target.value }))}
              className="input-field" />
          </FormField>
          <FormField label={t('admin.items_field_reorder_point')}>
            <input type="number" min="0" value={form.reorder_point}
              onChange={(e) => setForm((p) => ({ ...p, reorder_point: e.target.value }))}
              className="input-field" />
          </FormField>
          <FormField label={t('admin.items_field_safety_stock')}>
            <input type="number" min="0" value={form.safety_stock}
              onChange={(e) => setForm((p) => ({ ...p, safety_stock: e.target.value }))}
              className="input-field" />
          </FormField>
          <FormField label={t('admin.items_field_lead_time_days')}>
            <input type="number" min="1" value={form.lead_time_days}
              onChange={(e) => setForm((p) => ({ ...p, lead_time_days: e.target.value }))}
              className="input-field" />
          </FormField>
          <div className="col-span-2 flex gap-6">
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={form.critical_item}
                onChange={(e) => setForm((p) => ({ ...p, critical_item: e.target.checked }))}
                className="rounded" />
              <span className="text-sm font-medium">{t('admin.items_checkbox_critical')}</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={form.branch_requestable}
                onChange={(e) => setForm((p) => ({ ...p, branch_requestable: e.target.checked }))}
                className="rounded" />
              <span className="text-sm font-medium">{t('admin.items_checkbox_branch_requestable')}</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={form.active}
                onChange={(e) => setForm((p) => ({ ...p, active: e.target.checked }))}
                className="rounded" />
              <span className="text-sm font-medium">{t('admin.items_checkbox_active')}</span>
            </label>
          </div>
        </div>
        <div className="flex justify-end gap-3 mt-6">
          <button onClick={() => setModalOpen(false)} className="btn-secondary">{t('common.cancel')}</button>
          <button onClick={handleSave} className="btn-primary">
            {editing ? t('admin.btn_update') : t('admin.btn_create_short')}
          </button>
        </div>
      </Modal>
    </div>
  )
}

// ─── Users Management ──────────────────────────────────────────────────
export function UsersManagementPage() {
  const t = useT()
  const [users, setUsers] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [branches, setBranches] = useState([])
  const [warehouses, setWarehouses] = useState([])
  const [availableRoles, setAvailableRoles] = useState([])
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState({
    username: '', email: '', full_name: '', password: '',
    phone: '', branch_id: '', warehouse_id: '',
    role_names: [], status: 'active',
  })

  const FALLBACK_ROLES = [
    'super_admin', 'admin', 'internal_auditor',
    'branch_user', 'branch_manager',
    'warehouse_user', 'warehouse_manager',
    'operations_manager',
    'quality_visitor', 'quality_manager', 'trainer',
    'area_manager', 'evaluator', 'hr_manager',
    'sales_manager',
    'kitchen_manager', 'kitchen_section_manager', 'delivery_user',
  ]

  useEffect(() => {
    Promise.allSettled([masterApi.listBranches(), masterApi.listWarehouses(), usersApi.roles()])
      .then(([branchesResult, warehousesResult, rolesResult]) => {
        if (branchesResult.status === 'fulfilled') setBranches(branchesResult.value.data || [])
        if (warehousesResult.status === 'fulfilled') setWarehouses(warehousesResult.value.data || [])

        const rolesData = rolesResult.status === 'fulfilled' ? rolesResult.value.data : []
        const roleNames = (rolesData || []).map((role) => role.name).filter(Boolean)
        setAvailableRoles(roleNames.length ? roleNames : FALLBACK_ROLES)
      })
  }, [])

  const load = (p = 1) => {
    setLoading(true)
    usersApi.list({ page: p, page_size: 20, search: search || undefined })
      .then((r) => { setUsers(r.data.items); setTotal(r.data.total) })
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const openCreate = () => {
    setEditing(null)
    setForm({ username: '', email: '', full_name: '', password: '', phone: '', branch_id: '', warehouse_id: '', role_names: [], status: 'active' })
    setModalOpen(true)
  }

  const openEdit = (user) => {
    setEditing(user)
    setForm({
      username: user.username, email: user.email, full_name: user.full_name,
      password: '', phone: user.phone || '',
      branch_id: user.branch_id || '',
      warehouse_id: user.warehouse_id || '',
      role_names: user.roles || [],
      status: user.status,
    })
    setModalOpen(true)
  }

  const toggleRole = (role) => {
    setForm((p) => ({
      ...p,
      role_names: p.role_names.includes(role)
        ? p.role_names.filter((r) => r !== role)
        : [...p.role_names, role]
    }))
  }

  const handleSave = async () => {
    try {
      const payload = { ...form }
      if (!payload.branch_id) delete payload.branch_id
      if (!payload.warehouse_id) delete payload.warehouse_id
      if (editing && !payload.password) delete payload.password
      if (editing) {
        await usersApi.update(editing.id, payload)
        toast.success(t('admin.users_toast_updated'))
      } else {
        await usersApi.create(payload)
        toast.success(t('admin.users_toast_created'))
      }
      setModalOpen(false)
      load()
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('admin.users_toast_error'))
    }
  }

  const handleDelete = async (user) => {
    const msg = t('admin.users_confirm_delete', { name: user.full_name || user.username })
      || `هل أنت متأكد من حذف المستخدم "${user.full_name || user.username}"؟`
    if (!confirm(msg)) return
    try {
      await usersApi.delete(user.id)
      toast.success(t('admin.users_toast_deleted') || 'تم حذف المستخدم')
      load()
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('admin.users_toast_delete_error') || 'فشل الحذف')
    }
  }

  if (loading && users.length === 0) return <PageLoader />

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{t('admin.users_title')}</h1>
        <button onClick={openCreate} className="btn-primary">
          <Plus className="w-4 h-4" /> {t('admin.users_add')}
        </button>
      </div>

      <div className="flex gap-3 mb-4">
        <SearchInput value={search} onChange={(v) => { setSearch(v); load(1) }}
          placeholder={t('admin.users_search_placeholder')} className="w-64" />
      </div>

      <div className="card">
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>{t('admin.users_col_user')}</th>
                <th>{t('admin.users_col_email')}</th>
                <th>{t('admin.users_col_roles')}</th>
                <th>{t('admin.users_col_branch')}</th>
                <th>{t('admin.users_col_status')}</th>
                <th>{t('admin.users_col_actions')}</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>
                    <div>
                      <p className="font-medium">{u.full_name}</p>
                      <p className="text-xs text-gray-400">@{u.username}</p>
                    </div>
                  </td>
                  <td className="text-sm text-gray-600">{u.email}</td>
                  <td>
                    <div className="flex flex-wrap gap-1">
                      {u.roles?.map((r) => (
                        <span key={r} className="status-badge bg-blue-50 text-blue-700 text-[10px]">
                          {t(`roles.${r}`) || ROLE_LABELS[r] || r}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="text-sm text-gray-500">{u.branch_id ? t('admin.users_branch_display', { id: u.branch_id }) : '—'}</td>
                  <td><StatusBadge status={u.status} /></td>
                  <td>
                    <div className="flex gap-2">
                      <button onClick={() => openEdit(u)} className="p-1.5 hover:bg-gray-100 rounded" title={t('common.edit')}>
                        <Edit2 className="w-4 h-4 text-gray-500" />
                      </button>
                      <button onClick={() => handleDelete(u)} className="p-1.5 hover:bg-red-50 rounded" title={t('common.delete')}>
                        <Trash2 className="w-4 h-4 text-red-400" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Pagination total={total} page={page} pageSize={20} onChange={(p) => { setPage(p); load(p) }} />
      </div>

      <Modal open={modalOpen} onClose={() => setModalOpen(false)}
        title={editing ? t('admin.users_modal_edit_title') : t('admin.users_modal_create_title')} size="lg">
        <div className="grid grid-cols-2 gap-4">
          <FormField label={t('admin.users_field_username')} required>
            <input type="text" value={form.username}
              onChange={(e) => setForm((p) => ({ ...p, username: e.target.value }))}
              className="input-field" disabled={!!editing} />
          </FormField>
          <FormField label={t('admin.users_field_full_name')} required>
            <input type="text" value={form.full_name}
              onChange={(e) => setForm((p) => ({ ...p, full_name: e.target.value }))}
              className="input-field" />
          </FormField>
          <FormField label={t('admin.users_field_email')} required>
            <input type="email" value={form.email}
              onChange={(e) => setForm((p) => ({ ...p, email: e.target.value }))}
              className="input-field" />
          </FormField>
          <FormField label={editing ? t('admin.users_field_password_edit') : t('admin.users_field_password')} required={!editing}>
            <input type="password" value={form.password}
              onChange={(e) => setForm((p) => ({ ...p, password: e.target.value }))}
              className="input-field" placeholder={editing ? t('admin.users_password_placeholder_edit') : ''} />
          </FormField>
          <FormField label={t('admin.users_field_branch')}>
            <select value={form.branch_id}
              onChange={(e) => setForm((p) => ({ ...p, branch_id: e.target.value }))}
              className="input-field">
              <option value="">{t('admin.users_branch_placeholder')}</option>
              {branches.map((b) => <option key={b.id} value={b.id}>{b.branch_name}</option>)}
            </select>
          </FormField>
          <FormField label={t('admin.users_field_warehouse')}>
            <select value={form.warehouse_id}
              onChange={(e) => setForm((p) => ({ ...p, warehouse_id: e.target.value }))}
              className="input-field">
              <option value="">{t('admin.users_branch_placeholder')}</option>
              {warehouses.map((w) => <option key={w.id} value={w.id}>{w.warehouse_name}</option>)}
            </select>
          </FormField>
          <div className="col-span-2">
            <label className="label">{t('admin.users_field_roles')}</label>
            <div className="flex flex-wrap gap-2">
              {(availableRoles.length ? availableRoles : FALLBACK_ROLES).map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => toggleRole(r)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors
                    ${form.role_names.includes(r)
                      ? 'bg-primary-600 text-white border-primary-600'
                      : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'
                    }`}
                >
                  {t(`roles.${r}`) || ROLE_LABELS[r] || r}
                </button>
              ))}
            </div>
          </div>
          {editing && (
            <FormField label={t('admin.users_field_status')}>
              <select value={form.status}
                onChange={(e) => setForm((p) => ({ ...p, status: e.target.value }))}
                className="input-field">
                <option value="active">{t('admin.users_status_active')}</option>
                <option value="inactive">{t('admin.users_status_inactive')}</option>
                <option value="suspended">{t('admin.users_status_suspended')}</option>
              </select>
            </FormField>
          )}
        </div>
        <div className="flex justify-end gap-3 mt-6">
          <button onClick={() => setModalOpen(false)} className="btn-secondary">{t('common.cancel')}</button>
          <button onClick={handleSave} className="btn-primary">{editing ? t('admin.users_btn_update') : t('admin.users_btn_create')}</button>
        </div>
      </Modal>
    </div>
  )
}
