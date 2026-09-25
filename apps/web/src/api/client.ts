/**
 * Thin fetch wrapper for the CTCV API (`/v1`, brief §3, ADR-007 C6).
 *
 * Every non-2xx answer becomes an `ApiError` carrying the server's stable `code` and its
 * Vietnamese `message` (`{"error": {"code", "message"}}`); malformed bodies and network
 * failures map to generic codes with friendly messages from `src/i18n/vi.ts`.
 * The bearer token is read from `src/state/session.ts` (memory only) on every request.
 */
import { vi } from '../i18n/vi';
import { getAuthToken as readSessionToken, setSessionToken } from '../state/session';
import type { AskOut, AuthOut, IntakeCheckIn, IntakeCheckOut } from './types';

/** Path used when `VITE_API_BASE` is not set (the dev server proxies it to the API port). */
export const DEFAULT_API_BASE = '/v1';

/** Code used when the server answers an error without the unified body. */
export const UNKNOWN_ERROR_CODE = 'UNKNOWN_ERROR';

/** Code used when the request never reached the server. */
export const NETWORK_ERROR_CODE = 'NETWORK_ERROR';

/** Code used when the client gave up waiting (see `ASK_TIMEOUT_MS`). */
export const TIMEOUT_ERROR_CODE = 'TIMEOUT';

/**
 * How long `ask` waits: answers are composed on CPU (5–30 s typical) and the API itself
 * waits up to `serving.timeout_s` (120 s, config/rag.yaml) for the model, so the page
 * must wait a little longer than that before giving up.
 */
export const ASK_TIMEOUT_MS = 150_000;

/** Keep the bearer token in memory (never in any browser storage); `null` forgets it. */
export function setAuthToken(token: string | null): void {
  setSessionToken(token);
}

/** Current bearer token, or `null`. */
export function getAuthToken(): string | null {
  return readSessionToken();
}

export interface ApiErrorBody {
  error: { code: string; message: string; details?: unknown };
}

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: unknown;

  constructor(code: string, message: string, status: number, details?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

/** Shape guard for the unified error body. */
export function isApiErrorBody(value: unknown): value is ApiErrorBody {
  if (typeof value !== 'object' || value === null || !('error' in value)) return false;
  const error = (value as { error: unknown }).error;
  return (
    typeof error === 'object' &&
    error !== null &&
    typeof (error as { code?: unknown }).code === 'string' &&
    typeof (error as { message?: unknown }).message === 'string'
  );
}

/** Resolve the base URL from `VITE_API_BASE`, without a trailing slash. */
export function resolveBaseUrl(): string {
  const fromEnv = import.meta.env.VITE_API_BASE?.trim();
  const base = fromEnv && fromEnv.length > 0 ? fromEnv : DEFAULT_API_BASE;
  return base.replace(/\/+$/, '');
}

/** Turn a failed `Response` into an `ApiError` (never throws). */
export async function toApiError(response: Response): Promise<ApiError> {
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = undefined;
  }
  if (isApiErrorBody(body)) {
    return new ApiError(body.error.code, body.error.message, response.status, body.error.details);
  }
  return new ApiError(UNKNOWN_ERROR_CODE, vi.errors.generic, response.status);
}

export interface ClientOptions {
  baseUrl?: string;
  /** Injectable for tests; defaults to the global `fetch`. */
  fetchImpl?: typeof fetch;
  /** Override `ASK_TIMEOUT_MS` (tests only). */
  askTimeoutMs?: number;
}

export interface HealthOut {
  status: string;
  version: string;
  checks?: Record<string, string>;
}

export interface ApiClient {
  readonly baseUrl: string;
  request<T>(path: string, init?: RequestInit): Promise<T>;
  get<T>(path: string, init?: RequestInit): Promise<T>;
  post<T>(path: string, body: unknown, init?: RequestInit): Promise<T>;
  postForm<T>(path: string, form: FormData, init?: RequestInit): Promise<T>;
  health(): Promise<HealthOut>;
  /** `POST /auth/join` — enter a class from its QR code (citizen). */
  join(qrToken: string, displayName: string): Promise<AuthOut>;
  /** `POST /auth/login` — staff login (officer). */
  login(username: string, password: string): Promise<AuthOut>;
  /** `POST /coach/ask` — one question, one cited answer (waits up to `ASK_TIMEOUT_MS`). */
  ask(question: string): Promise<AskOut>;
  /** `POST /coach/intake-check` — compare received documents with the official list. */
  intakeCheck(request: IntakeCheckIn): Promise<IntakeCheckOut>;
}

function joinPath(baseUrl: string, path: string): string {
  return `${baseUrl}${path.startsWith('/') ? path : `/${path}`}`;
}

function withAuth(headers: HeadersInit | undefined): Record<string, string> {
  const merged: Record<string, string> = {
    Accept: 'application/json',
    ...((headers ?? {}) as Record<string, string>),
  };
  const token = readSessionToken();
  if (token && !merged.Authorization) merged.Authorization = `Bearer ${token}`;
  return merged;
}

/** Run `send` with an abort signal that fires after `timeoutMs`; map the abort to TIMEOUT. */
async function withTimeout<T>(timeoutMs: number, send: (signal: AbortSignal) => Promise<T>) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await send(controller.signal);
  } catch (error) {
    if (controller.signal.aborted) {
      throw new ApiError(TIMEOUT_ERROR_CODE, vi.errors.timeout, 0, error);
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

/** Build a client; `api` below is the default instance. */
export function createClient(options: ClientOptions = {}): ApiClient {
  const baseUrl = (options.baseUrl ?? resolveBaseUrl()).replace(/\/+$/, '');
  const doFetch: typeof fetch = options.fetchImpl ?? ((input, init) => fetch(input, init));
  const askTimeoutMs = options.askTimeoutMs ?? ASK_TIMEOUT_MS;

  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    let response: Response;
    try {
      response = await doFetch(joinPath(baseUrl, path), {
        ...init,
        headers: withAuth(init.headers),
      });
    } catch (cause) {
      if (init.signal?.aborted) throw cause;
      throw new ApiError(NETWORK_ERROR_CODE, vi.errors.network, 0, cause);
    }
    if (!response.ok) throw await toApiError(response);
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  }

  const post = <T>(path: string, body: unknown, init?: RequestInit): Promise<T> =>
    request<T>(path, {
      ...init,
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
      body: JSON.stringify(body),
    });

  return {
    baseUrl,
    request,
    get: (path, init) => request(path, { ...init, method: 'GET' }),
    post,
    postForm: (path, form, init) => request(path, { ...init, method: 'POST', body: form }),
    health: () => request<HealthOut>('/health', { method: 'GET' }),
    join: (qrToken, displayName) =>
      post<AuthOut>('/auth/join', { qr_token: qrToken, display_name: displayName }),
    login: (username, password) => post<AuthOut>('/auth/login', { username, password }),
    ask: (question) =>
      withTimeout(askTimeoutMs, (signal) => post<AskOut>('/coach/ask', { question }, { signal })),
    intakeCheck: (body) => post<IntakeCheckOut>('/coach/intake-check', body),
  };
}

export const api: ApiClient = createClient();
