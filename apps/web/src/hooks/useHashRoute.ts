/**
 * Minimal hash router (ADR-007 C7): `#hoi-thu-tuc` (citizen questions), `#can-bo` (one-stop
 * staff), anything else is the home screen. Hash routes need no server config and keep the
 * PWA's single `index.html` fallback.
 */
import { useCallback, useEffect, useState } from 'react';

export type Route = 'home' | 'hoi-thu-tuc' | 'can-bo';

const NAMED_ROUTES: readonly Route[] = ['hoi-thu-tuc', 'can-bo'];

/** Map `location.hash` to a route (exact, case-sensitive match). */
export function parseHash(hash: string): Route {
  const name = hash.replace(/^#/, '');
  return NAMED_ROUTES.find((route) => route === name) ?? 'home';
}

/** Hash for a route (`''` for home). */
export function routeHash(route: Route): string {
  return route === 'home' ? '' : `#${route}`;
}

function currentRoute(): Route {
  return typeof window === 'undefined' ? 'home' : parseHash(window.location.hash);
}

/** Current route plus a `navigate` that updates both the hash and the state. */
export function useHashRoute(): [Route, (route: Route) => void] {
  const [route, setRoute] = useState<Route>(currentRoute);

  useEffect(() => {
    const onChange = () => setRoute(currentRoute());
    window.addEventListener('hashchange', onChange);
    return () => window.removeEventListener('hashchange', onChange);
  }, []);

  const navigate = useCallback((next: Route) => {
    window.location.hash = routeHash(next);
    setRoute(next);
  }, []);

  return [route, navigate];
}
