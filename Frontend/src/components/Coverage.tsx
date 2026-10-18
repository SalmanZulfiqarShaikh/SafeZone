import { Clock, Languages, MapPin, UserCheck } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { Reveal } from "./Reveal";

/**
 * Four facts, directly under the hero.
 *
 * Someone who has just landed is deciding whether this is a real thing or a
 * poster. Four concrete numbers answer that faster than another paragraph,
 * and every one of them is checkable: the area count comes from the database
 * rather than the bundle, so the page cannot keep claiming coverage after
 * somebody removes an area.
 *
 * `null` renders a dash. A made-up number here would be the exact
 * overstatement AGENTS.md 17 #10 rules out, and this strip is the most
 * quotable thing on the page.
 */

const ITEMS: Array<{
  icon: LucideIcon;
  label: string;
  note: string;
}> = [
  { icon: MapPin, label: "areas across Karachi", note: "All seven districts" },
  { icon: Clock, label: "to the first reply", note: "Never waits for a human" },
  { icon: Languages, label: "ways to write it", note: "English, Urdu, Roman Urdu" },
  { icon: UserCheck, label: "manual step", note: "The official handoff" },
];

export function Coverage({ areaCount }: { areaCount: number | null }) {
  const values = [
    areaCount == null ? "—" : String(areaCount),
    "Seconds",
    "Any",
    "One",
  ];

  return (
    <section
      aria-label="Coverage"
      className="border-y border-sz-line bg-sz-raised/60"
    >
      <div className="mx-auto w-full max-w-6xl px-4 sm:px-6">
        <ul className="grid grid-cols-2 divide-sz-line sm:divide-x lg:grid-cols-4">
          {ITEMS.map((item, index) => (
            <Reveal key={item.label} delay={index * 0.05}>
              <li className="flex h-full items-start gap-3 px-0 py-5 sm:px-5 lg:py-6">
                <item.icon
                  className="mt-1 h-4.5 w-4.5 shrink-0 text-sz-water"
                  aria-hidden="true"
                />
                <div className="min-w-0">
                  <p className="font-mono text-[1.4rem] leading-none tabular-nums">
                    {values[index]}
                  </p>
                  <p className="mt-1.5 text-[13.5px] leading-snug text-sz-text-2">
                    {item.label}
                  </p>
                  <p className="mt-0.5 text-[12px] text-sz-text-3">{item.note}</p>
                </div>
              </li>
            </Reveal>
          ))}
        </ul>
      </div>
    </section>
  );
}
