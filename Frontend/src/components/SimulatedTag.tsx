import { cn } from "../lib/utils";

/**
 * The provenance marker.
 *
 * AGENTS.md section 2.2 makes this a product requirement, not a footnote:
 * anything simulated is labelled simulated *in the UI*. Demo volunteers on
 * team phones, seeded vehicles, an area centre standing in for a real pin.
 *
 * Always hatch AND a word. The hatch alone would be unreadable to anyone who
 * cannot pick it out, and "simulated" is too important to leave in texture.
 */
export function SimulatedTag({
  children = "Simulated",
  className,
  title,
}: {
  children?: string;
  className?: string;
  title?: string;
}) {
  return (
    <span
      title={title}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-sz-line bg-sz-panel px-2 py-0.5 text-[11px] whitespace-nowrap text-sz-text-2",
        className,
      )}
    >
      <span
        aria-hidden="true"
        className="sz-hatch block h-2.5 w-2.5 shrink-0 border border-current text-sz-text-3"
      />
      {children}
    </span>
  );
}

/** The same hatch as a bare swatch, for map pins and table cells where the
 *  word sits next to it rather than inside it. */
export function SimulatedSwatch({ className }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "sz-hatch block h-3 w-3 shrink-0 border border-current text-sz-norm",
        className,
      )}
    />
  );
}
