import { motion, useReducedMotion } from "framer-motion";
import { FaPeopleGroup, FaShip, FaTruckMedical } from "react-icons/fa6";
import { MdLocalFireDepartment, MdLocalPolice, MdVolunteerActivism } from "react-icons/md";
import { TbBuildingHospital } from "react-icons/tb";

import { Reveal } from "./Reveal";
import { BRAND } from "../lib/brand";

/**
 * Who actually comes, and where SafeZone sits relative to them.
 *
 * Generic icons, not official seals. A government crest on a third-party
 * page reads as "they use this", and someone standing in water who believes
 * that could wait for an ambulance nobody has called. There is no
 * arrangement with any of these services, and the strip says so twice.
 *
 * The numbers themselves are not written here either: they live in config
 * and must be filled from an official source by a human (AGENTS.md 2.1 #8).
 * A wrong emergency number printed on a page is worse than no number.
 */

const SERVICES = [
  { icon: MdLocalPolice, label: "Police" },
  { icon: MdLocalFireDepartment, label: "Fire & rescue" },
  { icon: FaTruckMedical, label: "Ambulance" },
  { icon: FaShip, label: "Rescue boats" },
  { icon: TbBuildingHospital, label: "Hospitals" },
  { icon: MdVolunteerActivism, label: "Relief camps" },
  { icon: FaPeopleGroup, label: "Neighbourhood volunteers" },
] as const;

const DETAIL = [
  {
    name: "Rescue 1122",
    body: "Sindh Emergency Service — ambulances, fire and rescue. Every medical, fire or trapped-person case points here first, in the first reply, before any volunteer is asked.",
  },
  {
    name: "Sindh Police",
    body: "For anything involving crime, crowds or public order. We pass the case; we never ask a volunteer to walk into one.",
  },
  {
    name: "Neighbourhood volunteers",
    body: "People who signed up to help on their own street. They handle what does not need a vehicle or a uniform, and they assess from a safe place.",
  },
];

function Marquee() {
  const reduceMotion = useReducedMotion();

  const row = (
    <ul className="flex shrink-0 items-center gap-3 pr-3" aria-hidden={!reduceMotion}>
      {SERVICES.map((service, index) => (
        <li
          key={`${service.label}-${index}`}
          className="flex shrink-0 items-center gap-2.5 rounded-full border border-sz-line bg-sz-base px-4 py-2.5"
        >
          <service.icon className="h-5 w-5 shrink-0 text-sz-water" aria-hidden="true" />
          <span className="text-[14px] font-medium whitespace-nowrap">{service.label}</span>
        </li>
      ))}
    </ul>
  );

  if (reduceMotion) {
    // No animation at all: the same items, wrapped, fully readable.
    return (
      <ul className="flex flex-wrap items-center gap-3">
        {SERVICES.map((service) => (
          <li
            key={service.label}
            className="flex items-center gap-2.5 rounded-full border border-sz-line bg-sz-base px-4 py-2.5"
          >
            <service.icon className="h-5 w-5 shrink-0 text-sz-water" aria-hidden="true" />
            <span className="text-[14px] font-medium">{service.label}</span>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <div
      className="relative overflow-hidden [mask-image:linear-gradient(to_right,transparent,black_6%,black_94%,transparent)]"
      role="list"
      aria-label="Services SafeZone is built to hand off to"
    >
      {/* Exactly two copies. The track travels its own half-width and
          resets, which is invisible because copy two is now where copy one
          started. A third copy would only repeat the words again. */}
      <motion.div
        className="flex w-max"
        animate={{ x: ["0%", "-50%"] }}
        transition={{ duration: 30, ease: "linear", repeat: Infinity }}
      >
        {row}
        {row}
      </motion.div>
    </div>
  );
}

export function Handoff() {
  return (
    <section className="mx-auto w-full max-w-6xl px-4 py-14 sm:px-6 sm:py-16">
      <Reveal>
        <h2 className="text-[1.6rem] font-semibold tracking-[-0.025em] sm:text-[2rem]">
          We feed the services. We don&rsquo;t replace them.
        </h2>
        <p className="mt-3 max-w-[62ch] text-sz-text-2">
          {BRAND} has no boats, no ambulances and no authority. What it has is the first
          hour: reading the messages, working out who is worst off, and handing a finished
          case to whoever can actually go.
        </p>
      </Reveal>

      <Reveal delay={0.06} className="mt-8">
        <Marquee />
      </Reveal>

      <Reveal delay={0.1}>
        <p className="mt-6 max-w-[72ch] rounded-sm border border-sz-elev/40 bg-sz-elev/8 px-4 py-3 text-[15px] text-sz-text-2">
          <span className="font-semibold text-sz-text">
            Built for these services, not affiliated with any of them.
          </span>{" "}
          {BRAND} is a student prototype. This is an offer rather than an arrangement: a
          working system any of them could be handed, not one any of them has adopted.
          Until that changes, the official numbers in our replies are the only connection
          between us and them.
        </p>
      </Reveal>

      <div className="mt-10 grid gap-5 md:grid-cols-3">
        {DETAIL.map((service, index) => (
          <Reveal key={service.name} delay={index * 0.08}>
            <div className="h-full rounded-lg border border-sz-line bg-sz-panel p-5">
              <h3 className="font-semibold">{service.name}</h3>
              <p className="mt-2 text-[15px] leading-relaxed text-sz-text-2">
                {service.body}
              </p>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}
