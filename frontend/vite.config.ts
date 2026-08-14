import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/element-plus')) return 'element-plus'
          if (id.includes('node_modules/vue') || id.includes('node_modules/@vue')) return 'vue'
        },
      },
    },
  },
  server: {
    // Public demo: npm run with VITE_API_BASE= so browser hits same origin; proxy to API.
    host: true,
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        timeout: 3_600_000,
        proxyTimeout: 3_600_000,
      },
      '/health': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
