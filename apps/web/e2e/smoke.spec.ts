import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { readAppConfig } from '../ctcv-config';
import { vi } from '../src/i18n/vi';
import { ptToPx } from '../src/theme/tokens';

const app = readAppConfig();
const minFontPx = ptToPx(app.minFontPt);
const MANDATORY_BUTTONS = [vi.buttons.speak, vi.buttons.repeat, vi.buttons.callVolunteer];

test.describe('Màn hình chính', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('tải được trang: tiêu đề, nhãn mô phỏng, không cuộn ngang', async ({ page }) => {
    await expect(page).toHaveTitle(/Cầm Tay Chỉ Việc/);
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(vi.appName);
    await expect(page.getByTestId('sim-badge')).toHaveText(vi.simBadge);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
  });

  test('ba nút bắt buộc luôn hiện trong khung nhìn', async ({ page }) => {
    for (const name of MANDATORY_BUTTONS) {
      await expect(page.getByRole('button', { name })).toBeInViewport();
    }
  });

  test(`phụ đề có cỡ chữ ≥ ${app.minFontPt} pt`, async ({ page }) => {
    const fontSize = await page
      .getByTestId('subtitle')
      .evaluate((el) => Number.parseFloat(getComputedStyle(el).fontSize));
    expect(fontSize).toBeGreaterThanOrEqual(minFontPx - 0.05);
  });

  test(`mọi nút cao và rộng ≥ ${app.minTapPx} px`, async ({ page }) => {
    for (const name of MANDATORY_BUTTONS) {
      const box = await page.getByRole('button', { name }).boundingBox();
      expect(box, name).not.toBeNull();
      expect(box?.height, name).toBeGreaterThanOrEqual(app.minTapPx);
      expect(box?.width, name).toBeGreaterThanOrEqual(app.minTapPx);
    }
  });

  test('bấm Nói với tôi thì phụ đề đổi và sóng âm chạy', async ({ page }) => {
    await page.getByRole('button', { name: vi.buttons.speak }).click();
    await expect(page.getByTestId('subtitle')).toHaveText(vi.subtitle.listening);
    await expect(page.getByTestId('voice-wave')).toHaveAttribute('data-active', 'true');
    await page.getByRole('button', { name: vi.buttons.repeat }).click();
    await expect(page.getByTestId('subtitle')).toHaveText(vi.subtitle.repeat);
  });

  test('không lỗi a11y nghiêm trọng (axe) @a11y', async ({ page }) => {
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'best-practice'])
      .analyze();
    const blocking = results.violations.filter(
      (v) => v.impact === 'serious' || v.impact === 'critical',
    );
    expect(blocking, JSON.stringify(blocking, null, 2)).toEqual([]);
  });
});
