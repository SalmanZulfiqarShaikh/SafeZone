import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { CheckCircle2, ScanSearch, ShieldCheck, Users } from "lucide-react";
import { FaWhatsapp } from "react-icons/fa6";
import { useEffect, useState, type ReactNode } from "react";

import { BRAND, FRAMING_SHORT } from "../lib/brand";

/** Once per page load, not once per route change. A refresh replays it, which
 *  is what you want when you are about to present. */
let alreadyShown = false;

/**
 * The opening.
 *
 * Five seconds, with the whole workflow drawn out underneath the mark one
 * step at a time. It is the first thing a judge sees and it answers the
 * question they are about to ask before they ask it.
 *
 * Five seconds is a long time to hold someone who came here because their
 * street is under water, so there is a Skip control from the first frame,
 * it never replays while they move between pages, and anyone who has asked
 * their system for reduced motion gets a brief fade instead of the sequence.
 */

const HOLD_MS = 5200;

/** What the system actually does, in the order it does it. If the backend
 *  behaviour changes, this changes with it -- an intro that describes a
 *  system we do not have is the overstatement AGENTS.md 17 #10 rules out. */
const STEPS = [
  {
    icon: FaWhatsapp,
    title: "You message us",
    body: "Any number, any words — English, Urdu or Roman Urdu. No app, no form, no account.",
  },
  {
    icon: ScanSearch,
    title: "We read it and rank it",
    body: "What happened, where, and who cannot move on their own. Duplicate reports merge into one case.",
  },
  {
    icon: Users,
    title: "Neighbours are asked",
    body: "The nearest on-duty volunteers are offered it immediately — your area and one line, never your name.",
  },
  {
    icon: ShieldCheck,
    title: "A coordinator approves the handoff",
    body: "The one manual step. Only the handoff to an official service waits for a person.",
  },
  {
    icon: CheckCircle2,
    title: "We check back",
    body: "Did help actually arrive? If not, the case goes straight back to the top of the queue.",
  },
];

/** The sequence has to finish comfortably inside HOLD_MS, or the last line
 *  appears as the overlay is already fading out. */
const FIRST_STEP_AT = 1.0;
const STEP_GAP = 0.62;

export function Splash({ children }: { children: ReactNode }) {
  const reduceMotion = useReducedMotion();
  const [done, setDone] = useState(alreadyShown);

  function dismiss() {
    alreadyShown = true;
    setDone(true);
  }

  useEffect(() => {
    if (alreadyShown) return undefined;
    const timer = window.setTimeout(
      () => {
        alreadyShown = true;
        setDone(true);
      },
      reduceMotion ? 400 : HOLD_MS,
    );
    return () => window.clearTimeout(timer);
  }, [reduceMotion]);

  // Escape skips it too. Someone who needs the page now should not have to
  // find a button with a mouse.
  useEffect(() => {
    if (done) return undefined;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape" || event.key === "Enter") dismiss();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [done]);

  return (
    <>
      {children}
      <AnimatePresence>
        {!done && (
          <motion.div
            key="splash"
            role="dialog"
            aria-label={`${BRAND} — how it works`}
            className="sz-grid fixed inset-0 z-50 flex flex-col items-center justify-center overflow-y-auto bg-sz-panel px-5 py-7 sm:py-10"
            initial={{ opacity: 1 }}
            exit={{ opacity: 0, scale: reduceMotion ? 1 : 1.02 }}
            transition={{ duration: reduceMotion ? 0.2 : 0.45, ease: [0.22, 1, 0.36, 1] }}
          >
            <button
              type="button"
              onClick={dismiss}
              className="absolute top-4 right-4 cursor-pointer rounded-full border border-sz-line px-3.5 py-1.5 text-[13px] text-sz-text-2 transition-colors hover:border-sz-water/60 hover:text-sz-text"
            >
              Skip
            </button>

            <div className="flex w-full max-w-xl flex-col items-center">
              {/* ─── The mark ─────────────────────────────────────────── */}
              <motion.svg
                width="52"
                height="60"
                viewBox="0 0 34 39"
                fill="none"
                role="img"
                aria-label={`${BRAND} logo`}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: reduceMotion ? 0 : 0.4, ease: "easeOut" }}
              >
                <motion.path
                  d="M17 2 3 7.6v12.2c0 8 5.8 13.8 14 17.2 8.2-3.4 14-9.2 14-17.2V7.6L17 2Z"
                  stroke="var(--color-sz-water)"
                  strokeWidth="1.8"
                  strokeLinejoin="round"
                  initial={{ pathLength: reduceMotion ? 1 : 0 }}
                  animate={{ pathLength: 1 }}
                  transition={{ duration: reduceMotion ? 0 : 0.6, ease: "easeInOut" }}
                />
                <motion.path
                  d="M11.2 19.4 15.4 23.6 23.2 15.2"
                  stroke="var(--color-sz-earth)"
                  strokeWidth="2.1"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  initial={{ pathLength: reduceMotion ? 1 : 0, opacity: reduceMotion ? 1 : 0 }}
                  animate={{ pathLength: 1, opacity: 1 }}
                  transition={{ duration: reduceMotion ? 0 : 0.3, delay: reduceMotion ? 0 : 0.38 }}
                />
              </motion.svg>

              <motion.h1
                className="mt-4 text-[1.9rem] font-semibold tracking-[-0.035em] text-sz-text sm:text-[2.3rem]"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: reduceMotion ? 0 : 0.4, delay: reduceMotion ? 0 : 0.15 }}
              >
                Welcome to {BRAND}
              </motion.h1>

              <motion.p
                className="mt-2 max-w-sm text-center text-[15px] text-sz-text-2"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: reduceMotion ? 0 : 0.4, delay: reduceMotion ? 0 : 0.3 }}
              >
                {FRAMING_SHORT}
              </motion.p>

              {/* ─── The workflow, one step at a time ─────────────────── */}
              <motion.p
                className="mt-5 font-mono text-[11px] tracking-wide text-sz-text-3 sm:mt-7"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: reduceMotion ? 0 : 0.75 }}
              >
                HOW IT WORKS
              </motion.p>

              <ol className="mt-3.5 flex w-full flex-col gap-2 sm:mt-4 sm:gap-2.5">
                {STEPS.map((step, index) => (
                  <motion.li
                    key={step.title}
                    className="flex items-start gap-3.5 rounded-lg border border-sz-line bg-sz-base/60 px-4 py-3"
                    initial={reduceMotion ? false : { opacity: 0, x: -14 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{
                      duration: reduceMotion ? 0 : 0.45,
                      delay: reduceMotion ? 0 : FIRST_STEP_AT + index * STEP_GAP,
                      ease: [0.22, 1, 0.36, 1],
                    }}
                  >
                    <span className="flex size-8 shrink-0 items-center justify-center rounded-full border border-sz-water/35 bg-sz-water/10">
                      <step.icon className="h-4 w-4 text-sz-water" aria-hidden="true" />
                    </span>
                    <span className="min-w-0">
                      <span className="block text-[14.5px] font-semibold text-sz-text">
                        {step.title}
                      </span>
                      <span className="mt-0.5 block text-[13px] leading-snug text-sz-text-2">
                        {step.body}
                      </span>
                    </span>
                  </motion.li>
                ))}
              </ol>

              {/* ─── Time left ────────────────────────────────────────── */}
              <div className="mt-6 h-px w-full max-w-xs overflow-hidden bg-sz-line sm:mt-7">
                <motion.span
                  className="block h-px w-full bg-sz-water"
                  initial={{ scaleX: 0, transformOrigin: "0% 50%" }}
                  animate={{ scaleX: 1 }}
                  transition={{
                    duration: reduceMotion ? 0.3 : HOLD_MS / 1000,
                    ease: "linear",
                  }}
                />
              </div>

              <p className="mt-3 text-center font-mono text-[11px] text-sz-text-3">
                Karachi · emergency operations
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
