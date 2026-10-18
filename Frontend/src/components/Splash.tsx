import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useEffect, useState, type ReactNode } from "react";

import { BRAND, FRAMING_SHORT } from "../lib/brand";

/** Once per page load, not once per route change. A refresh replays it, which
 *  is what you want when you are about to present. */
let alreadyShown = false;

const HOLD_MS = 1000;

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
      reduceMotion ? 300 : HOLD_MS,
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
            className="sz-grid fixed inset-0 z-50 flex flex-col items-center justify-center bg-sz-panel px-6"
            initial={{ opacity: 1 }}
            exit={{ opacity: 0, scale: reduceMotion ? 1 : 1.03 }}
            transition={{ duration: reduceMotion ? 0.2 : 0.45, ease: [0.22, 1, 0.36, 1] }}
          >
            <motion.svg
              width="60"
              height="69"
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
              className="mt-5 text-[2.1rem] font-semibold tracking-[-0.035em] text-sz-text sm:text-[2.6rem]"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: reduceMotion ? 0 : 0.4, delay: reduceMotion ? 0 : 0.15 }}
            >
              {BRAND}
            </motion.h1>

            <motion.p
              className="mt-2 max-w-sm text-center text-sz-text-2"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: reduceMotion ? 0 : 0.4, delay: reduceMotion ? 0 : 0.3 }}
            >
              {FRAMING_SHORT}
            </motion.p>

            <motion.div
              className="mt-7 h-px w-36 overflow-hidden bg-sz-line"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: reduceMotion ? 0 : 0.2 }}
            >
              <motion.span
                className="block h-px w-full bg-sz-water"
                initial={{ scaleX: 0, transformOrigin: "0% 50%" }}
                animate={{ scaleX: 1 }}
                transition={{ duration: reduceMotion ? 0.2 : 0.7, ease: "easeInOut" }}
              />
            </motion.div>

            <motion.p
              className="mt-3 font-mono text-[11px] text-sz-text-3"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: reduceMotion ? 0 : 0.35 }}
            >
              Karachi · emergency operations
            </motion.p>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
