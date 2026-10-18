import { Eye, EyeOff } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Navigate } from "react-router";

import * as api from "../lib/api";

import { AppShell } from "../components/AppShell";
import { SimulatedTag } from "../components/SimulatedTag";
import { StatusPill } from "../components/StatusPill";
import { useDashboard } from "../hooks/useDashboard";
import { capabilityLabel, maskPhone, prettyPhone } from "../lib/format";
import type { Volunteer, VolunteerStatus } from "../lib/types";
import { cn } from "../lib/utils";
import { severityOf } from "../lib/severity";

const DUTY: Record<VolunteerStatus, { label: string; tone: string }> = {
  on_duty: { label: "On duty", tone: "border-sz-earth/45 bg-sz-earth/12 text-sz-earth" },
  busy: { label: "On a case", tone: "border-sz-elev/45 bg-sz-elev/12 text-sz-elev" },
  off_duty: { label: "Off duty", tone: "border-sz-line bg-sz-raised text-sz-text-3" },
};

/** Area ids come back on the volunteer rows; the readable names come from
 *  /api/zones. Falling back to a de-slugged id means an area added to the
 *  database after this page loaded still reads sensibly rather than blank. */
function makeZoneName(names: Record<string, string>) {
  return (id: string): string => names[id] ?? id.replace(/-/g, " ");
}

function Row({
  volunteer,
  reveal,
  zoneName,
}: {
  volunteer: Volunteer;
  reveal: boolean;
  zoneName: (id: string) => string;
}) {
  const duty = DUTY[volunteer.status];
  return (
    <tr className="border-t border-sz-line-soft align-top">
      <td className="py-3 pr-4">
        <div className="flex items-center gap-2.5">
          <span
            aria-hidden="true"
            className="sz-hatch block h-3 w-3 shrink-0 border border-current text-sz-earth"
          />
          <span className="font-medium">{volunteer.name ?? "Unnamed"}</span>
        </div>
      </td>
      <td className="py-3 pr-4">
        <StatusPill tone={duty.tone}>{duty.label}</StatusPill>
      </td>
      <td className="py-3 pr-4 font-mono text-[12px] whitespace-nowrap text-sz-text-2">
        {reveal ? prettyPhone(volunteer.phone) : maskPhone(volunteer.phone)}
      </td>
      <td className="py-3 pr-4 text-sz-text-2">
        {volunteer.zone_ids.length > 0 ? volunteer.zone_ids.map(zoneName).join(", ") : "—"}
      </td>
      <td className="py-3">
        <ul className="flex flex-wrap gap-1.5">
          {volunteer.capabilities.map((capability) => (
            <li
              key={capability}
              className="rounded-sm border border-sz-line bg-sz-raised px-1.5 py-0.5 text-[11px] text-sz-text-2"
            >
              {capabilityLabel(capability)}
            </li>
          ))}
        </ul>
      </td>
    </tr>
  );
}

export default function Volunteers() {
  const { volunteers, admin, source, error, unauthorized, streaming, cases, toggleKillSwitch, reload } =
    useDashboard();
  const [reveal, setReveal] = useState(false);
  const [zoneNames, setZoneNames] = useState<Record<string, string>>({});

  // The area list is public and small, so it loads independently of the
  // volunteer fetch: a failure here costs readable area names, not the page.
  useEffect(() => {
    let cancelled = false;
    api
      .listZones()
      .then((areas) => {
        if (cancelled) return;
        setZoneNames(Object.fromEntries(areas.map((area) => [area.id, area.name])));
      })
      .catch(() => {
        /* ids will show de-slugged instead */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const zoneName = useMemo(() => makeZoneName(zoneNames), [zoneNames]);

  /** Several demo rows share one phone — the pool is two team handsets. Group
   *  by number so the control room sees that honestly rather than reading it
   *  as nine independent people. */
  const handsets = useMemo(() => {
    const grouped = new Map<string, Volunteer[]>();
    volunteers.forEach((volunteer) => {
      const list = grouped.get(volunteer.phone) ?? [];
      list.push(volunteer);
      grouped.set(volunteer.phone, list);
    });
    return [...grouped.entries()].map(([phone, members], index) => ({
      phone,
      members,
      label: `Phone ${String.fromCharCode(65 + index)}`,
    }));
  }, [volunteers]);

  const onDuty = volunteers.filter((v) => v.status === "on_duty").length;
  const busy = volunteers.filter((v) => v.status === "busy").length;

  if (unauthorized) return <Navigate to="/login" replace />;

  return (
    <AppShell
      admin={admin}
      source={source}
      streaming={streaming}
      openCount={cases.filter((row) => row.status !== "resolved").length}
      criticalCount={cases.filter((row) => severityOf(row.priority_score) === "critical").length}
      onToggleKillSwitch={toggleKillSwitch}
      error={source === "error" ? error : null}
      onRetry={reload}
    >
      <div className="mx-auto w-full max-w-5xl px-4 py-8 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
          <div>
            <h1 className="text-xl font-semibold tracking-[-0.02em]">Volunteer pool</h1>
            <p className="mt-2 max-w-[60ch] text-sz-text-2">
              {onDuty} on duty, {busy} already on a case, {volunteers.length} registered in all.
              Offers go to the three nearest on-duty volunteers who are not already busy.
            </p>
          </div>

          <button
            type="button"
            onClick={() => setReveal((value) => !value)}
            aria-pressed={reveal}
            className="inline-flex min-h-10 items-center gap-2 rounded-sm border border-sz-line bg-sz-raised px-3 text-sz-text-2 transition-colors hover:text-sz-text"
          >
            {reveal ? (
              <EyeOff className="h-3.5 w-3.5" aria-hidden="true" />
            ) : (
              <Eye className="h-3.5 w-3.5" aria-hidden="true" />
            )}
            {reveal ? "Hide numbers" : "Show numbers"}
          </button>
        </div>

        <p className="mt-4 flex flex-wrap items-center gap-2.5">
          <SimulatedTag title="A real volunteer network was not recruited in 24 hours. The pool is the team's own two handsets, with named profiles seeded per area so the map is populated without lying about it.">
            Demo volunteers on team phones
          </SimulatedTag>
          <span className="text-[12px] text-sz-text-3">
            Numbers are hidden by default — this screen gets projected.
          </span>
        </p>

        <div className="mt-8 flex flex-col gap-9">
          {handsets.map((handset) => (
            <section key={handset.phone}>
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <h2 className="font-medium">{handset.label}</h2>
                <span className="font-mono text-[12px] text-sz-text-3">
                  {reveal ? prettyPhone(handset.phone) : maskPhone(handset.phone)}
                </span>
                <span className="text-[12px] text-sz-text-3">
                  {handset.members.length} profiles route here
                </span>
              </div>

              <div className="sz-scroll mt-3 overflow-x-auto">
                <table className="w-full min-w-[40rem] border-collapse text-left">
                  <thead>
                    <tr className="text-[12px] text-sz-text-3">
                      <th scope="col" className="pb-2 pr-4 font-normal">
                        Name
                      </th>
                      <th scope="col" className="pb-2 pr-4 font-normal">
                        Duty
                      </th>
                      <th scope="col" className="pb-2 pr-4 font-normal">
                        Number
                      </th>
                      <th scope="col" className="pb-2 pr-4 font-normal">
                        Areas covered
                      </th>
                      <th scope="col" className="pb-2 font-normal">
                        Can reach by
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {handset.members.map((volunteer) => (
                      <Row
                        key={volunteer.id}
                        volunteer={volunteer}
                        reveal={reveal}
                        zoneName={zoneName}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ))}
        </div>

        <div className={cn("sz-lift mt-12 rounded-sm border border-sz-line bg-sz-panel p-5")}>
          <h2 className="font-medium">How someone joins</h2>
          <p className="mt-2 max-w-[62ch] text-sz-text-2">
            A volunteer texts <span className="font-mono text-sz-text">VOLUNTEER &lt;area&gt;</span>{" "}
            to the same WhatsApp number, shares a location pin and says what they can do — on foot,
            by car, by boat, first aid. They send{" "}
            <span className="font-mono text-sz-text">ON DUTY</span> when a shift starts, which also
            re-opens the 24-hour messaging window, and{" "}
            <span className="font-mono text-sz-text">ACCEPT &lt;case id&gt;</span> to claim a case.
            The exact location, first name and contact are released only to whoever accepts.
          </p>
        </div>
      </div>
    </AppShell>
  );
}
