import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, test, type Page, type Response } from '@playwright/test';
import type { AskOut, IntakeCheckOut } from '../../src/api/types';
import { demoOutDir } from './out-dir';

/**
 * The Data for Life 2026 demo (ADR-007 C9), recorded on the REAL stack: API + Ollama + Vite
 * started by `scripts/dev_cpu.py --run`. No `page.route`, no mock, no canned answer — every
 * step asserts on what the running system returned; a failing step fails the recording.
 *
 * Writes <CTCV_DEMO_OUT or docs/dossier/out/dfl/video>/timeline.json ([{id, t_start_ms, t_end_ms}] from the start
 * of the video) and two figures for the proposal. Screenshots are taken between steps, outside
 * every timeline window, so the viewport switch never appears in the cut video.
 * Secrets (CTCV_DEMO_QR_TOKEN, CTCV_DEMO_STAFF_PASSWORD) are read from the environment and never
 * printed: errors that could echo them are replaced by a generic message.
 */

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, '../../../..');
const VIDEO_OUT = demoOutDir();
const FIGURES = resolve(REPO, 'docs/dossier/dfl/figures');
const RAG_YAML = resolve(REPO, 'config/rag.yaml');

const TYPE_DELAY_MS = 60;
const ANSWER_TIMEOUT_MS = 120_000;
/** Pause after each result so viewers can read it (part of the step, not a cut). */
const HOLD_MS = 2_500;
/**
 * Every step stays on screen at least this long so its two-line subtitle can be read; the extra
 * time is a real pause on the live screen (no freeze frame, no speed change).
 */
const MIN_STEP_MS = 5_500;
const VIDEO_SIZE = { width: 1280, height: 720 };
const PHONE_SIZE = { width: 390, height: 844 };
const DEFAULT_STAFF_USERNAME = 'canbo-demo';

const Q_FEE = 'Đăng ký thường trú mất bao nhiêu tiền?';
const Q_DOCS = 'Làm căn cước cho cháu 14 tuổi cần mang giấy tờ gì?';
const Q_OUT_OF_KB = 'Thủ tục đăng ký kết hôn cần những gì?';
const Q_OTP = 'Có người xưng công an gọi xin mã OTP, tôi có đọc không?';
const OFFICER_QUERY = 'đăng ký tạm trú';

type StepId =
  | 'hoi-phi'
  | 'mo-nguon'
  | 'hoi-giay-to'
  | 'hoi-ngoai-kho'
  | 'hoi-otp'
  | 'can-bo-dang-nhap'
  | 'can-bo-tim'
  | 'can-bo-danh-dau'
  | 'can-bo-ket-qua';

interface Mark {
  id: StepId;
  t_start_ms: number;
  t_end_ms: number;
}

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Thiếu biến môi trường ${name}: chạy qua scripts/dev_cpu.py --run.`);
  }
  return value;
}

/**
 * `demo.staff_username` from config/rag.yaml (regex, no YAML parser in the web toolchain);
 * matches block style and the flow style `demo: {staff_username: canbo-demo}`.
 */
function staffUsername(): string {
  if (!existsSync(RAG_YAML)) return DEFAULT_STAFF_USERNAME;
  const match = /\bstaff_username:\s*["']?([\w.-]+)/.exec(readFileSync(RAG_YAML, 'utf8'));
  return match?.[1] ?? DEFAULT_STAFF_USERNAME;
}

/** Run `action`, replacing any error by `message` (the original could echo a secret). */
async function quietly(message: string, action: () => Promise<unknown>): Promise<void> {
  try {
    await action();
  } catch {
    throw new Error(message);
  }
}

function isPost(path: string) {
  return (response: Response) =>
    response.request().method() === 'POST' && new URL(response.url()).pathname.endsWith(path);
}

async function expectOk(response: Response, what: string): Promise<void> {
  expect(response.status(), `${what} phải trả 200 (hệ thống thật)`).toBe(200);
}

function makeRecorder(page: Page) {
  const t0 = Date.now();
  const marks: Mark[] = [];
  const step = async (id: StepId, body: () => Promise<void>) =>
    test.step(id, async () => {
      const start = Date.now() - t0;
      await body();
      const elapsed = Date.now() - t0 - start;
      await page.waitForTimeout(Math.max(HOLD_MS, MIN_STEP_MS - elapsed));
      marks.push({ id, t_start_ms: start, t_end_ms: Date.now() - t0 });
    });
  return { marks, step };
}

/** Type a question slowly, send it, and wait for the real `/v1/coach/ask` answer. */
async function ask(page: Page, question: string): Promise<AskOut> {
  const input = page.getByTestId('ask-input');
  await input.fill('');
  await input.pressSequentially(question, { delay: TYPE_DELAY_MS });
  const pending = page.waitForResponse(isPost('/v1/coach/ask'), { timeout: ANSWER_TIMEOUT_MS });
  await page.getByTestId('ask-submit').click();
  const response = await pending;
  await expectOk(response, '/v1/coach/ask');
  const body = (await response.json()) as AskOut;
  const answer = page.getByTestId('answer');
  await expect(answer).toHaveAttribute('data-reason', body.reason, { timeout: ANSWER_TIMEOUT_MS });
  await answer.evaluate((el) => el.scrollIntoView({ block: 'start' }));
  return body;
}

async function intake(page: Page, click: () => Promise<void>): Promise<IntakeCheckOut> {
  const pending = page.waitForResponse(isPost('/v1/coach/intake-check'), {
    timeout: ANSWER_TIMEOUT_MS,
  });
  await click();
  const response = await pending;
  await expectOk(response, '/v1/coach/intake-check');
  return (await response.json()) as IntakeCheckOut;
}

async function phoneShot(page: Page, path: string): Promise<void> {
  await page.setViewportSize(PHONE_SIZE);
  await page.getByTestId('answer').evaluate((el) => el.scrollIntoView({ block: 'start' }));
  await page.screenshot({ path });
  await page.setViewportSize(VIDEO_SIZE);
}

async function citizenSteps(page: Page, step: ReturnType<typeof makeRecorder>['step']) {
  await step('hoi-phi', async () => {
    await ask(page, Q_FEE);
    await expect(page.getByTestId('answer-text')).toHaveText(/\d/);
    await expect(page.getByTestId('btn-nguon')).toBeVisible();
  });
  await step('mo-nguon', async () => {
    await page.getByTestId('btn-nguon').click();
    const panel = page.getByTestId('source-panel');
    await expect(panel).toContainText('Cổng Dịch vụ công');
    await panel.evaluate((el) => el.scrollIntoView({ block: 'center' }));
  });
  await phoneShot(page, resolve(FIGURES, 'man-hinh-nguoi-dan.png'));
  await step('hoi-giay-to', async () => {
    await ask(page, Q_DOCS);
    const card = page.getByTestId('docs-card');
    await expect(card).toBeVisible();
    await card.evaluate((el) => el.scrollIntoView({ block: 'start' }));
    expect(await card.locator('[data-testid^="doc-item-"]').count()).toBeGreaterThanOrEqual(1);
  });
  await step('hoi-ngoai-kho', async () => {
    await ask(page, Q_OUT_OF_KB);
    await expect(page.getByTestId('escalate-box')).toBeVisible();
    await expect(page.getByTestId('answer')).toHaveAttribute('data-reason', 'no_source');
  });
  await step('hoi-otp', async () => {
    await ask(page, Q_OTP);
    await expect(page.getByTestId('refused-box')).toBeVisible();
    await expect(page.getByTestId('answer')).toHaveAttribute('data-reason', 'sensitive');
  });
}

async function officerSteps(
  page: Page,
  step: ReturnType<typeof makeRecorder>['step'],
  password: string,
) {
  const state: { lookup: IntakeCheckOut | null } = { lookup: null };
  await step('can-bo-dang-nhap', async () => {
    await page.evaluate(() => {
      window.location.hash = '#can-bo';
    });
    await page.getByTestId('officer-username').pressSequentially(staffUsername(), {
      delay: TYPE_DELAY_MS,
    });
    await quietly('Không điền được ô mật khẩu cán bộ.', () =>
      page.getByTestId('officer-password').fill(password),
    );
    const pending = page.waitForResponse(isPost('/v1/auth/login'));
    await page.getByTestId('officer-login-submit').click();
    await expectOk(await pending, '/v1/auth/login');
    await expect(page.getByTestId('officer-query')).toBeVisible();
  });
  await step('can-bo-tim', async () => {
    await page.getByTestId('officer-query').pressSequentially(OFFICER_QUERY, {
      delay: TYPE_DELAY_MS,
    });
    state.lookup = await intake(page, () => page.getByTestId('officer-search').click());
    await expect(page.getByTestId('officer-procedure')).toBeVisible();
    // The API lists a case's documents only once a case is chosen: choosing one re-queries it.
    if (state.lookup.needs_case) {
      state.lookup = await intake(page, async () => {
        await page.getByTestId('case-select').selectOption({ index: 1 });
      });
      expect(state.lookup.needs_case).toBe(false);
    }
    const items = page.locator('[data-testid^="checklist-item-"]');
    await expect(items.first()).toBeVisible();
    expect(await items.count()).toBeGreaterThanOrEqual(2);
  });
  await step('can-bo-danh-dau', async () => {
    const items = page.locator('[data-testid^="checklist-item-"]');
    const total = await items.count();
    expect(total).toBeGreaterThanOrEqual(1);
    for (let i = 0; i < total - 1; i += 1) await items.nth(i).check();
    await expect(page.locator('[data-testid^="checklist-item-"]:checked')).toHaveCount(total - 1);
  });
  await step('can-bo-ket-qua', async () => {
    const result = await intake(page, () => page.getByTestId('officer-check').click());
    expect(result.missing_count).toBeGreaterThanOrEqual(1);
    const missing = page.getByTestId('missing-list');
    await expect(missing.locator('li').first()).toBeVisible();
    await expect(page.getByTestId('citizen-message')).toBeVisible();
    await missing.evaluate((el) => el.closest('section')?.scrollIntoView({ block: 'start' }));
  });
}

test('demo DFL 2026: người dân hỏi thủ tục, cán bộ đối chiếu hồ sơ (hệ thống thật)', async ({
  page,
}) => {
  const recorder = makeRecorder(page);
  const qrToken = requireEnv('CTCV_DEMO_QR_TOKEN');
  const password = requireEnv('CTCV_DEMO_STAFF_PASSWORD');
  mkdirSync(VIDEO_OUT, { recursive: true });
  mkdirSync(FIGURES, { recursive: true });

  await quietly('Không mở được trang demo (API/web đã chạy qua dev_cpu.py chưa?).', async () => {
    await page.goto(`/?lop=${encodeURIComponent(qrToken)}#hoi-thu-tuc`);
    await expect(page.getByTestId('ask-input')).toBeVisible({ timeout: 30_000 });
  });
  // Boolean on purpose: a failing string assertion would print the URL (and the class code).
  await expect
    .poll(() => page.url().includes('lop='), { message: 'mã lớp phải được xóa khỏi địa chỉ' })
    .toBe(false);

  await citizenSteps(page, recorder.step);
  await officerSteps(page, recorder.step, password);
  await page.screenshot({ path: resolve(FIGURES, 'man-hinh-can-bo.png') });

  writeFileSync(
    resolve(VIDEO_OUT, 'timeline.json'),
    `${JSON.stringify(recorder.marks, null, 2)}\n`,
    'utf8',
  );
});
