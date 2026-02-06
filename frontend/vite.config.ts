import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8231',
        changeOrigin: true,
        rewrite: (path: string) => path.replace(/^\/api/, '/api')
      }
    }
  }
})
