import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import { Eye, EyeOff, Loader2 } from 'lucide-react'
import toast from 'react-hot-toast'
import { loginStart, loginSuccess, loginFail } from '../../store'
import { authApi } from '../../services/api'
import { useT, useLanguage } from '../../i18n'
import {
  LAN_TRIAL_LOGIN_GROUPS,
  LAN_TRIAL_LOGIN_NOTICE_KEY,
  LAN_TRIAL_LOGIN_TITLE_KEY,
  resolveLanTrialPassword,
} from '../../config/lanTrialLoginCards'

function LanTrialLoginCards({ loading, onQuickLogin, t }) {
  return (
    <div className="space-y-4 max-h-[28rem] overflow-y-auto pe-1">
      {LAN_TRIAL_LOGIN_GROUPS.map((group) => (
        <div key={group.groupKey}>
          <p className="text-xs font-semibold text-gray-500 mb-2">{t(group.groupKey)}</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
            {group.accounts.map((account) => (
              <button
                key={account.username}
                type="button"
                disabled={loading}
                onClick={() => onQuickLogin(
                  account.username,
                  resolveLanTrialPassword(account.passwordKind),
                )}
                className="text-right bg-gray-50 hover:bg-gray-100 border border-gray-200
                  rounded-lg p-2 transition-colors cursor-pointer disabled:opacity-50"
              >
                <p className="font-medium text-gray-700">{t(account.labelKey)}</p>
                <p className="text-gray-400 mt-0.5">{account.username}</p>
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

export default function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const { loading, error } = useSelector((s) => s.auth)
  const t = useT()
  const { lang } = useLanguage()

  const formatLoginError = (err) => {
    const data = err?.response?.data
    const d = data?.detail
    if (typeof d === 'string' && d.trim()) return d
    if (Array.isArray(d) && d.length > 0) {
      return d
        .map((e) => (typeof e === 'object' && e?.msg ? e.msg : String(e)))
        .join(' — ')
    }
    if (typeof data?.message === 'string' && data.message.trim()) return data.message
    if (typeof data?.error === 'string' && data.error.trim()) return data.error
    if (err?.code === 'ERR_NETWORK' || err?.message === 'Network Error') {
      return t('auth.error_network')
    }
    return t('auth.error_generic')
  }

  const doLogin = async (u, p) => {
    const normalizedUsername = String(u || '').trim()
    if (!normalizedUsername || !p) return
    dispatch(loginStart())
    try {
      const res = await authApi.login(normalizedUsername, p)
      dispatch(loginSuccess({
        user: res.data.user,
        token: res.data.access_token,
      }))
      toast.success(t('auth.welcome', { name: res.data.user.full_name }))
      const roleList = res.data.user?.roles || []
      const isSuperAdmin = roleList.includes('super_admin')
      const isAdmin = roleList.includes('admin')
      const isInternalAuditor = roleList.includes('internal_auditor')
      const supplyChainRoles = new Set([
        'branch_user', 'branch_manager', 'area_manager', 'kitchen_section_manager',
        'warehouse_user', 'warehouse_manager', 'delivery_user', 'operations_manager',
      ])
      const prefersSupplyChainHome = roleList.some((r) => supplyChainRoles.has(r))
      navigate(
        isSuperAdmin
          ? '/supply-chain/control'
          : isInternalAuditor
            ? '/audit/dashboard'
            : isAdmin
              ? '/dashboard'
              : prefersSupplyChainHome
                ? '/supply-chain/control'
                : '/dashboard',
      )
    } catch (err) {
      const msg = formatLoginError(err)
      dispatch(loginFail(msg))
      toast.error(msg)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    await doLogin(username, password)
  }

  const quickLogin = async (u, p) => {
    setUsername(u)
    setPassword(p)
    await doLogin(u, p)
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-primary-900 via-primary-800 to-primary-700 flex items-center justify-center p-4">
      <div className="w-full max-w-lg">
        <header className="text-center mb-8">
          <div className="w-20 h-20 bg-white/10 backdrop-blur rounded-3xl flex items-center justify-center mx-auto mb-4 border border-white/20">
            <span className="text-white font-black text-4xl">{lang === 'ar' ? 'ر' : 'R'}</span>
          </div>
          <h1 className="text-2xl font-bold text-white">{t('auth.company_title')}</h1>
          <p className="text-primary-200 text-sm mt-1">{t('auth.company_subtitle')}</p>
        </header>

        <section className="bg-white rounded-2xl shadow-2xl p-8" aria-labelledby="login-title">
          <h2 id="login-title" className="text-xl font-bold text-gray-900 mb-6">{t('auth.login')}</h2>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="login-username" className="label">{t('auth.username_or_email')}</label>
              <input
                id="login-username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="input-field"
                placeholder={t('auth.username_placeholder')}
                autoComplete="username"
                required
              />
            </div>

            <div>
              <label htmlFor="login-password" className="label">{t('auth.password')}</label>
              <div className="relative">
                <input
                  id="login-password"
                  type={showPw ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="input-field pl-10"
                  placeholder={t('auth.password_placeholder')}
                  autoComplete="current-password"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPw(!showPw)}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  aria-label={showPw ? 'إخفاء كلمة المرور' : 'إظهار كلمة المرور'}
                >
                  {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-sm text-red-700">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-primary-600 hover:bg-primary-700 disabled:opacity-50
                text-white font-semibold py-2.5 rounded-lg transition-colors
                flex items-center justify-center gap-2"
            >
              {loading && <Loader2 className="w-4 h-4 animate-spin" />}
              {loading ? t('auth.signing_in') : t('auth.submit')}
            </button>
          </form>

          {import.meta.env.DEV && (
            <div className="mt-6 pt-5 border-t border-gray-100 space-y-3">
              <p className="text-sm font-bold text-primary-700 text-center">
                {t(LAN_TRIAL_LOGIN_TITLE_KEY)}
              </p>
              <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 leading-relaxed">
                {t(LAN_TRIAL_LOGIN_NOTICE_KEY)}
              </p>
              <LanTrialLoginCards loading={loading} onQuickLogin={quickLogin} t={t} />
            </div>
          )}
        </section>

        <footer className="text-center text-primary-300 text-xs mt-6">
          {t('auth.copyright')}
        </footer>
      </div>
    </main>
  )
}
