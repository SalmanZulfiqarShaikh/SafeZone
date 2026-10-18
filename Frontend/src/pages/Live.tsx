import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Activity, Radio, RadioTower } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Navigate } from "react-router";

import { AppShell } from "../components/AppShell";
import { MapBase } from "../components/map/MapBase";
import { useDashboard } from "../hooks/useDashboard";
import * as api from "../lib/api";
import { project } from "../lib/geo";
import { severityOf } from "../lib/severity";
import { timeAgo } from "../lib/format";
import type { CaseDetail } from "../lib/types";

/**
 * The wall display: everything happening right now, on one screen.
 *
 * This is the only view in SafeZone built to be watched rather than used.
 * Nothing here is clickable, because its job is to be legible from across a
 * room while someone else works the queue on the control room page.
 *
 * Every ping is a real event off the ``/events`` stream, which is the same
 * stream the control room reads -- the backend emits on every state change,
 * so nothing on this page is on a timer or faked. When it is quiet, it is
 * quiet. A demo view that invents activity would be the exact dishonesty
 * AGENTS.md 17 #10 forbids, and the stillness is itself informative: it is
 * what a working night looks like.
 */

/** The backend's own event names, in words a room can read at a glance.
 *  Anything not listed falls back to a de-camel-cased form, so a new event
 *  type added later shows up readable rather than hidden. */
const EVENT_LABEL: Record<string, string> = {
  ReportReceived: "New WhatsApp report",
  ReportMerged: "Merged into an existing case",
  IncidentCreated: "Incident opened",
  CaseProposed: "Case ranked and queued",
  CaseApproved: "Approved — sent out",
  CaseReopened: "Re-opened — help did not arrive",
  CaseClosed: "Case closed",
  VolunteerOffered: "Offered to volunteers",
  VolunteerAccepted: "A volunteer accepted",
  VolunteerArrived: "Volunteer arrived",
  VolunteerDone: "Volunteer marked it done",
  VolunteerOnDuty: "Volunteer came on duty",
  VolunteerRegistered: "New volunteer registered",
  DispatchExpired: "Offer expired — re-escalating",
  ResponderLinkSent: "Handed to the official service",
  PersonConfirmedHelp: "Person confirmed help arrived",
  KillSwitchToggled: "Kill switch toggled",
};

/** How long a ping stays on the map. Long enough to notice from across a
 *  room, short enough that a busy minute does not become a solid wash. */
const PING_MS = 7000;

interface Ping {
  key: number;
  x: number;
  y: number;
  severity: "critical" | "elevated" | "normal";
  label: string;
}

interface Tick {
  key: number;
  at: Date;
  text: string;
  caseId: number | null;
}

export default function Live() {
  const { cases, volunteers, admin, source, error, unauthorized, streaming, reload } =
    useDashboard();
  const reduceMotion = useReducedMotion();

  const [pings, setPings] = useState<Ping[]>([]);
  const [ticks, setTicks] = useState<Tick[]>([]);
  const [sinceLoad, setSinceLoad] = useState(0);
  const seq = useRef(0);

  /* ─── The stream. One subscription, independent of the dashboard's, so
         this page keeps pinging even while the queue is being worked. ─── */
  useEffect(() => {
    const close = api.openEventStream({
      onEvent: (payload) => {
        const type = typeof payload.type === "string" ? payload.type : "Event";
        const caseId = Number(payload.case_id);
        const key = (seq.current += 1);

        setSinceLoad((n) => n + 1);
        setTicks((prev) =>
          [
            {
              key,
              at: new Date(),
              text: EVENT_LABEL[type] ?? humanise(type),
              caseId: Number.isFinite(caseId) ? caseId : null,
            },
            ...prev,
          ].slice(0, 40),
        );
      },
    });
    return close;
  }, []);

  /* ─── Turn events into pins. The event carries a case id; the coordinates
         come from the case the dashboard already holds. ───────────────── */
  useEffect(() => {
    const latest = ticks[0];
    if (!latest || latest.caseId == null) return;

    const row = cases.find((c) => c.id === latest.caseId);
    const point = project(row?.incident?.lat, row?.incident?.lng);
    if (!point) return;

    const ping: Ping = {
      key: latest.key,
      x: point.x,
      y: point.y,
      severity: severityOf(row?.priority_score ?? 0),
      label: row?.zone?.name ?? "",
    };
    setPings((prev) => [...prev, ping]);

    const timer = window.setTimeout(
      () => setPings((prev) => prev.filter((p) => p.key !== ping.key)),
      PING_MS,
    );
    return () => window.clearTimeout(timer);
  }, [ticks, cases]);

  /* ─── Standing pins: every live case, not just the ones that just moved ── */
  const live = useMemo(
    () => cases.filter((row) => row.status !== "resolved" && row.status !== "rejected"),
    [cases],
  );
  const critical = useMemo(
    () => live.filter((row) => severityOf(row.priority_score) === "critical"),
    [live],
  );
  const onDuty = volunteers.filter((v) => v.status === "on_duty").length;
  const waiting = live.filter((row) => row.dispatch_status === "none").length;

  if (unauthorized) return <Navigate to="/login" replace />;

  return (
    <AppShell
      admin={admin}
      source={source}
      streaming={streaming}
      openCount={live.length}
      criticalCount={critical.length}
      error={source === "error" ? error : null}
      onRetry={reload}
      fill
    >
      <div className="flex min-h-0 grow flex-col gap-3 p-3 lg:flex-row">
        {/* ─── The map ──────────────────────────────────────────────── */}
        <div className="sz-card relative min-h-[22rem] grow overflow-hidden">
          <MapBase />

          {/* Standing pins: where the open cases are. */}
          {live.map((row) => {
            const point = project(row.incident?.lat, row.incident?.lng);
            if (!point) return null;
            const severity = severityOf(row.priority_score);
            return (
              <span
                key={`pin-${row.id}`}
                className="absolute block h-2 w-2 -translate-x-1/2 -translate-y-1/2 rotate-45 border"
                style={{
                  left: `${point.x}%`,
                  top: `${point.y}%`,
                  borderColor: `var(--color-sz-${short(severity)})`,
                  background: `var(--color-sz-${short(severity)}-fill)`,
                }}
                title={`Case ${row.id}`}
              />
            );
          })}

          {/* Volunteers on duty, so the room can see cover as well as load. */}
          {volunteers
            .filter((v) => v.status === "on_duty")
            .map((v) => {
              const point = project(v.lat, v.lng);
              if (!point) return null;
              return (
                <span
                  key={`vol-${v.id}`}
                  className="absolute block h-1.5 w-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-sz-earth-fill ring-1 ring-sz-earth"
                  style={{ left: `${point.x}%`, top: `${point.y}%` }}
                />
              );
            })}

          {/* Pings: something just happened here. */}
          <AnimatePresence>
            {pings.map((ping) => (
              <motion.span
                key={ping.key}
                className="pointer-events-none absolute block rounded-full border-2"
                style={{
                  left: `${ping.x}%`,
                  top: `${ping.y}%`,
                  borderColor: `var(--color-sz-${short(ping.severity)})`,
                  translateX: "-50%",
                  translateY: "-50%",
                }}
                initial={{ width: 8, height: 8, opacity: 0.9 }}
                animate={
                  reduceMotion
                    ? { width: 36, height: 36, opacity: 0.35 }
                    : { width: [8, 120], height: [8, 120], opacity: [0.9, 0] }
                }
                exit={{ opacity: 0 }}
                transition={{ duration: reduceMotion ? 0.3 : 2.4, ease: "easeOut" }}
              />
            ))}
          </AnimatePresence>

          <div className="absolute top-3 left-3 flex items-center gap-2 rounded-full border border-sz-line bg-sz-panel/90 px-3 py-1.5 backdrop-blur-sm">
            {streaming ? (
              <RadioTower className="h-3.5 w-3.5 text-sz-earth" aria-hidden="true" />
            ) : (
              <Radio className="h-3.5 w-3.5 text-sz-text-3" aria-hidden="true" />
            )}
            <span className="text-[12px] font-medium">
              {streaming ? "Live stream connected" : "Stream offline"}
            </span>
          </div>
        </div>

        {/* ─── The numbers and the ticker ───────────────────────────── */}
        <div className="flex w-full shrink-0 flex-col gap-3 lg:w-80">
          <div className="grid grid-cols-2 gap-3">
            <Stat value={live.length} label="Open cases" />
            <Stat value={critical.length} label="Critical" tone="crit" />
            <Stat value={waiting} label="Not sent yet" tone={waiting ? "elev" : undefined} />
            <Stat value={onDuty} label="Volunteers on duty" tone="earth" />
          </div>

          <div className="sz-card flex min-h-0 grow flex-col overflow-hidden">
            <div className="flex shrink-0 items-center gap-2 border-b border-sz-line px-4 py-3">
              <Activity className="h-4 w-4 text-sz-water" aria-hidden="true" />
              <h2 className="font-semibold">Activity</h2>
              <span className="ml-auto font-mono text-[12px] text-sz-text-3">
                {sinceLoad} since opening
              </span>
            </div>

            <ol className="min-h-0 grow overflow-y-auto">
              <AnimatePresence initial={false}>
                {ticks.map((tick) => (
                  <motion.li
                    key={tick.key}
                    className="flex items-baseline gap-3 border-b border-sz-line-soft px-4 py-2.5 text-[13.5px]"
                    initial={reduceMotion ? false : { opacity: 0, x: -12 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
                  >
                    <span className="font-mono text-[11px] whitespace-nowrap text-sz-text-3">
                      {tick.at.toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                        second: "2-digit",
                      })}
                    </span>
                    <span className="min-w-0">
                      {tick.text}
                      {tick.caseId != null && (
                        <span className="text-sz-text-3"> · case {tick.caseId}</span>
                      )}
                    </span>
                  </motion.li>
                ))}
              </AnimatePresence>

              {ticks.length === 0 && (
                <p className="px-4 py-8 text-center text-[13.5px] text-sz-text-3">
                  {/* Honest, and the right thing to show. A wall display that
                      invents activity to look busy is lying to the room. */}
                  Nothing has happened since this page opened. Every line here is a
                  real event from the backend.
                </p>
              )}
            </ol>
          </div>

          <QuietestFirst cases={live} />
        </div>
      </div>
    </AppShell>
  );
}

function Stat({
  value,
  label,
  tone,
}: {
  value: number;
  label: string;
  tone?: "crit" | "elev" | "earth";
}) {
  const colour = tone ? `text-sz-${tone}` : "text-sz-text";
  return (
    <div className="sz-card px-4 py-3">
      <p className={`font-mono text-[1.75rem] leading-none tabular-nums ${colour}`}>
        {value}
      </p>
      <p className="mt-1.5 text-[12px] text-sz-text-2">{label}</p>
    </div>
  );
}

/** The case that has waited longest without being sent anywhere. On a wall
 *  display this is the one number worth standing up for. */
function QuietestFirst({ cases }: { cases: CaseDetail[] }) {
  const stalest = useMemo(() => {
    const waiting = cases.filter((row) => row.dispatch_status === "none");
    if (waiting.length === 0) return null;
    return waiting.reduce((worst, row) =>
      (row.created_at ?? "") < (worst.created_at ?? "") ? row : worst,
    );
  }, [cases]);

  if (!stalest) {
    return (
      <div className="sz-card shrink-0 px-4 py-3 text-[13px] text-sz-text-2">
        Every open case has been sent to someone.
      </div>
    );
  }

  return (
    <div className="shrink-0 rounded-sm border border-sz-crit/45 bg-sz-crit/8 px-4 py-3">
      <p className="text-[12px] text-sz-text-2">Waiting longest, nothing sent</p>
      <p className="mt-1 font-semibold">
        Case {stalest.id}
        {stalest.zone?.name ? ` · ${stalest.zone.name}` : ""}
      </p>
      <p className="mt-0.5 text-[13px] text-sz-crit">
        {timeAgo(stalest.created_at)} with no volunteer and no handoff.
      </p>
    </div>
  );
}

function short(severity: string) {
  return severity === "critical" ? "crit" : severity === "elevated" ? "elev" : "norm";
}

function humanise(type: string) {
  return type.replace(/([a-z])([A-Z])/g, "$1 $2").replace(/^./, (c) => c.toUpperCase());
}
