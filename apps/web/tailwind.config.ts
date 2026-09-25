import type { Config } from 'tailwindcss';
import { MIN_TAP_PX, colors, fontSizePx, spacingPx } from './src/theme/tokens';

const spacing = Object.fromEntries(
  Object.entries(spacingPx).map(([name, px]) => [name, `${px}px`]),
) as Record<keyof typeof spacingPx, string>;

const fontSize = Object.fromEntries(
  Object.entries(fontSizePx).map(([name, px]) => [name, [px, { lineHeight: '1.35' }]]),
) as Record<keyof typeof fontSizePx, [string, { lineHeight: string }]>;

const tap = `${MIN_TAP_PX}px`;

/**
 * Tailwind consumes the design tokens; the default type scale is replaced entirely so no
 * class below 20 pt exists (`text-sm`, `text-xs` are not generated on purpose).
 */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    fontSize,
    extend: {
      colors,
      spacing: { ...spacing, tap },
      minHeight: { tap },
      minWidth: { tap },
      fontFamily: {
        sans: [
          'system-ui',
          'Segoe UI',
          'Roboto',
          'Noto Sans',
          'Helvetica Neue',
          'Arial',
          'sans-serif',
        ],
      },
    },
  },
  plugins: [],
} satisfies Config;
