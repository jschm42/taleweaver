import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig(({ mode }) => {
  const frontendEnv = loadEnv(mode, fileURLToPath(new URL('./', import.meta.url)), '')
  const repoEnv = loadEnv(mode, fileURLToPath(new URL('../', import.meta.url)), '')

  const backendPort = frontendEnv.BACKEND_PORT || repoEnv.BACKEND_PORT || '8000'
  const frontendPort = parseInt(frontendEnv.FRONTEND_PORT || repoEnv.FRONTEND_PORT || '5173', 10)
  const cspHeader = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob: https://api.dicebear.com; font-src 'self' data:; connect-src 'self' ws: wss:; media-src 'self' data: blob:; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"

  return {
    plugins: [vue()],
    build: {
      rollupOptions: {
        output: {
          manualChunks: {
            'vendor-vue': ['vue', 'vue-router'],
            'vendor-graph': ['dagre', 'roughjs'],
            'vendor-sanitize': ['dompurify'],
            'vendor-icons': ['lucide-vue-next'],
          },
        },
      },
    },
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server: {
      port: frontendPort,
      proxy: {
        // Proxy REST API calls to the FastAPI backend
        '/api': {
          target: `http://127.0.0.1:${backendPort}`,
          changeOrigin: true,
        },
        // Proxy WebSocket connections
        '/ws': {
          target: `ws://127.0.0.1:${backendPort}`,
          ws: true,
          changeOrigin: true,
        },
        // Proxy media assets from backend data directory
        '/data': {
          target: `http://127.0.0.1:${backendPort}`,
          changeOrigin: true,
        },
        // Proxy backend catalog images only.
        '/assets/catalog': {
          target: `http://127.0.0.1:${backendPort}`,
          changeOrigin: true,
        },
      },
    },
    preview: {
      port: 4173,
      proxy: {
        '/api': {
          target: `http://127.0.0.1:${backendPort}`,
          changeOrigin: true,
        },
        '/ws': {
          target: `ws://127.0.0.1:${backendPort}`,
          ws: true,
          changeOrigin: true,
        },
        '/data': {
          target: `http://127.0.0.1:${backendPort}`,
          changeOrigin: true,
        },
        // Proxy backend catalog images only.
        '/assets/catalog': {
          target: `http://127.0.0.1:${backendPort}`,
          changeOrigin: true,
        },
      },
      headers: {
        'Content-Security-Policy': cspHeader,
        'X-Frame-Options': 'DENY',
      },
    },
  }
})
