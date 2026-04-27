/**
 * Sentry SDK scaffold (Vite + React).
 *
 * التفعيل شرطي: يعتمد على VITE_SENTRY_DSN في env. إن لم يكن موجودًا أو إن
 * لم تُثبَّت الحزمة `@sentry/react`، تعود الدالة بهدوء بدون كسر الـ build.
 *
 * لتفعيله:
 *   1. npm i @sentry/react
 *   2. عيِّن VITE_SENTRY_DSN في .env.production
 *
 * ملاحظة: main.jsx يستورد هذا الملف بشكل lazy فقط إذا VITE_SENTRY_DSN موجود،
 * وبالتالي Vite لا يفحص الـ `@sentry/react` import في بيئة التطوير العادية.
 */

export async function initSentry() {
  const dsn = import.meta.env.VITE_SENTRY_DSN
  if (!dsn) return false

  try {
    // NOTE: package name is held in a variable + /* @vite-ignore */ so that
    // Vite's import-analysis does NOT try to pre-resolve this at dev time.
    // بدون هذا، Vite يرمي "Failed to resolve import '@sentry/react'"
    // حتى لو كان الاستيراد ديناميكيًا داخل try/catch والحزمة غير مثبّتة.
    const pkg = '@sentry/react'
    const Sentry = await import(/* @vite-ignore */ pkg)
    const env = import.meta.env.MODE || 'development'
    const tracesRate = env === 'production' ? 0.1 : 0.0

    Sentry.init({
      dsn,
      environment: env,
      release: import.meta.env.VITE_APP_VERSION || '1.0.0',
      tracesSampleRate: tracesRate,
      // لا نرسل PII (cookies, IP) افتراضيًا
      sendDefaultPii: false,
      beforeSend(event) {
        // جرّد أي Authorization/Idempotency headers إذا ظهرت في الـ breadcrumbs
        if (event.request?.headers) {
          delete event.request.headers.Authorization
          delete event.request.headers['X-Idempotency-Key']
        }
        return event
      },
    })
    // eslint-disable-next-line no-console
    console.info(`[Sentry] initialised (env=${env}, traces=${tracesRate})`)
    return true
  } catch (err) {
    // @sentry/react غير مثبّت — نتجاهل بهدوء
    // eslint-disable-next-line no-console
    console.debug('[Sentry] @sentry/react not installed — monitoring disabled')
    return false
  }
}
