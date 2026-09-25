import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useId } from 'react';
import { describe, expect, it } from 'vitest';
import { ExpandToggle, previewText, useExpandable } from '../src/components/ExpandableText';
import { vi } from '../src/i18n/vi';
import { textPreview } from '../src/theme/tokens';

// Test-only wording, visibly marked "thử" so it can never pass for a real document name.
const WORD = 'giấy thử';

/** `count` repetitions of "giấy thử" — long text with no sentence end. */
function words(count: number): string {
  return Array.from({ length: count }, () => WORD).join(' ');
}

describe('previewText — rút gọn chữ dài, không đổi nội dung', () => {
  it('ngưỡng rút gọn là token thiết kế, không quá 120 ký tự', () => {
    expect(textPreview.maxChars).toBeLessThanOrEqual(120);
    expect(textPreview.minSentenceChars).toBeGreaterThan(0);
    expect(textPreview.minSentenceChars).toBeLessThan(textPreview.maxChars);
  });

  it('chữ ngắn thì giữ nguyên (không cần nút Xem đủ)', () => {
    expect(previewText('Tờ khai thử (mẫu MAU01)')).toBeNull();
    expect(previewText('x'.repeat(textPreview.maxChars))).toBeNull();
  });

  it('chữ dài có câu đầu đủ dài thì lấy câu đầu', () => {
    const first = 'Giấy tờ chứng minh chỗ ở hợp pháp của người đăng ký thử';
    const text = `${first}. ${words(30)}`;
    expect(previewText(text)).toBe(`${first}…`);
  });

  it('dấu chấm phẩy cũng là hết câu', () => {
    const first = 'Tờ khai thay đổi thông tin thử (mẫu MAU01 ban hành kèm theo văn bản thử)';
    expect(previewText(`${first}; ${words(30)}`)).toBe(`${first}…`);
  });

  it('câu đầu quá ngắn (như "1.") thì bỏ qua, cắt theo số ký tự', () => {
    const text = `1. ${words(40)}`;
    const out = previewText(text) ?? '';
    expect(out.length).toBeGreaterThan(textPreview.minSentenceChars);
    expect(out.startsWith('1. giấy thử')).toBe(true);
  });

  it('không có câu ngắn thì cắt ở ranh giới từ, không quá ngưỡng, thêm dấu …', () => {
    const text = words(40);
    const out = previewText(text) ?? '';
    expect(out.endsWith('…')).toBe(true);
    const head = out.slice(0, -1);
    expect(head.length).toBeLessThanOrEqual(textPreview.maxChars);
    expect(text.startsWith(head)).toBe(true);
    // Never ends in the middle of a word.
    expect(text.charAt(head.length)).toBe(' ');
  });

  it('câu đầu dài hơn ngưỡng thì vẫn cắt theo số ký tự', () => {
    const text = `${words(30)}. Câu sau thử.`;
    const head = (previewText(text) ?? '').slice(0, -1);
    expect(head.length).toBeLessThanOrEqual(textPreview.maxChars);
    expect(text.startsWith(head)).toBe(true);
  });

  it('gộp khoảng trắng thừa, bỏ dấu câu treo ở cuối bản rút gọn', () => {
    const text = `Giấy tờ thử,   bản sao thử:\n${words(40)}`;
    const out = previewText(text) ?? '';
    expect(out).not.toMatch(/\s{2}|\n/);
    expect(out).not.toMatch(/[\s,;:(]…$/u);
  });
});

function Demo({ text }: { text: string }) {
  const id = useId();
  const state = useExpandable(text);
  return (
    <div>
      <p id={id} data-testid="shown">
        {state.shown}
      </p>
      <ExpandToggle state={state} controls={id} testId="toggle" />
    </div>
  );
}

describe('ExpandToggle — nút Xem đủ / Thu gọn', () => {
  it('chữ dài: hiện bản rút gọn và nút Xem đủ; bấm thì hiện đủ, bấm lại thì thu gọn', async () => {
    const text = words(40);
    render(<Demo text={text} />);
    const toggle = screen.getByTestId('toggle');
    expect(toggle).toHaveTextContent(vi.docs.showMore);
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(toggle).toHaveAttribute('aria-controls', screen.getByTestId('shown').id);
    expect(toggle.className).toContain('min-h-tap');
    expect(toggle.className).toContain('min-w-tap');
    expect(screen.getByTestId('shown').textContent).toBe(previewText(text));

    const user = userEvent.setup();
    await user.click(toggle);
    expect(screen.getByTestId('shown')).toHaveTextContent(text);
    expect(toggle).toHaveTextContent(vi.docs.showLess);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');

    await user.click(toggle);
    expect(screen.getByTestId('shown').textContent).toBe(previewText(text));
  });

  it('chữ ngắn: không có nút', () => {
    render(<Demo text="Tờ khai thử" />);
    expect(screen.getByTestId('shown')).toHaveTextContent('Tờ khai thử');
    expect(screen.queryByTestId('toggle')).toBeNull();
  });
});
