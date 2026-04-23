import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      // Proxy REST API calls to the FastAPI backend
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // Proxy WebSocket connections
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
        changeOrigin: true,
      },
      // Proxy media assets from backend data directory
      '/data': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // Proxy static assets (catalog images, etc.) from backend
      '/assets': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
