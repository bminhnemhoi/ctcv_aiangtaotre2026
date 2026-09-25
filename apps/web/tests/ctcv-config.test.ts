import { describe, expect, it } from 'vitest';
import { parseAppYaml, readAppConfig } from '../ctcv-config';

describe('đọc config/app.yaml', () => {
  it('lấy đúng ngưỡng, cổng và 3 viewport', () => {
    const app = readAppConfig();
    expect(app.minFontPt).toBeGreaterThanOrEqual(20);
    expect(app.minTapPx).toBeGreaterThanOrEqual(48);
    expect(app.viewports.map((v) => v.name)).toEqual(['360x800', '390x844', '412x915']);
    expect(app.ports.web).toBeGreaterThan(0);
    expect(app.ports.api).toBeGreaterThan(0);
  });

  it('báo lỗi rõ khi thiếu khóa', () => {
    expect(() => parseAppYaml('version: 1\n')).toThrow(/min_font_pt/);
    const noViewports = 'ports:\n  api: 1\n  web: 2\nui:\n  min_font_pt: 20\n  min_tap_px: 56\n';
    expect(() => parseAppYaml(noViewports)).toThrow(/viewports/);
  });
});
