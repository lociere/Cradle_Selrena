import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// Vite config for the renderer app.
// Root is set to src/renderer because the entry index.html lives there.
export default defineConfig({
  root: path.resolve(__dirname, 'src', 'renderer'),
  plugins: [react()],
  base: './',
  build: {
    outDir: path.resolve(__dirname, 'dist', 'renderer'),
    emptyOutDir: true,
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
  },
});
