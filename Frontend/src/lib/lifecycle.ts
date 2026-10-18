/**
 * The four stages an SOS passes through, read off the real columns.
 *
 * Nothing here is new state. The backend already records everything this
 * needs — `cases.status`, `cases.dispatch_status`, `cases.priority_score` —
 * and every transition between them goes through `emit()`. The rail on a
 * message card is a reading of those columns, so it cannot drift away from
 * what actually happened: if a step shows as done here, there is an event row
 * behind it.
 *
 * Triage covers both halves of the work — extracting the report and scoring
 * it — because from a dispatcher's side they are one wait: the case is in
 * triage until there is something to send out.
 *
 * The one exception is `ui_stage`, set while a simulated SOS walks through
 * triage. Real triage happens faster than a person can watch, so the
 * simulation slows it down to make the flow visible. Those cases carry the
 * simulated marker everywhere they appear.
 */

import type { CaseDetail, Stage } from "./types";

export const STAGES: readonly Stage[] = [
  "received",
  "triaging",
  "dispatched",
  "resolved",
] as const;

export const STAGE_LABEL: Record<Stage, string> = {
  received: "WhatsApp received",
  triaging: "Triaging priority",
  dispatched: "Resource dispatched",
  resolved: "Status resolved",
};

/** Shorter forms, for anywhere there is no room for the full label. */
export const STAGE_SHORT: Record<Stage, string> = {
  received: "Received",
  triaging: "Triaging",
  dispatched: "Dispatched",
  resolved: "Resolved",
};

const DISPATCHED: ReadonlySet<string> = new Set([
  "offered",
  "accepted",
  "on_way",
  "arrived",
]);

const FINISHED: ReadonlySet<string> = new Set(["confirmed", "closed"]);

export function stageOf(row: CaseDetail): Stage {
  if (row.ui_stage) return row.ui_stage;
  if (row.status === "resolved" || FINISHED.has(row.dispatch_status)) return "resolved";
  if (DISPATCHED.has(row.dispatch_status)) return "dispatched";
  if (row.status === "proposed" || row.status === "approved") return "triaging";
  return "received";
}

export function stageIndex(stage: Stage): number {
  return STAGES.indexOf(stage);
}

/** A re-opened case is back in the queue, so the rail must not read as done.
 *  AGENTS.md section 4: a `2` to "Did help reach you?" puts it back on top. */
export function isStageComplete(row: CaseDetail, stage: Stage): boolean {
  if (row.reopened && stage === "resolved") return false;
  return stageIndex(stage) < stageIndex(stageOf(row));
}

/** Whether this case is waiting on the dispatcher rather than on the field.
 *  These are the ones the Dispatch control appears on. */
export function awaitingDispatch(row: CaseDetail): boolean {
  if (stageOf(row) !== "triaging" && !row.reopened) return false;
  // Still extracting: there is no priority to dispatch against yet.
  if (row.priority_score <= 0) return false;
  if (row.dispatch_status !== "none" && !row.reopened) return false;
  const incident = row.incident;
  // No pin, nothing to dispatch to. The bot keeps asking for a location.
  return Boolean(incident && (incident.location_source === "pin" || incident.location_known));
}
