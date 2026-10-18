import { motion, useReducedMotion } from "framer-motion";

import { Reveal } from "./Reveal";
import { BRAND } from "../lib/brand";
import collapsed from "../assets/photos/collapsed-building.jpg";
import flooded from "../assets/photos/flooded-street.jpg";
import rescue from "../assets/photos/rescue-crew.jpg";

/**
 * What the city looks like on the days this is built for.
 *
 * Captions matter more than the pictures here. Each one says what the
 * photograph is and what SafeZone's part in it would be -- never that
 * SafeZone did any of it. These are the emergencies, not our work: we have
 * not pulled anyone out of a building, and a page that implies we have is the
 * exact overstatement AGENTS.md 17 #10 exists to stop.
 *
 * The honest version is also the better pitch. "Here is the hour we work on"
 * is a sharper claim than a stock photo captioned "us helping", which every
 * judge has seen on every other submission.
 */

const SCENES = [
  {
    src: flooded,
    alt: "A flooded main road in Karachi, with a bus and motorcycles pushing through standing water.",
    title: "Monsoon flooding",
    body: "Streets go under in an hour. People message whoever they can and most of those messages reach nobody in a position to act.",
  },
  {
    src: rescue,
    alt: "Rescue workers in red vests standing beside a fire engine at an incident in Karachi.",
    title: "Crews already stretched",
    body: "Official services are out there and overloaded. Our job is to hand them a complete case, not to compete with them.",
  },
  {
    src: collapsed,
    alt: "People standing in front of a collapsed concrete building after an earthquake.",
    title: "Building collapse",
    body: "The first hour decides most outcomes. Knowing who is inside, and who cannot move on their own, is what makes that hour count.",
  },
];

export function WhatWeFace() {
  const reduceMotion = useReducedMotion();

  return (
    <section className="border-y border-sz-line bg-sz-panel">
      <div className="mx-auto w-full max-w-6xl px-4 py-14 sm:px-6 sm:py-16">
        <Reveal>
          <h2 className="text-[1.6rem] font-semibold tracking-[-0.025em] sm:text-[2rem]">
            The hour we work on
          </h2>
          <p className="mt-3 max-w-[58ch] text-sz-text-2">
            {BRAND} exists for the window between something happening and help arriving.
            These are the emergencies, photographed by others &mdash; not our work. We have
            never pulled anyone out of anything, and we are not going to pretend otherwise.
          </p>
        </Reveal>

        <ul className="mt-9 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {SCENES.map((scene, index) => (
            <Reveal key={scene.title} delay={index * 0.08}>
              <motion.li
                className="group h-full overflow-hidden rounded-lg border border-sz-line bg-sz-base"
                whileHover={reduceMotion ? undefined : { y: -4 }}
                transition={{ type: "spring", stiffness: 300, damping: 26 }}
              >
                <div className="aspect-[16/10] overflow-hidden">
                  <img
                    src={scene.src}
                    alt={scene.alt}
                    loading="lazy"
                    className={
                      reduceMotion
                        ? "h-full w-full object-cover"
                        : "h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.04]"
                    }
                  />
                </div>
                <div className="p-5">
                  <h3 className="font-semibold">{scene.title}</h3>
                  <p className="mt-1.5 text-[15px] leading-relaxed text-sz-text-2">
                    {scene.body}
                  </p>
                </div>
              </motion.li>
            </Reveal>
          ))}
        </ul>
      </div>
    </section>
  );
}
