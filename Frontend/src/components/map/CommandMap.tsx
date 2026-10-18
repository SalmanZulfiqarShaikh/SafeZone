import { ChevronDown, ChevronUp } from "lucide-react";
import { useMemo, useState } from "react";

import { coords } from "../../lib/format";
import { project } from "../../lib/geo";
import { CATEGORY_LABEL, severityOf } from "../../lib/severity";
import type { CaseDetail, Volunteer } from "../../lib/types";
import { cn } from "../../lib/utils";
import { MapBase } from "./MapBase";

const SEV_FILL: Record<string, string> = {
  critical: "bg-sz-crit-fill",
  elevated: "bg-sz-elev-fill",
  normal: "bg-sz-norm-fill",
};

const SEV_BORDER: Record<string, string> = {
  critical: "border-sz-crit",
  elevated: "border-sz-elev",
  normal: "border-sz-norm",
};

/* Held well back from the case pins. A volunteer is context for the decision,
   not the thing being decided — at full strength the hatches compete with the
   severity colours and the map stops reading at a glance. */
const DUTY_TEXT: Record<Volunteer["status"], string> = {
  on_duty: "text-sz-earth/50",
  busy: "text-sz-elev/50",
  off_duty: "text-sz-text-3/40",
};

function LegendRow({ swatch, label }: { swatch: React.ReactNode; label: string }) {
  return (
    <li className="flex items-center gap-2">
      <span className="flex h-3.5 w-3.5 shrink-0 items-center justify-center">{swatch}</span>
      <span className="text-sz-text-2">{label}</span>
    </li>
  );
}

export function CommandMap({
  cases,
  volunteers,
  selectedId,
  onSelect,
}: {
  cases: CaseDetail[];
  volunteers: Volunteer[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}) {
  const selected = cases.find((row) => row.id === selectedId) ?? null;
  // The legend sits over the top-left of the map, which is prime space once
  // you know what the shapes mean. Collapses to a single chip.
  const [legendOpen, setLegendOpen] = useState(true);

  /** One label per zone that currently has a case in it. Labelling all fifty
   *  areas would bury the pins. */
  const zoneLabels = useMemo(() => {
    const seen = new Map<string, { x: number; y: number; name: string }>();
    cases.forEach((row) => {
      const zone = row.zone;
      if (!zone || seen.has(zone.id)) return;
      const point = project(zone.lat, zone.lng);
      if (point) seen.set(zone.id, { ...point, name: zone.name });
    });
    return [...seen.values()];
  }, [cases]);

  const exactSelected =
    selected?.incident?.location_source === "pin" || selected?.incident?.location_known;

  /** A line per accepted offer, from whoever took it to where they are going. */
  const routes = useMemo(() => {
    const live = new Set(["accepted", "on_way", "arrived"]);
    const out: Array<{
      key: string;
      from: { x: number; y: number };
      to: { x: number; y: number };
      arrived: boolean;
    }> = [];

    cases.forEach((row) => {
      const to = project(row.incident?.lat, row.incident?.lng);
      if (!to) return;
      row.dispatches.forEach((dispatch) => {
        if (!live.has(dispatch.status)) return;
        const volunteer = volunteers.find((person) => person.id === dispatch.volunteer_id);
        const from = project(volunteer?.lat, volunteer?.lng);
        if (!from) return;
        out.push({
          key: `${row.id}-${dispatch.id}`,
          from,
          to,
          arrived: dispatch.status === "arrived",
        });
      });
    });

    return out;
  }, [cases, volunteers]);

  return (
    <section aria-label="Command map" className="relative min-h-[15rem] grow overflow-hidden">
      <MapBase />

      {/* Dispatch lines: volunteer position to the case they accepted. Drawn
          in the same 0–100 space as the pins so the endpoints land on them,
          with the dash marching towards the case so direction of travel reads
          without an arrowhead. Emerald once they have arrived. */}
      {routes.length > 0 && (
        <svg
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          aria-hidden="true"
          className="absolute inset-0 h-full w-full"
        >
          {routes.map((route) => (
            <line
              key={route.key}
              x1={route.from.x}
              y1={route.from.y}
              x2={route.to.x}
              y2={route.to.y}
              stroke={
                route.arrived ? "var(--color-sz-earth)" : "var(--color-sz-route)"
              }
              strokeWidth="1.5"
              strokeDasharray="4 4"
              strokeLinecap="round"
              vectorEffect="non-scaling-stroke"
              className={route.arrived ? undefined : "sz-march"}
              opacity={route.arrived ? 0.55 : 0.9}
            />
          ))}
        </svg>
      )}

      {/* Labels live in HTML rather than in the SVG: the basemap is drawn with
          preserveAspectRatio="none", which would stretch any text inside it. */}
      <span
        aria-hidden="true"
        className="pointer-events-none absolute text-[10px] tracking-[0.12em] text-sz-text-3/45"
        style={{ left: "4%", top: "88%" }}
      >
        Arabian Sea
      </span>

      {zoneLabels.map((zone) => (
        <span
          key={zone.name}
          aria-hidden="true"
          className="pointer-events-none absolute -translate-x-1/2 translate-y-2 text-[10px] whitespace-nowrap text-sz-text-3/70"
          style={{ left: `${zone.x}%`, top: `${zone.y}%` }}
        >
          {zone.name}
        </span>
      ))}

      {/* Volunteers first, so a case pin is never hidden behind one. */}
      {volunteers.map((volunteer) => {
        const point = project(volunteer.lat, volunteer.lng);
        if (!point) return null;
        return (
          <span
            key={`v-${volunteer.id}`}
            title={`${volunteer.name ?? "Volunteer"} — demo volunteer on a team phone, ${volunteer.status.replace("_", " ")}`}
            className={cn(
              "sz-hatch pointer-events-none absolute block h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 border border-current",
              DUTY_TEXT[volunteer.status],
            )}
            style={{ left: `${point.x}%`, top: `${point.y}%` }}
          />
        );
      })}

      {cases.map((row) => {
        const incident = row.incident;
        const point = project(incident?.lat, incident?.lng);
        if (!point) return null;

        const severity = severityOf(row.priority_score);
        const exact = incident?.location_source === "pin" || incident?.location_known;
        const active = row.id === selectedId;
        const category = incident ? CATEGORY_LABEL[incident.category] : "Case";

        return (
          <button
            key={`c-${row.id}`}
            type="button"
            onClick={() => onSelect(row.id)}
            aria-label={`Case ${row.id}, ${category} in ${row.zone?.name ?? "unknown area"}, ${severity}${exact ? "" : ", area centre only"}`}
            aria-current={active ? "true" : undefined}
            className="absolute flex h-8 w-8 -translate-x-1/2 -translate-y-1/2 cursor-pointer items-center justify-center"
            style={{ left: `${point.x}%`, top: `${point.y}%` }}
          >
            {/* Only critical pins pulse. If everything moved, movement would
                stop meaning anything. */}
            {severity === "critical" && exact && (
              <span
                aria-hidden="true"
                className={cn(
                  "sz-ping absolute h-4 w-4 rounded-full",
                  SEV_FILL[severity],
                  "opacity-50",
                )}
              />
            )}

            {exact ? (
              <span
                aria-hidden="true"
                className={cn(
                  "relative block h-3 w-3 rotate-45 border border-sz-panel",
                  SEV_FILL[severity],
                  active && "ring-2 ring-sz-text/70 ring-offset-0",
                )}
              />
            ) : (
              <span
                aria-hidden="true"
                className={cn(
                  "relative block h-5 w-5 rounded-full border-[1.5px] border-dashed bg-sz-elev/12",
                  SEV_BORDER[severity],
                  active && "ring-2 ring-sz-text/70",
                )}
              />
            )}
          </button>
        );
      })}

      <div className="absolute top-3 left-3 overflow-hidden rounded-lg border border-sz-line bg-sz-panel/95 backdrop-blur-sm">
        <button
          type="button"
          onClick={() => setLegendOpen((value) => !value)}
          aria-expanded={legendOpen}
          className="flex w-full cursor-pointer items-center gap-2 px-2.5 py-1.5 text-[12px] font-medium text-sz-text-2 transition-colors hover:text-sz-text"
          title={legendOpen ? "Collapse the legend" : "Show the legend"}
        >
          Legend
          {legendOpen ? (
            <ChevronUp className="h-3 w-3" aria-hidden="true" />
          ) : (
            <ChevronDown className="h-3 w-3" aria-hidden="true" />
          )}
        </button>
        <ul className="flex flex-col gap-1.5 px-2.5 pb-2" hidden={!legendOpen}>
          <LegendRow
            swatch={<span className="block h-3 w-3 rotate-45 bg-sz-crit" />}
            label="Exact pin from the person"
          />
          <LegendRow
            swatch={
              <span className="block h-3.5 w-3.5 rounded-full border-[1.5px] border-dashed border-sz-elev bg-sz-elev/12" />
            }
            label="Area centre, not a location"
          />
          <LegendRow
            swatch={<span className="sz-hatch block h-3 w-3 border border-current text-sz-earth" />}
            label="Demo volunteer, team phone"
          />
          {routes.length > 0 && (
            <LegendRow
              swatch={<span className="block h-0.5 w-3.5 rounded-full bg-sz-route" />}
              label="Volunteer en route"
            />
          )}
        </ul>
      </div>

      {selected && (
        <div className="absolute right-3 bottom-3 max-w-[16rem] rounded-sm border border-sz-line bg-sz-panel/92 px-2.5 py-2 backdrop-blur-sm">
          <p className="text-sz-text-2">
            Case <span className="font-mono text-sz-text">{selected.id}</span>
          </p>
          <p className="mt-0.5 font-mono text-[12px] text-sz-text">
            {coords(selected.incident?.lat, selected.incident?.lng)}
          </p>
          <p className="mt-1 text-[12px] text-sz-text-3">
            {exactSelected
              ? "Exact pin shared by the person."
              : `Area centre for ${selected.zone?.name ?? "this area"}. Not a person's location, and never shown to a responder.`}
          </p>
        </div>
      )}
    </section>
  );
}
