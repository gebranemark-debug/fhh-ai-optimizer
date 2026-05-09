import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import {
  getAuthToken,
  getMe,
  login as apiLogin,
  setAuthToken,
  setUnauthorizedHandler,
} from '../lib/api.js';

/**
 * Auth state for the FHH AI Optimizer dashboard.
 *
 * - The bearer token lives in localStorage so a hard reload keeps the user
 *   signed in. The api.js module is the synchronous source of truth used by
 *   every fetch call; this context mirrors it for React renders.
 * - On mount, if a token is already cached, we hit /auth/me to confirm it's
 *   still valid and hydrate the user object. A 401 (e.g. expired) is caught
 *   and treated as a clean logout.
 * - The api.js layer registers an unauthorized handler with us so any 401
 *   from any authed request triggers a token clear.
 *
 * Status enum:
 *   "loading"  — initial bootstrap, /auth/me in flight
 *   "anon"     — no token / token rejected; render Login
 *   "auth"     — user object loaded; render the app
 */

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [status, setStatus] = useState(getAuthToken() ? 'loading' : 'anon');
  const [user, setUser] = useState(null);
  const [error, setError] = useState(null);

  const logout = useCallback(() => {
    setAuthToken(null);
    setUser(null);
    setError(null);
    setStatus('anon');
  }, []);

  // Wire api.js → context: any 401 from a fetch call clears state.
  useEffect(() => {
    setUnauthorizedHandler(() => logout());
    return () => setUnauthorizedHandler(null);
  }, [logout]);

  // Bootstrap: if a token exists, validate it once via /auth/me.
  useEffect(() => {
    if (!getAuthToken()) return; // already 'anon'
    let cancelled = false;
    (async () => {
      try {
        const me = await getMe();
        if (cancelled) return;
        setUser(me);
        setStatus('auth');
      } catch (_) {
        if (cancelled) return;
        setAuthToken(null);
        setUser(null);
        setStatus('anon');
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const login = useCallback(async (email, password) => {
    setError(null);
    try {
      const result = await apiLogin(email, password);
      setAuthToken(result.access_token);
      setUser(result.user);
      setStatus('auth');
      return result.user;
    } catch (err) {
      // Surface a friendly message; preserve the raw error for debugging.
      const msg =
        err?.status === 401
          ? 'Email or password is incorrect.'
          : err?.message || 'Sign-in failed. Please try again.';
      setError(msg);
      throw err;
    }
  }, []);

  const value = useMemo(
    () => ({ status, user, error, login, logout }),
    [status, user, error, login, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used inside <AuthProvider>');
  }
  return ctx;
}
