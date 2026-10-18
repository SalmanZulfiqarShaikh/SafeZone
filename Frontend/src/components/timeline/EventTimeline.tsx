import { useId, useState } from "react";

import { clock, eventLabel } from "../../lib/format";
import type { EventRow } from "../../lib/types";
import { cn } from "../../lib/utils";

/**
 * The replay slider. Every state change in the backend goes through emit(),
 * so this is the whole life of a case rather than a UI-side animation log —
 * if a step is missing here, it did not happen.
 *
 * Events arrive newest-first from the API; this reads oldest-first because
 * the loop reads forwards.
 */
export function EventTimeline({ events, caseId }: { events: EventRow[]; caseId: number }) {
  const ordered = [...events].sort(
    (a, b) => Date.parse(a.created_at) - Date.parse(b.created_at),
  );
  const lastIndex = Math.max(0, ordered.length - 1);
  const sliderId = useId();

  // Held as a distance back from the newest event rather than an absolute
  // index. At zero the scrubber follows the live edge on its own as events
  // land, with no effect needed to chase the end of the list. Dashboard keys
  // this component by case id, so opening another case starts at the edge.
  const [offset, setOffset] = useState(0);
  const index = Math.max(0, lastIndex - Math.min(offset, lastIndex));

  const current = ordered[index];
  const atLiveEdge = offset === 0;

  if (ordered.length === 0) {
    return (
      <section className="px-4 py-3.5">
        <h2 className="font-semibold">Timeline</h2>
        <p className="mt-1.5 text-[12px] text-sz-text-3">
          No events yet for case {caseId}.
        </p>
      </section>
    );
  }

  return (
    <section
      aria-labelledby="timeline-heading"
      className="px-4 py-3.5"
    >
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h2 id="timeline-heading" className="font-semibold">
          Timeline, case {caseId}
        </h2>
        <p className="text-[12px] text-sz-text-3">
          {ordered.length} events{atLiveEdge ? ", at the live edge" : ", replaying"}
        </p>
      </div>

      <div className="relative mb-1 h-2">
        {ordered.map((event, i) => (
          <span
            key={event.id}
            aria-hidden="true"
            className={cn(
              "absolute top-0 h-2 w-0.5 -translate-x-1/2 rounded-full",
              i <= index ? "bg-sz-water" : "bg-sz-line",
            )}
            style={{
              left: `${ordered.length === 1 ? 50 : (i / (ordered.length - 1)) * 100}%`,
            }}
          />
        ))}
      </div>

      <label htmlFor={sliderId} className="sr-only">
        Replay position in the timeline for case {caseId}
      </label>
      <input
        id={sliderId}
        type="range"
        min={0}
        max={lastIndex}
        step={1}
        value={index}
        onChange={(event) => setOffset(lastIndex - Number(event.target.value))}
        className="h-4 w-full cursor-pointer accent-sz-water"
        aria-valuetext={current ? `${eventLabel(current.type)} at ${clock(current.created_at)}` : undefined}
      />

      <div className="mt-2.5 flex flex-wrap items-baseline gap-x-4 gap-y-1">
        {ordered.map((event, i) => (
          <span key={event.id} className="flex items-baseline gap-1.5">
            <span className="font-mono text-[11px] text-sz-text-3">
              {clock(event.created_at)}
            </span>
            <span
              className={cn(
                "text-[12px]",
                i === index ? "font-medium text-sz-water" : i < index ? "text-sz-text-2" : "text-sz-text-3/60",
              )}
            >
              {eventLabel(event.type)}
            </span>
          </span>
        ))}
      </div>
    </section>
  );
}
