import { motion, useReducedMotion, useScroll, useTransform } from "framer-motion";
import { QRCodeSVG } from "qrcode.react";
import { FaWhatsapp } from "react-icons/fa6";
import { useRef } from "react";

import { BRAND, FRAMING } from "../lib/brand";
import { SimulatedTag } from "./SimulatedTag";
import { useWhatsapp } from "../hooks/useWhatsapp";
import flooded from "../assets/photos/flooded-street.jpg";

/**
 * The hero.
 *
 * The photograph is the argument. Describing a flooded street in a headline
 * asks the reader to imagine it; showing one does not, and the whole case for
 * this product is that the hour after that water arrives is chaotic. The
 * image is captioned as what it is -- a Karachi monsoon street -- and never
 * implied to be SafeZone's own work. SafeZone does not rescue anyone, and a
 * page that hints otherwise has started lying in its first screen.
 *
 * Motion: one entrance, staged, plus a slow parallax drift on the photograph
 * as the page scrolls. Nothing loops, nothing bounces, and everything is off
 * under `prefers-reduced-motion`.
 */
export function Hero() {
  const { url: whatsappUrl, display: whatsappNumber } = useWhatsapp();
  const reduceMotion = useReducedMotion();
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start start", "end start"],
  });
  // Small. A photo that races the scroll draws attention to the effect
  // instead of the subject.
  const photoY = useTransform(scrollYProgress, [0, 1], ["0%", "14%"]);
  const fade = useTransform(scrollYProgress, [0, 0.85], [1, 0.25]);

  const stage = (index: number) =>
    reduceMotion
      ? { duration: 0 }
      : { duration: 0.55, delay: 0.15 + index * 0.1, ease: [0.22, 1, 0.36, 1] as const };

  return (
    <section ref={ref} className="relative isolate overflow-hidden bg-sz-header">
      <motion.div
        className="absolute inset-0 -z-10"
        style={reduceMotion ? undefined : { y: photoY, opacity: fade }}
      >
        <img
          src={flooded}
          alt="A flooded main road in Karachi during the monsoon — one of the emergencies SafeZone handles, alongside fire, medical and people trapped."
          className="h-[115%] w-full object-cover"
          loading="eager"
        />
        {/* Two layers rather than one: a flat wash would grey the photo out,
            while a gradient keeps the water readable at the top and gives the
            text a solid footing at the bottom. */}
        <div className="absolute inset-0 bg-sz-header/72" />
        <div className="absolute inset-0 bg-gradient-to-t from-sz-header via-sz-header/55 to-sz-header/35" />
      </motion.div>

      <div className="mx-auto w-full max-w-6xl px-4 py-14 sm:px-6 sm:py-20">
        <div className="grid items-center gap-10 lg:grid-cols-[minmax(0,1.15fr)_auto] lg:gap-14">
          <div>
            <motion.p
              className="text-[13px] font-medium tracking-wide text-sz-header-accent"
              initial={reduceMotion ? false : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={stage(0)}
            >
              For the community, by the community
            </motion.p>

            <motion.h1
              className="mt-4 max-w-[15ch] text-[2.5rem] leading-[1.02] font-semibold tracking-[-0.035em] text-sz-header-text sm:text-[3.3rem] lg:text-[3.6rem]"
              initial={reduceMotion ? false : { opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={stage(1)}
            >
              In an emergency, one message is enough.
            </motion.h1>

            <motion.p
              className="mt-5 max-w-[46ch] text-[17px] leading-relaxed text-sz-header-muted"
              initial={reduceMotion ? false : { opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={stage(2)}
            >
              Flood, fire, medical, trapped, no food or water &mdash; tell us what is
              happening and who is with you. No account, no form, nothing to install.
              Any number, day or night.
            </motion.p>

            <motion.div
              className="mt-8 flex flex-wrap items-center gap-x-5 gap-y-4"
              initial={reduceMotion ? false : { opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={stage(3)}
            >
              <motion.a
                href={whatsappUrl}
                className="inline-flex min-h-14 items-center gap-3 rounded-sm bg-sz-whatsapp px-7 text-[17px] font-semibold text-white"
                whileHover={reduceMotion ? undefined : { scale: 1.02 }}
                whileTap={reduceMotion ? undefined : { scale: 0.985 }}
                transition={{ type: "spring", stiffness: 420, damping: 28 }}
              >
                <FaWhatsapp className="h-6 w-6" aria-hidden="true" />
                Message {BRAND}
              </motion.a>

              {whatsappNumber ? (
                <p className="font-mono text-[15px] text-sz-header-muted">
                  {whatsappNumber}
                </p>
              ) : (
                <SimulatedTag title="Set WHATSAPP_PUBLIC_NUMBER in Backend/.env and restart the server.">
                  Number not set on this deployment
                </SimulatedTag>
              )}
            </motion.div>

            <motion.p
              className="mt-8 max-w-[50ch] border-l-2 border-sz-header-accent/60 pl-4 text-[14.5px] leading-relaxed text-sz-header-muted"
              initial={reduceMotion ? false : { opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ ...stage(4), duration: reduceMotion ? 0 : 0.7 }}
            >
              {FRAMING}
            </motion.p>
          </div>

          <motion.div
            className="flex w-full max-w-sm items-center gap-5 rounded-lg border border-sz-header-line bg-sz-header/75 p-5 backdrop-blur-sm lg:w-auto lg:flex-col lg:items-start"
            initial={reduceMotion ? false : { opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={stage(5)}
          >
            {whatsappUrl ? (
              <span className="rounded-sm bg-white p-2.5">
                <QRCodeSVG
                  value={whatsappUrl}
                  size={116}
                  level="M"
                  marginSize={0}
                  title={`Scan to message ${BRAND} on WhatsApp`}
                />
              </span>
            ) : (
              <span
                aria-hidden="true"
                className="sz-hatch block h-[136px] w-[136px] rounded-sm border border-sz-header-line text-sz-header-line"
              />
            )}
            <div className="max-w-[20ch]">
              <p className="font-medium text-sz-header-text">Scan to open WhatsApp</p>
              <p className="mt-1 text-[13px] text-sz-header-muted">
                {whatsappUrl
                  ? "Point a camera at it. Nothing to download."
                  : "The number is not set on this deployment yet."}
              </p>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
