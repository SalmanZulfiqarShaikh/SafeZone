import { LogIn, ShieldAlert } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";

import { ApiError } from "../lib/api";
import { BRAND } from "../lib/brand";
import { useAuth } from "../hooks/useAuth";

/**
 * The way into the control room.
 *
 * Deliberately plain. It carries no case counts, no map and no hint of what
 * is behind it, because everything on this page is visible to anyone who
 * finds the URL.
 */
export default function Login() {
  const { signIn, configured } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;

    setBusy(true);
    setError(null);
    try {
      await signIn(email, password);
      navigate("/control", { replace: true });
    } catch (caught) {
      // The server says the same thing for a wrong address and a wrong
      // password on purpose, and this passes that message through unchanged
      // rather than guessing which half was wrong.
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Could not reach the server. Is the backend running?",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-sz-bg px-4 py-12">
      <div className="w-full max-w-sm">
        <h1 className="text-2xl font-semibold text-sz-text-1">{BRAND} control room</h1>
        <p className="mt-2 text-sm text-sz-text-2">
          Coordinators only. Everything behind this screen carries people&rsquo;s names,
          numbers and locations.
        </p>

        {!configured && (
          <div
            role="status"
            className="mt-6 flex gap-2.5 rounded-sm border border-sz-line bg-sz-surface-2 p-3 text-sm text-sz-text-2"
          >
            <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <span>
              This server has no login configured, so no password will work yet. Run{" "}
              <code className="font-mono text-xs">python -m scripts.hash_password</code> and
              set <code className="font-mono text-xs">ADMIN_EMAIL</code> in the backend
              environment.
            </span>
          </div>
        )}

        <form onSubmit={submit} className="mt-6 flex flex-col gap-4">
          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-sz-text-1">Email</span>
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="username"
              required
              className="min-h-11 rounded-sm border border-sz-line bg-sz-surface-1 px-3 text-base text-sz-text-1 outline-none focus-visible:border-sz-header-accent"
            />
          </label>

          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-sz-text-1">Password</span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              required
              className="min-h-11 rounded-sm border border-sz-line bg-sz-surface-1 px-3 text-base text-sz-text-1 outline-none focus-visible:border-sz-header-accent"
            />
          </label>

          {error && (
            <p role="alert" className="text-sm text-sz-critical">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={busy}
            className="inline-flex min-h-11 items-center justify-center gap-2 rounded-sm bg-sz-header px-4 text-base font-semibold text-sz-header-text transition-opacity hover:opacity-90 disabled:opacity-60"
          >
            <LogIn className="h-4 w-4" aria-hidden="true" />
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <p className="mt-6 text-sm text-sz-text-2">
          Need help instead?{" "}
          <a href="/" className="underline">
            Go to the public page
          </a>
          .
        </p>
      </div>
    </main>
  );
}
