import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { FaWhatsapp } from "react-icons/fa6";
import { useEffect, useState } from "react";

import { BRAND } from "../lib/brand";
import { useWhatsapp } from "../hooks/useWhatsapp";

/**
 * A WhatsApp button pinned to the bottom of the screen on phones.
 *
 * Not a growth-hack bar. This site has one job and someone reading it on a
 * phone during a flood should never have to scroll back up to find the only
 * control that does anything. On a laptop the hero button is almost always
 * in view, so the bar is small-screen only.
 *
 * It appears once the hero has scrolled away, so it never sits on top of the
 * button it duplicates.
 */
export function StickyCta() {
  const { url } = useWhatsapp();
  const reduceMotion = useReducedMotion();
  const [past, setPast] = useState(false);

  useEffect(() => {
    // Roughly the height of the hero's own button. Cheap listener: a boolean
    // flip, no layout reads.
    const onScroll = () => setPast(window.scrollY > 420);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  if (!url) return null;

  return (
    <AnimatePresence>
      {past && (
        <motion.div
          initial={reduceMotion ? false : { y: 72 }}
          animate={{ y: 0 }}
          exit={reduceMotion ? undefined : { y: 72 }}
          transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
          className="fixed inset-x-0 bottom-0 z-40 border-t border-sz-line bg-sz-panel/95 p-3 backdrop-blur-sm sm:hidden"
          style={{ paddingBottom: "max(0.75rem, env(safe-area-inset-bottom))" }}
        >
          <a
            href={url}
            className="flex min-h-13 items-center justify-center gap-3 rounded-lg bg-sz-whatsapp px-5 text-[17px] font-semibold text-white"
          >
            <FaWhatsapp className="h-6 w-6" aria-hidden="true" />
            Message {BRAND}
          </a>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
