import { motion, useReducedMotion } from "framer-motion";
import { Check, CheckCheck } from "lucide-react";

import { BRAND } from "../lib/brand";

/**
 * The hero: a WhatsApp thread, playing once.
 *
 * A headline and a green button would describe the product. This shows it --
 * and more usefully, it shows what to write. Someone who has never used
 * SafeZone copies the shape of the message in front of them: where they are,
 * what is happening, who cannot move. That is worth more than a numbered list
 * of instructions, because it is read in half a second and the list is not.
 *
 * The message is written the way people in Karachi actually type -- Roman
 * Urdu and English in the same sentence -- for the same reason: someone
 * deciding whether this is for them should see their own words in it.
 *
 * The timings below are honest. The first reply really does arrive in
 * seconds, because it is deterministic code rather than a model call
 * (AGENTS.md 2.3). Nothing here claims a speed the system does not have.
 */

type Turn =
  | { from: "them"; text: string; at: string }
  | { from: "us"; text: string; at: string; note?: string };

const THREAD: Turn[] = [
  {
    from: "them",
    text: "Pani ghar me aa gaya hai. Gulistan-e-Jauhar block 7. Ammi 80 saal ki hain, upar nahi ja sakti.",
    at: "11:04",
  },
  {
    from: "us",
    text: "Samajh gaye. Ground floor chhoriye agar mumkin ho — upar ya chhat par jayein. Bijli ka main switch band kar dein. Madad ke liye aapka case bhej diya hai.",
    at: "11:04",
    note: "Arrives in seconds. No model call stands between you and this reply.",
  },
  {
    from: "us",
    text: "Aapke sab se qareeb volunteer ko bata diya gaya hai. Jab koi haan kehta hai, aapko unka naam bhejenge.",
    at: "11:05",
  },
  {
    from: "them",
    text: "Shukriya",
    at: "11:05",
  },
];

/** Stagger between bubbles. Slow enough to read one before the next lands,
 *  fast enough that the whole thread is up before anyone scrolls past. */
const STEP = 0.75;

export function ThreadDemo() {
  const reduceMotion = useReducedMotion();

  return (
    <figure className="m-0">
      <div className="overflow-hidden rounded-xl border border-sz-line bg-sz-panel shadow-[0_1px_2px_rgba(0,0,0,0.04),0_12px_32px_-12px_rgba(0,0,0,0.18)]">
        <div className="flex items-center gap-3 border-b border-sz-line bg-sz-raised px-4 py-3">
          <span
            aria-hidden="true"
            className="flex h-9 w-9 items-center justify-center rounded-full bg-sz-whatsapp/15 text-sz-whatsapp"
          >
            <svg viewBox="0 0 34 39" className="h-4 w-5" fill="none" aria-hidden="true">
              <path
                d="M17 2 3 7.6v12.2c0 8 5.8 13.8 14 17.2 8.2-3.4 14-9.2 14-17.2V7.6L17 2Z"
                stroke="currentColor"
                strokeWidth="2.4"
                strokeLinejoin="round"
              />
            </svg>
          </span>
          <div className="min-w-0">
            <p className="font-medium text-sz-text">{BRAND}</p>
            <p className="text-[12px] text-sz-text-3">Answers day and night</p>
          </div>
        </div>

        <ol className="flex flex-col gap-2.5 px-3.5 py-4">
          {THREAD.map((turn, index) => (
            <motion.li
              key={turn.text}
              className={cnRow(turn.from)}
              initial={reduceMotion ? false : { opacity: 0, y: 10, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{
                duration: 0.38,
                delay: reduceMotion ? 0 : 0.35 + index * STEP,
                ease: [0.22, 1, 0.36, 1],
              }}
            >
              <div className={cnBubble(turn.from)}>
                <p className="text-[14.5px] leading-[1.45]">{turn.text}</p>
                <span
                  className={
                    turn.from === "them"
                      ? "mt-1 flex items-center justify-end gap-1 text-[11px] text-sz-text-3"
                      : "mt-1 flex items-center justify-end gap-1 text-[11px] text-sz-text-3"
                  }
                >
                  {turn.at}
                  {turn.from === "them" ? (
                    <CheckCheck className="h-3 w-3 text-sz-water" aria-hidden="true" />
                  ) : (
                    <Check className="h-3 w-3" aria-hidden="true" />
                  )}
                </span>
              </div>

              {turn.from === "us" && turn.note && (
                <motion.p
                  className="mt-1.5 max-w-[34ch] text-[12px] leading-snug text-sz-text-3"
                  initial={reduceMotion ? false : { opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: reduceMotion ? 0 : 0.9 + index * STEP, duration: 0.4 }}
                >
                  {turn.note}
                </motion.p>
              )}
            </motion.li>
          ))}
        </ol>
      </div>

      <figcaption className="mt-3 text-[13px] text-sz-text-3">
        A real exchange, shortened. Write it however is fastest for you — Urdu, English or
        mixed.
      </figcaption>
    </figure>
  );
}

function cnRow(from: Turn["from"]) {
  return from === "them"
    ? "flex flex-col items-end"
    : "flex flex-col items-start";
}

function cnBubble(from: Turn["from"]) {
  return from === "them"
    ? "max-w-[85%] rounded-xl rounded-br-sm bg-sz-whatsapp/12 px-3.5 py-2.5 text-sz-text"
    : "max-w-[85%] rounded-xl rounded-bl-sm border border-sz-line bg-sz-raised px-3.5 py-2.5 text-sz-text";
}
