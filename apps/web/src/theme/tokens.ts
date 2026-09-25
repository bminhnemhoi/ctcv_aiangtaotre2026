/**
 * Design tokens for the elder-first UI (idea §4, prompt §5 D3, config/app.yaml `ui`).
 *
 * Every size is expressed in CSS px derived from points so the "≥ 20 pt" rule of the
 * product can be checked mechanically. `BASE_FONT_PT` and `MIN_TAP_PX` mirror
 * `ui.min_font_pt` / `ui.min_tap_px` in config/app.yaml — tests/tokens.test.ts asserts
 * the two never drift apart.
 */

/** CSS reference pixels per typographic point (96 px per inch ÷ 72 pt per inch). */
export const PX_PER_PT = 96 / 72;

/** Convert points to CSS px (20 pt → 26.67 px). */
export function ptToPx(pt: number): number {
  return pt * PX_PER_PT;
}

/** Convert CSS px to points. */
export function pxToPt(px: number): number {
  return px / PX_PER_PT;
}

/** Base (and smallest) font size in points — equals `ui.min_font_pt`. */
export const BASE_FONT_PT = 20;

/** Smallest tap target side in CSS px — equals `ui.min_tap_px`. */
export const MIN_TAP_PX = 56;

/** Minimum contrast ratio for every colour pair (WCAG 2.x AAA for normal text). */
export const MIN_CONTRAST = 7;

/** Type scale in points; nothing below the base exists on purpose. */
export const fontSizePt = {
  base: BASE_FONT_PT,
  lg: 24,
  xl: 28,
  '2xl': 34,
  '3xl': 40,
} as const;

export type FontSizeName = keyof typeof fontSizePt;

function pxString(pt: number): string {
  return `${Number(ptToPx(pt).toFixed(4))}px`;
}

/** The same scale as CSS px strings, consumed by tailwind.config.ts. */
export const fontSizePx: Record<FontSizeName, string> = {
  base: pxString(fontSizePt.base),
  lg: pxString(fontSizePt.lg),
  xl: pxString(fontSizePt.xl),
  '2xl': pxString(fontSizePt['2xl']),
  '3xl': pxString(fontSizePt['3xl']),
};

/**
 * Colours the coach can name out loud ("bấm nút màu xanh có chữ Tiếp tục").
 * Hex values are chosen so every pair in `contrastPairs` reaches `MIN_CONTRAST`.
 */
export const colors = {
  xanh: '#1E40AF',
  do: '#991B1B',
  vang: '#FACC15',
  xam: '#3F3F46',
  trang: '#FFFFFF',
  den: '#111111',
} as const;

export type ColorName = keyof typeof colors;

export interface ContrastPair {
  bg: ColorName;
  fg: ColorName;
  /** Where the pair is used, in plain Vietnamese. */
  usage: string;
}

/** Every background/foreground combination the components are allowed to use. */
export const contrastPairs: readonly ContrastPair[] = [
  { bg: 'xanh', fg: 'trang', usage: 'nút chính (Nói với tôi)' },
  { bg: 'do', fg: 'trang', usage: 'nút dừng / cảnh báo' },
  { bg: 'vang', fg: 'den', usage: 'nút Gọi tình nguyện viên' },
  { bg: 'xam', fg: 'trang', usage: 'nhãn Ứng dụng mô phỏng' },
  { bg: 'trang', fg: 'den', usage: 'chữ thường trên nền trắng' },
  { bg: 'trang', fg: 'xanh', usage: 'tiêu đề và nút phụ (Nói lại)' },
  { bg: 'trang', fg: 'do', usage: 'chữ cảnh báo trên nền trắng' },
];

/** Spacing scale in CSS px (8-pt grid, generous for big fingers). */
export const spacingPx = {
  xs: 8,
  sm: 12,
  md: 16,
  lg: 24,
  xl: 32,
  '2xl': 48,
} as const;

export type SpacingName = keyof typeof spacingPx;

/**
 * Long official wording (document names reach 600 characters, case labels 900) is shown as a
 * preview first: the first sentence when it ends within `maxChars` and is at least
 * `minSentenceChars` long, otherwise at most `maxChars` characters cut between two words.
 * A "Xem đủ" button always reveals the exact source text.
 */
export const textPreview = {
  maxChars: 120,
  minSentenceChars: 24,
} as const;

/** Side gutter of every screen in CSS px (phones from 360 px wide). */
export const GUTTER_PX = spacingPx.md;

export const tokens = {
  baseFontPt: BASE_FONT_PT,
  minTapPx: MIN_TAP_PX,
  minContrast: MIN_CONTRAST,
  fontSizePt,
  fontSizePx,
  colors,
  contrastPairs,
  spacingPx,
  gutterPx: GUTTER_PX,
  textPreview,
} as const;

export default tokens;
