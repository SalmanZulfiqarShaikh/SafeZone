# SafeZone

**A WhatsApp-first disaster triage system for Karachi.**
CODE//CONNECT'26 · UBIT, University of Karachi

> SafeZone does not rescue anyone. It finds who needs help and gets that case to
> someone who can act, with everything they need.

---

## The problem

During the monsoon, help in Karachi does not fail because nobody wants to give it.
It fails because in the first hour nobody can tell which of four hundred messages is
the one where someone cannot get up the stairs.

## What it does

Someone messages one WhatsApp number in whatever words they have — English, Urdu,
Roman Urdu, mixed, misspelled. No app, no account, no form. Then, within seconds:

1. **They get an answer.** Safety steps for their situation and the official
   emergency number. This fires before any model call and never waits for a human.
2. **The nearest on-duty volunteers are offered the case** — their area and a
   one-line summary, never a name or a number.
3. **A coordinator is alerted.** The case is scored on urgency and vulnerability,
   carries a plain-language reason for its rank, and duplicate reports of the same
   street merge into one case rather than competing for the same boat.
4. **A human approves the official handoff.** This is the one manual step. Asking a
   neighbour to look costs a walk; putting an ambulance on the road spends something
   the city has few of, so a person carries that decision.
5. **We check back.** When a case is marked done we ask the reporter whether help
   actually arrived. If it did not, the case returns to the top of the queue.

Coverage: 78 areas across all seven districts of Karachi Division.

---

## What it is not

These are the limits as they stand, not a roadmap. We would rather you read them
here than discover them in the middle of something.

- **Not an emergency service.** SafeZone cannot send a boat, an ambulance or a fire
  crew. Fire and medical cases surface the official emergency number first, always.
- **Not affiliated with Rescue 1122, the Sindh Police, or any government service.**
  It is built to feed them. That is an offer, not an arrangement — nobody has
  adopted it.
- **Volunteers are neighbours, not professionals.** In this prototype the volunteer
  pool is the team's own phones, labelled as demo volunteers everywhere they appear.
  They are not vetted, trained or insured, and they are asked to assess from a safe
  place rather than attempt a rescue. A real deployment needs all three.
- **The responder handoff is a link, not an integration.** Responders get a page
  with everything on it. That is a message we send them, not a live connection into
  any organisation's system.
- **Matching is nearest-first by straight-line distance**, not routed travel time. A
  volunteer 400 m away across a canal is further in practice than the ranking says.
- **Scoring weights are hand-tuned, not learned.** They are visible and adjustable
  rather than hidden, and every case carries a plain-language reason for its rank.
- **The hazard term in the scoring formula is a constant.** Live weather and fire
  feeds were the first thing cut for time, so the 0.20 hazard weight currently
  contributes a neutral default rather than real exposure data.
- **No SMS or USSD fallback.** Everything runs over WhatsApp. Networks fail during
  exactly the events this is built for, and that is a real gap rather than a detail.
- **No offline mode.** The system needs a connection to Supabase. A real deployment
  in a disaster zone would need local storage with sync.
- **`STOP` currently ends area alerts only**, not every message. Finishing it is the
  next thing on the list.
- **Emergency numbers come from configuration**, filled by a human from an official
  source. They are never hardcoded, and when they are unset the guidance ships
  without them rather than guessing. In the demo they point at a team-held redirect
  number and are labelled as simulated.

---

## How it is built

**Backend** — Python 3.11+, FastAPI, Supabase (PostgreSQL), WhatsApp Cloud API.
**Frontend** — React 19, TypeScript, Vite, Tailwind CSS v4, server-sent events.

Four rules the code holds to:

- **The model is never on the critical path.** Command parsing, routing, matching,
  scoring, timers and every message template are deterministic code. The model does
  one job: turning free text into structured fields. With every provider down, the
  system still accepts reports, still ranks them and still dispatches.
- **Every outbound message goes through one function**, which carries the kill
  switch, the rate limits, the allowlist and the 24-hour window check.
- **Every state change is an event.** The timeline replays from the log; if a change
  did not emit, it did not happen.
- **Every phone number is normalised on the way in and on the way to storage.**

463 tests, all passing, runnable with no network and no API keys.

---

## Running it

Requires a `.env` at the repository root — see `.env.example`. Emergency numbers,
WhatsApp credentials and the Supabase keys are filled per deployment and are never
committed; the repository is public.

**Backend** (from inside `Backend/`, not the repository root):

```bash
cd Backend
python -m venv .venv && .venv/Scripts/activate      # or source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

On startup it prints every configuration problem that would silently break a demo.
Read them.

**Frontend:**

```bash
cd Frontend
npm install
npm run dev        # dev server on :5173, proxies /api to :8000
npm run build      # builds into Backend/static, served by FastAPI
```

**Tests:**

```bash
cd Backend
python -m pytest -q
```

**Control room access** — generate a password hash and a session secret, then put
both in `.env`:

```bash
python -m scripts.hash_password
```

**Locality data** (optional, improves area matching) — downloads named Karachi
localities from OpenStreetMap into a committed data file, so nothing calls a
geocoding service at runtime:

```bash
python -m scripts.build_localities
```

---

## The team

Team Nova Strike — UBIT, University of Karachi

| | |
|---|---|
| Muhammad Salman | [@SalmanZulfiqarShaikh](https://github.com/SalmanZulfiqarShaikh) |
| Hussain Abbas | [@hussainabbas6706](https://github.com/hussainabbas6706) |
| Abdul Rehman | [@mabdulrehmankhan666](https://github.com/mabdulrehmankhan666) |
| Usaim | [@usaim35](https://github.com/usaim35) |

For the community, by the community.

---

## Attribution

Locality and place names from OpenStreetMap contributors, ODbL.
Photographs on the site are press images of Karachi emergencies by other
photographers, captioned as such. They are not SafeZone's own work — we have not
pulled anyone out of anything.

`AGENTS.md` holds the full specification, the non-negotiables and the ownership map.
