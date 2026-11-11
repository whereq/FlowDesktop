import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  optimizeDeps: {
    include: [
      'react-is',
    ],
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    allowedHosts: ['flowdesktop.local', 'www.flowdesktop.local'],
    proxy: {
      '/api': {
        // Docker DNS resolves the 'api' service alias to the backend container.
        // Override with API_PROXY_TARGET when the service name differs.
        target: process.env.API_PROXY_TARGET || 'http://api:8000',
        changeOrigin: true,
      },
    },
  },
})
