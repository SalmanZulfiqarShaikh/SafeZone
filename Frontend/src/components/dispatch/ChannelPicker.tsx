import type { Channel } from "../../lib/types";
import { cn } from "../../lib/utils";

const OPTIONS: Array<{ id: Channel; label: string; hint: string }> = [
  {
    id: "volunteers",
    label: "Nearby volunteers",
    hint: "Offers the case to the three nearest on-duty volunteers. First ACCEPT wins.",
  },
  {
    id: "responder",
    label: "Responder link",
    hint: "Mints a read-only handoff page you send to a desk, a group or a number.",
  },
  { id: "both", label: "Both", hint: "Offers it to volunteers and mints the handoff link." },
];

/**
 * Approve means "send this out" (AGENTS.md section 11), so the channel is
 * chosen before approving rather than being a separate step afterwards.
 */
export function ChannelPicker({
  value,
  onChange,
  disabled,
}: {
  value: Channel;
  onChange: (channel: Channel) => void;
  disabled?: boolean;
}) {
  const active = OPTIONS.find((option) => option.id === value);

  return (
    <div>
      <div
        role="group"
        aria-label="Where this case goes"
        className="flex overflow-hidden rounded-sm border border-sz-line"
      >
        {OPTIONS.map((option, index) => {
          const selected = option.id === value;
          return (
            <button
              key={option.id}
              type="button"
              disabled={disabled}
              aria-pressed={selected}
              onClick={() => onChange(option.id)}
              className={cn(
                "min-w-0 grow basis-0 cursor-pointer px-2 py-2 text-[12px] transition-colors disabled:cursor-not-allowed disabled:opacity-50",
                index > 0 && "border-l border-sz-line",
                selected
                  ? "bg-sz-water font-semibold text-sz-on-fill"
                  : "bg-sz-panel text-sz-text-2 hover:bg-sz-raised hover:text-sz-text",
              )}
            >
              {option.label}
            </button>
          );
        })}
      </div>
      {active && <p className="mt-2 text-[12px] text-sz-text-3">{active.hint}</p>}
    </div>
  );
}
