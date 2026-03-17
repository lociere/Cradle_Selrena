import { defineConfig } from 'vite';
import path from 'path';

// Vite config for the renderer app.
// Root is set to src/renderer because the entry index.html lives there.
export default defineConfig({
  root: path.resolve(__dirname, 'src', 'renderer'),
  build: {
    outDir: path.resolve(__dirname, 'dist'),
    emptyOutDir: true,
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
});
