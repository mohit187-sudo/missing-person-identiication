import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

// Dev server proxies API calls to the FastAPI backend so the browser only ever
// talks to one origin (never localhost fetches from remote previews).
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      // Tests in ../tests/frontend live outside this package root — map bare
      // imports to this package's node_modules so resolution always succeeds.
      '@testing-library/react': resolve(__dirname, 'node_modules/@testing-library/react'),
      '@testing-library/jest-dom': resolve(__dirname, 'node_modules/@testing-library/jest-dom'),
      '@testing-library/user-event': resolve(__dirname, 'node_modules/@testing-library/user-event'),
      'react-dom': resolve(__dirname, 'node_modules/react-dom'),
      'react-router-dom': resolve(__dirname, 'node_modules/react-router-dom'),
      react: resolve(__dirname, 'node_modules/react'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    // Allow any preview host (Arena e2b.app previews + localhost).
    allowedHosts: true,
    fs: {
      // Allow loading shared test sources from ../tests/frontend
      allow: [resolve(__dirname, '..')],
    },
    proxy: {
      '/api': {
        target: process.env.VITE_API_PROXY || 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}', '../tests/frontend/**/*.test.{ts,tsx}'],
  },
});
