import { ArrowRight, Check } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import { PublicShell } from "../components/PublicShell";
import { Flow } from "../components/Flow";
import { Hero } from "../components/Hero";
import { WhatWeFace } from "../components/WhatWeFace";
import * as api from "../lib/api";
import type { RegistrationResult } from "../lib/types";


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
  const [areas, setAreas] = useState<Array<{ id: string; name: string }>>([]);

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
        // Alerts are the optional path. Losing the dropdown must not touch
        // the part of this page that matters, which is the WhatsApp link.
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

      <WhatWeFace />

      <Flow />

      <div className="mx-auto w-full max-w-5xl px-4 py-12 sm:px-6 sm:py-14">
        <section className="sz-lift rounded-sm border border-sz-line bg-sz-panel p-5 sm:p-7">
          <h2 className="text-xl font-semibold tracking-[-0.02em]">Get alerts for your area</h2>
          <p className="mt-2 max-w-[56ch] text-sz-text-2">
            Optional. This is only so we can warn you early when something is happening nearby —
            you never need it to ask for help.
          </p>

          {result ? (
            <div className="mt-6">
              <p className="flex items-center gap-2 text-sz-earth">
                <Check className="h-4 w-4 shrink-0" aria-hidden="true" />
                One step left
              </p>
              <p className="mt-2.5 max-w-[56ch] text-sz-text-2">{result.instructions}</p>
              <p className="mt-4 inline-flex items-center gap-2.5 rounded-sm border border-sz-line bg-sz-raised px-3 py-2">
                <span className="text-[12px] text-sz-text-3">Your code</span>
                <span className="font-mono text-base tracking-[0.08em]">{result.code}</span>
              </p>
              {result.whatsapp_url && (
                <a
                  href={result.whatsapp_url}
                  className="mt-4 inline-flex min-h-11 items-center gap-2 rounded-sm bg-sz-whatsapp px-4 py-2.5 font-semibold text-white transition-opacity hover:opacity-90"
                >
                  Send it on WhatsApp
                  <ArrowRight className="h-4 w-4" aria-hidden="true" />
                </a>
              )}
              <p className="mt-4 text-[12px] text-sz-text-3">
                We never ask for your number here. It is whichever number sends that code — the
                only one we can prove reaches you.
              </p>
            </div>
          ) : (
            <form onSubmit={onSubmit} className="mt-6 flex flex-wrap items-end gap-4">
              <div className="min-w-0 grow basis-52">
                <label htmlFor="first-name" className="block text-sz-text-2">
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
                  className="mt-1.5 h-11 w-full rounded-sm border border-sz-line bg-sz-base px-3 text-sz-text placeholder:text-sz-text-3"
                  placeholder="So a volunteer knows who to ask for"
                />
              </div>

              <div className="min-w-0 grow basis-52">
                <label htmlFor="zone" className="block text-sz-text-2">
                  Your area
                </label>
                <select
                  id="zone"
                  name="zone"
                  value={zoneId}
                  onChange={(event) => setZoneId(event.target.value)}
                  className="mt-1.5 h-11 w-full rounded-sm border border-sz-line bg-sz-base px-3 text-sz-text"
                >
                  <option value="">
                    {areas.length ? "Choose an area" : "Loading areas\u2026"}
                  </option>
                  {areas.map((area) => (
                    <option key={area.id} value={area.id}>
                      {area.name}
                    </option>
                  ))}
                </select>
              </div>

              <button
                type="submit"
                disabled={sending}
                className="inline-flex h-11 items-center gap-2 rounded-sm border border-sz-water bg-sz-water/12 px-4 font-semibold text-sz-water transition-colors hover:bg-sz-water/20 disabled:opacity-50"
              >
                {sending ? "Sending" : "Get a code"}
              </button>

              {error && (
                <p role="alert" className="w-full text-sz-crit">
                  {error}
                </p>
              )}
            </form>
          )}
        </section>

        {/* Four bordered cards across two columns rather than loose bullets
            in a narrow left-hand strip. These are the honest limits
            (AGENTS.md 16), and a section that looks like an afterthought
            gets read like one. */}
        <h2 className="mt-14 text-[1.6rem] font-semibold tracking-[-0.025em] sm:text-[2rem]">
          What this is not
        </h2>
        <p className="mt-2.5 max-w-[60ch] text-sz-text-2">
          Worth knowing before you need us, rather than finding out in the middle of
          something.
        </p>
        <ul className="mt-6 grid gap-4 sm:grid-cols-2">
          {NOT.map((item) => (
            <li
              key={item.title}
              className="rounded-lg border border-sz-line bg-sz-panel p-5"
            >
              <h3 className="font-semibold">{item.title}</h3>
              <p className="mt-1.5 text-[14.5px] leading-relaxed text-sz-text-2">
                {item.body}
              </p>
            </li>
          ))}
        </ul>
      </div>
    </PublicShell>
  );
}
