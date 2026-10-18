import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";

import { useAuth } from "../hooks/useAuth";

/**
 * Keeps the coordinator pages off the screen for anyone without a session.
 *
 * This is a courtesy, not a defence. The backend refuses every endpoint
 * behind these pages without a session cookie, so someone who bypasses this
 * component -- by editing the bundle, or just by calling the API directly --
 * gets an empty shell and a row of 401s. That is the arrangement that
 * matters; this one only spares a signed-out coordinator a screen full of
 * errors.
 *
 * While the session is being checked it renders nothing rather than the
 * login form. A flash of "sign in" before landing on the dashboard reads as
 * a bug, and during an emergency it reads as being locked out.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { state } = useAuth();
  const location = useLocation();

  if (state === "checking") return null;

  if (state === "out") {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return <>{children}</>;
}
