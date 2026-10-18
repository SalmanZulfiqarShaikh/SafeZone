import { useCallback, useEffect, useState } from "react";

export type Theme = "light" | "dark";

const KEY = "savezone-theme";

/** Storage throws in a private window and comes back empty when site data is
 *  cleared, so every access is guarded and light is the fallback. */
function readStored(): Theme {
  try {
    const stored = localStorage.getItem(KEY);
    if (stored === "light" || stored === "dark") return stored;
  } catch {
    /* blocked or unavailable — fall through to the default */
  }
  return "light";
}

/**
 * Light and dark, driven by `data-theme` on <html>.
 *
 * Both token sets already live in index.css, so flipping the attribute
 * repaints everything — panels, severity colours, the chrome, and the basemap,
 * which reads its colours from the same variables rather than keeping a second
 * copy of the geography.
 */
export function useTheme(): { theme: Theme; toggle: () => void } {
  const [theme, setTheme] = useState<Theme>(readStored);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem(KEY, theme);
    } catch {
      /* the choice just will not survive a reload */
    }
  }, [theme]);

  const toggle = useCallback(
    () => setTheme((current) => (current === "light" ? "dark" : "light")),
    [],
  );

  return { theme, toggle };
}
