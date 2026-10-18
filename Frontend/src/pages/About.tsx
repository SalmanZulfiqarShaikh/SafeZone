import { useEffect, useState } from "react";
import { Check, Minus } from "lucide-react";

import { PageHeader } from "../components/PageHeader";
import { PublicShell } from "../components/PublicShell";
import { Reveal } from "../components/Reveal";
import * as api from "../lib/api";
import { BRAND, FRAMING } from "../lib/brand";
import { cn } from "../lib/utils";

/**
 * What SafeZone does, in as few words as will carry it.
 *
 * The previous version said everything correctly and nobody read it: six
 * numbered paragraphs and nine bulleted limits is a document, not a page.
 * Every claim here survives, cut to the sentence that earns it, because
 * what this page is actually for is letting someone decide in thirty
 * seconds whether to trust the number.
 *
 * The counts come from /api/zones rather than being typed in, so the page
 * cannot quietly claim coverage the system does not have.
 */

const STEPS = [
  { t: "You message", b: "Any number, any words. No account, no form." },
  { t: "We read it", b: "What happened, where, and who cannot move on their own." },
  { t: "It gets ranked", b: "Urgency and vulnerability decide the order. Duplicates merge." },
  { t: "Neighbours are asked", b: "Nearest on-duty volunteers, immediately. Area only." },
  { t: "A human approves", b: "The official handoff waits for a coordinator. Nothing else does." },
  { t: "We check", b: "Did help arrive? If not, the case goes back to the top." },
];

/** Stated as plainly as we can manage. A limit that reads like marketing is
 *  worse than no limit at all. */
const LIMITS = [
  "We cannot send a boat, an ambulance or a fire crew. Fire and medical point to the official number first.",
  "Volunteers are neighbours, not professionals — not vetted, trained or insured in this prototype.",
  "The handoff is a link we send, not a live connection into anyone's system.",
  "Nearest is straight-line distance, not routed travel time.",
  "Everything runs over WhatsApp. No SMS fallback, and networks fail during exactly these events.",
];

export default function About() {
  const [areaCount, setAreaCount] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .listZones()
      .then((zones) => {
        if (!cancelled) setAreaCount(zones.length);
      })
      .catch(() => {
        // The page reads fine without it; the tile just shows a dash rather
        // than a number we made up.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <PublicShell>
      <PageHeader kicker="About" title={`What ${BRAND} does`}>
        {FRAMING}
      </PageHeader>

      <div className="mx-auto w-full max-w-5xl px-4 py-10 sm:px-6">
        {/* ─── The whole argument, in four numbers ──────────────────── */}
        <Reveal>
          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-4 sm:gap-4">
            <Stat value={areaCount == null ? "—" : String(areaCount)} label="areas covered" />
            <Stat value="7" label="Karachi districts" />
            <Stat value="Seconds" label="to the first reply" small />
            <Stat value="1" label="manual step" />
          </ul>
        </Reveal>

        <Reveal delay={0.06}>
          <p className="mt-8 max-w-[58ch] text-[17px] leading-relaxed text-sz-text-2">
            During the monsoon, help does not fail because nobody wants to give it. It
            fails because in the first hour nobody can tell which of four hundred messages
            is the one where someone cannot get up the stairs.
          </p>
        </Reveal>

        {/* ─── How it works ─────────────────────────────────────────── */}
        <Reveal delay={0.08}>
          <h2 className="mt-12 text-[1.5rem] font-semibold tracking-[-0.02em]">
            How it works
          </h2>
        </Reveal>

        <ol className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {STEPS.map((step, index) => (
            <Reveal key={step.t} delay={index * 0.05}>
              <li className="flex h-full gap-3.5 rounded-lg border border-sz-line bg-sz-panel p-4">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-sz-water/40 bg-sz-water/10 font-mono text-[12px] text-sz-water">
                  {index + 1}
                </span>
                <span className="min-w-0">
                  <span className="block font-semibold">{step.t}</span>
                  <span className="mt-0.5 block text-[14px] leading-snug text-sz-text-2">
                    {step.b}
                  </span>
                </span>
              </li>
            </Reveal>
          ))}
        </ol>

        {/* ─── Can / cannot, side by side ───────────────────────────── */}
        <Reveal delay={0.08}>
          <h2 className="mt-12 text-[1.5rem] font-semibold tracking-[-0.02em]">
            What it is and is not
          </h2>
          <p className="mt-2 max-w-[56ch] text-sz-text-2">
            The limits as they stand today, not a roadmap.
          </p>
        </Reveal>

        <div className="mt-5 grid gap-4 lg:grid-cols-2">
          <Reveal delay={0.05}>
            <div className="h-full rounded-lg border border-sz-earth/40 bg-sz-earth/8 p-5">
              <h3 className="flex items-center gap-2 font-semibold">
                <Check className="h-4 w-4 text-sz-earth" aria-hidden="true" />
                What it does
              </h3>
              <ul className="mt-3 flex flex-col gap-2 text-[14.5px] leading-relaxed text-sz-text-2">
                <li>Reads messages in English, Urdu or Roman Urdu, however they are typed.</li>
                <li>Ranks by urgency and who is at risk, and shows its reasoning in words.</li>
                <li>Merges duplicate reports of the same street into one case.</li>
                <li>Hands responders a finished case with the location already in it.</li>
                <li>Asks afterwards whether help actually arrived.</li>
              </ul>
            </div>
          </Reveal>

          <Reveal delay={0.1}>
            <div className="h-full rounded-lg border border-sz-crit/35 bg-sz-crit/8 p-5">
              <h3 className="flex items-center gap-2 font-semibold">
                <Minus className="h-4 w-4 text-sz-crit" aria-hidden="true" />
                What it does not
              </h3>
              <ul className="mt-3 flex flex-col gap-2 text-[14.5px] leading-relaxed text-sz-text-2">
                {LIMITS.map((limit) => (
                  <li key={limit}>{limit}</li>
                ))}
              </ul>
            </div>
          </Reveal>
        </div>

        <Reveal delay={0.1}>
          <p className="mt-10 max-w-[64ch] text-sz-text-2">
            Built by team Nova Strike for CODE//CONNECT&rsquo;26 at UBIT. A working
            prototype on real infrastructure with a real WhatsApp number &mdash; and a
            prototype, which is what the list above means in practice.
          </p>
        </Reveal>
      </div>
    </PublicShell>
  );
}

function Stat({
  value,
  label,
  small,
}: {
  value: string;
  label: string;
  small?: boolean;
}) {
  return (
    <li className="rounded-lg border border-sz-line bg-sz-panel px-4 py-3.5">
      <p
        className={cn(
          "font-mono leading-none tabular-nums text-sz-water",
          small ? "text-[1.35rem]" : "text-[2rem]",
        )}
      >
        {value}
      </p>
      <p className="mt-2 text-[13px] text-sz-text-2">{label}</p>
    </li>
  );
}
