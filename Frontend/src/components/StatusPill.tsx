import type { ReactNode } from "react";

import { cn } from "../lib/utils";

/**
 * One pill, one meaning. The tone classes come from severity.ts so that no
 * component picks its own colour — every colour in this app resolves back to
 * a severity band or a lifecycle state.
 */
export function StatusPill({
  children,
  tone,
  className,
  dot = false,
}: {
  children: ReactNode;
  /** A class triple from dispatchTone(), offerTone() or SEVERITY_RING. */
  tone: string;
  className?: string;
  dot?: boolean;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] leading-tight font-medium whitespace-nowrap",
        tone,
        className,
      )}
    >
      {dot && <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-current" />}
      {children}
    </span>
  );
}
