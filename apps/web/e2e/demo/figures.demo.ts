import { existsSync, mkdirSync, readFileSync, readdirSync } from 'node:fs';
import { basename, dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { expect, test } from '@playwright/test';
import { demoOutDir } from './out-dir';

/**
 * Render the static dossier figures and video slides (ADR-007 C9) to PNG:
 *   docs/dossier/dfl/figures/src/*.html → docs/dossier/dfl/figures/<name>.png (1600x900)
 *   docs/dossier/dfl/video/slides/*.html → <CTCV_DEMO_OUT or docs/dossier/out/dfl/video>/slides/<name>.png
 *   (1920x1080)
 * Numbers come only from eval/reports/latest.json and ablation-tthc.json (read here with fs,
 * exposed as window.__METRICS__); an absent value is shown as "chưa đo" — never invented.
 * Pages must be self-contained (no network) and must fit the frame without scrolling.
 */

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, '../../../..');
const REPORTS = resolve(REPO, 'eval/reports');
const NOT_MEASURED = 'chưa đo';

interface Job {
  name: string;
  html: string;
  png: string;
  width: number;
  height: number;
}

function jobs(srcDir: string, outDir: string, width: number, height: number): Job[] {
  if (!existsSync(srcDir)) return [];
  return readdirSync(srcDir)
    .filter((file) => file.endsWith('.html'))
    .sort()
    .map((file) => ({
      name: basename(file, '.html'),
      html: resolve(srcDir, file),
      png: resolve(outDir, `${basename(file, '.html')}.png`),
      width,
      height,
    }));
}

function readJson(path: string): Record<string, unknown> | null {
  if (!existsSync(path)) return null;
  const data: unknown = JSON.parse(readFileSync(path, 'utf8'));
  return data && typeof data === 'object' ? (data as Record<string, unknown>) : null;
}

/** Same shape as build_dfl.py: latest.json with ablation-tthc.json under `ablation`. */
function loadMetrics(): Record<string, unknown> {
  const metrics = readJson(resolve(REPORTS, 'latest.json')) ?? {};
  const ablation = readJson(resolve(REPORTS, 'ablation-tthc.json'));
  return ablation ? { ...metrics, ablation } : metrics;
}

/**
 * Runs in the page: fill `[data-metric]` (text), `[data-bar]` (width %) and `[data-list]`
 * (comma list) from window.__METRICS__, formatting numbers like build_dossier.format_value.
 */
function fillMetrics(notMeasured: string): number {
  const root = (window as unknown as { __METRICS__?: unknown }).__METRICS__;
  const get = (path: string): unknown =>
    path.split('.').reduce<unknown>((node, key) => {
      if (node && typeof node === 'object') return (node as Record<string, unknown>)[key];
      return undefined;
    }, root);
  const format = (value: unknown): string | null => {
    if (typeof value === 'number' && Number.isFinite(value)) {
      if (Number.isInteger(value)) return value.toLocaleString('vi-VN');
      return value.toFixed(2).replace(/0+$/, '').replace(/\.$/, '').replace('.', ',');
    }
    return typeof value === 'string' && value.trim() ? value : null;
  };
  let filled = 0;
  for (const el of document.querySelectorAll<HTMLElement>('[data-metric]')) {
    const text = format(get(el.dataset.metric ?? ''));
    el.textContent = text ?? notMeasured;
    el.classList.toggle('chua-do', text === null);
    if (text !== null) filled += 1;
  }
  for (const el of document.querySelectorAll<HTMLElement>('[data-bar]')) {
    const value = get(el.dataset.bar ?? '');
    const ok = typeof value === 'number' && Number.isFinite(value);
    el.style.width = ok ? `${Math.max(0, Math.min(100, value))}%` : '0%';
    el.classList.toggle('chua-do', !ok);
  }
  for (const el of document.querySelectorAll<HTMLElement>('[data-list]')) {
    const value = get(el.dataset.list ?? '');
    const items = Array.isArray(value) ? value.map(String).filter(Boolean) : [];
    el.textContent = items.length ? items.join(', ') : notMeasured;
    el.classList.toggle('chua-do', items.length === 0);
  }
  return filled;
}

const JOBS = [
  ...jobs(
    resolve(REPO, 'docs/dossier/dfl/figures/src'),
    resolve(REPO, 'docs/dossier/dfl/figures'),
    1600,
    900,
  ),
  ...jobs(
    resolve(REPO, 'docs/dossier/dfl/video/slides'),
    resolve(demoOutDir(), 'slides'),
    1920,
    1080,
  ),
];

test.use({ video: 'off' });

test('có đủ hình và slide cần dựng', () => {
  const names = JOBS.map((job) => job.name);
  for (const name of [
    'kien-truc-dfl',
    'pipeline-du-lieu',
    'ablation',
    '01-van-de',
    '06-lo-trinh',
  ]) {
    expect(names).toContain(name);
  }
});

for (const job of JOBS) {
  test(`dựng ${job.name}.png (${job.width}x${job.height})`, async ({ page }) => {
    const external: string[] = [];
    page.on('request', (request) => {
      if (!request.url().startsWith('file:')) external.push(request.url());
    });
    await page.setViewportSize({ width: job.width, height: job.height });
    await page.addInitScript((metrics) => {
      Object.assign(window, { __METRICS__: metrics });
    }, loadMetrics());
    await page.goto(pathToFileURL(job.html).href);
    await page.evaluate(fillMetrics, NOT_MEASURED);
    await page.evaluate(() => document.fonts.ready);
    expect(external, 'hình phải tự chứa, không tải CDN').toEqual([]);
    const size = await page.evaluate(() => ({
      width: document.documentElement.scrollWidth,
      height: document.documentElement.scrollHeight,
    }));
    expect(size.width, 'nội dung tràn ngang').toBeLessThanOrEqual(job.width);
    expect(size.height, 'nội dung tràn dọc').toBeLessThanOrEqual(job.height);
    mkdirSync(dirname(job.png), { recursive: true });
    await page.screenshot({ path: job.png });
  });
}
