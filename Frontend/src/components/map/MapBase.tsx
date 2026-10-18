/**
 * The basemap: coastline, harbour, the two rivers, and the main arteries.
 *
 * Drawn in the same 0–100 space as lib/geo.ts, with preserveAspectRatio="none"
 * so the geography stretches exactly with the container and stays aligned to
 * percentage-positioned pins.
 *
 * Colours come from CSS variables rather than literals, so the one copy of the
 * geography serves both the light operations theme and the dark one. In light
 * mode the roads are white over pale land, which is how a road actually reads
 * on paper.
 *
 * vector-effect goes on every path individually — it is not an inherited
 * property, so setting it on a wrapping <g> silently does nothing and every
 * stroke scales up with the container. Without it a 1-unit stroke renders
 * around ten pixels wide and the city reads as scratches.
 *
 * A schematic, not a survey: a dispatcher needs to find Lyari in half a
 * second, and the responder page hands navigation to a real maps app.
 */

const STROKE = "non-scaling-stroke" as const;

const COAST =
  "M0 60 L6.7 66.7 L13.3 86.7 L20 76.7 L30 90 L43.3 93.3 L56 92 L70 90 L80 88 L93.3 86.7 L100 85";

export function MapBase() {
  return (
    <svg
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      aria-hidden="true"
      className="absolute inset-0 h-full w-full"
    >
      <rect width="100" height="100" fill="var(--color-sz-map-land)" />

      {/* Built-up density, so the land reads as a city rather than empty
          ground. Only a shade off the background: any more and the blocks
          read as shapes in their own right and compete with the pins. */}
      <g fill="var(--color-sz-map-block)">
        <path d="M22 44 L40 36 L52 42 L48 58 L30 64 L20 56 Z" />
        <path d="M44 24 L64 18 L76 26 L72 42 L54 48 L42 38 Z" />
        <path d="M52 56 L70 50 L82 58 L78 72 L60 78 L50 68 Z" />
        <path d="M14 58 L26 54 L32 66 L24 76 L12 70 Z" />
      </g>

      {/* Arabian Sea, Karachi harbour, and the creeks east of Korangi. */}
      <path d={`${COAST} L100 100 L0 100 Z`} fill="var(--color-sz-map-sea)" />
      <path
        d={COAST}
        stroke="var(--color-sz-map-coast)"
        strokeWidth="1"
        fill="none"
        vectorEffect={STROKE}
      />
      {/* The harbour channel, cutting north behind Kemari. */}
      <path
        d="M15.5 84 C16.5 76 17.6 68 18.2 61"
        stroke="var(--color-sz-map-sea)"
        strokeWidth="7"
        strokeLinecap="round"
        fill="none"
        vectorEffect={STROKE}
      />

      {/* Lyari river, north-east down to the harbour. */}
      <path
        d="M43.3 13.3 C38 24 34 30 30 36.7 C24 46 20 54 16.7 60"
        stroke="var(--color-sz-map-river)"
        strokeWidth="2.5"
        fill="none"
        strokeLinecap="round"
        vectorEffect={STROKE}
      />
      {/* Malir river, north-east down to the creek. */}
      <path
        d="M86.7 20 C82 30 79 38 76.7 46.7 C72 58 68 66 66.7 70 C65 78 64 83 63.3 86.7"
        stroke="var(--color-sz-map-river)"
        strokeWidth="2.5"
        fill="none"
        strokeLinecap="round"
        vectorEffect={STROKE}
      />

      {/* Main arteries. They orient, they do not compete with the pins. */}
      {[
        "M26.7 66.7 L40 62 L56 57 L73.3 53.3",
        "M20 76.7 L33 70 L46 63 L60 54 L73.3 44 L86.7 33",
        "M30 90 L36 76 L43.3 60 L48 44 L52 26 L56 10",
        "M43.3 93.3 L52 78 L60 62 L66 46 L70 28",
        "M13.3 55 L30 48 L48 40 L66 31 L84 22",
        "M63.3 86.7 L70 72 L76 56 L80 38 L83 20",
        "M6.7 66.7 L18 56 L30 46 L40 34 L48 20 L54 6",
      ].map((d) => (
        <path
          key={d}
          d={d}
          stroke="var(--color-sz-map-road)"
          strokeWidth="1.4"
          fill="none"
          strokeLinecap="round"
          vectorEffect={STROKE}
        />
      ))}

      {/* Northern bypass, the outer edge of the covered areas. */}
      <path
        d="M14 52 C22 30 44 12 70 14 C86 15 95 24 97 36"
        stroke="var(--color-sz-map-coast)"
        strokeWidth="1"
        fill="none"
        strokeDasharray="4 5"
        vectorEffect={STROKE}
      />
    </svg>
  );
}
