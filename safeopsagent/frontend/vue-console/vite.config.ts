import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  base: '/console/',
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    outDir: '../../backend/static/console',
    emptyOutDir: true,
    sourcemap: false,
  },
  server: {
    port: 5173,
    proxy: {
      '/health': 'http://127.0.0.1:8000',
      '/agent': 'http://127.0.0.1:8000',
      '/system': 'http://127.0.0.1:8000',
      '/chat': 'http://127.0.0.1:8000',
      '/tools': 'http://127.0.0.1:8000',
      '/audit': 'http://127.0.0.1:8000',
      '/auth': 'http://127.0.0.1:8000',
      '/security': 'http://127.0.0.1:8000',
    },
  },
})
