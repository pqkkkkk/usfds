/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  base: './',
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8200',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    // Node >= 25 ships a global `localStorage` that shadows jsdom's; disable it in test workers.
    execArgv: process.allowedNodeEnvironmentFlags.has('--experimental-webstorage')
      ? ['--no-experimental-webstorage']
      : [],
    // Force the same-origin `/api` base URL so tests never depend on a local `.env`.
    env: { VITE_API_BASE_URL: '' },
  },
})
