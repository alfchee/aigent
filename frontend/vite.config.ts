import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.ts', 'src/**/*.spec.ts'],
    exclude: ['e2e/**', 'node_modules/**'],
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8231',
        changeOrigin: true,
        rewrite: (path: string) => path.replace(/^\/api/, '/api'),
      },
    },
  },
})
