import React from 'react'
import { Edit2, Plus, UserRound, UserX } from 'lucide-react'
import toast from 'react-hot-toast'
import { useSelector } from 'react-redux'
import { branchEmployeesApi, masterApi } from '../../services/api'
import { Modal, PageLoader, FormField } from '../../components/common'
import { selectUser, selectUserRoles } from '../../store'
import { useT } from '../../i18n'

const EMPTY_FORM = {
  branch_id: '',
  full_name: '',
  job_title: '',
  work_number: '',
  phone: '',
  active: true,
}

export default function BranchEmployeesPage() {
  const t = useT()
  const user = useSelector(selectUser)
  const roles = useSelector(selectUserRoles)
  const isAdmin = roles.includes('admin') || roles.includes('super_admin')

  const [branches, setBranches] = React.useState([])
  const [selectedBranchId, setSelectedBranchId] = React.useState(user?.branch_id || null)
  const [items, setItems] = React.useState([])
  const [loading, setLoading] = React.useState(true)
  const [modalOpen, setModalOpen] = React.useState(false)
  const [editing, setEditing] = React.useState(null)
  const [form, setForm] = React.useState(EMPTY_FORM)

  React.useEffect(() => {
    if (!isAdmin) return
    let cancelled = false
    masterApi.listBranches({ active_only: true })
      .then((r) => {
        if (cancelled) return
        setBranches(Array.isArray(r?.data) ? r.data : [])
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [isAdmin])

  const load = React.useCallback(async () => {
    if (isAdmin && !selectedBranchId) {
      setItems([])
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const resp = await branchEmployeesApi.list(selectedBranchId ? { branch_id: selectedBranchId } : {})
      setItems(resp.data?.items || [])
    } catch (err) {
      toast.error(err?.response?.data?.message || err?.response?.data?.detail || 'تعذر تحميل موظفي الفرع')
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [isAdmin, selectedBranchId])

  React.useEffect(() => { load() }, [load])

  const openCreate = () => {
    setEditing(null)
    setForm({
      ...EMPTY_FORM,
      branch_id: isAdmin ? (selectedBranchId || '') : (user?.branch_id || ''),
    })
    setModalOpen(true)
  }

  const openEdit = (row) => {
    setEditing(row)
    setForm({
      branch_id: row.branch_id,
      full_name: row.full_name || '',
      job_title: row.job_title || '',
      work_number: row.work_number || '',
      phone: row.phone || '',
      active: row.active !== false,
    })
    setModalOpen(true)
  }

  const handleSave = async () => {
    try {
      const payload = {
        ...form,
        branch_id: isAdmin ? (form.branch_id ? Number(form.branch_id) : null) : undefined,
      }
      if (editing) {
        await branchEmployeesApi.update(editing.id, payload)
        toast.success('تم تحديث الموظف')
      } else {
        await branchEmployeesApi.create(payload)
        toast.success('تمت إضافة الموظف')
      }
      setModalOpen(false)
      await load()
    } catch (err) {
      toast.error(err?.response?.data?.message || err?.response?.data?.detail || 'تعذر حفظ الموظف')
    }
  }

  const handleDeactivate = async (row, nextActive = false) => {
    try {
      await branchEmployeesApi.deactivate(row.id, nextActive)
      toast.success(nextActive ? 'تمت إعادة التفعيل' : 'تم تعطيل الموظف')
      await load()
    } catch (err) {
      toast.error(err?.response?.data?.message || err?.response?.data?.detail || 'تعذر تحديث الحالة')
    }
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('branch_employees.title')}</h1>
          <p className="text-sm text-gray-500 mt-1">{t('branch_employees.subtitle')}</p>
        </div>
        <div className="flex items-center gap-3">
          {isAdmin && (
            <select
              value={selectedBranchId || ''}
              onChange={(e) => setSelectedBranchId(e.target.value ? Number(e.target.value) : null)}
              className="input-field w-72"
            >
              <option value="">{t('branch_employees.select_branch')}</option>
              {branches.map((branch) => (
                <option key={branch.id} value={branch.id}>{branch.branch_name}</option>
              ))}
            </select>
          )}
          <button onClick={openCreate} className="btn-primary">
            <Plus className="w-4 h-4" /> {t('branch_employees.add')}
          </button>
        </div>
      </div>

      {loading ? (
        <PageLoader />
      ) : isAdmin && !selectedBranchId ? (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-6 text-center text-blue-700">
          {t('branch_employees.select_branch_prompt')}
        </div>
      ) : (
        <div className="card table-container">
          <table className="table">
            <thead>
              <tr>
                <th>{t('branch_employees.col_name')}</th>
                <th>{t('branch_employees.col_job_title')}</th>
                <th>{t('branch_employees.col_work_number')}</th>
                <th>{t('branch_employees.col_status')}</th>
                <th>{t('branch_employees.col_created_at')}</th>
                <th>{t('branch_employees.col_actions')}</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-8 text-gray-400">{t('branch_employees.empty')}</td>
                </tr>
              ) : items.map((row) => (
                <tr key={row.id}>
                  <td className="font-medium">{row.full_name}</td>
                  <td>{row.job_title}</td>
                  <td className="font-mono text-xs">{row.work_number}</td>
                  <td>
                    <span className={`status-badge ${row.active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'}`}>
                      {row.active ? t('common.active') : t('branch_employees.inactive')}
                    </span>
                  </td>
                  <td>{row.created_at ? new Date(row.created_at).toLocaleDateString() : '-'}</td>
                  <td>
                    <div className="flex gap-2">
                      <button onClick={() => openEdit(row)} className="p-1.5 hover:bg-gray-100 rounded" title={t('common.edit')}>
                        <Edit2 className="w-4 h-4 text-gray-500" />
                      </button>
                      <button
                        onClick={() => handleDeactivate(row, !row.active)}
                        className="p-1.5 hover:bg-red-50 rounded"
                        title={row.active ? t('branch_employees.deactivate') : t('branch_employees.reactivate')}
                      >
                        {row.active ? <UserX className="w-4 h-4 text-red-500" /> : <UserRound className="w-4 h-4 text-green-600" />}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editing ? t('branch_employees.edit_title') : t('branch_employees.create_title')}
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {isAdmin && (
            <FormField label={t('branch_employees.field_branch')} required>
              <select
                value={form.branch_id || ''}
                onChange={(e) => setForm((prev) => ({ ...prev, branch_id: e.target.value ? Number(e.target.value) : '' }))}
                className="input-field"
              >
                <option value="">{t('branch_employees.select_branch')}</option>
                {branches.map((branch) => (
                  <option key={branch.id} value={branch.id}>{branch.branch_name}</option>
                ))}
              </select>
            </FormField>
          )}
          <FormField label={t('branch_employees.field_name')} required>
            <input
              type="text"
              value={form.full_name}
              onChange={(e) => setForm((prev) => ({ ...prev, full_name: e.target.value }))}
              className="input-field"
            />
          </FormField>
          <FormField label={t('branch_employees.field_job_title')} required>
            <input
              type="text"
              value={form.job_title}
              onChange={(e) => setForm((prev) => ({ ...prev, job_title: e.target.value }))}
              className="input-field"
            />
          </FormField>
          <FormField label={t('branch_employees.field_work_number')} required>
            <input
              type="text"
              value={form.work_number}
              onChange={(e) => setForm((prev) => ({ ...prev, work_number: e.target.value }))}
              className="input-field"
            />
          </FormField>
          <FormField label={t('branch_employees.field_phone')}>
            <input
              type="text"
              value={form.phone}
              onChange={(e) => setForm((prev) => ({ ...prev, phone: e.target.value }))}
              className="input-field"
            />
          </FormField>
        </div>

        <div className="flex justify-end gap-3 mt-6">
          <button onClick={() => setModalOpen(false)} className="btn-secondary">{t('common.cancel')}</button>
          <button onClick={handleSave} className="btn-primary">{editing ? t('common.save') : t('branch_employees.add')}</button>
        </div>
      </Modal>
    </div>
  )
}
