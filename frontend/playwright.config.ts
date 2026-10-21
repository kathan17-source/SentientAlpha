import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  timeout: 60000,
  expect: { timeout: 15000 },
  reporter: [['list'], ['json', { outputFile: 'playwright-results.json' }]],
  outputDir: 'test-results',
  use: {
    baseURL: process.env.DASHBOARD_URL || 'http://127.0.0.1:3000',
    headless: true,
    viewport: { width: 1440, height: 1000 },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
});
