import React, { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { masterApi } from '../../services/api'
import { PageLoader } from '../../components/common'
import { useT } from '../../i18n'

export default function KitchensAdminPage() {
  const t = useT()
  const [loading, setLoading] = useState(true)
  const [kitchens, setKitchens] = useState([])
  const [sections, setSections] = useState([])
  const [name, setName] = useState('')
  const [city, setCity] = useState('')
  const [selectedSectionIds, setSelectedSectionIds] = useState(() => new Set())

  const load = async () => {
    setLoading(true)
    try {
      const [k, s] = await Promise.all([
        masterApi.listKitchens({ active_only: false }),
        masterApi.listKitchenSections({ active_only: true }),
      ])
      setKitchens(Array.isArray(k.data) ? k.data : [])
      setSections(Array.isArray(s.data) ? s.data : [])
    } catch (e) {
      toast.error(e?.response?.data?.message || t('admin.kitchens_load_error'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const toggleSection = (id) => {
    setSelectedSectionIds((prev) => {
      const n = new Set(prev)
      if (n.has(id)) n.delete(id)
      else n.add(id)
      return n
    })
  }

  const submit = async (e) => {
    e.preventDefault()
    if (!name.trim() || !city.trim()) {
      toast.error(t('admin.kitchens_required'))
      return
    }
    try {
      await masterApi.createKitchen({
        name: name.trim(),
        city: city.trim(),
        active: true,
        section_ids: Array.from(selectedSectionIds),
      })
      toast.success(t('admin.kitchens_created'))
      setName('')
      setCity('')
      setSelectedSectionIds(new Set())
      await load()
    } catch (err) {
      toast.error(err?.response?.data?.message || err?.response?.data?.detail || t('admin.kitchens_save_error'))
    }
  }

  if (loading) return <PageLoader />

  return (
    <div className="p-6 space-y-8 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{t('admin.kitchens_title')}</h1>
        <p className="text-sm text-gray-500 mt-1">{t('admin.kitchens_subtitle')}</p>
      </div>

      <form onSubmit={submit} className="card p-6 space-y-4">
        <h2 className="font-semibold text-gray-800">{t('admin.kitchens_add')}</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label htmlFor="admin-kitchen-name" className="label">{t('admin.kitchens_name')}</label>
            <input id="admin-kitchen-name" className="input-field" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div>
            <label htmlFor="admin-kitchen-city" className="label">{t('admin.kitchens_city')}</label>
            <input id="admin-kitchen-city" className="input-field" value={city} onChange={(e) => setCity(e.target.value)} />
          </div>
        </div>
        <div>
          <p className="label mb-2">{t('admin.kitchens_sections')}</p>
          <div className="flex flex-wrap gap-2">
            {sections.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => toggleSection(s.id)}
                className={`text-xs px-3 py-1 rounded-full border ${selectedSectionIds.has(s.id) ? 'bg-primary-100 border-primary-400 text-primary-800' : 'bg-white border-gray-200 text-gray-600'}`}
              >
                {s.name}
              </button>
            ))}
          </div>
        </div>
        <button type="submit" className="btn-primary">{t('admin.kitchens_submit')}</button>
      </form>

      <div className="card table-container">
        <table className="table">
          <thead>
            <tr>
              <th>#</th>
              <th>{t('admin.kitchens_name')}</th>
              <th>{t('admin.kitchens_city')}</th>
              <th>{t('admin.kitchens_sections')}</th>
            </tr>
          </thead>
          <tbody>
            {kitchens.length === 0 ? (
              <tr><td colSpan={4} className="text-center text-gray-400 py-8">{t('admin.kitchens_empty')}</td></tr>
            ) : kitchens.map((k) => (
              <tr key={k.id}>
                <td>{k.id}</td>
                <td className="font-medium">{k.name}</td>
                <td>{k.city}</td>
                <td className="text-sm text-gray-600">{(k.section_ids || []).join(', ') || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
