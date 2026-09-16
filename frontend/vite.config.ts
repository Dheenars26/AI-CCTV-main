import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: true,
    port: 3000,
    strictPort: true,
    hmr: {
      clientPort: 3000,
    },
    warmup: {
      clientFiles: ['./src/main.tsx', './src/App.tsx', './src/pages/LoginPage.tsx', './src/pages/DashboardPage.tsx'],
    },
    proxy: {
      '/api/v1/ws': {
        target: 'ws://127.0.0.1:8000',
        ws: true,
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('error', (err) => {
            if ((err as any).code === 'ECONNRESET' || (err as any).code === 'ECONNREFUSED') {
              return;
            }
            console.warn('[vite ws proxy error]', err.message);
          });
          proxy.on('proxyReqWs', (_proxyReq, _req, socket) => {
            if (socket && typeof socket.on === 'function') {
              socket.on('error', () => { /* prevent unhandled ECONNRESET */ });
            }
          });
        },
      },
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        configure: (proxy) => {
          // Retry on connection failure (covers uvicorn --reload restart window)
          proxy.on('error', (err, req, res) => {
            const MAX_RETRIES = 3;
            const RETRY_DELAY_MS = 1500;
            const retryCount: number = ((req as any).__proxyRetry) || 0;
            const isIdempotent = req.method === 'GET' || req.method === 'HEAD';

            if (isIdempotent && retryCount < MAX_RETRIES && (err as any).code === 'ECONNREFUSED' && res && 'writeHead' in res) {
              (req as any).__proxyRetry = retryCount + 1;
              console.warn(`[vite proxy] Backend unavailable, retrying (${retryCount + 1}/${MAX_RETRIES}) in ${RETRY_DELAY_MS}ms...`);
              setTimeout(() => {
                try {
                  proxy.web(req, res, { target: 'http://127.0.0.1:8000' });
                } catch (_) { /* ignore retry error */ }
              }, RETRY_DELAY_MS);
              return;
            }

            console.warn('[vite proxy] Backend connection failed. Returning 502 for client failover.');
            if (res && 'headersSent' in res && !res.headersSent && 'writeHead' in res && typeof res.writeHead === 'function') {
              try {
                res.writeHead(502, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ detail: 'Backend server unavailable. Please start the backend service.' }));
              } catch (_) { /* ignore */ }
            } else if (res && 'destroy' in res && typeof (res as any).destroy === 'function') {
              try {
                (res as any).destroy();
              } catch (_) { /* ignore */ }
            }
          });
        },
      },
      '/evidence': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  optimizeDeps: {
    holdUntilCrawlEnd: false,
    include: [
      'react',
      'react-dom',
      'react-dom/client',
      'react-router-dom',
      'lucide-react',
      '@tanstack/react-query',
      'axios',
    ],
  },
  build: {
    target: 'esnext',
    minify: 'esbuild',
    cssMinify: true,
    sourcemap: false,
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-icons': ['lucide-react'],
          'vendor-query': ['@tanstack/react-query', 'axios'],
        },
      },
    },
  },
});
