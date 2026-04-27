/**
 * i18n context — Arabic (default) + English.
 *
 * Usage:
 *   import { LanguageProvider, useT, useLanguage } from './i18n'
 *   const t = useT()
 *   <span>{t('nav.dashboard')}</span>
 *
 * Key lookup: dot-path against the current dictionary. Falls back to the
 * Arabic dictionary, then to the raw key string.
 */
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import ar from './dict/ar.json'
import en from './dict/en.json'

const DICTS = { ar, en }
const STORAGE_KEY = 'raed.lang'
const DEFAULT_LANG = 'ar'

const LanguageContext = createContext({
  lang: DEFAULT_LANG,
  dir: 'rtl',
  setLang: () => {},
  toggle: () => {},
  t: (k) => k,
})

function resolveKey(dict, key) {
  if (!key) return ''
  const parts = key.split('.')
  let cur = dict
  for (const p of parts) {
    if (cur && typeof cur === 'object' && p in cur) cur = cur[p]
    else return undefined
  }
  return typeof cur === 'string' ? cur : undefined
}

function interpolate(str, params) {
  if (!params || typeof str !== 'string') return str
  return str.replace(/\{(\w+)\}/g, (_m, name) =>
    params[name] !== undefined && params[name] !== null ? String(params[name]) : `{${name}}`
  )
}

export function LanguageProvider({ children }) {
  const [lang, setLangState] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      if (saved && DICTS[saved]) return saved
    } catch (_e) {}
    return DEFAULT_LANG
  })

  const dir = lang === 'ar' ? 'rtl' : 'ltr'

  // Sync html lang + dir whenever the language changes.
  useEffect(() => {
    try {
      document.documentElement.lang = lang
      document.documentElement.dir = dir
    } catch (_e) {}
  }, [lang, dir])

  const setLang = useCallback((next) => {
    if (!DICTS[next]) return
    setLangState(next)
    try { localStorage.setItem(STORAGE_KEY, next) } catch (_e) {}
  }, [])

  const toggle = useCallback(() => {
    setLang(lang === 'ar' ? 'en' : 'ar')
  }, [lang, setLang])

  const t = useCallback((key, params) => {
    const dict = DICTS[lang] || DICTS[DEFAULT_LANG]
    const hit = resolveKey(dict, key)
    if (typeof hit === 'string') return interpolate(hit, params)
    // Fallback to default dictionary
    const fb = resolveKey(DICTS[DEFAULT_LANG], key)
    if (typeof fb === 'string') return interpolate(fb, params)
    return key
  }, [lang])

  const value = useMemo(() => ({ lang, dir, setLang, toggle, t }), [lang, dir, setLang, toggle, t])

  return (
    <LanguageContext.Provider value={value}>
      {children}
    </LanguageContext.Provider>
  )
}

export function useLanguage() {
  return useContext(LanguageContext)
}

export function useT() {
  return useContext(LanguageContext).t
}
