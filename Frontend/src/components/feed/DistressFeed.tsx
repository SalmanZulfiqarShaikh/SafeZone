import { AnimatePresence } from "framer-motion";

import { BRAND } from "../../lib/brand";
import type { CaseDetail } from "../../lib/types";
import { DistressCard } from "./DistressCard";

export function DistressFeed({
  cases,
  selectedId,
  busyCaseId,
  onSelect,
  onDispatch,
  loading,
}: {
  cases: CaseDetail[];
  selectedId: number | null;
  busyCaseId: number | null;
  onSelect: (id: number) => void;
  onDispatch: (id: number) => void;
  loading?: boolean;
}) {
  return (
    <section
      aria-labelledby="feed-heading"
      className="flex min-h-0 grow flex-col"
    >
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2 border-b border-sz-line px-4 py-3 sm:px-5">
        <h2 id="feed-heading" className="flex items-baseline gap-2 font-semibold">
          Incoming
          {cases.length > 0 && (
            <span className="font-mono text-[12px] font-normal text-sz-text-3">
              {cases.length}
            </span>
          )}
        </h2>
      </div>

      {cases.length === 0 ? (
        <div className="px-4 py-8 sm:px-5">
          <p className="text-sz-text-2">
            {loading
              ? "Reading the queue…"
              : "Nothing open. New reports appear here as they arrive."}
          </p>
        </div>
      ) : (
        <ul className="sz-scroll flex min-h-0 grow flex-col gap-2.5 overflow-y-auto px-3 py-3 sm:px-4">
          <AnimatePresence initial={false}>
            {cases.map((row) => (
              <DistressCard
                key={row.id}
                row={row}
                active={row.id === selectedId}
                busy={busyCaseId === row.id}
                onSelect={() => onSelect(row.id)}
                onDispatch={() => onDispatch(row.id)}
              />
            ))}
          </AnimatePresence>
        </ul>
      )}

      <p className="border-t border-sz-line px-4 py-2.5 text-[12px] text-sz-text-3 sm:px-5">
        Anyone can message {BRAND} with no account. Registration is only for area alerts.
      </p>
    </section>
  );
}
