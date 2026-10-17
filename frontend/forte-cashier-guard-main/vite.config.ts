import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react(), {
    name: 'offline-react-diagnostics',
    // React's diagnostic URL is informational, but keep even error messages local.
    renderChunk(code) {
      return { code: code.split('https://reactjs.org/docs/error-decoder.html?invariant=').join('/#ошибка-интерфейса-'), map: null };
    },
  }],
  base: '/',
  server: {
    port: 5173,
    proxy: {
      '/ui/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/health': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
});
