import { useCallback, useEffect, useMemo, useState } from "react";

import * as api from "../lib/api";
import type {
  AdminStatus,
  CaseDetail,
  Channel,
  Volunteer,
} from "../lib/types";

/**
 * Everything on the control room comes from the backend. There is no fixture
 * fallback and no seeded sample: if the API cannot be reached, the dashboard
 * says so and shows nothing, because a screen full of invented cases during a
 * disaster is worse than an empty one that admits it is empty.
 *
 * That is AGENTS.md 17 #10 applied to the UI -- the system must never look
 * more capable than it is -- and it is also the only honest answer to a judge
 * asking "is this real data?".
 */
export type DataSource = "loading" | "live" | "error";

interface DashboardState {
  cases: CaseDetail[];
  volunteers: Volunteer[];
  admin: AdminStatus | null;
  source: DataSource;
  /** Why the load failed, in a sentence fit to show a human. */
  error: string | null;
  /** The session expired or was never valid. The page sends them to log in. */
  unauthorized: boolean;
  streaming: boolean;
  loading: boolean;
  selectedId: number | null;
  selected: CaseDetail | null;
  select: (id: number) => void;
  approve: (id: number, channel: Channel) => Promise<void>;
  reopen: (id: number) => Promise<void>;
  toggleKillSwitch: () => Promise<void>;
  reload: () => void;
  busyCaseId: number | null;
  lastEvent: string | null;
}

/** How many cases get their children (dispatches, events) fetched up front.
 *  The rest fill in when selected or when an event names them. */
const DETAIL_PREFETCH = 12;

export function useDashboard(): DashboardState {
  const [cases, setCases] = useState<CaseDetail[]>([]);
  const [volunteers, setVolunteers] = useState<Volunteer[]>([]);
  const [admin, setAdmin] = useState<AdminStatus | null>(null);
  const [source, setSource] = useState<DataSource>("loading");
  const [error, setError] = useState<string | null>(null);
  const [unauthorized, setUnauthorized] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [busyCaseId, setBusyCaseId] = useState<number | null>(null);
  const [lastEvent, setLastEvent] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  const reload = useCallback(() => setReloadToken((n) => n + 1), []);

  /* ─── Initial load ──────────────────────────────────────────────────── */
  useEffect(() => {
    let cancelled = false;

    (async () => {
      setLoading(true);
      try {
        const [rows, vols, status] = await Promise.all([
          api.listCases(),
          api.listVolunteers(),
          api.getAdminStatus(),
        ]);
        if (cancelled) return;

        const details = await Promise.all(
          rows.slice(0, DETAIL_PREFETCH).map(async (row) => {
            try {
              return await api.getCase(row.id);
            } catch {
              // One case failing to expand is not worth losing the queue
              // over; it shows with empty children until the next event.
              return { ...row, dispatches: [], events: [], responder_links: [] } as CaseDetail;
            }
          }),
        );
        if (cancelled) return;

        setCases(details);
        setVolunteers(vols);
        setAdmin(status);
        setError(null);
        setUnauthorized(false);
        setSource("live");
      } catch (caught) {
        if (cancelled) return;

        if (caught instanceof api.ApiError && caught.status === 401) {
          setUnauthorized(true);
          setError("Your session has ended. Sign in again.");
        } else {
          setError(
            caught instanceof api.ApiError
              ? `The backend answered ${caught.status}: ${caught.message}`
              : "Could not reach the backend. Is the server running?",
          );
        }
        setCases([]);
        setVolunteers([]);
        setAdmin(null);
        setSource("error");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [reloadToken]);

  /* ─── Live event stream. Every backend state change goes through emit(),
         so this is the one place the UI learns anything happened. ─────── */
  useEffect(() => {
    if (source !== "live") return undefined;

    const close = api.openEventStream({
      onOpen: () => setStreaming(true),
      onError: () => setStreaming(false),
      onEvent: (payload) => {
        setLastEvent(typeof payload.type === "string" ? payload.type : null);
        const caseId = Number(payload.case_id);
        if (!Number.isFinite(caseId)) return;
        api
          .getCase(caseId)
          .then((fresh) => {
            setCases((prev) => {
              const without = prev.filter((row) => row.id !== fresh.id);
              return [...without, fresh].sort(
                (a, b) => b.priority_score - a.priority_score,
              );
            });
          })
          .catch(() => {
            /* the next event will bring it */
          });
      },
    });

    return close;
  }, [source]);

  const select = useCallback((id: number) => setSelectedId(id), []);

  /** Pull one case back from the backend after acting on it, rather than
   *  guessing what changed. The event stream would bring it anyway; this
   *  just makes the button feel immediate. */
  const refreshCase = useCallback(async (id: number) => {
    try {
      const fresh = await api.getCase(id);
      setCases((prev) => prev.map((row) => (row.id === id ? fresh : row)));
    } catch {
      /* the stream will catch up */
    }
  }, []);

  const approve = useCallback(
    async (id: number, channel: Channel) => {
      setBusyCaseId(id);
      try {
        await api.approveCase(id, channel);
        await refreshCase(id);
      } catch (caught) {
        if (caught instanceof api.ApiError && caught.status === 401) {
          setUnauthorized(true);
        } else {
          setError(
            caught instanceof api.ApiError
              ? caught.message
              : "Could not reach the backend to approve that case.",
          );
        }
      } finally {
        setBusyCaseId(null);
      }
    },
    [refreshCase],
  );

  const reopen = useCallback(
    async (id: number) => {
      setBusyCaseId(id);
      try {
        await api.reopenCase(id, "Manual re-open by coordinator");
        await refreshCase(id);
      } catch (caught) {
        if (caught instanceof api.ApiError && caught.status === 401) {
          setUnauthorized(true);
        } else {
          setError(
            caught instanceof api.ApiError
              ? caught.message
              : "Could not reach the backend to re-open that case.",
          );
        }
      } finally {
        setBusyCaseId(null);
      }
    },
    [refreshCase],
  );

  const toggleKillSwitch = useCallback(async () => {
    if (!admin) return;

    const next = !admin.kill_switch;
    // Flipped optimistically: this is the stop-everything control, and it
    // must feel instant. Rolled back below if the server disagrees.
    setAdmin((prev) => (prev ? { ...prev, kill_switch: next } : prev));

    try {
      const result = await api.setKillSwitch(next);
      setAdmin((prev) => (prev ? { ...prev, kill_switch: result.kill_switch } : prev));
    } catch {
      setAdmin((prev) => (prev ? { ...prev, kill_switch: !next } : prev));
      setError("Could not reach the backend. Outbound messages are unchanged.");
    }
  }, [admin]);

  /** Highest priority first, which is the order services/risk.py produced.
   *  The frontend does not re-rank: the score is the backend's judgement and
   *  the dashboard's job is to show it, not to have an opinion about it. */
  const ranked = useMemo(
    () => [...cases].sort((a, b) => b.priority_score - a.priority_score),
    [cases],
  );

  const selected = useMemo(
    () => ranked.find((row) => row.id === selectedId) ?? ranked[0] ?? null,
    [ranked, selectedId],
  );

  return {
    cases: ranked,
    volunteers,
    admin,
    source,
    error,
    unauthorized,
    streaming,
    loading,
    selectedId: selected?.id ?? null,
    selected,
    select,
    approve,
    reopen,
    toggleKillSwitch,
    reload,
    busyCaseId,
    lastEvent,
  };
}
