import { useEffect, useState } from "react";

import * as api from "../lib/api";

/**
 * The public WhatsApp number, from the backend.
 *
 * Deliberately not a build-time env var. A number baked into the bundle
 * means a second place to configure, a rebuild to change it, and a silent
 * failure mode where the button points at a bare wa.me link because one file
 * was never created. The backend already knows the number -- it sends the
 * replies from it -- so this asks.
 */
export interface Whatsapp {
  /** Ready to link to. Empty while loading or when nothing is configured. */
  url: string;
  /** Digits only, no plus. Undefined until known. */
  number?: string;
  /** "+92 349 2468494", for showing to a human. */
  display?: string;
  loading: boolean;
}

export function useWhatsapp(): Whatsapp {
  const [state, setState] = useState<Whatsapp>({ url: "", loading: true });

  useEffect(() => {
    let cancelled = false;

    api
      .getWhatsapp()
      .then((body) => {
        if (cancelled) return;
        setState({
          url: body.url ?? "",
          number: body.number ?? undefined,
          display: body.display ?? undefined,
          loading: false,
        });
      })
      .catch(() => {
        // The page still renders; it just shows the placeholder and says the
        // number is not available, which is honest rather than broken.
        if (!cancelled) setState({ url: "", loading: false });
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}
