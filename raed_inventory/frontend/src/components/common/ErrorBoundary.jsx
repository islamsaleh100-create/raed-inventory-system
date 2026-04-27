import React from 'react'

/**
 * React Error Boundary.
 *
 * يمسك أي خطأ غير متوقع في الشجرة ويعرض شاشة احتياطية بدلاً من Whitescreen.
 * - في production: رسالة عربية مهذبة + زر إعادة تحميل.
 * - في development: تفاصيل الخطأ (stack) تظهر للمطوّر.
 *
 * الاستخدام:
 *   <ErrorBoundary>
 *     <App />
 *   </ErrorBoundary>
 */
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null, info: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error('[ErrorBoundary] caught:', error, info?.componentStack)
    this.setState({ info })
  }

  handleReload = () => {
    window.location.reload()
  }

  handleGoHome = () => {
    window.location.assign('/dashboard')
  }

  render() {
    if (!this.state.hasError) return this.props.children

    const isDev = import.meta.env.DEV
    const { error, info } = this.state

    return (
      <div
        dir="rtl"
        className="min-h-screen bg-gray-50 flex items-center justify-center p-6"
      >
        <div className="w-full max-w-xl bg-white rounded-2xl shadow-lg p-8 border border-red-100">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-full bg-red-100 text-red-600 flex items-center justify-center font-bold">
              !
            </div>
            <h1 className="text-xl font-bold text-gray-900">حدث خطأ غير متوقع</h1>
          </div>

          <p className="text-sm text-gray-600 leading-6 mb-6">
            نعتذر — حدثت مشكلة غير متوقعة أثناء عرض هذه الصفحة. تم تسجيل الخطأ.
            جرّب إعادة التحميل، وإن استمرّت المشكلة تواصل مع مسؤول النظام.
          </p>

          <div className="flex gap-3">
            <button
              type="button"
              onClick={this.handleReload}
              className="px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg text-sm font-semibold"
            >
              إعادة تحميل الصفحة
            </button>
            <button
              type="button"
              onClick={this.handleGoHome}
              className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm font-semibold"
            >
              العودة للرئيسية
            </button>
          </div>

          {isDev && error && (
            <details className="mt-6 text-xs text-gray-500 bg-gray-50 rounded p-3 whitespace-pre-wrap">
              <summary className="cursor-pointer font-semibold mb-2 text-red-700">
                تفاصيل الخطأ (تطوير فقط)
              </summary>
              <div>
                <strong>Error:</strong> {String(error?.message || error)}
              </div>
              {error?.stack && (
                <pre className="mt-2 overflow-x-auto">{error.stack}</pre>
              )}
              {info?.componentStack && (
                <pre className="mt-2 overflow-x-auto text-gray-400">
                  {info.componentStack}
                </pre>
              )}
            </details>
          )}
        </div>
      </div>
    )
  }
}
