import { AlertTriangle, Moon, Radio, ShieldCheck, Sun, TriangleAlert, LogOut } from "lucide-react";
import { NavLink } from "react-router";
import type { ReactNode } from "react";

import { BRAND } from "../lib/brand";
import type { AdminStatus } from "../lib/types";
import { cn } from "../lib/utils";
import type { DataSource } from "../hooks/useDashboard";
import { useAuth } from "../hooks/useAuth";
import { useTheme } from "../hooks/useTheme";
import { SimulatedTag } from "./SimulatedTag";

const NAV = [
  { to: "/control", label: "Command", end: true },
  { to: "/live", label: "Live", end: false },
  { to: "/volunteers", label: "Volunteers", end: false },
  { to: "/", label: "Public page", end: true },
];

function navClass({ isActive }: { isActive: boolean }) {
  return cn(
    "relative cursor-pointer px-1 py-3.5 text-sz-header-muted transition-colors hover:text-sz-header-text",
    isActive &&
      "font-medium text-sz-header-text after:absolute after:inset-x-0 after:-bottom-px after:h-[3px] after:rounded-full after:bg-sz-header-accent",
  );
}

/** `tone="dark"` is for the navy chrome, where the brand reads amber over a
 *  cool check. The light tone is for pages with no chrome, like the responder
 *  handoff. */
export function Brandmark({
  className,
  tone = "light",
}: {
  className?: string;
  tone?: "light" | "dark";
}) {
  // Amber shield over a green check: fire and earth, the two elements the
  // brand actually stands between.
  const shield = tone === "dark" ? "var(--color-sz-header-accent)" : "var(--color-sz-water)";
  const check = tone === "dark" ? "var(--color-sz-header-safe)" : "var(--color-sz-earth)";

  return (
    <span className={cn("flex items-center gap-2.5", className)}>
      <svg width="18" height="21" viewBox="0 0 34 39" fill="none" aria-hidden="true">
        <path
          d="M17 2 3 7.6v12.2c0 8 5.8 13.8 14 17.2 8.2-3.4 14-9.2 14-17.2V7.6L17 2Z"
          stroke={shield}
          strokeWidth="2.1"
          strokeLinejoin="round"
        />
        <path
          d="M11.2 19.4 15.4 23.6 23.2 15.2"
          stroke={check}
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <span className="text-[16px] font-semibold tracking-[-0.02em]">{BRAND}</span>
    </span>
  );
}

export function AppShell({
  children,
  admin,
  source,
  streaming,
  openCount,
  criticalCount,
  onToggleKillSwitch,
  alert,
  error,
  onRetry,
  fill = false,
}: {
  children: ReactNode;
  admin?: AdminStatus | null;
  source?: DataSource;
  streaming?: boolean;
  openCount?: number;
  criticalCount?: number;
  onToggleKillSwitch?: () => void;
  /** One sentence naming what is worst right now. Rendered as the critical
   *  banner. Built from the live queue by the page, not written here. */
  alert?: string | null;
  /** Why the backend could not be reached. Shown instead of letting an empty
   *  dashboard read as "no emergencies right now", which is the dangerous
   *  misreading. */
  error?: string | null;
  onRetry?: () => void;
  /** Control-room layout: pin the shell to the viewport from `lg` up so the
   *  feed and the case panel scroll inside their own columns and the timeline
   *  stays put at the bottom. Below `lg` the screen stacks and scrolls like an
   *  ordinary page, because a phone cannot usefully hold three columns.
   *  `min-h-screen` alone would let the columns grow to their content height
   *  and push the timeline off the bottom of the page. */
  fill?: boolean;
}) {
  const killed = admin?.kill_switch ?? false;
  const { theme, toggle: toggleTheme } = useTheme();
  const { email, signOut } = useAuth();

  return (
    <div
      className={cn(
        "flex flex-col bg-sz-base",
        fill ? "min-h-screen lg:h-screen lg:overflow-hidden" : "min-h-screen",
      )}
    >
      <header className="sticky top-0 z-30 border-b-2 border-sz-header-accent/70 bg-sz-header text-sz-header-text">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-1 px-4 sm:px-5">
          {/* The shell is the operations chrome, so the brand goes back to the
              command view rather than out to the public page. */}
          <NavLink
            to="/control"
            className="flex items-center py-3"
            aria-label={`${BRAND} command`}
          >
            <Brandmark tone="dark" />
          </NavLink>

          <nav aria-label="Main" className="flex items-center gap-5">
            {NAV.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end} className={navClass}>
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="grow" />

          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2">
            {typeof openCount === "number" && (
              <p className="flex items-baseline gap-1.5">
                <span className="font-mono text-sm font-semibold">{openCount}</span>
                <span className="text-sz-header-muted">open</span>
                {typeof criticalCount === "number" && criticalCount > 0 && (
                  <>
                    <span className="text-sz-header-line">·</span>
                    <span className="font-mono text-sm font-semibold text-sz-crit-on-dark">
                      {criticalCount}
                    </span>
                    <span className="text-sz-header-muted">critical</span>
                  </>
                )}
              </p>
            )}

            {source && (
              <span
                className={cn(
                  // Pale pills on the navy bar: a 10%-alpha tint over navy
                  // leaves the label at about 3:1, so the chip carries a solid
                  // light background instead.
                  "inline-flex items-center gap-1.5 rounded-full border bg-sz-panel px-2 py-0.5 text-[11px]",
                  source === "live"
                    ? "border-sz-earth/50 text-sz-earth"
                    : "border-sz-header-line text-sz-text-2",
                )}
                title={
                  source === "live"
                    ? streaming
                      ? "Connected to the backend and receiving events."
                      : "Reading the backend, but the event stream is not connected."
                    : "The backend was not reachable, so these are demo fixtures from the frontend."
                }
              >
                {source === "live" ? (
                  <Radio className="h-3 w-3" aria-hidden="true" />
                ) : (
                  <span
                    aria-hidden="true"
                    className="sz-hatch block h-2.5 w-2.5 border border-current"
                  />
                )}
                {source === "live" ? (streaming ? "Live" : "Live, no stream") : "Demo fixtures"}
              </span>
            )}

            {admin?.mock_mode && (
              <SimulatedTag
                className="rounded-full border-sz-header-line bg-sz-panel"
                title="MOCK_MODE=1 — WhatsApp sends and LLM extractions are faked."
              >
                Mock sends
              </SimulatedTag>
            )}

            <button
              type="button"
              onClick={toggleTheme}
              aria-label={theme === "light" ? "Switch to dark mode" : "Switch to light mode"}
              title={theme === "light" ? "Switch to dark mode" : "Switch to light mode"}
              className="inline-flex size-8 cursor-pointer items-center justify-center rounded-full border border-sz-header-line text-sz-header-muted transition-colors hover:border-sz-header-accent hover:text-sz-header-accent"
            >
              {theme === "light" ? (
                <Moon className="h-4 w-4" aria-hidden="true" />
              ) : (
                <Sun className="h-4 w-4" aria-hidden="true" />
              )}
            </button>

            {onToggleKillSwitch && (
              <button
                type="button"
                onClick={onToggleKillSwitch}
                aria-pressed={killed}
                title="Stops every outbound message, volunteer messages included. Read at call time, so it takes effect on the next send."
                className={cn(
                  "inline-flex cursor-pointer items-center gap-2 rounded-full border bg-sz-panel px-2.5 py-1 transition-colors",
                  killed
                    ? "border-sz-crit/60 text-sz-crit"
                    : "border-sz-header-line text-sz-text-2 hover:text-sz-text",
                )}
              >
                <span
                  aria-hidden="true"
                  className={cn(
                    "relative block h-4 w-7 rounded-full transition-colors",
                    killed ? "bg-sz-crit/30" : "bg-sz-line",
                  )}
                >
                  <span
                    className={cn(
                      "absolute top-0.5 block h-3 w-3 rounded-full transition-all",
                      killed ? "left-0.5 bg-sz-crit-fill" : "left-3.5 bg-sz-earth-fill",
                    )}
                  />
                </span>
                {killed ? "Messages stopped" : "Messages on"}
              </button>
            )}

            {email && (
              <button
                type="button"
                onClick={signOut}
                title={`Signed in as ${email}`}
                className="inline-flex cursor-pointer items-center gap-1.5 rounded-full border border-sz-header-line bg-sz-panel px-2.5 py-1 text-sz-text-2 transition-colors hover:text-sz-text"
              >
                <LogOut className="h-3.5 w-3.5" aria-hidden="true" />
                Sign out
              </button>
            )}
          </div>
        </div>
      </header>

      {/* What is worst, right now, in one line. Dark red rather than tinted:
          this is the only thing on screen allowed to shout. */}
      {alert && (
        <div
          role="status"
          className="flex items-start gap-2.5 border-b border-sz-alert-line bg-sz-alert px-4 py-2.5 text-white sm:px-5"
        >
          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          {/* No "Critical:" prefix — the sentence already says it, and the bar
              is the only dark red thing on screen. */}
          <p className="font-medium">{alert}</p>
        </div>
      )}

      {error && (
        <div
          role="alert"
          className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-sz-alert-line bg-sz-alert px-4 py-2.5 text-white sm:px-5"
        >
          <TriangleAlert className="h-4 w-4 shrink-0" aria-hidden="true" />
          <p className="font-medium">{error}</p>
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="cursor-pointer rounded-sm border border-white/40 px-2 py-0.5 text-[12px] font-semibold hover:bg-white/10"
            >
              Try again
            </button>
          )}
        </div>
      )}

      {admin?.problems?.length ? (
        <div className="flex items-start gap-2.5 border-b border-sz-elev/30 bg-sz-elev/10 px-4 py-2 sm:px-5">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-sz-elev" aria-hidden="true" />
          <div className="min-w-0">
            {admin.problems.map((problem) => (
              <p key={problem} className="text-sz-elev">
                {problem}
              </p>
            ))}
          </div>
        </div>
      ) : null}

      {killed && (
        <div className="flex items-center gap-2.5 border-b border-sz-crit/35 bg-sz-crit/10 px-4 py-2 sm:px-5">
          <ShieldCheck className="h-3.5 w-3.5 shrink-0 text-sz-crit" aria-hidden="true" />
          <p className="text-sz-crit">
            Kill switch is on. Nothing goes out — not to people, not to volunteers. Cases keep
            being ranked.
          </p>
        </div>
      )}

      <main className={cn("flex min-h-0 grow flex-col", fill && "lg:overflow-hidden")}>
        {children}
      </main>

      <footer className="flex shrink-0 flex-wrap items-center gap-x-4 gap-y-1 border-t-2 border-sz-header-accent/70 bg-sz-header px-4 py-2 text-[12px] text-sz-header-muted sm:px-5">
        <span className="font-semibold text-sz-header-text">{BRAND}</span>
        <span>Emergency coordination, Karachi</span>
        <span className="grow" />
        {typeof openCount === "number" && <span>{openCount} open</span>}
        {typeof criticalCount === "number" && criticalCount > 0 && (
          <span className="font-medium text-sz-crit-on-dark">{criticalCount} critical</span>
        )}
        {admin?.demo_mode && <span>Demo mode</span>}
        <span className="inline-flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className={cn(
              "block size-1.5 rounded-full",
              killed ? "bg-sz-crit-on-dark" : "bg-sz-header-safe",
            )}
          />
          {killed ? "Outbound stopped" : "Outbound on"}
        </span>
      </footer>
    </div>
  );
}
