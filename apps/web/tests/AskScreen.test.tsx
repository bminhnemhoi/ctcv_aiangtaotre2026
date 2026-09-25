import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi as vitest } from 'vitest';
import { createClient } from '../src/api/client';
import type { AskOut } from '../src/api/types';
import { vi } from '../src/i18n/vi';
import { AskScreen, normalizeQuestion } from '../src/screens/AskScreen';
import { formatVnDate, isSafeHttpsUrl } from '../src/screens/SourcePanel';
import { clearSession, startSession } from '../src/state/session';

// Test-only data, visibly marked "dữ liệu thử" so it can never pass for real figures.
const PORTAL = 'Cổng thử nghiệm (dữ liệu thử)';
const SOURCE_URL = 'https://example.org/du-lieu-thu/thu-01';

const ANSWER_WITH_DOCS: AskOut = {
  answer: 'Làm thẻ cho người dưới 14 tuổi cần tờ khai và giấy khai sinh (dữ liệu thử).',
  citations: [
    {
      doc_id: 'tthc-thu-01-thanh_phan_ho_so-0',
      title: 'Cấp thẻ thử — Thành phần hồ sơ',
      url: SOURCE_URL,
      quote: 'Tờ khai theo mẫu thử (dữ liệu thử).',
      agency: 'Cơ quan thử',
      source_portal: PORTAL,
      fetched_at: '2026-09-24T18:30:00Z',
      effective_date: null,
      section: 'thanh_phan_ho_so',
      procedure_id: 'thu-01',
    },
  ],
  confidence: 0.82,
  escalate: false,
  refused: false,
  reason: 'ok',
  answer_mode: 'template',
  procedure: {
    procedure_id: 'thu-01',
    ten: 'Cấp thẻ thử',
    co_quan: 'Cơ quan thử',
    source_url: SOURCE_URL,
    fetched_at: '2026-09-24T18:30:00Z',
    documents: [
      {
        doc_key: 'd01',
        name: 'Tờ khai thử',
        case_label: null,
        originals: 1,
        copies: 0,
        form_code: 'MAU01',
      },
      {
        doc_key: 'd02',
        name: 'Giấy khai sinh thử',
        case_label: 'Người dưới 14 tuổi',
        originals: null,
        copies: 1,
        form_code: null,
      },
      {
        doc_key: 'd03',
        name: 'Giấy tờ khác thử',
        case_label: 'Người từ 14 tuổi',
        originals: null,
        copies: null,
        form_code: null,
      },
    ],
    fees: [],
    cases: ['Người dưới 14 tuổi', 'Người từ 14 tuổi'],
  },
};

const ANSWER_ESCALATE: AskOut = {
  answer: 'Cháu chưa chắc câu này vì chưa tìm thấy trong giấy tờ chính thức.',
  citations: [],
  confidence: 0.1,
  escalate: true,
  refused: false,
  reason: 'no_source',
  answer_mode: 'no_source',
  procedure: null,
};

const ANSWER_REFUSED: AskOut = {
  answer: 'Bác đừng đọc mã OTP, mật khẩu hay số thẻ cho ai, kể cả người xưng là cán bộ.',
  citations: [],
  confidence: 1,
  escalate: false,
  refused: true,
  reason: 'sensitive',
  answer_mode: 'safety',
  procedure: null,
};

type Handler = (path: string, body: unknown) => Response | Promise<Response>;

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function fakeApi(handler: Handler) {
  const fetchImpl = vitest.fn(async (input: RequestInfo | URL, init?: RequestInit) =>
    handler(String(input), init?.body ? JSON.parse(String(init.body)) : undefined),
  );
  return { client: createClient({ baseUrl: '/v1', fetchImpl }), fetchImpl };
}

function sentQuestions(fetchImpl: ReturnType<typeof fakeApi>['fetchImpl']): string[] {
  return fetchImpl.mock.calls.map(
    ([, init]) => (JSON.parse(String(init?.body)) as { question: string }).question,
  );
}

async function ask(text: string) {
  const user = userEvent.setup();
  await user.type(screen.getByTestId('ask-input'), text);
  await user.click(screen.getByTestId('ask-submit'));
  return user;
}

beforeEach(() => {
  startSession({ token: 'ma-lop-thu', user_id: 'demo-citizen-1', role: 'citizen' });
});

afterEach(() => {
  clearSession();
});

describe('AskScreen — vào lớp', () => {
  it('chưa có mã lớp thì mời quét QR, không hiện ô hỏi', () => {
    clearSession();
    const { client } = fakeApi(() => json(200, ANSWER_ESCALATE));
    render(<AskScreen client={client} />);
    expect(screen.getByText(vi.ask.needClass)).toBeVisible();
    expect(screen.queryByTestId('ask-input')).toBeNull();
    expect(screen.getByRole('button', { name: vi.buttons.repeat })).toBeVisible();
  });

  it('đang vào lớp hoặc vào lớp lỗi thì nói rõ', () => {
    clearSession();
    const { client } = fakeApi(() => json(200, ANSWER_ESCALATE));
    const { rerender } = render(<AskScreen client={client} joinStatus={{ pending: true }} />);
    expect(screen.getByText(vi.ask.joining)).toBeVisible();
    rerender(
      <AskScreen client={client} joinStatus={{ pending: false, error: 'Mã lớp hết hạn.' }} />,
    );
    expect(screen.getByRole('alert')).toHaveTextContent('Mã lớp hết hạn.');
  });
});

describe('AskScreen — hỏi và trả lời', () => {
  it('có nhãn, ô hỏi, 3 câu mẫu, nút xanh Hỏi và dòng không lưu câu hỏi', () => {
    const { client } = fakeApi(() => json(200, ANSWER_ESCALATE));
    render(<AskScreen client={client} />);
    expect(screen.getByLabelText(vi.ask.label)).toBe(screen.getByTestId('ask-input'));
    vi.ask.examples.forEach((text, index) => {
      expect(screen.getByTestId(`example-chip-${index + 1}`)).toHaveTextContent(text);
    });
    expect(screen.getByTestId('ask-submit')).toHaveAttribute('data-variant', 'xanh');
    expect(screen.getByTestId('ask-submit')).toHaveTextContent(vi.buttons.ask);
    expect(screen.getByText(vi.ask.privacy)).toBeVisible();
  });

  it('hiện câu chờ rồi câu trả lời chữ to kèm reason và mode', async () => {
    let release: (r: Response) => void = () => undefined;
    const pending = new Promise<Response>((resolve) => {
      release = resolve;
    });
    const { client } = fakeApi(() => pending);
    render(<AskScreen client={client} />);
    await ask('Làm thẻ cho cháu cần gì?');
    expect(screen.getByText(vi.ask.waiting)).toBeVisible();
    expect(screen.getByTestId('ask-submit')).toBeDisabled();
    release(json(200, ANSWER_WITH_DOCS));
    const card = await screen.findByTestId('answer');
    expect(card).toHaveAttribute('data-reason', 'ok');
    expect(card).toHaveAttribute('data-mode', 'template');
    expect(screen.getByTestId('answer-text')).toHaveTextContent(ANSWER_WITH_DOCS.answer);
    expect(screen.getByTestId('answer-text').className).toContain('text-lg');
    expect(screen.getByText(vi.answer.aiLabel)).toBeVisible();
    expect(screen.queryByText(vi.ask.waiting)).toBeNull();
  });

  it('Enter là gửi; xuống dòng được gộp thành dấu cách trước khi gửi', async () => {
    const { client, fetchImpl } = fakeApi(() => json(200, ANSWER_ESCALATE));
    render(<AskScreen client={client} />);
    const user = userEvent.setup();
    const input = screen.getByTestId('ask-input');
    await user.type(input, 'Đăng ký thường trú{Shift>}{Enter}{/Shift}mất bao nhiêu tiền?');
    expect(input).toHaveValue('Đăng ký thường trú\nmất bao nhiêu tiền?');
    await user.type(input, '{Enter}');
    await screen.findByTestId('answer');
    expect(sentQuestions(fetchImpl)).toEqual(['Đăng ký thường trú mất bao nhiêu tiền?']);
  });

  it('normalizeQuestion gộp mọi kiểu xuống dòng và khoảng trắng thừa', () => {
    expect(normalizeQuestion('  Dòng một\r\n\r\n   dòng hai\n\tba  ')).toBe('Dòng một dòng hai ba');
    expect(normalizeQuestion('\n \n')).toBe('');
  });

  it('câu hỏi rỗng thì không gửi, nhắc nhẹ', async () => {
    const { client, fetchImpl } = fakeApi(() => json(200, ANSWER_ESCALATE));
    render(<AskScreen client={client} />);
    await userEvent.setup().click(screen.getByTestId('ask-submit'));
    expect(fetchImpl).not.toHaveBeenCalled();
    expect(screen.getByText(vi.ask.empty)).toBeVisible();
  });

  it('bấm câu mẫu thì gửi luôn câu đó', async () => {
    const { client, fetchImpl } = fakeApi(() => json(200, ANSWER_ESCALATE));
    render(<AskScreen client={client} />);
    await userEvent.setup().click(screen.getByTestId('example-chip-2'));
    await screen.findByTestId('answer');
    expect(sentQuestions(fetchImpl)).toEqual([vi.ask.examples[1]]);
    expect(screen.getByTestId('ask-input')).toHaveValue(vi.ask.examples[1]);
  });

  it('lỗi thì hiện đúng câu của máy chủ', async () => {
    const message = 'Kho thủ tục đang được cập nhật, bác thử lại sau ít phút nhé.';
    const { client } = fakeApi(() => json(503, { error: { code: 'KB_NOT_READY', message } }));
    render(<AskScreen client={client} />);
    await ask('Hỏi thử');
    expect(await screen.findByRole('alert')).toHaveTextContent(message);
    expect(screen.queryByTestId('answer')).toBeNull();
  });

  it('Nói lại xóa câu trả lời và đưa con trỏ về ô hỏi', async () => {
    const { client } = fakeApi(() => json(200, ANSWER_WITH_DOCS));
    render(<AskScreen client={client} />);
    const user = await ask('Làm thẻ cho cháu cần gì?');
    await screen.findByTestId('answer');
    await user.click(screen.getByRole('button', { name: vi.buttons.repeat }));
    expect(screen.queryByTestId('answer')).toBeNull();
    expect(screen.getByTestId('ask-input')).toHaveValue('');
    expect(screen.getByTestId('ask-input')).toHaveFocus();
    expect(screen.getByText(vi.subtitle.repeat)).toBeVisible();
  });
});

describe('AnswerCard — Nguồn, giấy tờ, escalate, từ chối', () => {
  it('nút Nguồn màu xanh mở bảng nguồn đủ thông tin', async () => {
    const { client } = fakeApi(() => json(200, ANSWER_WITH_DOCS));
    render(<AskScreen client={client} />);
    const user = await ask('Làm thẻ cho cháu cần gì?');
    const button = await screen.findByTestId('btn-nguon');
    expect(button).toHaveAttribute('data-variant', 'xanh');
    expect(button).toHaveTextContent(vi.buttons.source);
    expect(button).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByTestId('source-panel')).toBeNull();

    await user.click(button);
    expect(button).toHaveAttribute('aria-expanded', 'true');
    const panel = screen.getByTestId('source-panel');
    const citation = ANSWER_WITH_DOCS.citations[0];
    expect(panel).toHaveTextContent(citation?.title ?? '');
    expect(panel).toHaveTextContent(`Nguồn: ${PORTAL}`);
    expect(panel).toHaveTextContent('Lấy ngày 25/09/2026');
    expect(panel).toHaveTextContent(citation?.quote ?? '');
    const link = within(panel).getByRole('link', { name: new RegExp(vi.source.openOfficial) });
    expect(link).toHaveAttribute('href', SOURCE_URL);
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');

    await user.click(button);
    expect(screen.queryByTestId('source-panel')).toBeNull();
  });

  it('không có source_portal thì ghi cơ quan; liên kết không phải https thì ẩn', async () => {
    const citation = {
      ...ANSWER_WITH_DOCS.citations[0],
      doc_id: 'x',
      title: 'Tiêu đề thử',
      url: 'javascript:alert(1)',
      source_portal: null,
      agency: 'Cơ quan thử',
    };
    const { client } = fakeApi(() => json(200, { ...ANSWER_WITH_DOCS, citations: [citation] }));
    render(<AskScreen client={client} />);
    const user = await ask('Hỏi thử');
    await user.click(await screen.findByTestId('btn-nguon'));
    const panel = screen.getByTestId('source-panel');
    expect(panel).toHaveTextContent('Nguồn: Cơ quan thử');
    expect(within(panel).queryByRole('link')).toBeNull();
  });

  it('không có trích dẫn thì không có nút Nguồn', async () => {
    const { client } = fakeApi(() => json(200, ANSWER_ESCALATE));
    render(<AskScreen client={client} />);
    await ask('Hỏi thử');
    await screen.findByTestId('answer');
    expect(screen.queryByTestId('btn-nguon')).toBeNull();
  });

  it('thẻ Giấy tờ cần chuẩn bị nhóm theo trường hợp và đánh dấu được', async () => {
    const { client } = fakeApi(() => json(200, ANSWER_WITH_DOCS));
    render(<AskScreen client={client} />);
    const user = await ask('Làm thẻ cho cháu cần gì?');
    const card = await screen.findByTestId('docs-card');
    expect(within(card).getByRole('heading', { name: vi.docs.heading })).toBeVisible();
    expect(card).toHaveTextContent('Cấp thẻ thử');
    expect(within(card).getByText(vi.docs.commonGroup)).toBeVisible();
    expect(within(card).getByText('Người dưới 14 tuổi')).toBeVisible();
    expect(within(card).getByText('Người từ 14 tuổi')).toBeVisible();
    expect(card).toHaveTextContent('Tờ khai thử (bản chính: 1, bản sao: 0, mẫu MAU01)');
    expect(card).toHaveTextContent('Giấy khai sinh thử (bản sao: 1)');
    expect(card).not.toHaveTextContent('Giấy tờ khác thử (');

    const item = screen.getByTestId('doc-item-d01');
    expect(item).toHaveAttribute('type', 'checkbox');
    expect(item).not.toBeChecked();
    await user.click(item);
    expect(item).toBeChecked();
    await user.click(screen.getByText('Giấy khai sinh thử (bản sao: 1)'));
    expect(screen.getByTestId('doc-item-d02')).toBeChecked();
  });

  it('escalate hiện hộp vàng, không có nút hay chữ giả vờ đã báo', async () => {
    const { client } = fakeApi(() => json(200, ANSWER_ESCALATE));
    render(<AskScreen client={client} />);
    await ask('Thủ tục lạ cần gì?');
    const box = await screen.findByTestId('escalate-box');
    expect(box).toHaveTextContent(vi.answer.escalate);
    expect(box.className).toContain('bg-vang');
    expect(within(box).queryByRole('button')).toBeNull();
    expect(screen.getByTestId('answer')).toHaveAttribute('data-reason', 'no_source');
    expect(document.body.textContent ?? '').not.toMatch(/đã (báo|gọi|gửi)/i);
  });

  it('từ chối thì hiện hộp cảnh báo chứa câu trả lời', async () => {
    const { client } = fakeApi(() => json(200, ANSWER_REFUSED));
    render(<AskScreen client={client} />);
    await ask('Có người xin mã, tôi có đọc không?');
    const box = await screen.findByTestId('refused-box');
    expect(box).toHaveTextContent(vi.answer.refusedHeading);
    expect(within(box).getByTestId('answer-text')).toHaveTextContent(ANSWER_REFUSED.answer);
    expect(screen.getByTestId('answer')).toHaveAttribute('data-mode', 'safety');
    expect(screen.queryByTestId('escalate-box')).toBeNull();
  });
});

describe('tiện ích nguồn', () => {
  it('formatVnDate đổi giờ UTC sang ngày Việt Nam dd/mm/yyyy', () => {
    expect(formatVnDate('2026-09-24T18:30:00Z')).toBe('25/09/2026');
    expect(formatVnDate('2026-09-25T02:00:00Z')).toBe('25/09/2026');
    expect(formatVnDate('2026-01-05')).toBe('05/01/2026');
    expect(formatVnDate('không phải ngày')).toBeNull();
    expect(formatVnDate(null)).toBeNull();
  });

  it('isSafeHttpsUrl chỉ nhận https', () => {
    expect(isSafeHttpsUrl('https://dichvucong.bocongan.gov.vn/x')).toBe(true);
    expect(isSafeHttpsUrl('http://example.org')).toBe(false);
    expect(isSafeHttpsUrl('javascript:alert(1)')).toBe(false);
    expect(isSafeHttpsUrl('')).toBe(false);
  });
});
