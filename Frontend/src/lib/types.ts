/**
 * Types mirroring the FastAPI payloads exactly as the backend returns them.
 *
 * Sources, so these stay honest when the backend moves:
 *   routes/cases.py       _case_view, _dispatch_rows, _event_rows, approve
 *   routes/responder.py   responder_view
 *   routes/volunteers.py  list_volunteers
 *   routes/admin.py       status, killswitch
 *   routes/register.py    register, registration_status
 *   data/schema.sql       column names and the status value lists
 *
 * Nullable columns are `| null` rather than optional: Supabase returns the key
 * with a null value, and treating that as "missing" hides real data problems.
 */

export type Category =
  | "flood"
  | "fire"
  | "medical"
  | "trapped"
  | "structural"
  | "other";

export type CaseStatus = "proposed" | "approved" | "rejected" | "resolved";

export type DispatchStatus =
  | "none"
  | "offered"
  | "accepted"
  | "on_way"
  | "arrived"
  | "confirmed"
  | "closed"
  | "reopened";

export type OfferStatus =
  | "offered"
  | "accepted"
  | "on_way"
  | "arrived"
  | "done"
  | "declined"
  | "expired";

export type VolunteerStatus = "off_duty" | "on_duty" | "busy";

export type RiskLevel = "normal" | "elevated" | "critical";

export type IncidentStatus = "open" | "active" | "resolved" | "closed";

/** How we came by an incident's coordinates. A responder only ever sees `pin`. */
export type LocationSource = "pin" | "area" | null;

/** AGENTS.md section 11: Approve means "send this out", and takes a channel. */
export type Channel = "volunteers" | "responder" | "both";

export interface Zone {
  id: string;
  name: string;
  risk_level: RiskLevel | null;
  lat: number | null;
  lng: number | null;
  volunteer_group?: string | null;
}

/** `person_vuln` is JSONB and intentionally open-ended; these keys are the
 *  ones services/intake.py fills. Unanswered means unknown, never false. */
export interface PersonVuln {
  elderly?: boolean;
  alone?: boolean;
  cannot_move?: boolean;
  children?: boolean;
  floor?: string;
  [key: string]: unknown;
}

export interface PersonBrief {
  id: number;
  first_name: string | null;
  person_vuln: PersonVuln;
}

export interface Incident {
  id: number;
  category: Category;
  lat: number | null;
  lng: number | null;
  zone_id: string | null;
  location_known: boolean;
  location_source?: LocationSource;
  report_count: number;
  confidence: number;
  urgency: number;
  priority_score: number;
  status: IncidentStatus;
  dispatch_status: DispatchStatus;
  reopened: boolean;
  reopen_reason: string | null;
  first_report_at: string;
  last_update_at: string;
}

/** A protocol node as stored in `cases.protocol_path` (JSONB array). The
 *  backend has written both shapes at different points; normalise with
 *  `protocolLabels()` rather than reading it directly. */
export type ProtocolNode = string | { id?: string; label?: string; node?: string };

export interface VolunteerBrief {
  id: number;
  name: string | null;
  /** Masked by core.phone.mask() — last four digits only. */
  phone_masked: string;
  is_demo: boolean;
}

export interface DispatchRow {
  id: number;
  case_id: number;
  volunteer_id: number;
  ring: number;
  status: OfferStatus;
  offered_at: string | null;
  accepted_at: string | null;
  arrived_at: string | null;
  done_at: string | null;
  volunteer: VolunteerBrief;
}

export interface EventRow {
  id: number;
  type: string;
  case_id: number | null;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface ResponderLinkRow {
  token: string;
  target_label: string | null;
  created_at: string;
  expires_at: string;
}

export interface CaseRow {
  id: number;
  incident_id: number | null;
  person_id: number | null;
  priority_score: number;
  reason: string | null;
  vuln_summary: string | null;
  protocol_path: ProtocolNode[];
  status: CaseStatus;
  dispatch_status: DispatchStatus;
  reopened: boolean;
  reopen_reason: string | null;
  created_at: string;
  closed_at: string | null;
  incident: Incident | null;
  person: PersonBrief | null;
  zone: Zone | null;
  dispatch_count: number;
}

/**
 * The operator-facing lifecycle, as shown on each message card.
 *
 * These are not new state: they are a reading of `status`, `dispatch_status`
 * and `priority_score`, which is why lifecycle.ts derives them rather than
 * storing them. See `stageOf()`.
 */
export type Stage = "received" | "triaging" | "dispatched" | "resolved";

export interface CaseDetail extends CaseRow {
  responder_links: ResponderLinkRow[];
  dispatches: DispatchRow[];
  events: EventRow[];

  /** Frontend-only. Set while a simulated SOS is walking through triage, so
   *  the rail can show stages the backend passes through faster than a person
   *  can watch. Absent on anything that came from the API. */
  ui_stage?: Stage;

  /** Frontend-only. True for a case injected by the Simulate SOS control, so
   *  every surface showing it can carry the simulated marker — the same rule
   *  AGENTS.md section 2.2 applies to demo volunteers and seeded vehicles. */
  simulated?: boolean;
}

export interface Volunteer {
  id: number;
  name: string | null;
  /** Unmasked here on purpose: the coordinator calls these phones when a case
   *  stalls, and the request runs server-side with the service key. */
  phone: string;
  status: VolunteerStatus;
  zone_ids: string[];
  capabilities: string[];
  lat: number | null;
  lng: number | null;
  is_demo: boolean;
}

export interface ResponderView {
  token: string;
  target_label: string | null;
  expires_at: string;
  case: {
    id: number;
    status: CaseStatus;
    dispatch_status: DispatchStatus;
    priority_score: number;
    reason: string | null;
    vuln_summary: string | null;
    protocol_path: ProtocolNode[];
    reopened: boolean;
    reopen_reason: string | null;
    created_at: string;
  };
  incident: {
    id: number;
    category: Category;
    urgency: number;
    confidence: number;
    location_known: boolean;
    lat: number | null;
    lng: number | null;
    area: string | null;
    status: IncidentStatus;
    dispatch_status: DispatchStatus;
    created_at: string;
    report_count: number;
  } | null;
  person: { first_name: string | null } | null;
  zone: Pick<Zone, "id" | "name" | "risk_level"> | null;
  /** `number` is null until a human fills it in config from an official
   *  source. AGENTS.md section 2.1.8: never hardcoded from memory. */
  call: { label: string; number: string | null };
}

export interface AdminStatus {
  kill_switch: boolean;
  mock_mode: boolean;
  demo_mode: boolean;
  allowlist_only: boolean;
  /** Human-readable problems from config.startup_report(). */
  problems: string[];
}

export interface ApproveResult {
  case_id: number;
  status: "approved";
  channel: Channel;
  offered?: Array<{ id: number; name: string | null; phone_masked: string }>;
  dispatch_warning?: string;
  responder_link?: {
    token: string;
    url: string;
    expires_at: string;
    target_label: string | null;
  };
  official?: {
    required: boolean;
    label: string;
    service: string | null;
    target_label: string | null;
  };
  official_forced?: string;
}

export interface RegistrationResult {
  code: string;
  expires_at: string;
  whatsapp_url: string | null;
  instructions: string;
}

export interface RegistrationStatus {
  found: boolean;
  verified: boolean;
  first_name?: string | null;
  zone_id?: string | null;
}

/* ─── Frontend-only ────────────────────────────────────────────────────────
   There is no resources table in schema.sql, and AGENTS.md section 2.2
   requires seeded vehicles to be labelled simulated in the UI. These shapes
   exist so the allocation bar has something to render, and everything built
   from them carries the simulated marker. */

export type ResourceKind = "shelter" | "medical" | "vehicle" | "relief";

export interface ResourceStat {
  kind: ResourceKind;
  label: string;
  available: number;
  deployed: number;
  /** Always true in this prototype. Kept as a field so that the day any of
   *  these become real, the marker disappears on its own. */
  simulated: boolean;
}
