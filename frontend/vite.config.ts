import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
        secure: false,
        configure: (proxy, options) => {
          proxy.on('error', (err) => {
            console.log('proxy error', err)
          })
          proxy.on('open', (proxySocket) => {
            console.log('proxy ws open')
          })
          proxy.on('close', (proxySocket) => {
            console.log('proxy ws close')
          })
        },
      },
    },
  },
})
