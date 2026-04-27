import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

/**
 * Vite config — ENV-driven.
 *
 * المتغيرات المتاحة (اعمل .env أو .env.local):
 *   VITE_API_URL          = 'http://localhost:8010'  // للـ backend
 *   VITE_DEV_PORT         = '3000'                   // منفذ الـ dev server
 *   VITE_DEV_PROXY_TARGET = 'http://localhost:8010'  // target للبروكسي
 *   VITE_SOURCEMAP        = 'true' | 'false'         // في production
 *   VITE_DEV_BIND_LAN     = '0' | 'false'            // اختياري: عطّل الاستماع على LAN (افتراضي: مفعّل)
 */
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const devPort = parseInt(env.VITE_DEV_PORT || '3000', 10)
  // Windows: Node proxy often resolves "localhost" to ::1 while uvicorn may listen on IPv4 only —
  // use 127.0.0.1 by default so POST /api/v1/auth/login reliably reaches the backend.
  const proxyTarget =
    env.VITE_DEV_PROXY_TARGET || env.VITE_API_URL || 'http://127.0.0.1:8010'
  const enableSourcemap =
    mode === 'development' ? true : env.VITE_SOURCEMAP === 'true'
  const hostAllInterfaces =
    env.VITE_DEV_BIND_LAN === '0' || env.VITE_DEV_BIND_LAN === 'false'
      ? false
      : true

  return {
    plugins: [react()],
    server: {
      host: hostAllInterfaces,
      port: devPort,
      proxy: {
        '/api': {
          target: proxyTarget,
          changeOrigin: true,
        },
      },
    },
    build: {
      sourcemap: enableSourcemap,
      chunkSizeWarningLimit: 1000,
    },
  }
})
