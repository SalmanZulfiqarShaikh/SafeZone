import { ArrowRight, BellRing, Check, ShieldAlert } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import { AreaPicker, type Area } from "../components/AreaPicker";
import { Coverage } from "../components/Coverage";
import { Flow } from "../components/Flow";
import { Hero } from "../components/Hero";
import { PublicShell } from "../components/PublicShell";
import { Reveal } from "../components/Reveal";
import { WhatWeFace } from "../components/WhatWeFace";
import * as api from "../lib/api";
import type { RegistrationResult } from "../lib/types";

/**
 * The landing page.
 *
 * Every section shares one container width, because the eye reads a ragged
 * left edge down a page as carelessness even when it cannot say why.
 */

const NOT = [
  {
    title: "Not an emergency service",
    body: "We cannot send a boat or an ambulance ourselves. Fire and medical always point you to the official number first, in the very first reply.",
  },
  {
    title: "Volunteers are neighbours, not professionals",
    body: "People who signed up to help on their own street. They are not vetted, trained or insured in this prototype, and they are asked to assess from a safe place.",
  },
  {
    title: "The handoff is a link, not an integration",
    body: "Responders get a page with everything on it. That is a message we send them, not a live connection into any organisation's system.",
  },
  {
    title: "The volunteer pool is our own phones",
    body: "In this prototype the volunteers are the team, and they are labelled as demo volunteers everywhere they appear.",
  },
];

export default function Home() {
  const [firstName, setFirstName] = useState("");
  const [zoneId, setZoneId] = useState("");
  const [result, setResult] = useState<RegistrationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [areas, setAreas] = useState<Area[]>([]);
  const [areasLoading, setAreasLoading] = useState(true);

  // The real area list, from the database rather than a list baked into the
  // bundle: adding an area to data/areas.py and re-seeding must show up here
  // without a frontend release.
  useEffect(() => {
    let cancelled = false;
    api
      .listZones()
      .then((zones) => {
        if (!cancelled) setAreas(zones.map(({ id, name }) => ({ id, name })));
      })
      .catch(() => {
        // Alerts are the optional path. Losing the list must not touch the
        // part of this page that matters, which is the WhatsApp link.
      })
      .finally(() => {
        if (!cancelled) setAreasLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!firstName.trim()) return;
    setSending(true);
    setError(null);
    try {
      const minted = await api.register(firstName.trim(), zoneId || null);
      setResult(minted);

      // Send them straight to WhatsApp with the code. Registration is only
      // finished when that code arrives from their own number, so leaving
      // them on a page holding six characters is leaving the job half done.
      // The code stays on screen either way, because a blocked pop-up must
      // not lose it.
      // The backend builds this link with its own number and the code
      // already in the text, so there is nothing to assemble here.
      const next = minted.whatsapp_url;
      if (next) window.open(next, "_blank", "noopener,noreferrer");
    } catch {
      setError(
        "That did not go through. You do not need to register to get help — message us on WhatsApp instead.",
      );
    } finally {
      setSending(false);
    }
  }

  return (
    <PublicShell>
      <Hero />

      <Coverage areaCount={areasLoading ? null : areas.length} />

      <WhatWeFace />

      <Flow />

      {/* ─── Area alerts ───────────────────────────────────────────────
          A band rather than a lone card. Two columns so the form has a
          reason beside it: what it is for, and the one thing people
          actually want to know, which is whether this costs them their
          phone number. */}
      <section className="border-t border-sz-line bg-sz-raised/60">
        <div className="mx-auto w-full max-w-6xl px-4 py-14 sm:px-6 sm:py-16">
          <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)] lg:gap-16">
            <Reveal>
              <div>
                <p className="flex items-center gap-2 text-[13px] font-medium text-sz-water">
                  <BellRing className="h-4 w-4" aria-hidden="true" />
                  Optional
                </p>
                <h2 className="mt-2.5 text-[1.6rem] font-semibold tracking-[-0.025em] sm:text-[2rem]">
                  Get alerts for your area
                </h2>
                <p className="mt-3 max-w-[52ch] text-sz-text-2">
                  So we can warn you early when something is happening nearby. You never
                  need this to ask for help &mdash; anyone can message us with no account
                  and no code.
                </p>

                <ul className="mt-6 flex flex-col gap-2.5 text-[14.5px] text-sz-text-2">
                  <li className="flex gap-2.5">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-sz-earth" aria-hidden="true" />
                    We never ask for your number on this page. It is whichever number sends
                    the code &mdash; the only one we can prove reaches you.
                  </li>
                  <li className="flex gap-2.5">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-sz-earth" aria-hidden="true" />
                    Reply STOP at any time and the alerts stop.
                  </li>
                </ul>
              </div>
            </Reveal>

            <Reveal delay={0.08}>
              <div className="rounded-xl border border-sz-line bg-sz-panel p-5 sm:p-6">
                {result ? (
                  <div>
                    <p className="flex items-center gap-2 font-medium text-sz-earth">
                      <Check className="h-4 w-4 shrink-0" aria-hidden="true" />
                      One step left
                    </p>
                    <p className="mt-2.5 text-[14.5px] leading-relaxed text-sz-text-2">
                      {result.instructions}
                    </p>
                    <p className="mt-4 flex items-center justify-between gap-3 rounded-lg border border-sz-line bg-sz-base px-3.5 py-3">
                      <span className="text-[12px] text-sz-text-3">Your code</span>
                      <span className="font-mono text-lg tracking-[0.12em]">{result.code}</span>
                    </p>
                    {result.whatsapp_url && (
                      <a
                        href={result.whatsapp_url}
                        className="mt-4 flex min-h-12 items-center justify-center gap-2 rounded-lg bg-sz-whatsapp px-4 font-semibold text-white transition-opacity hover:opacity-90"
                      >
                        Send it on WhatsApp
                        <ArrowRight className="h-4 w-4" aria-hidden="true" />
                      </a>
                    )}
                  </div>
                ) : (
                  <form onSubmit={onSubmit} className="flex flex-col gap-4">
                    <div>
                      <label htmlFor="first-name" className="block text-[14px] text-sz-text-2">
                        First name
                      </label>
                      <input
                        id="first-name"
                        name="first-name"
                        value={firstName}
                        onChange={(event) => setFirstName(event.target.value)}
                        autoComplete="given-name"
                        maxLength={80}
                        required
                        className="mt-1.5 h-12 w-full rounded-lg border border-sz-line bg-sz-base px-3.5 text-sz-text transition-colors outline-none placeholder:text-sz-text-3 focus:border-sz-water focus:ring-2 focus:ring-sz-water/25"
                        placeholder="So a volunteer knows who to ask for"
                      />
                    </div>

                    <AreaPicker
                      areas={areas}
                      value={zoneId}
                      onChange={setZoneId}
                      loading={areasLoading}
                    />

                    <button
                      type="submit"
                      disabled={sending}
                      className="mt-1 inline-flex h-12 cursor-pointer items-center justify-center gap-2 rounded-lg bg-sz-water px-4 font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
                    >
                      {sending ? "Sending…" : "Get a code"}
                      {!sending && <ArrowRight className="h-4 w-4" aria-hidden="true" />}
                    </button>

                    {error && (
                      <p role="alert" className="text-[14px] text-sz-crit">
                        {error}
                      </p>
                    )}
                  </form>
                )}
              </div>
            </Reveal>
          </div>
        </div>
      </section>

      {/* ─── The limits ────────────────────────────────────────────────
          These are the honest limits (AGENTS.md 16). A section that looks
          like an afterthought gets read like one, so it gets the same
          weight as everything above it. */}
      <div className="mx-auto w-full max-w-6xl px-4 py-14 sm:px-6 sm:py-16">
        <Reveal>
          <p className="flex items-center gap-2 text-[13px] font-medium text-sz-crit">
            <ShieldAlert className="h-4 w-4" aria-hidden="true" />
            Before you need us
          </p>
          <h2 className="mt-2.5 text-[1.6rem] font-semibold tracking-[-0.025em] sm:text-[2rem]">
            What this is not
          </h2>
          <p className="mt-3 max-w-[60ch] text-sz-text-2">
            Worth knowing now, rather than finding out in the middle of something.
          </p>
        </Reveal>

        <ul className="mt-7 grid gap-4 sm:grid-cols-2">
          {NOT.map((item, index) => (
            <Reveal key={item.title} delay={index * 0.05}>
              <li className="h-full rounded-xl border border-sz-line bg-sz-panel p-5 transition-colors hover:border-sz-crit/40">
                <h3 className="font-semibold">{item.title}</h3>
                <p className="mt-2 text-[14.5px] leading-relaxed text-sz-text-2">
                  {item.body}
                </p>
              </li>
            </Reveal>
          ))}
        </ul>
      </div>
    </PublicShell>
  );
}
