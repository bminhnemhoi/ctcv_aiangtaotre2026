import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { StrictMode } from 'react';
import { afterEach, describe, expect, it, vi as vitest } from 'vitest';
import App from '../src/App';
import { createClient } from '../src/api/client';
import { parseHash } from '../src/hooks/useHashRoute';
import { vi } from '../src/i18n/vi';
import { clearSession, getSession, startSession } from '../src/state/session';

describe('màn hình chính', () => {
  it('hiện tiêu đề, nhãn mô phỏng và ba nút bắt buộc', () => {
    render(<App />);
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(vi.appName);
    expect(screen.getByTestId('sim-badge')).toHaveTextContent(vi.simBadge);
    expect(screen.getByRole('button', { name: vi.buttons.speak })).toBeVisible();
    expect(screen.getByRole('button', { name: vi.buttons.repeat })).toBeVisible();
    expect(screen.getByRole('button', { name: vi.buttons.callVolunteer })).toBeVisible();
  });

  it('chỉ có một nút chính màu xanh', () => {
    render(<App />);
    const primaries = screen.getAllByRole('button').filter((b) => b.dataset.variant === 'xanh');
    expect(primaries).toHaveLength(1);
    expect(primaries[0]).toHaveTextContent(vi.buttons.speak);
  });

  it('phụ đề đổi khi bấm Nói với tôi, Nói lại và Gọi tình nguyện viên', async () => {
    const user = userEvent.setup();
    render(<App />);
    const subtitle = screen.getByTestId('subtitle');
    expect(subtitle).toHaveTextContent(vi.subtitle.idle);

    await user.click(screen.getByRole('button', { name: vi.buttons.speak }));
    expect(subtitle).toHaveTextContent(vi.subtitle.listening);
    expect(screen.getByRole('button', { name: vi.buttons.speak })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    expect(screen.getByTestId('voice-wave')).toHaveAttribute('data-active', 'true');

    await user.click(screen.getByRole('button', { name: vi.buttons.speak }));
    expect(subtitle).toHaveTextContent(vi.subtitle.idle);

    await user.click(screen.getByRole('button', { name: vi.buttons.repeat }));
    expect(subtitle).toHaveTextContent(vi.subtitle.repeat);

    await user.click(screen.getByRole('button', { name: vi.buttons.callVolunteer }));
    expect(subtitle).toHaveTextContent(vi.subtitle.volunteer);
    expect(screen.getByTestId('voice-wave')).toHaveAttribute('data-active', 'false');
  });

  it('phụ đề là vùng thông báo đọc được bởi trình đọc màn hình', () => {
    render(<App />);
    expect(screen.getByRole('status')).toHaveAttribute('aria-live', 'polite');
  });
});

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function fakeClient(handler: (path: string) => Response) {
  const fetchImpl = vitest.fn(async (input: RequestInfo | URL) => handler(String(input)));
  return { client: createClient({ baseUrl: '/v1', fetchImpl }), fetchImpl };
}

/** Every string leaf of `vi` (functions and arrays of strings included). */
function allStrings(value: unknown): string[] {
  if (typeof value === 'string') return [value];
  if (typeof value === 'object' && value !== null) return Object.values(value).flatMap(allStrings);
  return [];
}

describe('điều hướng theo dấu #', () => {
  afterEach(() => {
    clearSession();
    window.history.replaceState(null, '', '/');
  });

  it('parseHash: #hoi-thu-tuc, #can-bo, còn lại là trang đầu', () => {
    expect(parseHash('#hoi-thu-tuc')).toBe('hoi-thu-tuc');
    expect(parseHash('#can-bo')).toBe('can-bo');
    expect(parseHash('')).toBe('home');
    expect(parseHash('#')).toBe('home');
    expect(parseHash('#khac')).toBe('home');
    expect(parseHash('#HOI-THU-TUC')).toBe('home');
  });

  it('trang đầu có nút Hỏi thủ tục, bấm thì sang màn hỏi', async () => {
    const user = userEvent.setup();
    render(<App />);
    const button = screen.getByTestId('hoi-thu-tuc-button');
    expect(button).toHaveTextContent(vi.buttons.askProcedure);
    expect(button.className).toContain('min-h-tap');
    await user.click(button);
    expect(window.location.hash).toBe('#hoi-thu-tuc');
    expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent(vi.ask.title);
    expect(screen.getByText(vi.ask.needClass)).toBeVisible();
  });

  it('#can-bo mở màn cán bộ; đổi dấu # thì đổi màn', async () => {
    window.history.replaceState(null, '', '/#can-bo');
    render(<App />);
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(vi.officer.title);
    expect(screen.getByTestId('officer-login')).toBeVisible();
    act(() => {
      window.location.hash = '#hoi-thu-tuc';
      window.dispatchEvent(new HashChangeEvent('hashchange'));
    });
    expect(await screen.findByText(vi.ask.needClass)).toBeVisible();
  });

  it('mọi màn có nhãn mô phỏng; màn người dân luôn có Nói lại và Gọi tình nguyện viên', () => {
    for (const hash of ['/', '/#hoi-thu-tuc', '/#can-bo']) {
      window.history.replaceState(null, '', hash);
      const { unmount } = render(<App />);
      expect(screen.getByTestId('sim-badge'), hash).toHaveTextContent(vi.simBadge);
      if (hash !== '/#can-bo') {
        expect(screen.getByRole('button', { name: vi.buttons.repeat }), hash).toBeVisible();
        expect(screen.getByRole('button', { name: vi.buttons.callVolunteer }), hash).toBeVisible();
      }
      unmount();
    }
  });

  it('Gọi tình nguyện viên ở màn hỏi chỉ hướng dẫn thật, không giả vờ đã báo', async () => {
    startSession({ token: 'ma-lop', user_id: 'demo-citizen-1', role: 'citizen' });
    window.history.replaceState(null, '', '/#hoi-thu-tuc');
    render(<App />);
    await userEvent.setup().click(screen.getByTestId('btn-call'));
    expect(screen.getByTestId('volunteer-note')).toHaveTextContent(vi.subtitle.volunteer);
    for (const text of allStrings(vi)) {
      expect(text, text).not.toMatch(/đã (báo|gọi|gửi|liên hệ)|đang (tới|đến)|sẽ (gọi|liên hệ)/i);
    }
  });
});

/** Fake class code for tests (not a secret; kept out of `key: 'literal'` form for gitleaks). */
const SAMPLE_CLASS_CODE = ['lop', 'thu', 'nghiem', '0001'].join('-');

describe('vào lớp bằng ?lop=', () => {
  afterEach(() => {
    clearSession();
    window.history.replaceState(null, '', '/');
  });

  it('gọi join đúng một lần với tên Học viên, giữ mã trong bộ nhớ, bỏ mã khỏi địa chỉ', async () => {
    window.history.replaceState(null, '', `/?lop=${SAMPLE_CLASS_CODE}#hoi-thu-tuc`);
    const { client, fetchImpl } = fakeClient(() =>
      json(200, { token: 'ma-lop', user_id: 'demo-citizen-1', role: 'citizen' }),
    );
    render(
      <StrictMode>
        <App client={client} />
      </StrictMode>,
    );
    expect(await screen.findByTestId('ask-input')).toBeVisible();
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('/v1/auth/join');
    expect(JSON.parse(String(init.body))).toEqual({
      qr_token: SAMPLE_CLASS_CODE,
      display_name: vi.ask.learnerName,
    });
    expect(getSession()).toEqual({ token: 'ma-lop', userId: 'demo-citizen-1', role: 'citizen' });
    expect(window.localStorage.length).toBe(0);
    expect(window.location.search).toBe('');
    expect(window.location.hash).toBe('#hoi-thu-tuc');
  });

  it('join lỗi thì hiện câu của máy chủ dưới lời mời quét QR', async () => {
    window.history.replaceState(null, '', '/?lop=sai#hoi-thu-tuc');
    const message = 'Phần này đang được hoàn thiện.';
    const { client } = fakeClient(() => json(501, { error: { code: 'NOT_IMPLEMENTED', message } }));
    render(<App client={client} />);
    expect(await screen.findByRole('alert')).toHaveTextContent(message);
    expect(screen.getByText(vi.ask.needClass)).toBeVisible();
    await waitFor(() => expect(getSession().token).toBeNull());
  });

  it('không có ?lop thì không gọi máy chủ', () => {
    const { client, fetchImpl } = fakeClient(() => json(200, {}));
    render(<App client={client} />);
    expect(fetchImpl).not.toHaveBeenCalled();
  });
});
