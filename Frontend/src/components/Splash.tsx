import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useEffect, useState, type ReactNode } from "react";

import { BRAND } from "../lib/brand";

/** Once per page load, not once per route change. A refresh replays it, which
 *  is what you want when you are about to present. */
let alreadyShown = false;

/**
 * The opening: the mark, a glow, and out.
 *
 * This used to spend five seconds drawing the whole workflow. It explained
 * well and it was still five seconds between someone opening the page and
 * being able to use it -- and on an emergency site the page is the point, not
 * the intro. The workflow it described is on the landing page a scroll below,
 * where someone can read it at their own pace.
 */

const HOLD_MS = 1200;

export function Splash({ children }: { children: ReactNode }) {
  const reduceMotion = useReducedMotion();
  const [done, setDone] = useState(alreadyShown);

  useEffect(() => {
    if (alreadyShown) return undefined;
    const timer = window.setTimeout(
      () => {
        alreadyShown = true;
        setDone(true);
      },
      reduceMotion ? 250 : HOLD_MS,
    );
    return () => window.clearTimeout(timer);
  }, [reduceMotion]);

  return (
    <>
      {children}
      <AnimatePresence>
        {!done && (
          <motion.div
            key="splash"
            aria-hidden="true"
            className="sz-grid fixed inset-0 z-50 flex flex-col items-center justify-center bg-sz-panel"
            initial={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: reduceMotion ? 0.15 : 0.35, ease: "easeOut" }}
          >
            <div className="relative flex flex-col items-center">
              {/* The glow. A blurred disc behind the mark rather than a filter
                  on it: filters animate on the compositor here, so this stays
                  smooth on a laptop that is also running the control room. */}
              {!reduceMotion && (
                <motion.span
                  className="pointer-events-none absolute top-1/2 left-1/2 -z-10 h-40 w-40 -translate-x-1/2 -translate-y-[60%] rounded-full bg-sz-water/30 blur-3xl"
                  initial={{ opacity: 0, scale: 0.6 }}
                  animate={{ opacity: [0, 1, 0.65], scale: [0.6, 1.1, 1] }}
                  transition={{ duration: 1.1, ease: "easeOut", times: [0, 0.55, 1] }}
                />
              )}

              <motion.svg
                width="56"
                height="64"
                viewBox="0 0 34 39"
                fill="none"
                role="img"
                aria-label={`${BRAND} logo`}
                initial={reduceMotion ? false : { opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
              >
                <motion.path
                  d="M17 2 3 7.6v12.2c0 8 5.8 13.8 14 17.2 8.2-3.4 14-9.2 14-17.2V7.6L17 2Z"
                  stroke="var(--color-sz-water)"
                  strokeWidth="1.8"
                  strokeLinejoin="round"
                  initial={{ pathLength: reduceMotion ? 1 : 0 }}
                  animate={{ pathLength: 1 }}
                  transition={{ duration: reduceMotion ? 0 : 0.55, ease: "easeInOut" }}
                />
                <motion.path
                  d="M11.2 19.4 15.4 23.6 23.2 15.2"
                  stroke="var(--color-sz-earth)"
                  strokeWidth="2.1"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  initial={{ pathLength: reduceMotion ? 1 : 0, opacity: reduceMotion ? 1 : 0 }}
                  animate={{ pathLength: 1, opacity: 1 }}
                  transition={{ duration: reduceMotion ? 0 : 0.28, delay: reduceMotion ? 0 : 0.35 }}
                />
              </motion.svg>

              <motion.p
                className="mt-4 text-[1.6rem] font-semibold tracking-[-0.03em] text-sz-text"
                initial={reduceMotion ? false : { opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: reduceMotion ? 0 : 0.2 }}
              >
                {BRAND}
              </motion.p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
