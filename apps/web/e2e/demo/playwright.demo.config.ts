import { resolve } from 'node:path';
import { defineConfig } from '@playwright/test';
import { readAppConfig } from '../../ctcv-config';
import { demoOutDir } from './out-dir';

/**
 * Recorded demo and dossier figures (ADR-007 C9) — NOT part of `pnpm e2e` (files end in
 * `.demo.ts`, the e2e config only matches `.spec.ts`). No webServer: the real stack (API +
 * Ollama + Vite) is started by `scripts/dev_cpu.py --run`, e.g.
 *
 *   uv run python scripts/dev_cpu.py --run pnpm -C apps/web exec playwright test \
 *     -c e2e/demo/playwright.demo.config.ts
 *
 * Playwright empties `outputDir` (the raw demo video) at the start of every run, so render the
 * figures first or in the same run (`figures.demo.ts` sorts before `record-demo.demo.ts`).
 * `CTCV_DEMO_OUT` (relative to the repo root) redirects raw video, timeline and slides to another
 * folder, e.g. `docs/dossier/out/dfl/v2/video`, so an earlier cut is never overwritten.
 */
const app = readAppConfig();
const VIDEO_SIZE = { width: 1280, height: 720 };

export default defineConfig({
  testDir: '.',
  testMatch: /.*\.demo\.ts$/,
  outputDir: resolve(demoOutDir(), 'raw'),
  workers: 1,
  fullyParallel: false,
  retries: 0,
  timeout: 300_000,
  reporter: [['list']],
  use: {
    baseURL: `http://127.0.0.1:${app.ports.web}`,
    browserName: 'chromium',
    locale: 'vi-VN',
    viewport: VIDEO_SIZE,
    video: { mode: 'on', size: VIDEO_SIZE },
    trace: 'off',
    screenshot: 'off',
  },
});
