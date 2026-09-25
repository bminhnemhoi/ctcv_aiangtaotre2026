/**
 * WCAG 2.x relative luminance and contrast ratio for hex colours.
 * Reference: https://www.w3.org/TR/WCAG21/#dfn-contrast-ratio
 */

const HEX_RE = /^#(?:[0-9a-f]{3}|[0-9a-f]{6})$/i;

/** Parse `#RGB` or `#RRGGBB` into 0–255 channels; throws on anything else. */
export function hexToRgb(hex: string): [number, number, number] {
  if (!HEX_RE.test(hex)) throw new Error(`Mã màu không hợp lệ: ${hex}`);
  let body = hex.slice(1);
  if (body.length === 3) {
    body = body
      .split('')
      .map((c) => c + c)
      .join('');
  }
  const value = Number.parseInt(body, 16);
  return [(value >> 16) & 0xff, (value >> 8) & 0xff, value & 0xff];
}

function linearise(channel: number): number {
  const c = channel / 255;
  return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

/** Relative luminance in [0, 1] (0 = black, 1 = white). */
export function relativeLuminance(hex: string): number {
  const [r, g, b] = hexToRgb(hex);
  return 0.2126 * linearise(r) + 0.7152 * linearise(g) + 0.0722 * linearise(b);
}

/** Contrast ratio between two colours, from 1 (identical) to 21 (black on white). */
export function contrastRatio(a: string, b: string): number {
  const la = relativeLuminance(a);
  const lb = relativeLuminance(b);
  const [hi, lo] = la >= lb ? [la, lb] : [lb, la];
  return (hi + 0.05) / (lo + 0.05);
}

/** True when the pair reaches `minimum` (default 7:1 — WCAG AAA for normal text). */
export function meetsContrast(a: string, b: string, minimum = 7): boolean {
  return contrastRatio(a, b) >= minimum;
}
