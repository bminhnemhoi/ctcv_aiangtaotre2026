/**
 * Long official wording, shown short first. Document names in the real data run to 600
 * characters (case labels to 900): on a phone with 20 pt text that is a wall of 30 lines per
 * tick box. The preview is the first sentence, or at most `textPreview.maxChars` characters cut
 * between words, followed by "…"; the "Xem đủ" button reveals the exact source text. Nothing is
 * rewritten: the preview is always a prefix of the source text.
 */
import { useState } from 'react';
import { vi } from '../i18n/vi';
import { textPreview } from '../theme/tokens';

/** A full stop or semicolon followed by a space ends a sentence ("1.004222" does not). */
const SENTENCE_END = /[.;](?=\s)/gu;
/** Punctuation that must not dangle before the "…". */
const TRAILING = /[\s,;:.(–-]+$/u;

function firstSentenceEnd(text: string, minChars: number): number {
  for (const match of text.matchAll(SENTENCE_END)) {
    if (match.index >= minChars) return match.index;
  }
  return -1;
}

function cutAtWord(text: string, maxChars: number): string {
  const space = text.lastIndexOf(' ', maxChars);
  return space > 0 ? text.slice(0, space) : text.slice(0, maxChars);
}

/** The preview of `text`, or `null` when the text is short enough to show in full. */
export function previewText(
  text: string,
  maxChars: number = textPreview.maxChars,
  minSentenceChars: number = textPreview.minSentenceChars,
): string | null {
  const clean = text.replace(/\s+/gu, ' ').trim();
  if (clean.length <= maxChars) return null;
  const end = firstSentenceEnd(clean, minSentenceChars);
  const head = end !== -1 && end <= maxChars ? clean.slice(0, end) : cutAtWord(clean, maxChars);
  return `${head.replace(TRAILING, '')}…`;
}

export interface Expandable {
  /** What to render now: the preview, or the full text once opened (or when short). */
  shown: string;
  canExpand: boolean;
  expanded: boolean;
  toggle: () => void;
}

/** Preview/full state of one piece of text. */
export function useExpandable(text: string): Expandable {
  const [expanded, setExpanded] = useState(false);
  const preview = previewText(text);
  return {
    shown: expanded || preview === null ? text : preview,
    canExpand: preview !== null,
    expanded,
    toggle: () => setExpanded((value) => !value),
  };
}

export interface ExpandToggleProps {
  state: Expandable;
  /** `id` of the element whose text is shortened. */
  controls: string;
  testId?: string;
  className?: string;
}

/** "Xem đủ" / "Thu gọn" — a real button (≥ 56 px), rendered only when there is more to show. */
export function ExpandToggle({ state, controls, testId, className = '' }: ExpandToggleProps) {
  if (!state.canExpand) return null;
  return (
    <button
      type="button"
      data-testid={testId}
      aria-expanded={state.expanded}
      aria-controls={controls}
      onClick={state.toggle}
      className={`min-h-tap min-w-tap self-start rounded-2xl border-4 border-xanh bg-trang px-md py-xs text-base font-bold leading-tight text-xanh shadow-sm active:scale-95 ${className}`}
    >
      {state.expanded ? vi.docs.showLess : vi.docs.showMore}
    </button>
  );
}
