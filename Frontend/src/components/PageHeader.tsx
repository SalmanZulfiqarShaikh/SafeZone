import { motion, useReducedMotion } from "framer-motion";
import type { ReactNode } from "react";

/**
 * The band at the top of About, FAQs and Contact.
 *
 * Without it all three pages open as a heading over a wall of grey text, and
 * at a glance they look like the same page. The navy band borrows the
 * header's colour so each one opens with the same weight as the landing
 * page, and the kicker says which page you are on without a tracked-out
 * all-caps label.
 */
export function PageHeader({
  kicker,
  title,
  children,
}: {
  kicker: string;
  title: string;
  children?: ReactNode;
}) {
  const reduceMotion = useReducedMotion();

  const rise = (index: number) =>
    reduceMotion
      ? { duration: 0 }
      : { duration: 0.5, delay: index * 0.08, ease: [0.22, 1, 0.36, 1] as const };

  return (
    <section className="relative overflow-hidden border-b border-sz-header-line bg-sz-header">
      {/* A single soft light from the top left, so the band is not a flat
          rectangle of navy. Nothing animates: it is a surface, not an event. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-32 -left-24 h-72 w-72 rounded-full bg-sz-water/20 blur-3xl"
      />

      <div className="mx-auto w-full max-w-3xl px-4 py-12 sm:px-6 sm:py-16">
        <motion.p
          className="text-[13px] font-medium tracking-wide text-sz-header-accent"
          initial={reduceMotion ? false : { opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={rise(0)}
        >
          {kicker}
        </motion.p>

        <motion.h1
          className="mt-3 text-[2.2rem] leading-[1.05] font-semibold tracking-[-0.035em] text-sz-header-text sm:text-[2.9rem]"
          initial={reduceMotion ? false : { opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={rise(1)}
        >
          {title}
        </motion.h1>

        {children && (
          <motion.div
            className="mt-5 max-w-[60ch] text-[17px] leading-relaxed text-sz-header-muted"
            initial={reduceMotion ? false : { opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={rise(2)}
          >
            {children}
          </motion.div>
        )}
      </div>
    </section>
  );
}
