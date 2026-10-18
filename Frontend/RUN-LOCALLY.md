# SaveZone frontend — running it locally

## Fast path (no backend needed)

```bash
cd Frontend
npm install
npm run dev
```

Open the URL Vite prints (usually `http://localhost:5173`).

Everything works without the backend running. `useDashboard` tries the API
first; when it cannot reach it the app falls back to the fixtures in
`src/lib/mockData.ts` and the header badge switches from **Live** to **Demo
fixtures**. That is the state all the screenshots were taken in.

Try this in order:

1. Watch the splash (1s), then the dashboard.
2. Click **Simulate SOS** in the Incoming header.
3. Watch the card rail: *WhatsApp received → Triaging priority*.
4. Click **Dispatch resource** on that card.
5. Watch the map draw the volunteer's route, the rail advance to *Resource
   dispatched*, and the timeline fill in.

## Theme

There is a light/dark toggle in the header — the moon/sun button next to the
outbound switch. The choice is kept in `localStorage`, so it survives a reload.

Both token sets live in `src/index.css`: light on `@theme`, dark under
`[data-theme="dark"]`. Flipping the attribute repaints everything — chrome,
panels, severity colours, and the basemap, which reads its colours from the
same variables rather than keeping a second copy of the geography.

To change which one a fresh visitor gets, edit the fallback in
`src/hooks/useTheme.ts`:

```ts
return "light";   // or "dark"
```

To retune the palette, the tokens at the top of `src/index.css` are the only
place colours are defined. `--color-sz-base` is the canvas, `--color-sz-panel`
the cards, `--color-sz-header` the navy chrome. Nothing in the components
writes a raw hex.

Routes: `/` command dashboard · `/help` public WhatsApp page ·
`/volunteers` volunteer pool · `/r/<anything>` responder handoff.

## Against the real backend

```bash
cd Backend
cp ../.env.example .env        # then fill SUPABASE_URL + SUPABASE_SERVICE_KEY
pip install -r requirements.txt
uvicorn main:app --reload
```

Then either:

- **Same origin (simplest).** `cd Frontend && npm run build` writes to
  `Backend/static/`, which `main.py` already serves. Open
  `http://localhost:8000`. No CORS, SSE works.
- **Separate dev servers.** Create `Frontend/.env.local`:
  ```
  VITE_API_BASE=http://localhost:8000
  ```
  Then `npm run dev`. The backend needs CORS for `http://localhost:5173`, and
  `/events` is on the backend origin.

## Checks

```bash
cd Frontend
npm run lint     # clean
npm run build    # clean
```

## New dependencies

Added to `Frontend/package.json` — `npm install` picks them up:

- `framer-motion` — splash, feed entry animation, triage panel stagger
- `@fontsource-variable/geist-mono` — mono face for IDs, scores, coordinates

## What is in this archive

Extract at the repo root — paths are already `Frontend/...` so they land in the
right place and overwrite the old versions.

Everything under `Frontend/` that the app needs is here, including
`tsconfig*.json`, `vite.config.ts`, `eslint.config.js` and `components.json`.
Those four are byte-identical to what you already have; they are included only
so the archive builds on its own rather than failing in a fresh directory.
`node_modules/` is not included — run `npm install`.

Nothing under `Backend/` is included or altered. `Backend/static/` is build
output and is gitignored — it regenerates on `npm run build`.

## Known gaps

- The QR on `/help` is a labelled placeholder until `WHATSAPP_NUMBER` is set.
- Emergency numbers render as "not set in config" everywhere, including the
  responder Call button, which therefore does not dial. Fill `EMERGENCY_FIRE`,
  `EMERGENCY_AMBULANCE` and `EMERGENCY_POLICE` from an official source.
- The map is a hand-drawn SVG of Karachi projected from real lat/lng, not
  react-map-gl. No network dependency, no token.
- `src/pages/ControlRoom.tsx` was deleted — it was an unrouted stub replaced by
  `pages/Dashboard.tsx`. Delete it in your copy too if git restores it.
