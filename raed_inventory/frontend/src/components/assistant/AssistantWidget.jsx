import React, { useState, useRef, useEffect, useCallback } from 'react'
import { Bot, Send, X, Trash2, Loader2 } from 'lucide-react'
import { useT, useLanguage } from '../../i18n'
import { assistantApi } from '../../services/api'

/**
 * Floating AI Assistant chat widget.
 *
 * - Mounted globally inside AppLayoutV2 (visible only when user is authenticated).
 * - Hidden if backend reports assistant.available === false.
 * - RTL aware: bubble appears on the right side in Arabic, left side in English.
 * - Conversation is held in component state only; refreshing the page clears it.
 *   (Multi-turn persistence is intentionally out of scope for the MVP.)
 */
export default function AssistantWidget() {
  const t = useT()
  const { lang, dir } = useLanguage()
  const [available, setAvailable] = useState(null) // null = not yet checked
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState([]) // [{role, content, lang?, model?}]
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  // Check backend availability once on mount.
  useEffect(() => {
    let cancelled = false
    assistantApi
      .status()
      .then((r) => {
        if (cancelled) return
        setAvailable(Boolean(r?.data?.available))
      })
      .catch(() => {
        if (!cancelled) setAvailable(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  // Auto-scroll to the latest message.
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, loading])

  // Focus input when panel opens.
  useEffect(() => {
    if (open && inputRef.current) {
      inputRef.current.focus()
    }
  }, [open])

  // Show welcome message when panel opens for the first time with no messages.
  useEffect(() => {
    if (open && messages.length === 0) {
      setMessages([{ role: 'assistant', content: t('assistant.welcome'), lang }])
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  const handleSend = useCallback(async () => {
    const question = input.trim()
    if (!question || loading) return

    const userMsg = { role: 'user', content: question }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const r = await assistantApi.ask(question)
      const data = r?.data || {}
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: data.answer || t('assistant.error'),
          lang: data.language,
          model: data.model,
        },
      ])
    } catch (err) {
      const status = err?.response?.status
      const msg =
        status === 429
          ? t('assistant.rate_limit')
          : status === 503
            ? t('assistant.unavailable')
            : t('assistant.error')
      setMessages((prev) => [...prev, { role: 'assistant', content: msg, isError: true }])
    } finally {
      setLoading(false)
    }
  }, [input, loading, t])

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleClear = () => {
    setMessages([{ role: 'assistant', content: t('assistant.welcome'), lang }])
  }

  if (!available) return null

  // Side: in RTL Arabic, the floating button hangs on the LEFT to avoid the
  // sidebar; in LTR English, it sits on the RIGHT for the same reason.
  // Tailwind doesn't have logical inset utilities for floating, so we pick
  // explicit sides based on direction.
  const sideClass = dir === 'rtl' ? 'left-4 md:left-6' : 'right-4 md:right-6'

  return (
    <>
      {/* Floating launcher button */}
      {!open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className={`fixed bottom-4 md:bottom-6 ${sideClass} z-[60] flex items-center gap-2 rounded-full bg-gradient-to-br from-emerald-600 to-emerald-700 px-4 py-3 text-white shadow-lg hover:shadow-xl transition-all hover:scale-105`}
          aria-label={t('assistant.open_button')}
        >
          <Bot size={20} />
          <span className="hidden sm:inline text-sm font-medium">
            {t('assistant.open_button')}
          </span>
        </button>
      )}

      {/* Chat panel */}
      {open && (
        <div
          dir={dir}
          className={`fixed bottom-4 md:bottom-6 ${sideClass} z-[60] flex flex-col w-[min(92vw,400px)] h-[min(80vh,600px)] bg-white rounded-2xl shadow-2xl border border-gray-200 overflow-hidden`}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-emerald-600 to-emerald-700 text-white">
            <div className="flex items-center gap-2">
              <Bot size={20} />
              <span className="font-semibold">{t('assistant.title')}</span>
            </div>
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={handleClear}
                className="p-1.5 rounded-md hover:bg-white/20 transition"
                aria-label={t('assistant.clear')}
                title={t('assistant.clear')}
              >
                <Trash2 size={16} />
              </button>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="p-1.5 rounded-md hover:bg-white/20 transition"
                aria-label={t('assistant.close')}
                title={t('assistant.close')}
              >
                <X size={18} />
              </button>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-3 py-4 space-y-3 bg-gray-50">
            {messages.map((m, idx) => (
              <MessageBubble key={idx} message={m} dir={dir} />
            ))}
            {loading && (
              <div className="flex items-center gap-2 text-gray-500 text-sm px-2">
                <Loader2 size={14} className="animate-spin" />
                <span>{t('assistant.thinking')}</span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="border-t border-gray-200 p-3 bg-white">
            <div className="flex items-end gap-2">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={t('assistant.placeholder')}
                rows={1}
                disabled={loading}
                className="flex-1 resize-none rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 disabled:bg-gray-100"
                style={{ maxHeight: '120px' }}
              />
              <button
                type="button"
                onClick={handleSend}
                disabled={!input.trim() || loading}
                className="rounded-lg bg-emerald-600 text-white p-2 hover:bg-emerald-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition"
                aria-label={t('assistant.send')}
                title={t('assistant.send')}
              >
                <Send size={16} />
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

function MessageBubble({ message, dir }) {
  const isUser = message.role === 'user'
  const align = isUser
    ? dir === 'rtl' ? 'self-start' : 'self-end'
    : dir === 'rtl' ? 'self-end' : 'self-start'
  const bg = isUser
    ? 'bg-emerald-600 text-white'
    : message.isError
      ? 'bg-red-50 text-red-800 border border-red-200'
      : 'bg-white text-gray-900 border border-gray-200'

  return (
    <div className={`flex flex-col max-w-[85%] ${align}`}>
      <div className={`rounded-2xl px-3 py-2 text-sm whitespace-pre-wrap break-words ${bg}`}>
        {message.content}
      </div>
    </div>
  )
}
