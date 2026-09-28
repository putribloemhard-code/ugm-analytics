import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  base: process.env.VITE_APP_BASE_PATH ?? '/',
  plugins: [react()],
  // Proxy dev: /api -> API lokal (lihat dev_api_mysql.py), jadi browser satu-origin dan tidak kena CORS.
  // xfwd: API tahu alamat :3000 yang dibuka browser (tautan reset & callback login Google).
  server: { host: '127.0.0.1', port: 3000, proxy: { '/api': { target: 'http://127.0.0.1:8000', xfwd: true } } },
  preview: { host: '127.0.0.1', port: 3000 },
});
