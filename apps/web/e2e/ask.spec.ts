import AxeBuilder from '@axe-core/playwright';
import { mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, test, type Page, type Route, type TestInfo } from '@playwright/test';
import { readAppConfig } from '../ctcv-config';
import { vi } from '../src/i18n/vi';
import { ptToPx } from '../src/theme/tokens';

/**
 * "Hỏi thủ tục" and "#can-bo" on the three phone viewports, with `/v1/**` mocked by
 * `page.route` (UI test only — the recorded demo runs against the real API, see e2e/demo).
 * Every mock string says "dữ liệu thử" so no screenshot can pass for real figures.
 */

const app = readAppConfig();
const minFontPx = ptToPx(app.minFontPt);
const HERE = dirname(fileURLToPath(import.meta.url));
/** Screenshots for review are taken on this viewport only. */
const SHOT_VIEWPORT = '390x844';

const CLASS_CODE = 'lop-thu-nghiem-0001';
const CITIZEN_TOKEN = 'ma-lop-thu';
const OFFICER_TOKEN = 'ma-can-bo-thu';
const MOCK_URL = 'https://example.org/du-lieu-thu/thu-tuc-mau';
const MOCK_FETCHED_AT = '2026-09-24T18:30:00Z';
const MOCK_PORTAL = 'Cổng thử nghiệm (dữ liệu thử)';

const Q_FEE = 'Đăng ký thường trú mất bao nhiêu tiền?';
const Q_DOCS = 'Làm căn cước cho cháu 14 tuổi cần giấy tờ gì?';
const Q_UNKNOWN = 'Thủ tục đăng ký kết hôn cần những gì?';
const Q_OTP = 'Có người xưng công an gọi xin mã OTP, tôi có đọc không?';

const CITATION = {
  doc_id: 'tthc-thu-01-phi_le_phi-0',
  title: 'Thủ tục mẫu (dữ liệu thử) — Phí, lệ phí',
  url: MOCK_URL,
  quote: 'Đoạn trích mẫu dùng để kiểm thử màn hình (dữ liệu thử).',
  agency: 'Cơ quan thử',
  source_portal: MOCK_PORTAL,
  fetched_at: MOCK_FETCHED_AT,
  effective_date: null,
  section: 'phi_le_phi',
  procedure_id: 'thu-01',
};

interface MockDoc {
  doc_key: string;
  name: string;
  case_label: string | null;
  originals: number | null;
  copies: number | null;
  form_code: string | null;
  conditional?: boolean;
}

const DOCUMENTS: MockDoc[] = [
  {
    doc_key: 'd01',
    name: 'Tờ khai mẫu (dữ liệu thử)',
    case_label: null,
    originals: 1,
    copies: 0,
    form_code: 'MAU01',
  },
  {
    doc_key: 'd02',
    name: 'Giấy khai sinh mẫu (dữ liệu thử)',
    case_label: 'Trường hợp mẫu A',
    originals: null,
    copies: 1,
    form_code: null,
  },
  {
    doc_key: 'd03',
    name: 'Văn bản đồng ý mẫu (dữ liệu thử)',
    case_label: 'Trường hợp mẫu B',
    originals: 1,
    copies: null,
    form_code: null,
  },
];

// The real data has names up to 600 characters: the card shows the first sentence + "Xem đủ".
const LONG_HEAD = 'Giấy tờ chứng minh chỗ ở mẫu (dữ liệu thử)';
const LONG_TAIL = 'phần giải thích dài chỉ hiện khi bấm Xem đủ (dữ liệu thử)';
const LONG_DOC: MockDoc = {
  doc_key: 'd04',
  name: `${LONG_HEAD}. Trừ trường hợp thông tin mẫu đã có trong cơ sở dữ liệu mẫu thì không phải nộp, ${LONG_TAIL}.`,
  case_label: null,
  originals: 1,
  copies: 0,
  form_code: null,
};
const COND_DOC: MockDoc = {
  doc_key: 'd05',
  name: 'Trường hợp mẫu ở nước ngoài về thì nộp tờ khai mẫu khác (dữ liệu thử)',
  case_label: null,
  originals: 1,
  copies: null,
  form_code: null,
  conditional: true,
};
const ASK_DOCUMENTS: MockDoc[] = [...DOCUMENTS, LONG_DOC, COND_DOC];

const PROCEDURE = {
  procedure_id: 'thu-01',
  ten: 'Thủ tục mẫu (dữ liệu thử)',
  co_quan: 'Cơ quan thử',
  source_url: MOCK_URL,
  fetched_at: MOCK_FETCHED_AT,
};

function askReply(question: string) {
  const base = { citations: [CITATION], confidence: 0.8, escalate: false, refused: false };
  if (question.includes('tiền')) {
    const answer =
      'Đây là câu trả lời mẫu để kiểm thử màn hình, không phải số liệu thật. Bác bấm nút xanh có chữ Nguồn để xem trang gốc nhé.';
    return { ...base, answer, reason: 'ok', answer_mode: 'template', procedure: null };
  }
  if (question.includes('giấy tờ')) {
    const answer =
      'Đây là danh mục mẫu (dữ liệu thử). Bác xem thẻ Giấy tờ cần chuẩn bị ngay bên dưới nhé.';
    const procedure = {
      ...PROCEDURE,
      documents: ASK_DOCUMENTS,
      fees: [],
      cases: ['Trường hợp mẫu A', 'Trường hợp mẫu B'],
    };
    return { ...base, answer, reason: 'ok', answer_mode: 'template', procedure };
  }
  if (question.includes('OTP')) {
    const answer = 'Bác đừng đọc mã OTP, mật khẩu hay số thẻ cho ai, kể cả người xưng là cán bộ.';
    return {
      ...base,
      citations: [],
      answer,
      refused: true,
      reason: 'sensitive',
      answer_mode: 'safety',
      procedure: null,
    };
  }
  const answer = 'Cháu chưa chắc câu này vì chưa tìm thấy trong giấy tờ chính thức.';
  return {
    ...base,
    citations: [],
    answer,
    escalate: true,
    confidence: 0.1,
    reason: 'no_source',
    answer_mode: 'no_source',
    procedure: null,
  };
}

/** Every document belongs to a case, like "Đăng ký tạm trú" in the real data. */
const CASE_PROCEDURE = {
  ...PROCEDURE,
  procedure_id: 'thu-04',
  ten: 'Thủ tục theo trường hợp (dữ liệu thử)',
};
// Case labels are the source's lead-in sentence: sent back verbatim, shown without "gồm".
const CASE_ONE = 'Hồ sơ trường hợp mẫu thứ nhất gồm';
const CASE_ONE_SHOWN = 'Hồ sơ trường hợp mẫu thứ nhất';
const CASE_TWO = 'Trường hợp mẫu theo danh sách, hồ sơ gồm';
const CASE_TWO_SHOWN = 'Trường hợp mẫu theo danh sách';

const CASE_DOCUMENTS: MockDoc[] = [
  {
    doc_key: 'd01',
    name: 'Tờ khai mẫu (dữ liệu thử)',
    case_label: CASE_ONE,
    originals: 1,
    copies: 0,
    form_code: 'MAU01',
  },
  {
    doc_key: 'd02',
    name: 'Giấy tờ chỗ ở mẫu (dữ liệu thử)',
    case_label: CASE_ONE,
    originals: 1,
    copies: null,
    form_code: null,
  },
  {
    doc_key: 'd04',
    name: 'Trường hợp mẫu có điều kiện thì nộp thêm giấy mẫu (dữ liệu thử)',
    case_label: CASE_ONE,
    originals: 1,
    copies: null,
    form_code: null,
    conditional: true,
  },
  {
    doc_key: 'd03',
    name: 'Văn bản đề nghị mẫu (dữ liệu thử)',
    case_label: CASE_TWO,
    originals: 1,
    copies: null,
    form_code: null,
  },
];

const OTHER_PROCEDURE = {
  ...PROCEDURE,
  procedure_id: 'thu-02',
  ten: 'Thủ tục mẫu khác (dữ liệu thử)',
};

interface IntakeBody {
  query?: string;
  procedure_id?: string;
  received: string[];
  case_label?: string;
}

function pickProcedure(body: IntakeBody) {
  const byCase = body.procedure_id
    ? body.procedure_id === CASE_PROCEDURE.procedure_id
    : (body.query ?? '').includes('trường hợp');
  return byCase
    ? { procedure: CASE_PROCEDURE, documents: CASE_DOCUMENTS }
    : { procedure: PROCEDURE, documents: DOCUMENTS };
}

/**
 * Mirrors the real `/v1/coach/intake-check` (services/agent intake.py): common documents plus
 * the chosen case only, `needs_case` until a case is sent, alternatives only for a name search,
 * 422 for a case the procedure does not have.
 */
function intakeReply(body: IntakeBody): { status: number; json: unknown } {
  const { procedure, documents } = pickProcedure(body);
  const cases = [...new Set(documents.flatMap((d) => (d.case_label ? [d.case_label] : [])))];
  if (body.case_label && !cases.includes(body.case_label)) {
    const message = 'Trường hợp này không có trong danh mục (dữ liệu thử).';
    return { status: 422, json: { error: { code: 'CASE_NOT_FOUND', message } } };
  }
  const items = documents
    .filter((d) => !d.case_label || d.case_label === body.case_label)
    .map((d) => ({ ...d, status: body.received.includes(d.doc_key) ? 'da_nhan' : 'thieu' }));
  // "Only if it applies" documents are never counted as missing (services/agent intake.py).
  const missing = items.filter((i) => i.status === 'thieu' && !i.conditional);
  const json = {
    procedure,
    alternatives: body.procedure_id ? [] : [OTHER_PROCEDURE],
    cases,
    needs_case: cases.length > 0 && !body.case_label,
    items,
    missing_count: missing.length,
    message_for_citizen:
      'Tin nhắn mẫu (dữ liệu thử): anh/chị bổ sung giấy tờ còn thiếu rồi quay lại nhé.',
    citations: [{ ...CITATION, section: 'thanh_phan_ho_so' }],
  };
  return { status: 200, json };
}

interface MockLog {
  joins: unknown[];
  logins: unknown[];
  asks: string[];
  intakes: unknown[];
}

async function fulfilJson(route: Route, status: number, json: unknown) {
  await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(json) });
}

async function mockApi(page: Page): Promise<MockLog> {
  const log: MockLog = { joins: [], logins: [], asks: [], intakes: [] };
  await page.route('**/v1/**', async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const body = request.postDataJSON() as Record<string, unknown> | null;
    const auth = request.headers().authorization;
    if (path.endsWith('/auth/join')) {
      log.joins.push(body);
      return fulfilJson(route, 200, {
        token: CITIZEN_TOKEN,
        user_id: 'demo-citizen-thu',
        role: 'citizen',
      });
    }
    if (path.endsWith('/auth/login')) {
      log.logins.push(body);
      return fulfilJson(route, 200, {
        token: OFFICER_TOKEN,
        user_id: 'demo-officer',
        role: 'officer',
      });
    }
    if (path.endsWith('/coach/ask') && auth === `Bearer ${CITIZEN_TOKEN}`) {
      const question = String(body?.question ?? '');
      log.asks.push(question);
      return fulfilJson(route, 200, askReply(question));
    }
    if (path.endsWith('/coach/intake-check') && auth === `Bearer ${OFFICER_TOKEN}`) {
      log.intakes.push(body);
      const reply = intakeReply(body as unknown as IntakeBody);
      return fulfilJson(route, reply.status, reply.json);
    }
    return fulfilJson(route, 401, {
      error: { code: 'UNAUTHORIZED', message: 'Chưa đăng nhập (thử).' },
    });
  });
  return log;
}

async function expectElderSizes(page: Page) {
  const problems = await page.evaluate(
    ({ minTap, minFont }) => {
      const out: string[] = [];
      const visible = (el: Element) => {
        const box = el.getBoundingClientRect();
        const style = getComputedStyle(el);
        return box.width > 1 && box.height > 1 && style.visibility !== 'hidden';
      };
      const label = (el: Element) =>
        `${el.tagName} "${(el.textContent ?? '').trim().slice(0, 40)}"`;
      for (const el of document.body.querySelectorAll('*')) {
        const ownText = [...el.childNodes].some(
          (n) => n.nodeType === 3 && (n.textContent ?? '').trim(),
        );
        if (!ownText || !visible(el)) continue;
        const size = Number.parseFloat(getComputedStyle(el).fontSize);
        if (size < minFont - 0.05) out.push(`chữ ${size}px: ${label(el)}`);
      }
      const targets =
        'button, a[href], input:not([type=checkbox]), select, textarea, label:has(input[type=checkbox])';
      for (const el of document.body.querySelectorAll(targets)) {
        if (!visible(el)) continue;
        const box = el.getBoundingClientRect();
        if (box.height < minTap - 0.5 || box.width < minTap - 0.5) {
          out.push(`vùng bấm ${Math.round(box.width)}x${Math.round(box.height)}: ${label(el)}`);
        }
      }
      return out;
    },
    { minTap: app.minTapPx, minFont: minFontPx },
  );
  expect(problems).toEqual([]);
}

async function expectAccessible(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'best-practice'])
    .analyze();
  const blocking = results.violations.filter(
    (v) => v.impact === 'serious' || v.impact === 'critical',
  );
  expect(blocking, JSON.stringify(blocking, null, 2)).toEqual([]);
  // AAA contrast (≥ 7:1 for normal text) — the product rule, stricter than WCAG AA.
  const aaa = await new AxeBuilder({ page }).withRules(['color-contrast-enhanced']).analyze();
  expect(aaa.violations, JSON.stringify(aaa.violations, null, 2)).toEqual([]);
}

/** Scrolled to the very end, the last content sits above the fixed "Gọi tình nguyện viên" bar. */
async function expectEndClearOfFooter(page: Page) {
  const box = await page.evaluate(() => {
    window.scrollTo(0, document.documentElement.scrollHeight);
    const main = document.querySelector('main')?.getBoundingClientRect();
    const footer = document.querySelector('footer')?.getBoundingClientRect();
    return { mainBottom: main?.bottom ?? Infinity, footerTop: footer?.top ?? -Infinity };
  });
  expect(box.mainBottom).toBeLessThanOrEqual(box.footerTop + 0.5);
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow, 'không được cuộn ngang').toBeLessThanOrEqual(0);
}

function isoDate(date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/** Save a review screenshot to docs/screens/<today>/ (390x844 only). */
async function shoot(page: Page, testInfo: TestInfo, name: string, fullPage = false) {
  if (testInfo.project.name !== SHOT_VIEWPORT) return;
  const dir = resolve(HERE, '../../../docs/screens', isoDate());
  mkdirSync(dir, { recursive: true });
  await page.screenshot({
    path: resolve(dir, `${isoDate()}-P5-${name}-${SHOT_VIEWPORT}.png`),
    fullPage,
  });
}

test.describe('Hỏi thủ tục (API giả trong test)', () => {
  test('vào lớp bằng ?lop= → hỏi → trả lời → Nguồn → giấy tờ', async ({ page }, testInfo) => {
    const log = await mockApi(page);
    await page.goto(`/?lop=${CLASS_CODE}#hoi-thu-tuc`);
    await expect(page.getByTestId('ask-input')).toBeVisible();
    expect(log.joins).toEqual([{ qr_token: CLASS_CODE, display_name: vi.ask.learnerName }]);
    expect(page.url()).not.toContain('lop=');
    await expect(page.getByTestId('sim-badge')).toHaveText(vi.simBadge);
    await expect(page.getByRole('button', { name: vi.buttons.repeat })).toBeVisible();
    await expect(page.getByTestId('btn-call')).toBeInViewport();
    await expectElderSizes(page);
    await shoot(page, testInfo, 'hoi-thu-tuc');

    await page.getByTestId('ask-input').fill('Đăng ký thường trú\nmất bao nhiêu tiền?');
    await page.getByTestId('ask-submit').click();
    const answer = page.getByTestId('answer');
    await expect(answer).toHaveAttribute('data-reason', 'ok');
    await expect(answer).toHaveAttribute('data-mode', 'template');
    expect(log.asks).toEqual([Q_FEE]);
    const nguon = page.getByTestId('btn-nguon');
    await expect(nguon).toHaveAttribute('data-variant', 'xanh');
    await nguon.click();
    const panel = page.getByTestId('source-panel');
    await expect(panel).toContainText(CITATION.title);
    await expect(panel).toContainText(`Nguồn: ${MOCK_PORTAL}`);
    await expect(panel).toContainText('Lấy ngày 25/09/2026');
    await expect(panel).toContainText(CITATION.quote);
    const link = panel.getByRole('link', { name: new RegExp(vi.source.openOfficial) });
    await expect(link).toHaveAttribute('href', MOCK_URL);
    await expect(link).toHaveAttribute('target', '_blank');
    await expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    await expectElderSizes(page);
    await expectAccessible(page);
    await shoot(page, testInfo, 'tra-loi-nguon-ca-trang', true);
    await nguon.evaluate((el) => el.scrollIntoView({ block: 'start' }));
    await shoot(page, testInfo, 'tra-loi-nguon');

    await page.getByTestId('ask-input').fill(Q_DOCS);
    await page.getByTestId('ask-input').press('Enter');
    const docs = page.getByTestId('docs-card');
    await expect(docs).toContainText(vi.docs.heading);
    await expect(docs).toContainText(
      'Tờ khai mẫu (dữ liệu thử) (bản chính: 1, bản sao: 0, mẫu MAU01)',
    );
    await page.getByTestId('doc-item-d01').check();
    await expect(page.getByTestId('doc-item-d01')).toBeChecked();
    expect(log.asks).toEqual([Q_FEE, Q_DOCS]);

    // Long official wording: first sentence + "Xem đủ"; the button never ticks the box.
    await expect(docs).toContainText(`${LONG_HEAD}… (bản chính: 1, bản sao: 0)`);
    await expect(docs).not.toContainText(LONG_TAIL);
    const more = page.getByTestId('more-doc-item-d04');
    await expect(more).toHaveText(vi.docs.showMore);
    await expect(more).toHaveAttribute('aria-expanded', 'false');
    await expectElderSizes(page);
    await more.evaluate((el) => el.closest('[data-testid^="doc-row-"]')?.scrollIntoView());
    await shoot(page, testInfo, 'giay-to-rut-gon');
    await more.click();
    await expect(docs).toContainText(LONG_TAIL);
    await expect(more).toHaveText(vi.docs.showLess);
    await expect(page.getByTestId('doc-item-d04')).not.toBeChecked();
    await expect(page.getByTestId('doc-item-d05')).toHaveAccessibleName(
      new RegExp(`^${vi.docs.conditional}`),
    );
    await expectEndClearOfFooter(page);
    await expectElderSizes(page);
    await expectAccessible(page);
    await docs.evaluate((el) => el.scrollIntoView({ block: 'start' }));
    await shoot(page, testInfo, 'giay-to');
  });

  test('câu ngoài kho → hộp vàng chưa chắc; câu OTP → hộp cảnh báo', async ({ page }, testInfo) => {
    await mockApi(page);
    await page.goto(`/?lop=${CLASS_CODE}#hoi-thu-tuc`);
    await page.getByTestId('ask-input').fill(Q_UNKNOWN);
    await page.getByTestId('ask-submit').click();
    const escalate = page.getByTestId('escalate-box');
    await expect(escalate).toHaveText(vi.answer.escalate);
    // A new answer scrolls itself clear of the fixed footer (focus alone does not scroll).
    const footerTop = await page.locator('footer').evaluate((el) => el.getBoundingClientRect().top);
    const box = await escalate.boundingBox();
    expect(box?.y ?? -1).toBeGreaterThanOrEqual(0);
    expect((box?.y ?? 0) + (box?.height ?? 0)).toBeLessThanOrEqual(footerTop);
    await expect(page.getByRole('heading', { name: vi.answer.heading })).toBeFocused();
    await expect(escalate.getByRole('button')).toHaveCount(0);
    await expect(page.getByTestId('btn-nguon')).toHaveCount(0);
    await expectAccessible(page);
    await shoot(page, testInfo, 'chua-chac');

    await page.getByTestId('ask-input').fill(Q_OTP);
    await page.getByTestId('ask-submit').click();
    await expect(page.getByTestId('refused-box')).toContainText(vi.answer.refusedHeading);
    await expect(page.getByTestId('answer')).toHaveAttribute('data-reason', 'sensitive');
    await expectAccessible(page);
    await shoot(page, testInfo, 'canh-bao-otp');
  });

  test('thanh Gọi tình nguyện viên không che phần cuối trang, kể cả khi hiện lời nhắc', async ({
    page,
  }, testInfo) => {
    await mockApi(page);
    await page.goto(`/?lop=${CLASS_CODE}#hoi-thu-tuc`);
    await page.getByTestId('ask-input').fill(Q_DOCS);
    await page.getByTestId('ask-submit').click();
    await expect(page.getByTestId('docs-card')).toBeVisible();
    await expectEndClearOfFooter(page);
    await page.getByTestId('btn-call').click();
    await expect(page.getByTestId('volunteer-note')).toHaveText(vi.subtitle.volunteer);
    await expectEndClearOfFooter(page);
    await shoot(page, testInfo, 'cuoi-trang-loi-nhac');
    await page.goto('/');
    await expectEndClearOfFooter(page);
  });

  test('chưa có mã lớp thì mời quét QR', async ({ page }) => {
    await mockApi(page);
    await page.goto('/#hoi-thu-tuc');
    await expect(page.getByText(vi.ask.needClass)).toBeVisible();
    await expect(page.getByTestId('ask-input')).toHaveCount(0);
    await expectAccessible(page);
  });

  test('trang đầu: nút Hỏi thủ tục không đẩy 3 nút cũ ra khỏi khung nhìn', async ({
    page,
  }, testInfo) => {
    await page.goto('/');
    for (const name of [vi.buttons.speak, vi.buttons.repeat, vi.buttons.callVolunteer]) {
      await expect(page.getByRole('button', { name })).toBeInViewport();
    }
    const entry = page.getByTestId('hoi-thu-tuc-button');
    await expect(entry).toHaveText(vi.buttons.askProcedure);
    // "Nói lại" is never covered by the fixed footer; the new entry sits below the E01
    // controls (never pushing them down) and can always be scrolled clear of the footer
    // (360x800 needs one short scroll).
    const footerTop = await page.locator('footer').evaluate((el) => el.getBoundingClientRect().top);
    const bottomOf = async (locator: typeof entry) => {
      const box = await locator.boundingBox();
      expect(box).not.toBeNull();
      return (box?.y ?? 0) + (box?.height ?? 0);
    };
    const repeat = page.getByRole('button', { name: vi.buttons.repeat });
    expect(await bottomOf(repeat)).toBeLessThanOrEqual(footerTop);
    await entry.evaluate((el) => el.scrollIntoView({ block: 'center' }));
    expect(await bottomOf(entry)).toBeLessThanOrEqual(footerTop);
    await page.evaluate(() => window.scrollTo(0, 0));
    await expectElderSizes(page);
    await shoot(page, testInfo, 'trang-dau');
    await entry.click();
    await expect(page).toHaveURL(/#hoi-thu-tuc$/);
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(vi.ask.title);
  });
});

test.describe('Màn cán bộ một cửa (API giả trong test)', () => {
  test('đăng nhập → tìm → đánh dấu → kiểm tra → thiếu gì, tin nhắn, nguồn', async ({
    page,
    context,
    baseURL,
  }, testInfo) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: baseURL });
    const log = await mockApi(page);
    await page.goto('/#can-bo');
    await expect(page.getByTestId('officer-login')).toBeVisible();
    await expect(page.getByTestId('officer-password')).toHaveAttribute('type', 'password');
    await expectElderSizes(page);
    await expectAccessible(page);
    await shoot(page, testInfo, 'can-bo-dang-nhap');

    await page.getByTestId('officer-username').fill('canbo-demo');
    await page.getByTestId('officer-password').fill('mat-khau-thu-nghiem');
    await page.getByTestId('officer-login-submit').click();
    await page.getByTestId('officer-query').fill('đăng ký tạm trú');
    await page.getByTestId('officer-search').click();
    const summary = page.getByTestId('officer-procedure');
    await expect(summary).toContainText(PROCEDURE.ten);
    await expect(summary).toContainText(`Cơ quan: ${PROCEDURE.co_quan}`);
    // Without a case the API lists the common documents only.
    await expect(page.getByTestId('case-hint')).toBeVisible();
    await expect(page.locator('[data-testid^="checklist-item-"]')).toHaveCount(1);
    await page.getByTestId('case-select').selectOption('Trường hợp mẫu A');
    await expect(page.getByTestId('checklist-item-d02')).toBeVisible();
    await expect(page.getByTestId('case-hint')).toHaveCount(0);
    await page.getByTestId('checklist-item-d01').check();
    await page.getByTestId('officer-check').click();

    const missing = page.getByTestId('missing-list');
    await expect(missing).toContainText('Còn thiếu 1 giấy tờ:');
    await expect(missing).toContainText('Giấy khai sinh mẫu (dữ liệu thử)');
    await expect(missing).toHaveCSS('color', 'rgb(153, 27, 27)');
    await expect(page.getByTestId('citizen-message')).toContainText('Tin nhắn mẫu (dữ liệu thử)');
    await page.getByTestId('copy-message').click();
    await expect(page.getByText(vi.officer.copied)).toBeVisible();
    await expect(
      page.getByRole('link', { name: new RegExp(vi.officer.sourceLink) }),
    ).toHaveAttribute('href', MOCK_URL);
    expect(log.logins).toEqual([{ username: 'canbo-demo', password: 'mat-khau-thu-nghiem' }]);
    expect(log.intakes).toEqual([
      { query: 'đăng ký tạm trú', received: [] },
      { procedure_id: 'thu-01', received: [], case_label: 'Trường hợp mẫu A' },
      { procedure_id: 'thu-01', received: ['d01'], case_label: 'Trường hợp mẫu A' },
    ]);
    const stored = await page.evaluate(() => localStorage.length + sessionStorage.length);
    expect(stored).toBe(0);
    await expectElderSizes(page);
    await expectAccessible(page);
    await missing.evaluate((el) => el.closest('section')?.scrollIntoView({ block: 'start' }));
    await shoot(page, testInfo, 'can-bo-ket-qua');
    await shoot(page, testInfo, 'can-bo-ket-qua-ca-trang', true);
  });

  test('chọn trường hợp thì gọi lại API và hiện giấy tờ của trường hợp', async ({
    page,
  }, testInfo) => {
    const log = await mockApi(page);
    await page.goto('/#can-bo');
    await page.getByTestId('officer-username').fill('canbo-demo');
    await page.getByTestId('officer-password').fill('mat-khau-thu-nghiem');
    await page.getByTestId('officer-login-submit').click();
    await page.getByTestId('officer-query').fill('tạm trú theo trường hợp');
    await page.getByTestId('officer-search').click();
    await expect(page.getByTestId('officer-procedure')).toContainText(CASE_PROCEDURE.ten);

    // Every document belongs to a case: nothing to tick until a case is chosen.
    const items = page.locator('[data-testid^="checklist-item-"]');
    await expect(page.getByTestId('case-hint')).toHaveText(vi.officer.caseHint);
    await expect(items).toHaveCount(0);
    const select = page.getByTestId('case-select');
    await expect(select.locator('option')).toHaveText([
      vi.officer.noCase,
      CASE_ONE_SHOWN,
      CASE_TWO_SHOWN,
    ]);
    await expectElderSizes(page);
    await expectAccessible(page);
    await shoot(page, testInfo, 'can-bo-cho-chon-truong-hop');

    await select.selectOption({ label: CASE_ONE_SHOWN });
    await expect(items).toHaveCount(3);
    await expect(page.getByTestId('checklist-item-d04')).toHaveAccessibleName(
      new RegExp(`^${vi.docs.conditional}`),
    );
    await expect(select).toHaveValue(CASE_ONE);
    await expect(page.getByTestId('case-hint')).toHaveCount(0);
    await expect(page.locator('legend', { hasText: CASE_ONE_SHOWN })).toBeVisible();
    await expect(page.getByTestId(`officer-alt-${OTHER_PROCEDURE.procedure_id}`)).toBeVisible();
    expect(log.intakes).toEqual([
      { query: 'tạm trú theo trường hợp', received: [] },
      { procedure_id: CASE_PROCEDURE.procedure_id, received: [], case_label: CASE_ONE },
    ]);
    await expectElderSizes(page);
    await expectAccessible(page);
    await select.evaluate((el) => el.scrollIntoView({ block: 'start' }));
    await shoot(page, testInfo, 'can-bo-da-chon-truong-hop');

    await page.getByTestId('checklist-item-d01').check();
    await page.getByTestId('officer-check').click();
    const missing = page.getByTestId('missing-list');
    await expect(missing).toContainText('Còn thiếu 1 giấy tờ:');
    await expect(missing).toContainText('Giấy tờ chỗ ở mẫu (dữ liệu thử)');
    await expect(missing).not.toContainText('có điều kiện');
    await expect(page.getByTestId('conditional-list')).toContainText(vi.officer.conditionalHeading);
    await expect(page.getByTestId('conditional-list')).toContainText('có điều kiện');
    await expect(page.getByTestId('citizen-message')).toContainText('Tin nhắn mẫu (dữ liệu thử)');
    await expectElderSizes(page);
    await expectAccessible(page);
    await missing.evaluate((el) => el.closest('section')?.scrollIntoView({ block: 'start' }));
    await shoot(page, testInfo, 'can-bo-giay-co-dieu-kien');
    expect(log.intakes.at(-1)).toEqual({
      procedure_id: CASE_PROCEDURE.procedure_id,
      received: ['d01'],
      case_label: CASE_ONE,
    });
    expect(log.intakes).toHaveLength(3);
  });
});
