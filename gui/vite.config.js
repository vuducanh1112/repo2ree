import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  resolve: {
    alias: {
      '@core': fileURLToPath(new URL('./src/core', import.meta.url)),
      '@shell': fileURLToPath(new URL('./src/shell', import.meta.url)),
    },
  },
  plugins: [react()],
  test: {
    exclude: ["tests/e2e/**", "tests/demo/**", "node_modules/**", "dist/**"],
  },
  server: {
    port: 5173,
    proxy: {
      // Proxy API calls to the backend FastAPI server
      '/api': 'http://localhost:8000'
    }
  }
})
