import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

// Sentry init — lazy-loaded ONLY when DSN is set, to avoid dragging
// `@sentry/react` into Vite's import-analysis when it isn't installed.
if (import.meta.env.VITE_SENTRY_DSN) {
  import('./utils/sentry.js').then(({ initSentry }) => initSentry())
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
