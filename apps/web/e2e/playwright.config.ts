import { defineConfig, devices } from '@playwright/test';
import { readAppConfig } from '../ctcv-config';

/**
 * Playwright smoke suite on the three phone viewports declared in config/app.yaml.
 * Run with `pnpm e2e` (or `E2E=1 make e2e`); never part of `pnpm test`.
 */
const app = readAppConfig();
const port = app.ports.web;
const baseURL = `http://localhost:${port}`;

export default defineConfig({
  testDir: '.',
  testMatch: /.*\.spec\.ts$/,
  outputDir: '../test-results',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { open: 'never', outputFolder: '../playwright-report' }]],
  use: {
    baseURL,
    locale: 'vi-VN',
    trace: 'on-first-retry',
  },
  projects: app.viewports.map((viewport) => ({
    name: viewport.name,
    use: {
      ...devices['Pixel 5'],
      viewport: { width: viewport.width, height: viewport.height },
    },
  })),
  webServer: {
    command: `pnpm exec vite --port ${port} --strictPort`,
    url: baseURL,
    cwd: '..',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
