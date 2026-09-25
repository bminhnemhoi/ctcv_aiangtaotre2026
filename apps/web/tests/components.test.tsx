import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { BigButton } from '../src/components/BigButton';
import { SimBadge } from '../src/components/SimBadge';
import { Subtitle } from '../src/components/Subtitle';
import { VoiceWave } from '../src/components/VoiceBar';
import { MicIcon } from '../src/components/icons';
import { vi } from '../src/i18n/vi';

describe('BigButton', () => {
  it('có vùng bấm tối thiểu, hình và chữ', () => {
    render(<BigButton label="Tiếp tục" icon={<MicIcon />} />);
    const button = screen.getByRole('button', { name: 'Tiếp tục' });
    expect(button.className).toContain('min-h-tap');
    expect(button.className).toContain('min-w-tap');
    expect(button.querySelector('[data-icon="mic"]')).not.toBeNull();
    expect(button).toHaveAttribute('type', 'button');
  });

  it('mỗi biến thể dùng đúng cặp màu có tên', () => {
    const { rerender } = render(<BigButton label="A" variant="vang" />);
    expect(screen.getByRole('button').className).toMatch(/bg-vang.*text-den/);
    rerender(<BigButton label="A" variant="do" />);
    expect(screen.getByRole('button').className).toMatch(/bg-do.*text-trang/);
    rerender(<BigButton label="A" variant="trang" />);
    expect(screen.getByRole('button').className).toMatch(/bg-trang.*text-xanh/);
  });
});

describe('Subtitle / SimBadge / VoiceWave', () => {
  it('Subtitle dùng cỡ chữ lớn và aria-live', () => {
    render(<Subtitle text="Xin chào bác" />);
    const p = screen.getByTestId('subtitle');
    expect(p).toHaveTextContent('Xin chào bác');
    expect(p.className).toContain('text-lg');
    expect(p).toHaveAttribute('aria-live', 'polite');
  });

  it('SimBadge hiện đúng chữ Ứng dụng mô phỏng', () => {
    render(<SimBadge />);
    expect(screen.getByTestId('sim-badge')).toHaveTextContent(vi.simBadge);
  });

  it('VoiceWave đổi nhãn theo trạng thái nghe', () => {
    const { rerender } = render(<VoiceWave active={false} />);
    expect(screen.getByRole('img')).toHaveAccessibleName(vi.voice.idleLabel);
    rerender(<VoiceWave active />);
    expect(screen.getByRole('img')).toHaveAccessibleName(vi.voice.listeningLabel);
    expect(screen.getByTestId('voice-wave').querySelectorAll('.voice-wave-bar')).toHaveLength(5);
  });
});
