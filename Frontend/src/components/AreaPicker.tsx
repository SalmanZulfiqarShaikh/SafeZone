import { Check, ChevronDown, Search, X } from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState } from "react";

import { cn } from "../lib/utils";

/**
 * Pick one of seventy-eight areas.
 *
 * A native <select> with seventy-eight options is fine on a laptop and
 * miserable on a phone: an unsearchable wheel someone has to spin past
 * "Gulshan-e-Iqbal" to reach "Surjani". Nobody browses this list -- they
 * already know their area and want to type three letters of it.
 *
 * So: type to filter, arrows to move, Enter to choose, Escape to close,
 * and the whole thing still works from the keyboard without a mouse. The
 * matching is loose on purpose, because people spell their own
 * neighbourhood a dozen ways and "jauhar" should find "Gulistan-e-Jauhar".
 */

export interface Area {
  id: string;
  name: string;
}

/** Strip the punctuation people never agree on. "Gulistan-e-Jauhar",
 *  "Gulistan e Jauhar" and "gulistanejauhar" all collapse to one string, so
 *  any of them finds the area. */
function loose(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]/g, "");
}

export function AreaPicker({
  areas,
  value,
  onChange,
  loading,
}: {
  areas: Area[];
  value: string;
  onChange: (id: string) => void;
  loading?: boolean;
}) {
  const listId = useId();
  const inputId = useId();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const wrapRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const selected = areas.find((area) => area.id === value) ?? null;

  const matches = useMemo(() => {
    const needle = loose(query);
    if (!needle) return areas;
    // Areas whose name starts with what was typed come first: someone typing
    // "kor" wants Korangi above "Mehmoodabad, Korangi side".
    const starts: Area[] = [];
    const contains: Area[] = [];
    for (const area of areas) {
      const hay = loose(area.name);
      if (hay.startsWith(needle)) starts.push(area);
      else if (hay.includes(needle)) contains.push(area);
    }
    return [...starts, ...contains];
  }, [areas, query]);

  // Close when the click lands anywhere else. Pointerdown rather than click,
  // so a tap that starts outside does not first fire a selection inside.
  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: PointerEvent) {
      if (!wrapRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  // Keep the highlighted row in view while arrowing through a long list.
  useEffect(() => {
    if (!open) return;
    listRef.current
      ?.querySelector(`[data-index="${active}"]`)
      ?.scrollIntoView({ block: "nearest" });
  }, [active, open]);

  function choose(area: Area) {
    onChange(area.id);
    setQuery("");
    setOpen(false);
  }

  function onKeyDown(event: React.KeyboardEvent) {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (!open) {
        setOpen(true);
        return;
      }
      const step = event.key === "ArrowDown" ? 1 : -1;
      setActive((current) => {
        if (matches.length === 0) return 0;
        return (current + step + matches.length) % matches.length;
      });
      return;
    }
    if (event.key === "Enter" && open) {
      event.preventDefault();
      const pick = matches[active];
      if (pick) choose(pick);
      return;
    }
    if (event.key === "Escape") {
      setOpen(false);
      return;
    }
    if (event.key === "Tab") setOpen(false);
  }

  return (
    <div ref={wrapRef} className="relative">
      <label htmlFor={inputId} className="block text-[14px] text-sz-text-2">
        Your area
      </label>

      <div className="relative mt-1.5">
        <Search
          className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-sz-text-3"
          aria-hidden="true"
        />
        <input
          id={inputId}
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={open && matches[active] ? `${listId}-${active}` : undefined}
          autoComplete="off"
          disabled={loading}
          value={open ? query : (selected?.name ?? "")}
          placeholder={loading ? "Loading areas…" : "Start typing — e.g. Johar, FB Area"}
          onFocus={() => setOpen(true)}
          onChange={(event) => {
            setQuery(event.target.value);
            setActive(0);
            setOpen(true);
          }}
          onKeyDown={onKeyDown}
          className="h-12 w-full rounded-lg border border-sz-line bg-sz-base pr-16 pl-9 text-sz-text transition-colors outline-none placeholder:text-sz-text-3 focus:border-sz-water focus:ring-2 focus:ring-sz-water/25 disabled:opacity-60"
        />

        <div className="absolute top-1/2 right-2 flex -translate-y-1/2 items-center gap-0.5">
          {selected && !open && (
            <button
              type="button"
              aria-label="Clear area"
              onClick={() => {
                onChange("");
                setQuery("");
              }}
              className="inline-flex size-7 cursor-pointer items-center justify-center rounded-full text-sz-text-3 transition-colors hover:text-sz-text"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          )}
          <ChevronDown
            className={cn(
              "h-4 w-4 text-sz-text-3 transition-transform",
              open && "rotate-180",
            )}
            aria-hidden="true"
          />
        </div>
      </div>

      {open && (
        <ul
          id={listId}
          ref={listRef}
          role="listbox"
          aria-label="Areas"
          className="absolute inset-x-0 top-full z-20 mt-1.5 max-h-64 overflow-y-auto rounded-lg border border-sz-line bg-sz-panel py-1 shadow-lg shadow-black/20"
        >
          {matches.length === 0 && (
            <li className="px-3 py-3 text-[14px] text-sz-text-2">
              No area matches that. You can leave it blank &mdash; we work it out from
              your message.
            </li>
          )}

          {matches.map((area, index) => (
            <li
              key={area.id}
              id={`${listId}-${index}`}
              data-index={index}
              role="option"
              aria-selected={area.id === value}
              onPointerEnter={() => setActive(index)}
              onClick={() => choose(area)}
              className={cn(
                "flex cursor-pointer items-center justify-between gap-3 px-3 py-2 text-[14.5px]",
                index === active && "bg-sz-water/12 text-sz-text",
              )}
            >
              {area.name}
              {area.id === value && (
                <Check className="h-4 w-4 shrink-0 text-sz-water" aria-hidden="true" />
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
