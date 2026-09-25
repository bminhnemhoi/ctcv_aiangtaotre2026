import { afterEach, describe, expect, it, vi as vitest } from 'vitest';
import {
  ASK_TIMEOUT_MS,
  ApiError,
  DEFAULT_API_BASE,
  NETWORK_ERROR_CODE,
  TIMEOUT_ERROR_CODE,
  UNKNOWN_ERROR_CODE,
  createClient,
  getAuthToken,
  isApiErrorBody,
  resolveBaseUrl,
  setAuthToken,
  toApiError,
} from '../src/api/client';
import { vi } from '../src/i18n/vi';
import { getSession, startSession } from '../src/state/session';

/** Fake class code for tests (not a secret; kept out of `key: 'literal'` form for gitleaks). */
const SAMPLE_CLASS_CODE = ['lop', 'thu', 'nghiem', '0001'].join('-');

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

afterEach(() => {
  vitest.unstubAllEnvs();
});

describe('resolveBaseUrl', () => {
  it('mặc định /v1 khi không có VITE_API_BASE', () => {
    vitest.stubEnv('VITE_API_BASE', '');
    expect(resolveBaseUrl()).toBe(DEFAULT_API_BASE);
  });

  it('đọc VITE_API_BASE và bỏ dấu / cuối', () => {
    vitest.stubEnv('VITE_API_BASE', 'https://api.example.org/v1/');
    expect(resolveBaseUrl()).toBe('https://api.example.org/v1');
    expect(createClient().baseUrl).toBe('https://api.example.org/v1');
  });
});

describe('createClient', () => {
  it('trả JSON khi 2xx và ghép đường dẫn đúng', async () => {
    const fetchImpl = vitest.fn(async () => jsonResponse(200, { status: 'ok', version: '0.1.0' }));
    const client = createClient({ baseUrl: '/v1', fetchImpl });
    await expect(client.health()).resolves.toEqual({ status: 'ok', version: '0.1.0' });
    expect(fetchImpl).toHaveBeenCalledWith(
      '/v1/health',
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('ánh xạ lỗi {error:{code,message}} thành ApiError', async () => {
    const body = {
      error: {
        code: 'NOT_IMPLEMENTED',
        message: 'Phần này đang được hoàn thiện.',
        details: { epic: 'E04' },
      },
    };
    const client = createClient({ baseUrl: '/v1', fetchImpl: async () => jsonResponse(501, body) });
    const error = await client.post('/speech/tts', { text: 'xin chào' }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    const apiError = error as ApiError;
    expect(apiError.code).toBe('NOT_IMPLEMENTED');
    expect(apiError.message).toBe(body.error.message);
    expect(apiError.status).toBe(501);
    expect(apiError.details).toEqual({ epic: 'E04' });
  });

  it('lỗi không đúng khuôn → mã UNKNOWN_ERROR và câu tiếng Việt thân thiện', async () => {
    const client = createClient({
      baseUrl: '/v1',
      fetchImpl: async () => new Response('<html>502</html>', { status: 502 }),
    });
    const error = (await client.get('/x').catch((e: unknown) => e)) as ApiError;
    expect(error.code).toBe(UNKNOWN_ERROR_CODE);
    expect(error.status).toBe(502);
    expect(error.message).toBe(vi.errors.generic);
  });

  it('mất mạng → NETWORK_ERROR, status 0', async () => {
    const client = createClient({
      baseUrl: '/v1',
      fetchImpl: async () => {
        throw new TypeError('Failed to fetch');
      },
    });
    const error = (await client.get('/health').catch((e: unknown) => e)) as ApiError;
    expect(error.code).toBe(NETWORK_ERROR_CODE);
    expect(error.status).toBe(0);
    expect(error.message).toBe(vi.errors.network);
  });

  it('post gửi JSON, postForm gửi multipart và 204 trả undefined', async () => {
    const fetchImpl = vitest.fn(async () => new Response(null, { status: 204 }));
    const client = createClient({ baseUrl: '/v1', fetchImpl });
    await expect(client.post('/a', { x: 1 })).resolves.toBeUndefined();
    const [, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(init.body).toBe('{"x":1}');
    expect((init.headers as Record<string, string>)['Content-Type']).toBe('application/json');

    const form = new FormData();
    form.append('audio', new Blob(['x']), 'a.wav');
    await client.postForm('/speech/asr', form);
    const [, formInit] = fetchImpl.mock.calls[1] as unknown as [string, RequestInit];
    expect(formInit.body).toBe(form);
  });
});

describe('helpers', () => {
  it('isApiErrorBody chỉ nhận đúng khuôn', () => {
    expect(isApiErrorBody({ error: { code: 'X', message: 'y' } })).toBe(true);
    expect(isApiErrorBody({ error: { code: 1 } })).toBe(false);
    expect(isApiErrorBody(null)).toBe(false);
    expect(isApiErrorBody('lỗi')).toBe(false);
  });

  it('toApiError không ném lỗi với body rỗng', async () => {
    const error = await toApiError(new Response(null, { status: 500 }));
    expect(error.code).toBe(UNKNOWN_ERROR_CODE);
  });
});

describe('mã đăng nhập giữ trong bộ nhớ và các hàm /v1 mới', () => {
  const ASK_OK = {
    answer: 'Câu trả lời thử.',
    citations: [],
    confidence: 0.9,
    escalate: false,
    refused: false,
    reason: 'ok',
    answer_mode: 'template',
    procedure: null,
  };

  function lastInit(fetchImpl: ReturnType<typeof vitest.fn>): [string, RequestInit] {
    return fetchImpl.mock.calls.at(-1) as unknown as [string, RequestInit];
  }

  function headersOf(init: RequestInit): Record<string, string> {
    return init.headers as Record<string, string>;
  }

  afterEach(() => {
    setAuthToken(null);
    vitest.restoreAllMocks();
  });

  it('gắn Authorization: Bearer khi đã có mã, gửi câu hỏi tới /coach/ask', async () => {
    setAuthToken('ma-thu.abc');
    const fetchImpl = vitest.fn(async () => jsonResponse(200, ASK_OK));
    const client = createClient({ baseUrl: '/v1', fetchImpl });
    await expect(client.ask('Đăng ký thường trú mất bao nhiêu tiền?')).resolves.toEqual(ASK_OK);
    const [url, init] = lastInit(fetchImpl);
    expect(url).toBe('/v1/coach/ask');
    expect(init.method).toBe('POST');
    expect(headersOf(init).Authorization).toBe('Bearer ma-thu.abc');
    expect(JSON.parse(String(init.body))).toEqual({
      question: 'Đăng ký thường trú mất bao nhiêu tiền?',
    });
  });

  it('không gắn Authorization khi chưa có mã, setAuthToken(null) xóa mã', async () => {
    const fetchImpl = vitest.fn(async () => jsonResponse(200, { status: 'ok', version: '1' }));
    const client = createClient({ baseUrl: '/v1', fetchImpl });
    setAuthToken('abc');
    expect(getAuthToken()).toBe('abc');
    setAuthToken(null);
    expect(getAuthToken()).toBeNull();
    await client.health();
    expect(headersOf(lastInit(fetchImpl)[1]).Authorization).toBeUndefined();
  });

  it('không ghi mã vào localStorage hay sessionStorage', async () => {
    const setItem = vitest.spyOn(Storage.prototype, 'setItem');
    const fetchImpl = vitest.fn(async () =>
      jsonResponse(200, { token: 'ma-lop', user_id: 'demo-citizen-1', role: 'citizen' }),
    );
    const client = createClient({ baseUrl: '/v1', fetchImpl });
    const auth = await client.join(SAMPLE_CLASS_CODE, 'Học viên');
    startSession(auth);
    setAuthToken('ma-khac');
    expect(setItem).not.toHaveBeenCalled();
    expect(window.localStorage.length).toBe(0);
    expect(window.sessionStorage.length).toBe(0);
  });

  it('join gửi qr_token và display_name; startSession nhớ vai trò', async () => {
    const auth = { token: 'ma-lop', user_id: 'demo-citizen-1', role: 'citizen' };
    const fetchImpl = vitest.fn(async () => jsonResponse(200, auth));
    const client = createClient({ baseUrl: '/v1', fetchImpl });
    const out = await client.join(SAMPLE_CLASS_CODE, 'Học viên');
    const [url, init] = lastInit(fetchImpl);
    expect(url).toBe('/v1/auth/join');
    expect(JSON.parse(String(init.body))).toEqual({
      qr_token: SAMPLE_CLASS_CODE,
      display_name: 'Học viên',
    });
    startSession(out);
    expect(getSession()).toEqual({ token: 'ma-lop', userId: 'demo-citizen-1', role: 'citizen' });
    expect(getAuthToken()).toBe('ma-lop');
  });

  it('login 401 → ApiError INVALID_CREDENTIALS với câu của máy chủ', async () => {
    const message = 'Tên đăng nhập hoặc mật khẩu chưa đúng, anh/chị kiểm tra lại nhé.';
    const fetchImpl = vitest.fn(async () =>
      jsonResponse(401, { error: { code: 'INVALID_CREDENTIALS', message } }),
    );
    const client = createClient({ baseUrl: '/v1', fetchImpl });
    const error = (await client.login('canbo-demo', 'sai').catch((e: unknown) => e)) as ApiError;
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(401);
    expect(error.code).toBe('INVALID_CREDENTIALS');
    expect(error.message).toBe(message);
    const [url, init] = lastInit(fetchImpl);
    expect(url).toBe('/v1/auth/login');
    expect(JSON.parse(String(init.body))).toEqual({ username: 'canbo-demo', password: 'sai' });
  });

  it('ask 503 KB_NOT_READY → ApiError giữ câu tiếng Việt', async () => {
    const message = 'Kho thủ tục đang được cập nhật, bác thử lại sau ít phút nhé.';
    const client = createClient({
      baseUrl: '/v1',
      fetchImpl: async () => jsonResponse(503, { error: { code: 'KB_NOT_READY', message } }),
    });
    const error = (await client.ask('Hỏi thử').catch((e: unknown) => e)) as ApiError;
    expect(error.status).toBe(503);
    expect(error.code).toBe('KB_NOT_READY');
    expect(error.message).toBe(message);
  });

  it('intakeCheck gửi đúng thân yêu cầu tới /coach/intake-check', async () => {
    setAuthToken('ma-can-bo');
    const fetchImpl = vitest.fn(async () => jsonResponse(200, { items: [] }));
    const client = createClient({ baseUrl: '/v1', fetchImpl });
    await client.intakeCheck({ procedure_id: 'p-01', received: ['d01'], case_label: 'A' });
    const [url, init] = lastInit(fetchImpl);
    expect(url).toBe('/v1/coach/intake-check');
    expect(headersOf(init).Authorization).toBe('Bearer ma-can-bo');
    expect(JSON.parse(String(init.body))).toEqual({
      procedure_id: 'p-01',
      received: ['d01'],
      case_label: 'A',
    });
  });

  it('ask chờ quá lâu → mã TIMEOUT và câu khích lệ', async () => {
    const fetchImpl = vitest.fn(
      (_input: RequestInfo | URL, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener('abort', () =>
            reject(new DOMException('aborted', 'AbortError')),
          );
        }),
    );
    const client = createClient({ baseUrl: '/v1', fetchImpl, askTimeoutMs: 20 });
    const error = (await client.ask('Hỏi thử').catch((e: unknown) => e)) as ApiError;
    expect(error.code).toBe(TIMEOUT_ERROR_CODE);
    expect(error.message).toBe(vi.errors.timeout);
  });

  it('thời gian chờ mặc định của ask không dưới 120 giây (máy chỉ có CPU)', () => {
    expect(ASK_TIMEOUT_MS).toBeGreaterThanOrEqual(120_000);
  });
});
