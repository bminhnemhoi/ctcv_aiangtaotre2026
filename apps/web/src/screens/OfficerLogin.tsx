/**
 * Staff login for the one-stop intake check. Inputs are uncontrolled: the password is read
 * from the form once, sent to `/v1/auth/login`, then cleared — never kept in React state or
 * any browser storage. The returned token goes to the in-memory session only.
 */
import { useId, useRef, useState, type FormEvent } from 'react';
import { ApiError, type ApiClient } from '../api/client';
import { BigButton } from '../components/BigButton';
import { vi } from '../i18n/vi';
import { startSession } from '../state/session';

/** Roles allowed to use `/v1/coach/intake-check`. */
export const STAFF_ROLES = ['officer', 'volunteer'] as const;

export interface OfficerLoginProps {
  client: ApiClient;
}

const FIELD_CLASS =
  'min-h-tap w-full rounded-2xl border-4 border-xam bg-trang px-md py-sm text-lg text-den';

export function OfficerLogin({ client }: OfficerLoginProps) {
  const userId = useId();
  const passwordId = useId();
  const passwordRef = useRef<HTMLInputElement>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const username = String(data.get('username') ?? '').trim();
    const password = String(data.get('password') ?? '');
    if (passwordRef.current) passwordRef.current.value = '';
    if (!username || !password) {
      setError(vi.officer.missingCredentials);
      return;
    }
    setPending(true);
    setError(null);
    try {
      const auth = await client.login(username, password);
      if (!(STAFF_ROLES as readonly string[]).includes(auth.role)) {
        setError(vi.officer.wrongRole);
        return;
      }
      startSession(auth);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : vi.errors.generic);
    } finally {
      setPending(false);
    }
  };

  return (
    <form
      data-testid="officer-login"
      onSubmit={(event) => void onSubmit(event)}
      aria-busy={pending}
      className="flex flex-col gap-md"
    >
      <h2 className="text-xl font-bold leading-snug text-den">{vi.officer.loginHeading}</h2>
      <label htmlFor={userId} className="text-lg font-bold text-den">
        {vi.officer.username}
      </label>
      <input
        id={userId}
        name="username"
        data-testid="officer-username"
        autoComplete="username"
        autoCapitalize="none"
        spellCheck={false}
        className={FIELD_CLASS}
      />
      <label htmlFor={passwordId} className="text-lg font-bold text-den">
        {vi.officer.password}
      </label>
      <input
        id={passwordId}
        ref={passwordRef}
        name="password"
        type="password"
        data-testid="officer-password"
        autoComplete="current-password"
        className={FIELD_CLASS}
      />
      <BigButton
        type="submit"
        data-testid="officer-login-submit"
        label={pending ? vi.officer.loggingIn : vi.buttons.login}
        variant="xanh"
        disabled={pending}
      />
      {error ? (
        <p
          role="alert"
          className="rounded-2xl border-4 border-do bg-trang p-md text-lg font-semibold text-do"
        >
          {error}
        </p>
      ) : null}
    </form>
  );
}
