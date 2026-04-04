import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import tailwindcss from '@tailwindcss/vite';

const BACKEND = process.env.CUTTOFFL_BACKEND || 'http://127.0.0.1:10036';

export default defineConfig({
  plugins: [svelte(), tailwindcss()],
  server: {
    host: '127.0.0.1',
    port: 10037,
    strictPort: true,
    proxy: {
      '/api': { target: BACKEND, changeOrigin: true },
      '/ws': { target: BACKEND, changeOrigin: true, ws: true },
    },
  },
  preview: { host: '127.0.0.1', port: 10037, strictPort: true },
});
