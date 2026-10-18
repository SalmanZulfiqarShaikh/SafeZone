import { motion, useReducedMotion } from "framer-motion";
import type { ReactNode } from "react";

/**
 * Brings a block in as it reaches the viewport, once.
 *
 * `once: true` matters. A section that re-animates every time it scrolls back
 * into view turns reading into a slideshow, and on a page someone may be
 * reading in an emergency that is actively hostile.
 *
 * Everything collapses to nothing under `prefers-reduced-motion`: the content
 * is simply there, which is the correct behaviour rather than a degraded one.
 */
export function Reveal({
  children,
  delay = 0,
  y = 16,
  className,
}: {
  children: ReactNode;
  delay?: number;
  /** Distance travelled. Keep it small — a long slide reads as decoration. */
  y?: number;
  className?: string;
}) {
  const reduceMotion = useReducedMotion();

  if (reduceMotion) return <div className={className}>{children}</div>;

  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.5, delay, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}
