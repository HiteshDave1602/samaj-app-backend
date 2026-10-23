import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import tailwindcss from '@tailwindcss/vite'

// The API has no CORS, so dev requests go through this proxy (same origin).
const API = 'http://localhost:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: { '/admin': API, '/superadmin': API, '/media': API },
  },
})
