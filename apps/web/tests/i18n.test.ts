import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { vi } from '../src/i18n/vi';

const GUARDRAILS_PATH = resolve(__dirname, '../../../config/guardrails.yaml');

/** Read `banned_terms[].term` from config/guardrails.yaml without a YAML parser. */
function bannedTerms(): string[] {
  const text = readFileSync(GUARDRAILS_PATH, 'utf8');
  const block = /^banned_terms:\n((?:[ \t]+-[^\n]*\n)+)/m.exec(text)?.[1] ?? '';
  return [...block.matchAll(/term:\s*([^,}]+)/g)].map((m) => (m[1] ?? '').trim());
}

function flatten(value: unknown, path = ''): [string, string][] {
  if (typeof value === 'string') return [[path, value]];
  if (typeof value === 'object' && value !== null) {
    return Object.entries(value).flatMap(([k, v]) => flatten(v, path ? `${path}.${k}` : k));
  }
  return [];
}

function containsWholeWord(text: string, term: string): boolean {
  const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return new RegExp(`(?<![\\p{L}\\p{N}_])${escaped}(?![\\p{L}\\p{N}_])`, 'iu').test(text);
}

describe('chuỗi tiếng Việt', () => {
  const strings = flatten(vi);

  it('có đủ các nhãn bắt buộc', () => {
    expect(vi.buttons.repeat).toBe('Nói lại');
    expect(vi.buttons.callVolunteer).toBe('Gọi tình nguyện viên');
    expect(vi.simBadge).toBe('Ứng dụng mô phỏng');
  });

  it('không chuỗi nào rỗng', () => {
    for (const [path, text] of strings) expect(text.trim(), path).not.toBe('');
  });

  it('không dùng thuật ngữ trong config/guardrails.yaml: banned_terms', () => {
    const terms = bannedTerms();
    expect(terms.length).toBeGreaterThan(5);
    for (const [path, text] of strings) {
      for (const term of terms) {
        expect(containsWholeWord(text, term), `${path} chứa thuật ngữ "${term}"`).toBe(false);
      }
    }
  });
});
