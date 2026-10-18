import { Moon, Sun } from "lucide-react";
import { FaGithub } from "react-icons/fa6";
import { NavLink } from "react-router";
import type { ReactNode } from "react";

import { Brandmark } from "./AppShell";
import { StickyCta } from "./StickyCta";
import { BRAND, FRAMING } from "../lib/brand";
import { useTheme } from "../hooks/useTheme";
import { cn } from "../lib/utils";
import { ChatWidget } from "./chat/ChatWidget";

/**
 * The chrome for the pages anyone can open.
 *
 * Separate from AppShell on purpose. AppShell is the operations chrome: its
 * nav links to the command view and the volunteer roster, it carries the kill
 * switch, and it shows how many cases are critical right now. None of that
 * belongs in front of a stranger -- at best it is noise to someone who needs
 * help, and at worst it is a signpost to the control room for someone who
 * should not find it.
 *
 * So this shell knows nothing about cases, holds no session, and makes no API
 * call of its own.
 */

const NAV = [
  { to: "/", label: "Get help", end: true },
  { to: "/about", label: "About", end: false },
  { to: "/faq", label: "FAQs", end: false },
  { to: "/contact", label: "Contact", end: false },
];

/** The four of us. Order is the order we joined the repo, which is as good a
 *  reason as any and better than ranking teammates. */
const TEAM = [
  { name: "Salman", url: "https://github.com/SalmanZulfiqarShaikh" },
  { name: "Hussain", url: "https://github.com/hussainabbas6706" },
  { name: "Abdul Rehman", url: "https://github.com/mabdulrehmankhan666" },
  { name: "Usaim", url: "https://github.com/usaim35" },
];

function navClass({ isActive }: { isActive: boolean }) {
  return cn(
    "relative cursor-pointer px-1 py-3 text-[14px] text-sz-header-muted transition-colors hover:text-sz-header-text sm:py-3.5 sm:text-[15px]",
    isActive &&
      "font-medium text-sz-header-text after:absolute after:inset-x-0 after:-bottom-px after:h-[3px] after:rounded-full after:bg-sz-header-accent",
  );
}

export function PublicShell({ children }: { children: ReactNode }) {
  const { theme, toggle } = useTheme();

  return (
    <div className="flex min-h-screen flex-col bg-sz-base text-sz-text">
      {/* Three columns rather than a flex row, so the nav sits on the true
          centre of the header regardless of how wide the brand and the
          toggle happen to be. A flex row with ml-auto would push it
          off-centre by the difference between them.

          Below `sm` those three columns do not fit: four links plus the
          brand plus the toggle is wider than a phone, and the grid would
          push the toggle off the right edge rather than wrap. So on a phone
          the nav drops to its own full-width row underneath, reordered with
          `order` so the markup stays in reading order. */}
      <header className="sticky top-0 z-30 border-b-2 border-sz-header-accent/70 bg-sz-header text-sz-header-text">
        <div className="grid grid-cols-[1fr_auto] items-center gap-x-4 px-4 sm:grid-cols-[1fr_auto_1fr] sm:px-5">
          <NavLink
            to="/"
            className="order-1 flex items-center py-3"
            aria-label={`${BRAND} home`}
          >
            <Brandmark tone="dark" />
          </NavLink>

          <nav
            aria-label="Main"
            className="order-3 col-span-2 flex items-center justify-center gap-4 border-t border-sz-header-line sm:order-2 sm:col-span-1 sm:gap-7 sm:border-0"
          >
            {NAV.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end} className={navClass}>
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="order-2 flex items-center justify-end py-2 sm:order-3">
            <button
              type="button"
              onClick={toggle}
              aria-label={theme === "light" ? "Switch to dark mode" : "Switch to light mode"}
              title={theme === "light" ? "Switch to dark mode" : "Switch to light mode"}
              className="inline-flex h-9 w-9 cursor-pointer items-center justify-center rounded-full border border-sz-header-line bg-sz-panel text-sz-text-2 transition-colors hover:text-sz-text"
            >
              {theme === "light" ? (
                <Moon className="h-4 w-4" aria-hidden="true" />
              ) : (
                <Sun className="h-4 w-4" aria-hidden="true" />
              )}
            </button>
          </div>
        </div>
      </header>

      <main className="grow">{children}</main>

      {/* Every public page, not just the landing page: whichever page someone
          happens to be on when they decide they need help, the button is one
          tap away. The extra bottom padding below is the room it sits in. */}
      <StickyCta />

      <footer className="border-t border-sz-header-line bg-sz-header px-4 pt-9 pb-24 text-sz-header-muted sm:px-5 sm:pb-9">
        <div className="mx-auto flex w-full max-w-5xl flex-col gap-7">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
            <div className="max-w-[48ch]">
              <Brandmark tone="dark" />
              {/* The honest framing from AGENTS.md section 1, on every public
                  page rather than buried in one. It is the sentence that
                  stops someone waiting here instead of calling for help. */}
              <p className="mt-3 text-[13px] leading-relaxed">{FRAMING}</p>
            </div>

            <nav aria-label="Team" className="shrink-0">
              <p className="text-[13px] font-medium text-sz-header-text">Built by</p>
              <ul className="mt-2.5 flex flex-col gap-1.5">
                {TEAM.map((member) => (
                  <li key={member.url}>
                    <a
                      href={member.url}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="inline-flex items-center gap-2 text-[13px] transition-colors hover:text-sz-header-text"
                    >
                      <FaGithub className="h-3.5 w-3.5" aria-hidden="true" />
                      {member.name}
                    </a>
                  </li>
                ))}
              </ul>
            </nav>
          </div>

          <div className="flex flex-col gap-1.5 border-t border-sz-header-line pt-5 text-[13px] sm:flex-row sm:items-center sm:justify-between">
            <p>&copy; 2026 {BRAND}. All rights reserved.</p>
            <p>A CODE//CONNECT&rsquo;26 prototype. Not an emergency service.</p>
          </div>
        </div>
      </footer>

      <ChatWidget />
    </div>
  );
}
