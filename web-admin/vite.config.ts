import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

const mockTarget = process.env.CONTRACT_MOCK_URL ?? 'http://127.0.0.1:4010';

function contractProxy() {
  return {
    target: mockTarget,
    changeOrigin: true,
    configure(proxy: {
      on: (
        event: 'proxyReq',
        listener: (
          proxyRequest: { setHeader: (name: string, value: string) => void },
          request: { url?: string },
        ) => void,
      ) => void;
    }) {
      proxy.on('proxyReq', (proxyRequest, request) => {
        proxyRequest.setHeader('Authorization', 'Bearer contract-placeholder');
        if (request.url?.includes('/api/v1/jobs/')) {
          proxyRequest.setHeader('Prefer', 'example=partiallySucceeded');
        }
        if (request.url?.startsWith('/api/v1/providers')) {
          proxyRequest.setHeader('Prefer', 'example=availableProviders');
        }
      });
    },
  };
}

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': contractProxy(),
      '/health': contractProxy(),
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: true,
    coverage: { provider: 'v8', reporter: ['text', 'html'] },
  },
});
