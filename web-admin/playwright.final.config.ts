import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  testMatch: '**/*.smoke.ts',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI
    ? [['list'], ['junit', { outputFile: './reports/playwright.xml' }]]
    : 'list',
  use: {
    baseURL: 'http://127.0.0.1:4173',
    trace: 'retain-on-failure',
    ...devices['Desktop Chrome'],
    channel: process.platform === 'win32' ? 'msedge' : undefined,
  },
  webServer: [
    {
      command:
        'corepack pnpm@10.34.5 --dir ../contracts/tooling exec prism mock ../generated/openapi.yaml --host 127.0.0.1 --port 4010',
      url: 'http://127.0.0.1:4010/health/live',
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: 'corepack pnpm@10.34.5 exec vite --host 127.0.0.1 --port 4173',
      url: 'http://127.0.0.1:4173/contract-status',
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
