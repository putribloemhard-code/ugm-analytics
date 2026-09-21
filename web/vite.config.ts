import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  base: process.env.VITE_APP_BASE_PATH ?? '/',
  plugins: [react()],
  // Proxy dev: /api -> API lokal (lihat dev_api_mysql.py), jadi browser satu-origin dan tidak kena CORS.
  server: { host: '127.0.0.1', port: 3000, proxy: { '/api': 'http://127.0.0.1:8000' } },
  preview: { host: '127.0.0.1', port: 3000 },
});
