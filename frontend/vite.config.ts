import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: 'localhost',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: process.env.F2R_API_PROXY_TARGET ?? 'http://127.0.0.1:8000',
        changeOrigin: false,
      },
    },
  },
});
