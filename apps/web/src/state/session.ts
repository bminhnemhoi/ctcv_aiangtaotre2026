/**
 * In-memory login state (ADR-007 C7): the bearer token lives only in this module, never in
 * localStorage/sessionStorage/cookies, so closing or reloading the page forgets it.
 */
import { useSyncExternalStore } from 'react';
import type { AuthOut, Role } from '../api/types';

export interface SessionState {
  readonly token: string | null;
  readonly userId: string | null;
  readonly role: Role | null;
}

const EMPTY: SessionState = Object.freeze({ token: null, userId: null, role: null });

let state: SessionState = EMPTY;
const listeners = new Set<() => void>();

function publish(next: SessionState): void {
  state = next;
  for (const listener of listeners) listener();
}

/** Current state (stable object between changes, as `useSyncExternalStore` requires). */
export function getSession(): SessionState {
  return state;
}

/** Bearer token or `null`. */
export function getAuthToken(): string | null {
  return state.token;
}

/** Replace the token only; a different token forgets the previous user and role. */
export function setSessionToken(token: string | null): void {
  if (token === state.token) return;
  publish(token ? { token, userId: null, role: null } : EMPTY);
}

/** Remember the answer of `/v1/auth/join` or `/v1/auth/login`. */
export function startSession(auth: AuthOut): void {
  publish(Object.freeze({ token: auth.token, userId: auth.user_id, role: auth.role }));
}

/** Forget everything (reload does the same). */
export function clearSession(): void {
  if (state !== EMPTY) publish(EMPTY);
}

export function subscribeSession(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** React binding: re-renders when the session changes. */
export function useSession(): SessionState {
  return useSyncExternalStore(subscribeSession, getSession, getSession);
}
