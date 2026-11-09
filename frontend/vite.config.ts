import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    // En desarrollo, las peticiones /api se reenvían al backend FastAPI
    proxy: { '/api': 'http://localhost:8000' },
  },
})
