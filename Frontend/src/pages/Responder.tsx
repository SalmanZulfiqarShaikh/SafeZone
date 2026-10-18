import { Clock, MapPin, Navigation, Phone, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { useParams } from "react-router";

import { Brandmark } from "../components/AppShell";
import { MapBase } from "../components/map/MapBase";
import { StatusPill } from "../components/StatusPill";
import * as api from "../lib/api";
import { coords, score as fmtScore, timeAgo, timeUntil } from "../lib/format";
import { project } from "../lib/geo";
import {
  CATEGORY_LABEL,
  DISPATCH_LABEL,
  dispatchTone,
  protocolLabels,
  SEVERITY_LABEL,
  SEVERITY_RING,
  severityOf,
} from "../lib/severity";
import type { ResponderView } from "../lib/types";
import { cn } from "../lib/utils";

export default function Responder() {
  const { token = "" } = useParams<{ token: string }>();
  const [view, setView] = useState<ResponderView | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "gone">("loading");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const fresh = await api.getResponderView(token);
        if (cancelled) return;
        setView(fresh);
        setState("ready");
      } catch {
        if (cancelled) return;
        // Every failure lands here, and every failure means "we cannot show
        // you this case". There is deliberately no fallback view: a rescue
        // crew shown an invented address would drive to it. A link that is
        // wrong, expired, or merely unreachable all deserve the same answer.
        setState("gone");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  if (state === "loading") {
    return (
      <main className="flex min-h-screen items-center justify-center bg-sz-base px-6">
        <p className="text-sz-text-2">Opening the case…</p>
      </main>
    );
  }

  if (state === "gone" || !view) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-sz-base px-6 text-center">
        <TriangleAlert className="h-7 w-7 text-sz-elev" aria-hidden="true" />
        <h1 className="text-xl font-semibold">This link no longer works</h1>
        <p className="max-w-[40ch] text-sz-text-2">
          Handoff links expire on their own so a forwarded one stops working after the event. Ask
          the coordinator for a fresh link.
        </p>
      </main>
    );
  }

  const incident = view.incident;
  const severity = severityOf(view.case.priority_score);
  const point = project(incident?.lat, incident?.lng);
  const protocol = protocolLabels(view.case.protocol_path);
  const navigateUrl =
    incident?.lat && incident?.lng
      ? `https://www.google.com/maps/dir/?api=1&destination=${incident.lat},${incident.lng}`
      : null;
  const expiresIn = timeUntil(view.expires_at);

  return (
    // Bottom padding clears the pinned action bar, which is taller than it
    // looks once the "number not set" state wraps onto two lines.
    <div className="flex min-h-screen flex-col bg-sz-base pb-32">
      <header className="flex items-center justify-between gap-3 border-b border-sz-line px-4 py-3">
        <Brandmark />
        <span className="text-[12px] text-sz-text-3">Responder handoff</span>
      </header>

      <main className="grow">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-4">
          <h1 className="font-mono text-xl font-medium tracking-[-0.01em]">
            Case {view.case.id}
          </h1>
          <StatusPill tone={SEVERITY_RING[severity]} className="px-2 py-1 text-[12px]">
            {SEVERITY_LABEL[severity]}
          </StatusPill>
          <StatusPill tone={dispatchTone(view.case.dispatch_status)}>
            {DISPATCH_LABEL[view.case.dispatch_status]}
          </StatusPill>
        </div>

        <p className="px-4 text-base text-sz-text">
          {incident ? CATEGORY_LABEL[incident.category] : "Unknown"} in{" "}
          {view.zone?.name ?? incident?.area ?? "an unknown area"}
        </p>

        {/* Only an exact pin is ever shown here. An area centre is not a
            person's location and never reaches a responder. */}
        {point && incident?.location_known ? (
          <div className="relative mt-4 h-44 overflow-hidden border-y border-sz-line">
            <MapBase />
            <span
              aria-hidden="true"
              className="absolute flex h-9 w-9 -translate-x-1/2 -translate-y-1/2 items-center justify-center"
              style={{ left: `${point.x}%`, top: `${point.y}%` }}
            >
              <span className={cn("sz-ping absolute h-5 w-5 rounded-full opacity-50", "bg-sz-crit-fill")} />
              <span className="relative block h-3.5 w-3.5 rotate-45 border border-sz-panel bg-sz-crit-fill" />
            </span>
            <p className="absolute right-2.5 bottom-2.5 rounded-sm border border-sz-line bg-sz-panel/92 px-2 py-1 font-mono text-[11px] text-sz-text-2 backdrop-blur-sm">
              {coords(incident.lat, incident.lng)}
            </p>
          </div>
        ) : (
          <p className="mt-4 flex items-start gap-2 border-y border-sz-elev/30 bg-sz-elev/8 px-4 py-3 text-sz-elev">
            <MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            <span>
              No exact location yet. The coordinator is still asking for a pin — call them before
              setting out.
            </span>
          </p>
        )}

        <div className="px-4 py-5">
          {view.case.vuln_summary && (
            <>
              <h2 className="font-medium">Who is at risk</h2>
              <p className="mt-1.5 max-w-[56ch] text-base text-sz-text-2">
                {view.case.vuln_summary}
              </p>
            </>
          )}

          <dl className="mt-5 flex flex-wrap gap-x-8 gap-y-3.5">
            {[
              { label: "Reports", value: String(incident?.report_count ?? 1) },
              {
                label: "Since first report",
                value: timeAgo(incident?.created_at ?? view.case.created_at),
              },
              { label: "Confidence", value: fmtScore(incident?.confidence) },
              { label: "Urgency", value: fmtScore(incident?.urgency) },
            ].map((stat) => (
              <div key={stat.label}>
                <dt className="text-[12px] text-sz-text-3">{stat.label}</dt>
                <dd className="font-mono text-base">{stat.value}</dd>
              </div>
            ))}
          </dl>

          {view.case.reason && (
            <>
              <h2 className="mt-7 font-medium">Why this was sent to you</h2>
              <p className="mt-1.5 max-w-[56ch] text-sz-text-2">{view.case.reason}</p>
            </>
          )}

          {protocol.length > 0 && (
            <div className="mt-6 flex flex-wrap items-center gap-1.5">
              <span className="text-[12px] text-sz-text-3">Guidance given to the person</span>
              {protocol.map((step) => (
                <span
                  key={step}
                  className="rounded-sm bg-sz-raised px-1.5 py-0.5 font-mono text-[11px] text-sz-text-2"
                >
                  {step}
                </span>
              ))}
            </div>
          )}

          <p className="mt-7 flex items-start gap-2 text-[12px] text-sz-text-3">
            <Clock className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            <span>
              First name only on this page, never a phone number. The link expires{" "}
              {expiresIn ? `in ${expiresIn}` : "on its own"}
              {view.target_label ? `, and was prepared for ${view.target_label}` : ""}. Nothing was
              sent to any organisation — a coordinator sent you this link.
            </span>
          </p>
        </div>
      </main>

      {/* Pinned in thumb reach: this is read standing up, one-handed, often in
          the rain. */}
      <div className="sz-lift fixed inset-x-0 bottom-0 z-20 flex gap-2.5 border-t border-sz-line bg-sz-panel px-4 py-3">
        {navigateUrl ? (
          <a
            href={navigateUrl}
            target="_blank"
            rel="noreferrer"
            className="inline-flex min-h-13 grow cursor-pointer items-center justify-center gap-2.5 rounded-sm bg-sz-water px-4 text-base font-semibold text-sz-on-fill transition-opacity hover:opacity-90"
          >
            <Navigation className="h-4.5 w-4.5" aria-hidden="true" />
            Navigate
          </a>
        ) : (
          <span className="inline-flex min-h-13 grow items-center justify-center rounded-sm border border-sz-line bg-sz-raised px-4 text-sz-text-3">
            No location to navigate to
          </span>
        )}

        {view.call.number ? (
          <a
            href={`tel:${view.call.number}`}
            className="inline-flex min-h-13 items-center justify-center gap-2.5 rounded-sm border border-sz-earth bg-sz-earth/12 px-4 text-base font-semibold text-sz-earth transition-colors hover:bg-sz-earth/20"
          >
            <Phone className="h-4.5 w-4.5" aria-hidden="true" />
            Call {view.call.label.toLowerCase()}
          </a>
        ) : (
          <span
            className="inline-flex min-h-13 items-center justify-center gap-2.5 rounded-sm border border-sz-elev/40 bg-sz-elev/10 px-4 text-sz-elev"
            title="EMERGENCY_FIRE, EMERGENCY_AMBULANCE and EMERGENCY_POLICE are empty in config. They must be filled from an official source by a human, never from memory."
          >
            <Phone className="h-4.5 w-4.5 shrink-0" aria-hidden="true" />
            <span className="text-left leading-tight">
              {view.call.label} number
              <br />
              <span className="font-mono text-[11px]">not set in config</span>
            </span>
          </span>
        )}
      </div>
    </div>
  );
}
