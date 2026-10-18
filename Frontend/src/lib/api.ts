/**
 * The API surface, one function per existing endpoint. Nothing here invents a
 * route: every path below is already defined in Backend/routes.
 *
 * Same origin by default — main.py serves the built SPA, so in production the
 * frontend and the API share a host. Point VITE_API_BASE at the backend when
 * running `npm run dev` against a separately running uvicorn.
 */

import type {
  AdminStatus,
  ApproveResult,
  CaseDetail,
  CaseRow,
  Channel,
  DispatchRow,
  RegistrationResult,
  RegistrationStatus,
  ResponderView,
  Volunteer,
} from "./types";

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: init?.body ? { "Content-Type": "application/json" } : undefined,
    // The session is an HttpOnly cookie. Same-origin requests send it
    // anyway; this is here so that pointing VITE_API_BASE at another host
    // during development does not silently sign you out.
    credentials: "include",
    ...init,
  });

  if (!response.ok) {
    // FastAPI puts the useful part in `detail`; fall back to the status text
    // so an HTML error page from a proxy does not surface as "[object Object]".
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body?.detail) detail = body.detail;
    } catch {
      /* not JSON — keep the status text */
    }
    throw new ApiError(response.status, detail);
  }

  return (await response.json()) as T;
}

/* ─── Session ─────────────────────────────────────────────────────────── */

/** Sign in. The server replies with an HttpOnly cookie, which JavaScript
 *  cannot read -- so there is no token to store and none to leak. */
export const login = (email: string, password: string) =>
  request<{ email: string; expires_in: number }>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });

export const logout = () =>
  request<{ signed_out: boolean }>("/api/auth/logout", { method: "POST" });

/** Who is signed in. Always 200, so a signed-out first visit is not an error
 *  in the console. `configured` is false when the server has no admin
 *  credentials set at all, which is worth telling the operator plainly. */
export const me = () =>
  request<{ authenticated: boolean; email: string | null; configured: boolean }>(
    "/api/auth/me",
  );

/** Where to message SafeZone. Served from the backend's own
 *  WHATSAPP_PUBLIC_NUMBER, so the button, the QR and the number people
 *  actually message can never drift apart, and changing it needs no rebuild. */
export const getWhatsapp = () =>
  request<{
    configured: boolean;
    number: string | null;
    display: string | null;
    url: string | null;
  }>("/api/whatsapp");

/* ─── Areas ───────────────────────────────────────────────────────────── */

/** The real zone list from the database. Public: the registration form on
 *  the public page needs it, and that form is open to anyone. */
export const listZones = () =>
  request<Array<{ id: string; name: string; lat: number | null; lng: number | null }>>(
    "/api/zones",
  );

/* ─── Coordinator ─────────────────────────────────────────────────────── */

export const listCases = () => request<CaseRow[]>("/api/cases");

export const getCase = (caseId: number) =>
  request<CaseDetail>(`/api/cases/${caseId}`);

export const listDispatches = (caseId: number) =>
  request<DispatchRow[]>(`/api/cases/${caseId}/dispatches`);

/** Approve means "send this out". The channel decides whether volunteers are
 *  offered it, a responder link is minted, or both. */
export const approveCase = (
  caseId: number,
  channel: Channel,
  targetLabel?: string,
) =>
  request<ApproveResult>(`/api/proposals/${caseId}/approve`, {
    method: "POST",
    body: JSON.stringify({ channel, target_label: targetLabel ?? null }),
  });

export const createResponderLink = (caseId: number, targetLabel?: string) =>
  request<{
    token: string;
    url: string;
    expires_at: string;
    target_label: string | null;
  }>(`/api/cases/${caseId}/responderlink`, {
    method: "POST",
    body: JSON.stringify({ target_label: targetLabel ?? null }),
  });

export const reopenCase = (caseId: number, reason: string, reoffer = true) =>
  request<{ case_id: number; reopened: boolean; reason: string; case: CaseRow }>(
    `/api/cases/${caseId}/reopen`,
    { method: "POST", body: JSON.stringify({ reason, reoffer }) },
  );

export const listVolunteers = () => request<Volunteer[]>("/api/volunteers");

/* ─── Public responder handoff ────────────────────────────────────────── */

export const getResponderView = (token: string) =>
  request<ResponderView>(`/api/r/${encodeURIComponent(token)}`);

/* ─── Admin switches ──────────────────────────────────────────────────── */

export const getAdminStatus = () => request<AdminStatus>("/api/admin/status");

/** Omit `enabled` to toggle. The switch is read at call time inside
 *  services/whatsapp, so this stops the next outbound message immediately. */
export const setKillSwitch = (enabled?: boolean) =>
  request<{ kill_switch: boolean }>("/api/admin/killswitch", {
    method: "POST",
    body: JSON.stringify({ enabled: enabled ?? null }),
  });

/* ─── Registration (the optional alerts path) ─────────────────────────── */

export const register = (
  firstName: string,
  zoneId: string | null,
  wantsAlerts = true,
) =>
  request<RegistrationResult>("/api/register", {
    method: "POST",
    body: JSON.stringify({
      first_name: firstName,
      zone_id: zoneId,
      wants_alerts: wantsAlerts,
    }),
  });

export const registrationStatus = (code: string) =>
  request<RegistrationStatus>(`/api/register/${encodeURIComponent(code)}`);

/* ─── Live event stream ───────────────────────────────────────────────── */

export interface StreamHandlers {
  onEvent: (payload: { type: string; [key: string]: unknown }) => void;
  onOpen?: () => void;
  onError?: () => void;
}

/**
 * Subscribe to /events. One subscriber per open tab, as routes/events.py
 * expects. Returns a cleanup function — call it on unmount so the backend can
 * drop the queue rather than keep filling it for a tab that has gone.
 */
export function openEventStream({ onEvent, onOpen, onError }: StreamHandlers): () => void {
  if (typeof EventSource === "undefined") return () => {};

  const source = new EventSource(`${BASE}/events`);

  source.onopen = () => onOpen?.();
  source.onerror = () => onError?.();
  source.onmessage = (message) => {
    if (!message.data) return;
    try {
      onEvent(JSON.parse(message.data) as { type: string });
    } catch {
      /* A dropped or partial frame is an inconvenience, not data loss — the
         timeline rebuilds from the events table. */
    }
  };

  return () => source.close();
}
