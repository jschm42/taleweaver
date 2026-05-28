import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig(({ mode }) => {
  const frontendEnv = loadEnv(mode, fileURLToPath(new URL('./', import.meta.url)), '')
  const repoEnv = loadEnv(mode, fileURLToPath(new URL('../', import.meta.url)), '')

  const backendPort = frontendEnv.BACKEND_PORT || repoEnv.BACKEND_PORT || '8000'
  const frontendPort = parseInt(frontendEnv.FRONTEND_PORT || repoEnv.FRONTEND_PORT || '5173', 10)

  return {
    plugins: [vue()],
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
        // Proxy static assets (catalog images, etc.) from backend
        '/assets': {
          target: `http://127.0.0.1:${backendPort}`,
          changeOrigin: true,
        },
      },
    },
  }
})
