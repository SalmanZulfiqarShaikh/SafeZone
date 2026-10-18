import { useCallback, useEffect, useState } from "react";

import * as api from "../lib/api";

/**
 * Whether this browser has a control-room session.
 *
 * This hook decides what the UI *shows*. It is not what keeps anyone out --
 * the backend refuses /api/cases, /api/volunteers, /api/admin and /events
 * without a session cookie, so a user who skips the login screen gets a page
 * with nothing on it rather than a page with someone's address on it.
 *
 * Worth being blunt about, because the opposite arrangement is a common and
 * expensive mistake: a login form in React with an open API behind it
 * protects nothing at all.
 */

export type AuthState = "checking" | "in" | "out";

interface Auth {
  state: AuthState;
  email: string | null;
  /** False when the server has no ADMIN_EMAIL / ADMIN_PASSWORD_HASH /
   *  SESSION_SECRET set, in which case no password will ever work and the
   *  login form should say so instead of blaming the operator. */
  configured: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  /** Re-check with the server, e.g. after a 401 from somewhere else. */
  refresh: () => void;
}

export function useAuth(): Auth {
  const [state, setState] = useState<AuthState>("checking");
  const [email, setEmail] = useState<string | null>(null);
  const [configured, setConfigured] = useState(true);
  const [token, setToken] = useState(0);

  const refresh = useCallback(() => setToken((n) => n + 1), []);

  useEffect(() => {
    let cancelled = false;

    api
      .me()
      .then((body) => {
        if (cancelled) return;
        setEmail(body.email);
        setConfigured(body.configured);
        setState(body.authenticated ? "in" : "out");
      })
      .catch(() => {
        // The server is unreachable. Treat that as signed out: showing the
        // control room shell with no data behind it would be worse.
        if (!cancelled) setState("out");
      });

    return () => {
      cancelled = true;
    };
  }, [token]);

  const signIn = useCallback(async (address: string, password: string) => {
    const body = await api.login(address, password);
    setEmail(body.email);
    setState("in");
  }, []);

  const signOut = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      // Local state clears either way. A failed logout call must not leave
      // someone looking at a control room they think they have left.
      setEmail(null);
      setState("out");
    }
  }, []);

  return { state, email, configured, signIn, signOut, refresh };
}
