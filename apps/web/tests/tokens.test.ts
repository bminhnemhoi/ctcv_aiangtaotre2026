import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { readAppConfig } from '../ctcv-config';
import { contrastRatio, hexToRgb, meetsContrast } from '../src/theme/contrast';
import {
  BASE_FONT_PT,
  MIN_CONTRAST,
  MIN_TAP_PX,
  colors,
  contrastPairs,
  fontSizePt,
  fontSizePx,
  ptToPx,
  pxToPt,
  spacingPx,
} from '../src/theme/tokens';

const app = readAppConfig();

describe('cỡ chữ', () => {
  it('quy đổi pt → px theo 96/72', () => {
    expect(ptToPx(20)).toBeCloseTo(26.6667, 3);
    expect(pxToPt(ptToPx(24))).toBeCloseTo(24, 6);
  });

  it('cỡ chữ cơ sở đúng bằng ui.min_font_pt trong config/app.yaml', () => {
    expect(BASE_FONT_PT).toBe(app.minFontPt);
    expect(fontSizePt.base).toBe(app.minFontPt);
  });

  it('không có cỡ chữ nào dưới ngưỡng tối thiểu', () => {
    const minPx = ptToPx(app.minFontPt);
    for (const [name, pt] of Object.entries(fontSizePt)) {
      const px = Number.parseFloat(fontSizePx[name as keyof typeof fontSizePx]);
      expect(pt, name).toBeGreaterThanOrEqual(app.minFontPt);
      expect(px, name).toBeCloseTo(ptToPx(pt), 3);
      expect(px, name).toBeGreaterThanOrEqual(minPx - 1e-3);
    }
  });
});

describe('vùng bấm và khoảng cách', () => {
  it('vùng bấm tối thiểu đúng bằng ui.min_tap_px', () => {
    expect(MIN_TAP_PX).toBe(app.minTapPx);
    expect(MIN_TAP_PX).toBeGreaterThanOrEqual(56);
  });

  it('thang khoảng cách tăng dần, bội số của 4', () => {
    const values = Object.values(spacingPx);
    for (let i = 1; i < values.length; i += 1) {
      expect(values[i]).toBeGreaterThan(values[i - 1] ?? 0);
    }
    for (const value of values) expect(value % 4).toBe(0);
  });
});

describe('màu có tên gọi được', () => {
  it('đủ 6 màu và đều là mã hex hợp lệ', () => {
    expect(Object.keys(colors).sort()).toEqual(['den', 'do', 'trang', 'vang', 'xam', 'xanh']);
    for (const hex of Object.values(colors)) expect(() => hexToRgb(hex)).not.toThrow();
  });

  it('hàm tương phản đúng với các mốc WCAG', () => {
    expect(contrastRatio('#000000', '#FFFFFF')).toBeCloseTo(21, 5);
    expect(contrastRatio('#FFFFFF', '#000000')).toBeCloseTo(21, 5);
    expect(contrastRatio('#777777', '#777777')).toBeCloseTo(1, 5);
    expect(contrastRatio('#777777', '#FFFFFF')).toBeCloseTo(4.48, 2);
    expect(hexToRgb('#abc')).toEqual([0xaa, 0xbb, 0xcc]);
    expect(() => hexToRgb('xanh')).toThrow();
  });

  it(`mọi cặp màu dùng trong giao diện đạt tương phản ≥ ${MIN_CONTRAST}:1`, () => {
    expect(MIN_CONTRAST).toBeGreaterThanOrEqual(7);
    expect(contrastPairs.length).toBeGreaterThan(0);
    for (const pair of contrastPairs) {
      const ratio = contrastRatio(colors[pair.bg], colors[pair.fg]);
      const label = `${pair.bg}/${pair.fg} (${pair.usage}) = ${ratio.toFixed(2)}`;
      expect(ratio, label).toBeGreaterThanOrEqual(MIN_CONTRAST);
      expect(meetsContrast(colors[pair.bg], colors[pair.fg], MIN_CONTRAST)).toBe(true);
    }
  });

  it('mỗi màu có ít nhất một cặp đạt chuẩn', () => {
    for (const name of Object.keys(colors) as (keyof typeof colors)[]) {
      const used = contrastPairs.some((p) => p.bg === name || p.fg === name);
      expect(used, `${name} chưa có cặp tương phản nào`).toBe(true);
    }
  });

  it('theme-color trong index.html trùng màu xanh của token, lang="vi"', () => {
    const html = readFileSync(resolve(__dirname, '../index.html'), 'utf8');
    const match = /<meta name="theme-color" content="([^"]+)"/.exec(html);
    expect(match?.[1]?.toUpperCase()).toBe(colors.xanh.toUpperCase());
    expect(html).toMatch(/<html lang="vi">/);
  });
});
