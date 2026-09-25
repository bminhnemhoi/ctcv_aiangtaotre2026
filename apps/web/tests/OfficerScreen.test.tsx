import { act, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi as vitest } from 'vitest';
import { createClient } from '../src/api/client';
import type { ChecklistItem, IntakeCheckIn, IntakeCheckOut, ProcedureRef } from '../src/api/types';
import { previewText } from '../src/components/ExpandableText';
import { vi } from '../src/i18n/vi';
import { displayCaseLabel } from '../src/screens/DocumentsCard';
import { OfficerScreen } from '../src/screens/OfficerScreen';
import { clearSession, getSession, startSession } from '../src/state/session';

// Test-only data, visibly marked "thử" so it can never pass for real figures.
const REF: ProcedureRef = {
  procedure_id: 'thu-02',
  ten: 'Đăng ký tạm trú thử',
  co_quan: 'Công an xã thử',
  source_url: 'https://example.org/du-lieu-thu/thu-02',
  fetched_at: '2026-09-25T02:00:00Z',
};

const ALT: ProcedureRef = {
  ...REF,
  procedure_id: 'thu-03',
  ten: 'Gia hạn tạm trú thử',
  source_url: 'https://example.org/du-lieu-thu/thu-03',
};

/** Every document of this procedure belongs to a case (like "Đăng ký tạm trú" in the data). */
const CASE_REF: ProcedureRef = {
  ...REF,
  procedure_id: 'thu-04',
  ten: 'Đăng ký tạm trú theo trường hợp thử',
  source_url: 'https://example.org/du-lieu-thu/thu-04',
};

// Case labels are the source's lead-in sentence: sent back verbatim, shown without "gồm"/":".
const CASE_A = 'Hồ sơ đăng ký tạm trú cho người chưa thành niên thử gồm';
const CASE_A_SHOWN = 'Hồ sơ đăng ký tạm trú cho người chưa thành niên thử';
const CASE_B = 'Đăng ký tạm trú theo danh sách thử, hồ sơ gồm:';
const CASE_B_SHOWN = 'Đăng ký tạm trú theo danh sách thử';

type Doc = Omit<ChecklistItem, 'status'>;

function doc(doc_key: string, name: string, case_label: string | null = null): Doc {
  return { doc_key, name, case_label, originals: 1, copies: null, form_code: null };
}

const DOCS: Doc[] = [
  { ...doc('d01', 'Tờ khai thử'), copies: 0, form_code: 'MAU01' },
  { ...doc('d02', 'Giấy tờ chỗ ở thử'), originals: null, copies: 1 },
];

const CASE_DOCS: Doc[] = [
  doc('d03', 'Văn bản đồng ý thử', CASE_A),
  doc('d04', 'Giấy tờ chỗ ở của cha mẹ thử', CASE_A),
  doc('d05', 'Danh sách người đăng ký thử', CASE_B),
];

const MESSAGE = 'Anh/chị bổ sung Giấy tờ chỗ ở thử rồi quay lại nộp nhé.';

function pickRef(req: IntakeCheckIn): ProcedureRef {
  if (req.procedure_id === ALT.procedure_id) return ALT;
  if (req.procedure_id === CASE_REF.procedure_id) return CASE_REF;
  return req.query?.includes('trường hợp') ? CASE_REF : REF;
}

/** Mirrors the real API: common documents plus the chosen case only; `needs_case` until chosen. */
function intake(req: IntakeCheckIn): IntakeCheckOut {
  const ref = pickRef(req);
  const docs = ref === CASE_REF ? CASE_DOCS : DOCS;
  const cases = [...new Set(docs.flatMap((d) => (d.case_label ? [d.case_label] : [])))];
  const items = docs
    .filter((d) => !d.case_label || d.case_label === req.case_label)
    .map(
      (d) => ({ ...d, status: req.received.includes(d.doc_key) ? 'da_nhan' : 'thieu' }) as const,
    );
  const missing = items.filter((i) => i.status === 'thieu').length;
  return {
    procedure: ref,
    // Like the real API: alternatives only for a name search, never for a by-id request.
    alternatives: req.procedure_id ? [] : [ALT],
    cases,
    needs_case: cases.length > 0 && !req.case_label,
    items,
    missing_count: missing,
    message_for_citizen: missing ? MESSAGE : 'Hồ sơ đủ rồi.',
    citations: [
      {
        doc_id: 'tthc-thu-02-thanh_phan_ho_so-0',
        title: 'Đăng ký tạm trú thử — Thành phần hồ sơ',
        url: ref.source_url,
        source_portal: 'Cổng thử nghiệm',
        fetched_at: ref.fetched_at,
      },
    ],
  };
}

const LOGIN_OK = { token: 'ma-can-bo', user_id: 'demo-officer', role: 'officer' };

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

type Override = (body: IntakeCheckIn) => Response | Promise<Response>;

function fakeApi(overrides: Record<string, Override> = {}) {
  const fetchImpl = vitest.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    const override = overrides[path];
    if (override) return override(body as IntakeCheckIn);
    if (path === '/v1/auth/login') return json(200, LOGIN_OK);
    if (path === '/v1/coach/intake-check') return json(200, intake(body as IntakeCheckIn));
    return json(404, { error: { code: 'NOT_FOUND', message: 'Không có.' } });
  });
  return { client: createClient({ baseUrl: '/v1', fetchImpl }), fetchImpl };
}

function bodiesTo(fetchImpl: ReturnType<typeof fakeApi>['fetchImpl'], path: string): unknown[] {
  return fetchImpl.mock.calls
    .filter(([input]) => String(input) === path)
    .map(([, init]) => JSON.parse(String(init?.body)));
}

async function login(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByTestId('officer-username'), 'canbo-demo');
  await user.type(screen.getByTestId('officer-password'), 'mat-khau-thu-nghiem');
  await user.click(screen.getByTestId('officer-login-submit'));
  await screen.findByTestId('officer-query');
}

async function search(user: ReturnType<typeof userEvent.setup>, query = 'đăng ký tạm trú') {
  await user.type(screen.getByTestId('officer-query'), query);
  await user.click(screen.getByTestId('officer-search'));
  await screen.findByTestId('officer-procedure');
}

afterEach(() => {
  clearSession();
  vitest.restoreAllMocks();
});

describe('OfficerLogin', () => {
  it('chưa đăng nhập thì hiện ô tên và ô mật khẩu bị che', () => {
    render(<OfficerScreen client={fakeApi().client} />);
    expect(screen.getByTestId('officer-login')).toBeVisible();
    expect(screen.getByLabelText(vi.officer.username)).toBe(screen.getByTestId('officer-username'));
    expect(screen.getByTestId('officer-password')).toHaveAttribute('type', 'password');
    expect(screen.getByTestId('officer-login-submit')).toHaveTextContent(vi.buttons.login);
    expect(screen.queryByTestId('officer-query')).toBeNull();
  });

  it('người dân đã vào lớp vẫn phải đăng nhập mới dùng được màn cán bộ', () => {
    startSession({ token: 'ma-lop', user_id: 'demo-citizen-1', role: 'citizen' });
    render(<OfficerScreen client={fakeApi().client} />);
    expect(screen.getByTestId('officer-login')).toBeVisible();
  });

  it('sai mật khẩu thì hiện câu của máy chủ và xóa ô mật khẩu', async () => {
    const message = 'Tên đăng nhập hoặc mật khẩu chưa đúng, anh/chị kiểm tra lại nhé.';
    const { client } = fakeApi({
      '/v1/auth/login': () => json(401, { error: { code: 'INVALID_CREDENTIALS', message } }),
    });
    render(<OfficerScreen client={client} />);
    const user = userEvent.setup();
    await user.type(screen.getByTestId('officer-username'), 'canbo-demo');
    await user.type(screen.getByTestId('officer-password'), 'sai-mat-khau');
    await user.click(screen.getByTestId('officer-login-submit'));
    expect(await screen.findByRole('alert')).toHaveTextContent(message);
    expect(screen.getByTestId('officer-password')).toHaveValue('');
    expect(getSession().token).toBeNull();
  });

  it('không ghi mật khẩu hay mã vào localStorage', async () => {
    const setItem = vitest.spyOn(Storage.prototype, 'setItem');
    const { client, fetchImpl } = fakeApi();
    render(<OfficerScreen client={client} />);
    await login(userEvent.setup());
    expect(bodiesTo(fetchImpl, '/v1/auth/login')).toEqual([
      { username: 'canbo-demo', password: 'mat-khau-thu-nghiem' },
    ]);
    expect(setItem).not.toHaveBeenCalled();
    expect(getSession()).toEqual({ token: 'ma-can-bo', userId: 'demo-officer', role: 'officer' });
  });
});

describe('OfficerScreen — kiểm tra hồ sơ', () => {
  it('đăng nhập → tìm → đánh dấu → kiểm tra → danh sách thiếu, tin nhắn, nguồn', async () => {
    const { client, fetchImpl } = fakeApi();
    render(<OfficerScreen client={client} />);
    const user = userEvent.setup();
    // After setup(): user-event installs its own clipboard stub there.
    const writeText = vitest.fn(async () => undefined);
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
    await login(user);
    await search(user);

    const summary = screen.getByTestId('officer-procedure');
    expect(summary).toHaveTextContent(REF.ten);
    expect(summary).toHaveTextContent(`Cơ quan: ${REF.co_quan}`);
    expect(screen.getByTestId('checklist-item-d01')).not.toBeChecked();
    await user.click(screen.getByTestId('checklist-item-d01'));
    await user.click(screen.getByTestId('officer-check'));

    const missing = await screen.findByTestId('missing-list');
    expect(missing).toHaveTextContent('Còn thiếu 1 giấy tờ:');
    expect(missing).toHaveTextContent('Giấy tờ chỗ ở thử');
    expect(missing).not.toHaveTextContent('Tờ khai thử');
    expect(missing.className).toContain('text-do');
    expect(screen.getByTestId('citizen-message')).toHaveTextContent(MESSAGE);
    const link = screen.getByRole('link', { name: new RegExp(vi.officer.sourceLink) });
    expect(link).toHaveAttribute('href', REF.source_url);
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');

    await user.click(screen.getByTestId('copy-message'));
    expect(writeText).toHaveBeenCalledWith(MESSAGE);
    expect(await screen.findByText(vi.officer.copied)).toBeVisible();

    expect(bodiesTo(fetchImpl, '/v1/coach/intake-check')).toEqual([
      { query: 'đăng ký tạm trú', received: [] },
      { procedure_id: 'thu-02', received: ['d01'] },
    ]);
  });

  it('thủ tục không có trường hợp thì không hiện ô chọn, không gọi thêm', async () => {
    const { client, fetchImpl } = fakeApi();
    render(<OfficerScreen client={client} />);
    const user = userEvent.setup();
    await login(user);
    await search(user);
    expect(screen.queryByTestId('case-select')).toBeNull();
    expect(screen.queryByTestId('case-hint')).toBeNull();
    expect(screen.getByTestId('checklist-item-d02')).toBeVisible();
    expect(bodiesTo(fetchImpl, '/v1/coach/intake-check')).toHaveLength(1);
  });

  it('chọn trường hợp thì gọi lại API và hiện giấy tờ của trường hợp', async () => {
    const { client, fetchImpl } = fakeApi();
    render(<OfficerScreen client={client} />);
    const user = userEvent.setup();
    await login(user);
    await search(user, 'tạm trú theo trường hợp');
    // The first answer has no documents at all: every one belongs to a case.
    expect(screen.queryAllByTestId(/^checklist-item-/)).toHaveLength(0);
    expect(screen.getByTestId('case-hint')).toHaveTextContent(vi.officer.caseHint);
    const select = screen.getByTestId('case-select');
    expect(within(select).getByRole('option', { name: CASE_A_SHOWN })).toHaveValue(CASE_A);
    expect(within(select).getByRole('option', { name: CASE_B_SHOWN })).toHaveValue(CASE_B);

    await user.selectOptions(select, CASE_A);
    expect(await screen.findByTestId('checklist-item-d03')).toBeVisible();
    expect(screen.getByTestId('checklist-item-d04')).not.toBeChecked();
    expect(screen.queryByTestId('checklist-item-d05')).toBeNull();
    expect(screen.queryByTestId('case-hint')).toBeNull();
    expect(screen.getByTestId('case-select')).toHaveValue(CASE_A);
    expect(screen.getByText(CASE_A_SHOWN, { selector: 'legend' })).toBeVisible();
    // The by-id answer has no alternatives; the ones from the search stay on screen.
    expect(screen.getByTestId(`officer-alt-${ALT.procedure_id}`)).toBeVisible();
    expect(bodiesTo(fetchImpl, '/v1/coach/intake-check')).toEqual([
      { query: 'tạm trú theo trường hợp', received: [] },
      { procedure_id: 'thu-04', received: [], case_label: CASE_A },
    ]);
  });

  it('chọn trường hợp thì gửi case_label và chỉ hiện giấy tờ của trường hợp đó', async () => {
    const { client, fetchImpl } = fakeApi();
    render(<OfficerScreen client={client} />);
    const user = userEvent.setup();
    await login(user);
    await search(user, 'tạm trú theo trường hợp');
    await user.selectOptions(screen.getByTestId('case-select'), CASE_A);
    await user.click(await screen.findByTestId('checklist-item-d03'));
    await user.click(screen.getByTestId('officer-check'));
    const missing = await screen.findByTestId('missing-list');
    expect(missing).toHaveTextContent('Còn thiếu 1 giấy tờ:');
    expect(missing).toHaveTextContent('Giấy tờ chỗ ở của cha mẹ thử');
    expect(bodiesTo(fetchImpl, '/v1/coach/intake-check').at(-1)).toEqual({
      procedure_id: 'thu-04',
      received: ['d03'],
      case_label: CASE_A,
    });
  });

  it('đổi trường hợp thì tải lại danh mục, dấu đã đánh vẫn nhớ theo từng giấy tờ', async () => {
    const { client, fetchImpl } = fakeApi();
    render(<OfficerScreen client={client} />);
    const user = userEvent.setup();
    await login(user);
    await search(user, 'tạm trú theo trường hợp');
    await user.selectOptions(screen.getByTestId('case-select'), CASE_A);
    await user.click(await screen.findByTestId('checklist-item-d03'));

    await user.selectOptions(screen.getByTestId('case-select'), CASE_B);
    expect(await screen.findByTestId('checklist-item-d05')).not.toBeChecked();
    expect(screen.queryByTestId('checklist-item-d03')).toBeNull();
    await user.click(screen.getByTestId('officer-check'));
    await screen.findByTestId('missing-list');
    expect(bodiesTo(fetchImpl, '/v1/coach/intake-check').at(-1)).toEqual({
      procedure_id: 'thu-04',
      received: [],
      case_label: CASE_B,
    });

    await user.selectOptions(screen.getByTestId('case-select'), CASE_A);
    expect(await screen.findByTestId('checklist-item-d03')).toBeChecked();
    expect(screen.queryByTestId('missing-list')).toBeNull();

    await user.selectOptions(screen.getByTestId('case-select'), '');
    expect(await screen.findByTestId('case-hint')).toBeVisible();
    expect(screen.queryAllByTestId(/^checklist-item-/)).toHaveLength(0);
    expect(bodiesTo(fetchImpl, '/v1/coach/intake-check').at(-1)).toEqual({
      procedure_id: 'thu-04',
      received: [],
    });
  });

  it('tải trường hợp bị lỗi thì báo và giữ lựa chọn cũ', async () => {
    const message = 'Mất mạng rồi, bác thử lại sau một chút nhé.';
    const { client } = fakeApi({
      '/v1/coach/intake-check': (body) =>
        body.case_label === CASE_B
          ? json(503, { error: { code: 'UNAVAILABLE', message } })
          : json(200, intake(body)),
    });
    render(<OfficerScreen client={client} />);
    const user = userEvent.setup();
    await login(user);
    await search(user, 'tạm trú theo trường hợp');
    await user.selectOptions(screen.getByTestId('case-select'), CASE_A);
    await screen.findByTestId('checklist-item-d03');
    await user.selectOptions(screen.getByTestId('case-select'), CASE_B);
    expect(await screen.findByRole('alert')).toHaveTextContent(message);
    expect(screen.getByTestId('case-select')).toHaveValue(CASE_A);
    expect(screen.getByTestId('checklist-item-d03')).toBeVisible();
  });

  it('chỉ lấy câu trả lời của lần chọn trường hợp sau cùng', async () => {
    let releaseA: () => void = () => undefined;
    const slowA = new Promise<void>((resolve) => {
      releaseA = resolve;
    });
    const { client } = fakeApi({
      '/v1/coach/intake-check': async (body) => {
        if (body.case_label === CASE_A) await slowA;
        return json(200, intake(body));
      },
    });
    render(<OfficerScreen client={client} />);
    const user = userEvent.setup();
    await login(user);
    await search(user, 'tạm trú theo trường hợp');
    await user.selectOptions(screen.getByTestId('case-select'), CASE_A);
    await user.selectOptions(screen.getByTestId('case-select'), CASE_B);
    expect(await screen.findByTestId('checklist-item-d05')).toBeVisible();
    await act(async () => {
      releaseA();
      for (let tick = 0; tick < 5; tick += 1) await new Promise((r) => setTimeout(r, 10));
    });
    expect(screen.getByTestId('checklist-item-d05')).toBeVisible();
    expect(screen.queryByTestId('checklist-item-d03')).toBeNull();
    expect(screen.getByTestId('case-select')).toHaveValue(CASE_B);
  });

  it('thủ tục cần chọn trường hợp mà chưa chọn thì nhắc, không gửi', async () => {
    const { client, fetchImpl } = fakeApi();
    render(<OfficerScreen client={client} />);
    const user = userEvent.setup();
    await login(user);
    await search(user, 'tạm trú theo trường hợp');
    await user.click(screen.getByTestId('officer-check'));
    expect(screen.getByRole('alert')).toHaveTextContent(vi.officer.needsCase);
    expect(bodiesTo(fetchImpl, '/v1/coach/intake-check')).toHaveLength(1);
  });

  it('bấm thủ tục gần giống thì tải danh mục của thủ tục đó', async () => {
    const { client, fetchImpl } = fakeApi();
    render(<OfficerScreen client={client} />);
    const user = userEvent.setup();
    await login(user);
    await search(user);
    const alt = screen.getByRole('button', { name: new RegExp(ALT.ten) });
    await user.click(alt);
    expect(await screen.findByText(ALT.ten, { selector: 'h2' })).toBeVisible();
    expect(bodiesTo(fetchImpl, '/v1/coach/intake-check').at(-1)).toEqual({
      procedure_id: 'thu-03',
      received: [],
    });
  });

  it('đổi ô đánh dấu sau khi kiểm tra thì ẩn kết quả cũ', async () => {
    const { client } = fakeApi();
    render(<OfficerScreen client={client} />);
    const user = userEvent.setup();
    await login(user);
    await search(user);
    await user.click(screen.getByTestId('officer-check'));
    await screen.findByTestId('missing-list');
    await user.click(screen.getByTestId('checklist-item-d02'));
    expect(screen.queryByTestId('missing-list')).toBeNull();
  });

  it('không tìm thấy thủ tục thì hiện câu của máy chủ', async () => {
    const message = 'Chưa tìm thấy thủ tục này trong kho, anh/chị thử gõ tên khác nhé.';
    const { client } = fakeApi({
      '/v1/coach/intake-check': () =>
        json(404, { error: { code: 'PROCEDURE_NOT_FOUND', message } }),
    });
    render(<OfficerScreen client={client} />);
    const user = userEvent.setup();
    await login(user);
    await user.type(screen.getByTestId('officer-query'), 'thủ tục lạ');
    await user.click(screen.getByTestId('officer-search'));
    expect(await screen.findByRole('alert')).toHaveTextContent(message);
    expect(screen.queryByTestId('officer-procedure')).toBeNull();
  });

  it('tên thủ tục quá ngắn thì nhắc, không gọi máy chủ', async () => {
    const { client, fetchImpl } = fakeApi();
    render(<OfficerScreen client={client} />);
    const user = userEvent.setup();
    await login(user);
    await user.type(screen.getByTestId('officer-query'), 'a');
    await user.click(screen.getByTestId('officer-search'));
    expect(screen.getByRole('alert')).toHaveTextContent(vi.officer.shortQuery);
    expect(bodiesTo(fetchImpl, '/v1/coach/intake-check')).toHaveLength(0);
  });

  it('không sao chép được thì hướng dẫn sao chép tay', async () => {
    const { client } = fakeApi();
    render(<OfficerScreen client={client} />);
    const user = userEvent.setup();
    Object.defineProperty(navigator, 'clipboard', { value: undefined, configurable: true });
    await login(user);
    await search(user);
    await user.click(screen.getByTestId('officer-check'));
    await user.click(await screen.findByTestId('copy-message'));
    expect(await screen.findByText(vi.officer.copyFailed)).toBeVisible();
    const result = screen.getByTestId('citizen-message');
    expect(within(result).getByText(MESSAGE)).toBeVisible();
  });
});

describe('displayCaseLabel — nhãn trường hợp gọn hơn, giá trị gửi đi giữ nguyên', () => {
  it.each([
    ['Hồ sơ đăng ký tạm trú gồm', 'Hồ sơ đăng ký tạm trú'],
    ['Đăng ký tạm trú theo danh sách, hồ sơ gồm', 'Đăng ký tạm trú theo danh sách'],
    ['Hồ sơ đề nghị sát hạch của cá nhân gồm:', 'Hồ sơ đề nghị sát hạch của cá nhân'],
    ['Hồ sơ gia hạn bao gồm:', 'Hồ sơ gia hạn'],
    ['Đối với cơ quan, tổ chức:', 'Đối với cơ quan, tổ chức'],
    ['  Trường hợp thuộc điểm c khoản 1 :  ', 'Trường hợp thuộc điểm c khoản 1'],
    ['Người dưới 14 tuổi', 'Người dưới 14 tuổi'],
    ['Giấy tờ bao gồm cả bản sao', 'Giấy tờ bao gồm cả bản sao'],
  ])('%j → %j', (raw, shown) => {
    expect(displayCaseLabel(raw)).toBe(shown);
  });

  it('không bỏ hết chữ khi nhãn chỉ có "Hồ sơ gồm"', () => {
    expect(displayCaseLabel('Hồ sơ gồm:')).toBe('Hồ sơ gồm');
    expect(displayCaseLabel('gồm')).toBe('gồm');
  });

  it('nhận cả chữ tiếng Việt dựng sẵn lẫn tổ hợp (NFD)', () => {
    expect(displayCaseLabel('Hồ sơ đăng ký tạm trú gồm'.normalize('NFD'))).toBe(
      'Hồ sơ đăng ký tạm trú',
    );
  });
});

// ---- conditional documents and long official wording (v2) ---------------------------------
const COND_REF: ProcedureRef = {
  ...REF,
  procedure_id: 'thu-06',
  ten: 'Đăng ký thường trú thử',
  source_url: 'https://example.org/du-lieu-thu/thu-06',
};
const LONG_DOC =
  'Giấy tờ, tài liệu thử chứng minh việc sở hữu chỗ ở hợp pháp của người đăng ký thử. Trừ ' +
  'trường hợp thông tin thử đã có trong cơ sở dữ liệu thử thì cán bộ thử tự tra cứu, người ' +
  'đăng ký thử không phải nộp thêm giấy tờ thử nào khác.';
const COND_DOC = 'Trường hợp thử người định cư ở nước ngoài thì nộp tờ khai thử mẫu CT02';
const LONG_CASE =
  'Trường hợp thử đăng ký vào chỗ ở hợp pháp không thuộc quyền sở hữu của mình, gồm vợ về ở ' +
  'với chồng, chồng về ở với vợ, con về ở với cha mẹ, người cao tuổi về ở với anh chị em ' +
  'ruột thử, hồ sơ gồm';

type CondMode = 'status' | 'flag';

function escapeRe(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/** The two shapes the API may use for "only if it applies" (ADR-007 C6, optional fields). */
function condIntake(mode: CondMode): Override {
  const docs: Doc[] = [doc('d01', LONG_DOC), doc('d02', COND_DOC), doc('d03', 'Tờ khai thử')];
  return (req) => {
    const items: ChecklistItem[] = docs.map((d) => {
      const conditional = d.doc_key === 'd02';
      const received = req.received.includes(d.doc_key);
      const status = received
        ? 'da_nhan'
        : conditional && mode === 'status'
          ? 'neu_ap_dung'
          : 'thieu';
      return mode === 'flag' ? { ...d, status, conditional } : { ...d, status };
    });
    const missing = items.filter((i) => i.status === 'thieu' && i.doc_key !== 'd02').length;
    return json(200, {
      ...intake({ ...req, procedure_id: REF.procedure_id }),
      procedure: COND_REF,
      alternatives: [],
      items,
      missing_count: missing,
      message_for_citizen: MESSAGE,
    });
  };
}

describe('OfficerScreen — giấy tờ chỉ cần khi đúng trường hợp, tên dài', () => {
  it.each<CondMode>(['status', 'flag'])(
    'giấy tờ có điều kiện có nhãn riêng, không bị tính là còn thiếu (%s)',
    async (mode) => {
      const { client } = fakeApi({ '/v1/coach/intake-check': condIntake(mode) });
      render(<OfficerScreen client={client} />);
      const user = userEvent.setup();
      await login(user);
      await search(user, 'thường trú thử');
      expect(screen.getByTestId('checklist-item-d02')).toHaveAccessibleName(
        new RegExp(`^${vi.docs.conditional}`),
      );
      expect(screen.getByTestId('checklist-item-d03')).not.toHaveAccessibleName(
        new RegExp(vi.docs.conditional),
      );
      await user.click(screen.getByTestId('checklist-item-d03'));
      await user.click(screen.getByTestId('officer-check'));

      const missing = await screen.findByTestId('missing-list');
      expect(missing).toHaveTextContent('Còn thiếu 1 giấy tờ:');
      expect(missing).toHaveTextContent('Giấy tờ, tài liệu thử chứng minh việc sở hữu');
      expect(missing).not.toHaveTextContent(COND_DOC);
      const conditional = screen.getByTestId('conditional-list');
      expect(conditional).toHaveTextContent(vi.officer.conditionalHeading);
      expect(conditional).toHaveTextContent(COND_DOC);
      expect(conditional.className).not.toContain('text-do');
    },
  );

  it('đã nhận giấy tờ có điều kiện thì không nhắc lại; đủ giấy bắt buộc thì báo đủ', async () => {
    const { client } = fakeApi({ '/v1/coach/intake-check': condIntake('status') });
    render(<OfficerScreen client={client} />);
    const user = userEvent.setup();
    await login(user);
    await search(user, 'thường trú thử');
    for (const key of ['d01', 'd02', 'd03']) {
      await user.click(screen.getByTestId(`checklist-item-${key}`));
    }
    await user.click(screen.getByTestId('officer-check'));
    expect(await screen.findByTestId('complete-note')).toHaveTextContent(vi.officer.complete);
    expect(screen.queryByTestId('conditional-list')).toBeNull();
  });

  it('chỉ thiếu giấy tờ có điều kiện thì vẫn báo đủ, kèm lời nhắc hỏi thêm', async () => {
    const { client } = fakeApi({ '/v1/coach/intake-check': condIntake('flag') });
    render(<OfficerScreen client={client} />);
    const user = userEvent.setup();
    await login(user);
    await search(user, 'thường trú thử');
    await user.click(screen.getByTestId('checklist-item-d01'));
    await user.click(screen.getByTestId('checklist-item-d03'));
    await user.click(screen.getByTestId('officer-check'));
    expect(await screen.findByTestId('complete-note')).toBeVisible();
    expect(screen.queryByTestId('missing-list')).toBeNull();
    expect(screen.getByTestId('conditional-list')).toHaveTextContent(COND_DOC);
  });

  it('tên giấy tờ dài trong danh mục: bản rút gọn và nút Xem đủ, không tự đánh dấu', async () => {
    const { client } = fakeApi({ '/v1/coach/intake-check': condIntake('status') });
    render(<OfficerScreen client={client} />);
    const user = userEvent.setup();
    await login(user);
    await search(user, 'thường trú thử');
    const box = screen.getByTestId('checklist-item-d01');
    expect(box).toHaveAccessibleName(new RegExp(`^${escapeRe(previewText(LONG_DOC) ?? '')}`));
    const more = screen.getByTestId('more-checklist-item-d01');
    await user.click(more);
    expect(more).toHaveAttribute('aria-expanded', 'true');
    expect(box).toHaveAccessibleName(new RegExp('người đăng ký thử không phải nộp thêm'));
    expect(box).not.toBeChecked();
    expect(screen.queryByTestId('more-checklist-item-d03')).toBeNull();
  });

  it('ô chọn trường hợp rút gọn nhãn dài; giá trị gửi đi vẫn là nguyên văn', async () => {
    const needsCase: Override = (req) =>
      json(200, {
        ...intake({ ...req, procedure_id: REF.procedure_id }),
        procedure: COND_REF,
        cases: [LONG_CASE],
        needs_case: !req.case_label,
        items: [],
        missing_count: 0,
      });
    const { client, fetchImpl } = fakeApi({ '/v1/coach/intake-check': needsCase });
    render(<OfficerScreen client={client} />);
    const user = userEvent.setup();
    await login(user);
    await search(user, 'thường trú thử');
    const select = screen.getByTestId('case-select');
    const shown = previewText(displayCaseLabel(LONG_CASE)) ?? '';
    expect(within(select).getByRole('option', { name: shown })).toHaveValue(LONG_CASE);
    await user.selectOptions(select, LONG_CASE);
    expect(bodiesTo(fetchImpl, '/v1/coach/intake-check').at(-1)).toEqual({
      procedure_id: COND_REF.procedure_id,
      received: [],
      case_label: LONG_CASE,
    });
  });
});
