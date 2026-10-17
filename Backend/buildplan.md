# SafeZone — Build Plan and Full Context

**Written:** 2026-10-17, ~18:30 PKT.
**For:** the coding agent continuing this project.
**Read order:** `AGENTS.md` first (product spec, source of truth), then this file
(what is done, what is left, in what order). `HANDOFF.md` has the current source of
every backend file — but it goes stale the moment anyone edits a file, so trust the
actual code over it.

---

## 1. What this is

CODE//CONNECT'26 hackathon, Problem Statement 01 — Disaster Response. Karachi,
Pakistan. Flooding is the primary scenario.

SafeZone is a WhatsApp-first disaster triage system. People message a number for help.
The system extracts what happened and where, scores urgency and vulnerability, ranks
every open case in one queue, and shows that queue to a human coordinator. The
coordinator approves a case and it goes out — to nearby registered volunteers, or as
a complete handoff link to an official responder, or both.

**The framing that must survive into the UI, README and pitch:**

> SafeZone does not rescue anyone. It finds who needs help and gets that case to someone
> who can act, with everything they need. Rescue is done by people and organisations
> on the ground. Our job is the last mile.

Judges are explicitly graded on: a working prototype shown live, trade-offs named out
loud, and how the system behaves when data is incomplete or wrong.

---

## 2. Team

- **Salman** — WhatsApp boundary, intake, deploy, all secrets, Supabase projects.
  Holds prod keys.
- **Hussain** — scoring, protocol, extraction, dispatch logic, lifecycle timers.
- **Abdul Rehman** — junior. Seed data, events, read-only endpoints, simple pages.
  Give him self-contained tickets only; nothing touching the webhook or timers.
- **Usaim** — frontend lead, **not available**. His work is unassigned.

Ownership per file is in `AGENTS.md` §18. Two agents editing one file in parallel
produces conflicts nobody has time to resolve.

---

## 3. Current state (verified)

### Done
- Folder restructure: `Backend/{core,routes,services,data,tests}`, flat imports
- In-memory DB removed — Supabase only, one data layer
- `core/config.py` — env loading, `get_emergency_number()` (never raises),
  `startup_report()`
- `core/phone.py` — `normalize_phone()`, `try_normalize()`, `mask()`, `PhoneError`
- `core/db.py` — Supabase client, `DbError`, `execute()` wrapper
- `data/schema.sql` — 10 tables, RLS enabled with zero policies, CHECK constraints,
  unique index on `dispatches(case_id, volunteer_id)`, `outbox` audit table
- `main.py` — lifespan logging `startup_report()`, `mount_spa()` called last,
  404s for `api/`, `webhook/`, `events/` prefixes
- Frontend scaffold: React 19, TS, Vite, Tailwind v4, shadcn (Base UI), React Router.
  Four placeholder pages.
- 17 backend tests pass. `npm run build` and `npm run lint` clean.
- Meta WhatsApp: app created, token and phone ID obtained, **outbound send proven
  working** against a real number.

### Not done — the entire product
No `core/events.py`. `routes/` and `services/` contain only empty `__init__.py`.
The only endpoint is `/api/hello`. No webhook, no send, no intake, no scoring, no
dispatch, no seed data, no UI beyond placeholders.

### Blockers right now
1. **No `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` in `.env`.** `get_db()` fails in
   lifespan, so uvicorn will not start. Salman must create `safezone-dev` and
   `safezone-prod` projects and run `data/schema.sql` on both.
2. **`supabase` not installed** in `Backend/.venv`. Run
   `python -m pip install -r requirements.txt`.
3. **Emergency numbers empty.** `EMERGENCY_FIRE`, `EMERGENCY_AMBULANCE`,
   `EMERGENCY_POLICE` must be filled by a human from an official source. Never
   guess them. Until then the guidance reply ships without its most important line.
4. **Inbound WhatsApp never tested.** Outbound works. The webhook half — receiving
   `ACCEPT 14` — has never been proven. The entire dispatch loop depends on it.
   Test with ngrok before building on it.

---

## 4. Non-negotiables

Violating one of these is a bug, not a preference.

### Safety
1. The first reply **never promises rescue**. It says help has been alerted. No ETA,
   never "someone is coming".
2. Fire and medical **always surface the official emergency number first**.
   Volunteers are an extra pair of hands, never the primary response.
3. **No medical advice.** Safety steps only.
4. Every volunteer offer says: assess from a safe place, do not enter floodwater or
   burning buildings.
5. **Personal data is released only after ACCEPT.** The offer contains zone-level
   location and a one-line summary. Exact pin, first name and phone go only to the
   volunteer who accepts.
6. **Consent before sharing**: tell the person their location and number are being
   shared with a nearby volunteer. They can reply STOP.
7. `KILL_SWITCH` stops every outbound message including volunteer messages.
8. Emergency numbers are never hardcoded from memory. Empty config degrades the
   message; it must not crash the reply.

### Honesty
Anything simulated is labelled simulated **in the UI**, not just the README: demo
volunteers (team phones), seeded boats and ambulances, and the responder handoff
("a link, not an integration"). Never claim a relationship with Edhi, Chhipa,
Alkhidmat, 1122 or any organisation unless a human has actually spoken to them.

### Architecture
1. **The LLM is never on the critical path.** All parsing, routing, matching,
   scoring, timers and templates are plain deterministic code. The LLM does one job:
   free text → structured fields. If it is down, the system still accepts reports,
   still ranks, still dispatches.
2. **Every state change goes through `emit()`.** If it did not emit, it did not
   happen — the timeline replays from the events table.
3. **Every outbound message goes through `send_message()`.** No direct Meta calls
   anywhere else. All guards live in that one function.
4. **Every phone number goes through `normalize_phone()`** on the way in and on the
   way to storage. This is the single most likely silent demo failure.
5. **`MOCK_MODE` fakes WhatsApp sends and LLM extraction only.** Storage is always
   Supabase. There is no offline fallback database. This is a named trade-off.
6. **The webhook always returns HTTP 200**, even on internal failure. Meta retries
   anything else and you get duplicate reports.
7. **Use `mask()` in every log line that touches a phone number.**
8. **Register every router before `mount_spa(app)`.** The catch-all is greedy;
   anything after it is silently dead with no error.

---

## 5. Contracts — freeze before adding callers

```python
# core/phone.py (DONE)
def normalize_phone(raw: str) -> str: ...     # raises PhoneError(ValueError)
def try_normalize(raw: str) -> str | None: ...
def mask(phone: str) -> str: ...

# core/db.py (DONE)
def get_db(): ...                             # Supabase client; raises DbError
def execute(query): ...                       # wraps failures in DbError

# core/config.py (DONE)
def get_emergency_number(category: str) -> str | None: ...   # never raises
def startup_report() -> list[str]: ...

# core/events.py (TO BUILD — build first)
def emit(type: str, payload: dict, case_id: int | None = None) -> None:
    """Append to events, push to SSE subscribers. NEVER raises."""

# services/whatsapp.py (TO BUILD)
def send_message(to: str, text: str) -> bool:
    """The ONLY outbound path. Guards in order: kill switch, global cap,
    per-number rate limit, allowlist, 24h window, mock/live.
    Writes to outbox on every path including suppression. Never raises."""

# services/protocol.py (TO BUILD)
def guidance_reply(category: str, shelter: str | None = None) -> tuple[str, list[str]]:
    """Instant first reply + protocol_path. No DB, no LLM, no network."""

# services/risk.py (TO BUILD)
def score(incident: dict, person_vuln: dict) -> tuple[float, str]:
    """Returns (priority_score, plain_language_reason)."""

# services/dispatch.py (TO BUILD)
def offer_case(case_id: int, ring: int) -> list[int]:
    """Returns volunteer ids offered the case."""
```

---

## 6. Build order — do not reorder

Each step has a gate. Do not pass the gate.

| # | What | Owner | Gate |
|---|---|---|---|
| 0 | Supabase dev+prod, schema+RLS applied, `.env` filled, `pip install -r requirements.txt` | Salman | `uvicorn main:app` boots |
| 1 | `core/events.py` | Rehman | an event writes and reads back |
| 2 | `services/whatsapp.py` | Salman | mock send writes an `outbox` row |
| 3 | `services/protocol.py` + `data/protocol_graph.json` | Hussain | guidance reply renders for all 6 categories |
| 4 | `data/seed.py` | Rehman | 7 zones + demo volunteers in dev DB |
| 5 | `services/intake.py` + `routes/webhook.py` | Salman | **a real WhatsApp message gets an instant guidance reply** |
| 6 | `services/extract.py` | Hussain | free text → structured fields; canned fake in mock |
| 7 | `services/risk.py` | Hussain | queue ranks, every case has a `reason` |
| 8 | `services/dispatch.py` | Hussain | ACCEPT releases contact to accepter only |
| 9 | `services/silence.py` | Hussain | unaccepted offer expires → ring 2 + alert |
| 10 | Routes: cases, volunteers, responder, admin | Rehman | endpoints return JSON |
| 11 | ControlRoom.tsx, Responder.tsx | Salman | queue + map render, approve works |
| 12 | Home.tsx, Volunteers.tsx | Rehman | WhatsApp button + QR, volunteer table |

**Step 5 is the milestone that matters.** Everything before it is setup. Get one
real message producing one real reply before touching scoring or dispatch.

---

## 7. Detailed specs for what is left

### `core/events.py`

Event type constants from `AGENTS.md` §5.3, as module-level strings plus an
`EVENT_TYPES` frozenset:

```
ReportReceived, ReportMerged, IncidentCreated, CaseProposed, CaseApproved,
VolunteerRegistered, VolunteerOnDuty, VolunteerOffered, VolunteerAccepted,
VolunteerArrived, VolunteerDone, DispatchExpired, ResponderLinkSent,
PersonConfirmedHelp, CaseReopened, CaseClosed, KillSwitchToggled
```

`emit(type, payload, case_id=None)` inserts into `events` and fans out to SSE
subscribers. It must **never raise** — a failed audit insert must not break a help
request. Log unknown event types rather than accepting typos silently.

SSE: a module-level `set[asyncio.Queue]` of subscribers, `subscribe()` /
`unsubscribe()`, and a `set_loop()` called once from the FastAPI lifespan (emit may
run in a worker thread, so pushing to asyncio queues needs the captured loop and
`call_soon_threadsafe`). Drop frames on a full queue rather than block.

Add `sse_format(record) -> str` producing `event: <type>\ndata: <json>\n\n`.

### `services/whatsapp.py`

`send_message(to: str, text: str) -> bool`. Guards in this exact order:

1. `KILL_SWITCH` on → suppress
2. Global message cap reached → suppress
3. Per-number rate limit (`PER_NUMBER_RATE_LIMIT` per `PER_NUMBER_RATE_WINDOW_S`) → suppress
4. `ALLOWLIST_ONLY` and `to` not in `DEMO_ALLOWLIST` → suppress
5. 24h WhatsApp window closed → suppress and log
6. `MOCK_MODE` → log to console, write `outbox` row with `mode='mock'`, return True
7. Otherwise → POST to Meta, write `outbox` row with `mode='live'`

**Every path writes an `outbox` row**, including suppressions, with
`suppressed_reason` set. That table is the primary debugging surface when the demo
misbehaves. Returns `False` when suppressed. Never raises.

Also here: webhook signature verification, and the Meta client.

Meta endpoint: `POST https://graph.facebook.com/v26.0/<WHATSAPP_PHONE_ID>/messages`
with header `Authorization: Bearer <WHATSAPP_TOKEN>` and body
`{"messaging_product":"whatsapp","to":<number>,"type":"text","text":{"body":<text>}}`.
This is verified working.

### `data/protocol_graph.json` + `services/protocol.py`

Six categories: `flood`, `fire`, `medical`, `trapped`, `structural`, `other`.

Each node has: `label`, `emergency_kind` (`fire`|`medical`|`police`),
`official_first` (bool — true for fire, medical, structural), `volunteer_eligible`
(bool — false for structural), `safety_steps` (2–3 short strings), `questions`
(location first, then one vulnerability question).

Example — flood safety steps: move to the highest floor you can reach safely; stay
away from electrical switches and wet wiring; do not walk or drive through moving
floodwater.

`guidance_reply(category, shelter=None) -> (text, protocol_path)` builds the instant
reply: emergency number (first line if `official_first`), safety steps, nearest
shelter if given, then "We have flagged your case and alerted help nearby. Send your
location pin or tell me your area." If `get_emergency_number()` returns `None`, omit
the line, record `emergency_number_missing` in the path, and still return a usable
message.

`next_question(category, asked)` returns `None` after 2 questions. Location first.

No DB, no LLM, no network in this module.

### `data/seed.py`

Seven Karachi zones with centroid lat/lng: johar, gulshan, surjani, lyari, gujjar,
korangi, dha. Several named demo volunteer rows per zone, all routed to two team
phones (`is_demo=1`). **Obviously fake numbers only** — `923000000001` style. Real
numbers live only in `DEMO_VOLUNTEERS` on prod, held by Salman. A handful of sample
incidents across categories so the queue renders. Idempotent: re-running must not
duplicate.

### `services/intake.py` + `routes/webhook.py`

`GET /webhook/whatsapp` — verify `hub.verify_token` against `WHATSAPP_VERIFY_TOKEN`,
echo `hub.challenge` as plain text, else 403.

`POST /webhook/whatsapp` — **always returns 200.** Parse the Meta payload (status
updates arrive on the same endpoint and have no `messages` key — ignore them).
Normalize the sender with `try_normalize()`; a malformed number asks for
clarification, it does not 500.

Command router, plain code, case-insensitive, **case ID required** on case commands
(one phone holds several cases in the demo; a bare `ACCEPT` is ambiguous and is
rejected with `Reply ACCEPT <case id>`):

| Who | Command | Effect |
|---|---|---|
| Volunteer | `VOLUNTEER <area>` + pin | Register/update location, ask capabilities |
| Volunteer | `ON DUTY` / `OFF DUTY` | Start/end shift; `ON DUTY` reopens the 24h window |
| Volunteer | `ACCEPT <id>` | Claim, first wins |
| Volunteer | `DECLINE <id>` | Pass, trigger next sooner |
| Volunteer | `ARRIVED <id>` / `DONE <id>` | Advance lifecycle |
| Person | `1` / `2` after "Did help reach you?" | Confirm or reopen |
| Person | `STOP` | Opt out |
| Anyone | anything else | Help request → slot-filling |

**Registration is optional and is NOT the front door** (`AGENTS.md` §9). Unknown
numbers go straight into slot-filling. Website registration and `JOIN <code>` exist
only for proactive area alerts. Build the unregistered path as the default or the
webhook gets written twice.

Direct-message flow: instant guidance reply fires **before** the LLM and before
location → `extract_report` slot-filling, at most 2 questions, location first →
optional vulnerability questions only if not already urgent → create incident, enter
the same ranked queue → after the case, one non-pushy line inviting registration.

No location after 2 questions → incident created `location_unknown`, low confidence,
flagged. **Cannot be dispatched to volunteers or minted as a responder link.**
Coordinator sees it at the top for a phone call. If a pin arrives later, the case
upgrades in place and re-ranks.

### `services/extract.py`

One LLM call. Output shape:

```json
{
  "category": "flood",
  "category_confidence": 0.9,
  "urgency": "high",
  "people_count": 3,
  "location_text": "Gulshan 13-D near the masjid",
  "zone_guess": "gulshan",
  "vulnerability": {"elderly": true, "alone": null, "floor": "ground"},
  "needs": ["evacuation"],
  "missing_fields": ["exact_location"],
  "next_question": "Can you send your location pin, or the nearest landmark?"
}
```

`urgency` ∈ `low|medium|high|critical`. Provider from `LLM_PROVIDER` / `LLM_MODEL`.
`MOCK_MODE` returns a deterministic canned extraction with no network call. If the
LLM fails, fall back to keyword matching for category and continue — the system must
still accept, rank and dispatch.

### `services/risk.py`

```
priority = (0.40 * vulnerability_score
          + 0.30 * urgency_score
          + 0.20 * hazard_exposure
          + 0.10 * time_decay) * confidence

confidence = clamp(source_factor * (0.6 + 0.1 * min(report_count, 4)), 0, 1)
```

`source_factor`: WhatsApp 1.0, web 0.7. Unknown vulnerability fields score as a
**neutral default** — never zero risk, never maximum. Record which fields were
actually answered; the coordinator needs to see a score resting on two answers, not
six.

**Every case carries a plain-language `reason`.** Judges will ask why case 14
outranks case 9 and "the model said so" loses. Example: "Elderly person alone on a
ground floor, water rising, 3 separate reports in 20 minutes."

### `services/merge.py`

Same category within ~300 m and 30 minutes → one incident, confidence rises.
Merging never lowers urgency — take the max.

### `services/dispatch.py`

Rank on-duty, not-busy volunteers by straight-line distance. Ring 1 = 3 nearest.
In demo mode the zone's primary phone is ring 1, the other phone is ring 2. A
volunteer holding an active case is `busy` and skipped.

`dispatches(case_id, volunteer_id)` is **unique** — re-offering must update or
upsert, not blind-insert.

Offer message (no exact location, no contact):
```
Case 14 near Gulshan 13-D. Elderly person alone, ground floor, water rising.
Reply ACCEPT 14 to take it.
Assess from a safe place. Do not enter floodwater or burning buildings.
```

After ACCEPT — **this is the only place contact is released**:
```
Case 14 is yours. Name: <first name>. Contact: <phone>. Location: <map link>.
Reply ARRIVED 14 when you get there, DONE 14 when finished.
```

To others: `Case 14 was taken, thanks.` To the person: `A volunteer is on the way.`
After DONE: `Did help reach you? Reply 1 yes, 2 no.`

### `services/silence.py`

Background loop. Re-escalation triggers — case jumps to top of queue, tagged
`re-opened`, coordinator alerted:
- Nobody accepts within `VOLUNTEER_ACCEPT_TIMEOUT_S` (60–90s in demo)
- Person replies `2` to "Did help reach you?"
- Person goes silent after being marked helped
- Volunteer accepts but never sends `ARRIVED` within `VOLUNTEER_ARRIVE_TIMEOUT_S`

### Routes

| Method | Path | Owner |
|---|---|---|
| GET/POST | `/webhook/whatsapp` | Salman |
| POST | `/api/proposals/{id}/approve` (body: `channel` = volunteers\|responder\|both) | Salman |
| POST | `/api/cases/{id}/responderlink` | Rehman |
| GET | `/api/cases/{id}/dispatches` | Rehman |
| POST | `/api/cases/{id}/reopen` | Rehman |
| GET | `/api/volunteers` | Rehman |
| GET | `/api/r/{token}` | Rehman |
| GET | `/events` (SSE) | Rehman |
| POST | `/api/admin/killswitch` | Rehman |

Use Pydantic models for request and response bodies — especially the Meta webhook
payload, rather than `body["entry"][0]["changes"][0]...` index-chaining.

Responder page data: map pin + Navigate, category, urgency, report count, time since
first report, confidence, vulnerability summary, plain-language reason, protocol
path, live status, Call button. No login. Token unguessable
(`secrets.token_urlsafe(16)`), expires. **First name only** unless the coordinator
explicitly included a phone for that handoff.

### Frontend

- `Home.tsx` — "Need help? Message us on WhatsApp", button + QR code. Registration
  is secondary: "Get alerts for your area".
- `ControlRoom.tsx` — Leaflet map, ranked queue, case drawer, dispatch panel,
  approve-with-channel picker, event list, kill switch. Volunteer pins labelled
  **"Demo volunteers (team phones)"**.
- `Responder.tsx` — `/r/:token`, mobile-first, read-only.
- `Volunteers.tsx` — duty table, labelled as demo volunteers.

---

## 8. Cut order

If time runs short, cut in this order:
1. `hazards.py` — use a constant hazard value
2. Volunteer map pins
3. Multi-volunteer-per-zone seeding
4. The "Both" approve option
5. Timeline slider → plain reverse-chronological event list

**Never cut:** the instant guidance reply, ACCEPT/ARRIVED/DONE, the responder link,
the honest labelling of simulated things.

---

## 9. Definition of done

- [ ] A stranger with no registration gets the emergency number, is asked for a
      location, and appears in the ranked queue
- [ ] A volunteer can send `ON DUTY` and receive an offer
- [ ] `ACCEPT <id>` releases location and contact **only** to the accepting volunteer
- [ ] `ARRIVED` and `DONE` update the case and notify the person
- [ ] The person is asked "Did help reach you?" and a `2` re-opens the case
- [ ] An unaccepted offer expires, goes to the next ring, alerts the coordinator
- [ ] The responder link opens on a phone with map, Navigate and case summary
- [ ] No volunteer phone number appears in the repo or any public page
- [ ] Location-unknown cases are flagged and cannot be dispatched
- [ ] The whole demo runs with `MOCK_MODE=1` against `safezone-dev`, no WhatsApp or
      LLM calls

---

## 10. Demo

Volunteer pool is two team phones. Phone A covers johar, gulshan, surjani. Phone B
covers lyari, gujjar, korangi, dha. Each is the other's fallback ring. Say this
openly.

### Pre-demo checklist
- [ ] Both phone owners agreed to receive test messages
- [ ] Both numbers in `DEMO_VOLUNTEERS` (prod only) and `DEMO_ALLOWLIST`
- [ ] Both added as approved recipients in Meta if still on a test number
- [ ] Both phones sent `ON DUTY` (reopens the 24h window)
- [ ] Both phones messaged the SafeZone number within the last 24 hours
- [ ] Demo mode on, 60–90s accept timeout
- [ ] Emergency numbers filled from official sources
- [ ] Responder link opened and tested on a phone
- [ ] Dry run of ACCEPT / ARRIVED / DONE with case IDs, including one forced timeout
- [ ] `npm run build` run and `localhost:8000` verified — do not let the first test
      of the production path be during judging

### Script
A judge texts "I need help" from their own phone with no setup and appears in the
queue. Coordinator picks **Notify nearby volunteers**, clicks Approve. A teammate's
phone buzzes; they reply `ACCEPT 14`. The judge's phone shows "A volunteer is on the
way." Teammate replies `ARRIVED 14`, then `DONE 14`. The judge is asked "Did help
reach you?" and replies `1`. The timeline shows every step and the case closes. On a
second case nobody accepts, the other phone gets it after the timeout, and the
coordinator sees the re-escalation alert. Finally, open the responder link on a phone.

### If a judge asks "who actually helps?"
> SafeZone doesn't replace emergency services, it feeds them. It tells the person what
> to do immediately, mobilises registered neighbours who are nearest, and gives
> official responders a complete, ranked case so they spend their time rescuing
> instead of triaging. In this prototype the volunteer pool is our own phones, and
> the responder handoff is a link, not a live integration.

Name the limit before they do.

---

## 11. README trade-offs — must ship

- Volunteer pool is seeded with team phones. No real network was recruited; the UI
  labels them as demo volunteers.
- Responder handoff is a shareable link, not a live integration with any emergency
  service or NGO.
- Seeded boats and ambulances are simulated.
- Matching is nearest-first by straight-line distance, not routed travel time.
- Volunteers are not vetted or trained. A real deployment would need vetting,
  training and insurance.
- Fire and medical always point to official emergency numbers first.
- Scoring weights are hand-tuned, not learned. They are visible and adjustable.
- The system requires network connectivity to Supabase. No offline or local-first
  mode — a real deployment in a disaster zone, where networks fail exactly when the
  system is needed, would need local storage with sync.
- No SMS or USSD fallback. The system assumes WhatsApp reaches the person.

---

## 12. Known gotchas

1. `get_db()` validates config only — no network call. A bad URL or revoked key fails
   on the first query, not at startup. Do not claim startup proves connectivity.
2. `mount_spa()` checks `STATIC_DIR.exists()` at **import time**. Build the frontend
   before starting uvicorn, or restart after building. An empty `static/` gives a 500,
   not a 404.
3. `execute()` exists but nothing uses it yet. New code must use it or the typed-error
   boundary is lost.
4. Config is read **once at import**. Changing `.env` needs a process restart.
5. CHECK constraints are added after table creation. On a DB with pre-existing bad
   rows the ALTER fails and the script aborts. Run against a clean dev project first.
6. The unique index on `dispatches` means re-offering must update or upsert.
7. Em dashes in log strings render as `?` on the Windows console. Use ASCII in logs if
   terminal output is part of the demo.
8. The app was renamed from Dastak to SafeZone on 2026-10-17. The new name is used
   everywhere: FastAPI title, logger names (`safezone.*`), docs, schema header and UI.
   The Supabase project names in this plan are `safezone-dev` / `safezone-prod` to
   match; if a project was already created under the old name, only its URL matters.
9. `Frontend/index.html` references `/favicon.svg` but `public/favicon.svg` is deleted
   in the working tree. Restore or remove the reference.
10. `.env.example` is stale — it lists `GROQ_API_KEY`, which the code never reads.
    Regenerate it from the variables `core/config.py` actually reads.
11. `README.md` is only a team table. Add run instructions: backend is
    `uvicorn main:app --reload` from **inside** `Backend/`.
12. `httpx2`, `httpcore2`, `annotated-doc`, `strenum` in the venv are legitimate
    (Pydantic Services, tiangolo, irgeek), arrived transitively. Not typosquats. Do
    not add them to `requirements.txt`.

---

## 13. Rules for the coding agent

1. Read `AGENTS.md` fully. Anything marked PROPOSED there is a guess — flag it, don't
   build three modules on it.
2. Never introduce a second data layer. Supabase only. Fail loudly on missing config.
3. Never hardcode emergency numbers. Leave them empty until a human supplies them.
4. Never put real phone numbers anywhere — not in seeds, tests, comments or fixtures.
5. Every feature must work with `MOCK_MODE=1` and no WhatsApp or LLM call, on the
   same commit.
6. The webhook always returns 200.
7. Register routers before `mount_spa(app)`.
8. Use `mask()` in every log line touching a phone number.
9. Commit small, working states. `type(scope): description` per `CONTRIBUTING.md`.
10. Stay in your lane — `AGENTS.md` §18 assigns file ownership.
11. **Prefer finishing a vertical slice over starting a horizontal layer.** One case
    moving end to end beats four half-built subsystems.
12. Refuse to make the system sound more capable than it is. The honesty is the pitch.