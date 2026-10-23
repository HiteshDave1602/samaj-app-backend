import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import tailwindcss from '@tailwindcss/vite'

// The API has no CORS, so dev requests go through this proxy (same origin).
// Trailing slashes keep the API prefixes from swallowing the panel URLs (/super-admin/, /city-admin/).
const API = 'http://localhost:8000'
const page = (p) => fileURLToPath(new URL(p, import.meta.url))

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: { '/admin/': API, '/superadmin/': API, '/cityadmin/': API, '/media/': API },
  },
  build: {
    rollupOptions: {
      // One page per panel: each loads only its own code.
      input: {
        index: page('./index.html'),
        'super-admin': page('./super-admin/index.html'),
        'city-admin': page('./city-admin/index.html'),
      },
    },
  },
})
