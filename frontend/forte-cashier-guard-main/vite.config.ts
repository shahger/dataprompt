import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

// Dev-прокси нужен только когда бэкенд готов и вы переключили источник на «API».
// По умолчанию бэкенд ожидается на http://localhost:8000 (см. .env.example).
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        '/api': { target: env.API_PROXY_TARGET || 'http://localhost:8000', changeOrigin: true },
      },
    },
  };
});
