import { motion } from "framer-motion";
import { Send } from "lucide-react";

import { score as fmtScore, timeAgo } from "../../lib/format";
import { awaitingDispatch } from "../../lib/lifecycle";
import {
  CATEGORY_ELEMENT,
  CATEGORY_LABEL,
  DISPATCH_LABEL,
  dispatchTone,
  SEVERITY_BG,
  SEVERITY_TEXT,
  severityOf,
} from "../../lib/severity";
import type { CaseDetail } from "../../lib/types";
import { cn } from "../../lib/utils";
import { StatusPill } from "../StatusPill";
import { LifecycleRail } from "./LifecycleRail";

export function DistressCard({
  row,
  active,
  busy,
  onSelect,
  onDispatch,
}: {
  row: CaseDetail;
  active: boolean;
  busy: boolean;
  onSelect: () => void;
  onDispatch: () => void;
}) {
  const severity = severityOf(row.priority_score);
  const incident = row.incident;
  const category = incident ? CATEGORY_LABEL[incident.category] : "Unknown";
  const noPin = incident ? !(incident.location_source === "pin" || incident.location_known) : true;
  const canDispatch = awaitingDispatch(row);

  return (
    <motion.li
      layout="position"
      initial={{ opacity: 0, y: -12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
      className={cn(
        // shrink-0 matters: this is a flex child of a scrolling column, and
        // flex items shrink by default — without it every card is squashed to
        // a sliver with its text clipped instead of the list scrolling.
        "sz-card shrink-0 overflow-hidden transition-all",
        active
          ? "border-sz-water/60 ring-1 ring-sz-water/25"
          : "hover:-translate-y-px hover:border-sz-water/40",
      )}
    >
      <button
        type="button"
        onClick={onSelect}
        aria-current={active ? "true" : undefined}
        className={cn(
          "flex w-full cursor-pointer gap-3 px-3 pt-3 pb-2.5 text-left transition-colors",
          active ? "bg-sz-raised" : "hover:bg-sz-raised",
        )}
      >
        {/* On every row, so it reads as a severity column rather than a
            decorative accent on whichever one is selected. */}
        <span
          aria-hidden="true"
          className={cn("w-[3px] shrink-0 self-stretch rounded-full", SEVERITY_BG[severity])}
        />

        <span className="flex min-w-0 grow flex-col gap-2">
          <span className="flex items-baseline justify-between gap-3">
            <span className="flex min-w-0 items-baseline gap-2.5">
              <span className={cn("font-mono text-[13px] font-medium", SEVERITY_TEXT[severity])}>
                {row.priority_score > 0 ? fmtScore(row.priority_score) : "—"}
              </span>
              <span
                className={cn(
                  "font-medium whitespace-nowrap",
                  incident ? CATEGORY_ELEMENT[incident.category] : "text-sz-text",
                )}
              >
                {category}
              </span>
            </span>
            <span className="font-mono text-[11px] whitespace-nowrap text-sz-text-2">
              {timeAgo(incident?.first_report_at ?? row.created_at)}
            </span>
          </span>

          <span className="flex min-w-0 items-baseline gap-2 text-[12px] text-sz-text-2">
            <span className="truncate">{row.zone?.name ?? "Area unknown"}</span>
            <span className="text-sz-line">·</span>
            <span className="whitespace-nowrap">
              {incident?.report_count ?? 1} {incident?.report_count === 1 ? "report" : "reports"}
            </span>
          </span>

          {row.vuln_summary && (
            <span className="line-clamp-2 text-[12px] text-sz-text-3">{row.vuln_summary}</span>
          )}

          <LifecycleRail row={row} />

          <span className="flex flex-wrap items-center gap-1.5 pt-0.5">
            <span className="font-mono text-[11px] text-sz-text-3">Case {row.id}</span>
            <StatusPill
              tone={dispatchTone(row.dispatch_status)}
              dot={row.dispatch_status === "accepted" || row.dispatch_status === "on_way"}
            >
              {DISPATCH_LABEL[row.dispatch_status]}
            </StatusPill>
            {noPin && (
              <StatusPill tone="border-sz-elev/45 bg-sz-elev/12 text-sz-elev">No pin yet</StatusPill>
            )}
            {row.reopened && (
              <StatusPill tone="border-sz-elev/45 bg-sz-elev/12 text-sz-elev">Re-opened</StatusPill>
            )}
          </span>
        </span>
      </button>

      {/* One-click dispatch, on the message itself. Appears only once triage
          has produced a score and there is a pin to send someone to. */}
      {canDispatch && (
        <div className="border-t border-sz-line-soft bg-sz-raised px-3 py-2.5">
          <button
            type="button"
            disabled={busy}
            onClick={onDispatch}
            className="inline-flex min-h-9 cursor-pointer items-center gap-2 rounded-sm border border-sz-water/50 bg-sz-water/10 px-3 font-medium text-sz-water transition-colors hover:bg-sz-water/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Send className="h-3.5 w-3.5" aria-hidden="true" />
            {busy ? "Dispatching" : "Dispatch resource"}
          </button>
        </div>
      )}
    </motion.li>
  );
}
