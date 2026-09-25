/** Inline SVG glyphs (decorative — every icon sits next to a text label). */
import type { SVGProps } from 'react';

const base: SVGProps<SVGSVGElement> = {
  width: '1.2em',
  height: '1.2em',
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2.4,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  'aria-hidden': true,
  focusable: false,
};

export function MicIcon() {
  return (
    <svg {...base} data-icon="mic">
      <rect x="9" y="3" width="6" height="11" rx="3" fill="currentColor" stroke="none" />
      <path d="M5 11a7 7 0 0 0 14 0" />
      <path d="M12 18v3M8 21h8" />
    </svg>
  );
}

export function RepeatIcon() {
  return (
    <svg {...base} data-icon="repeat">
      <path d="M4 12a8 8 0 0 1 13.7-5.7L20 8" />
      <path d="M20 3v5h-5" />
      <path d="M20 12a8 8 0 0 1-13.7 5.7L4 16" />
      <path d="M4 21v-5h5" />
    </svg>
  );
}

export function PhoneIcon() {
  return (
    <svg {...base} data-icon="phone">
      <path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z" />
    </svg>
  );
}
