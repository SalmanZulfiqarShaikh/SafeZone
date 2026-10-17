# AGENTS.md — Dastak

> Read this file completely before writing any code. It is the single source of truth
> for this project. If something here conflicts with your instincts, this file wins.
> If something is marked PROPOSED, it is a guess that has not been confirmed by a
> human — flag it before you build on it, do not silently extend it.

---

## 0. Context

**Event:** CODE//CONNECT'26 Vibe Coding Hackathon, Problem Statement 01 — Disaster Response.
**Core question we answer:** How do we identify the most at-risk people and match scarce
resources to them before it is critical?

**Deliverable:** a working prototype demonstrated live, not slides. Judges explicitly
grade on trade-offs being named out loud and on how the system behaves when data is
incomplete or wrong.

**Location context:** Karachi, Pakistan. Flooding is the primary scenario. Zones used
throughout: Johar, Gulshan, Surjani, Lyari, Gujjar, Korangi, DHA.

**Team reality (important for scoping):**
- Salman — doing backend, AI, *and* frontend. Holds prod keys and secrets.
- Abdul Rehman — junior, backend support, needs small well-defined tickets.
- Usaim (frontend lead) — not available. His work falls to Salman.
- Hussain — may or may not be available; do not assume his pieces are covered.

Scope accordingly. Prefer boring and finished over clever and half-built.

---

## 1. What Dastak is, in one paragraph

Dastak is a WhatsApp-first disaster triage system. People message a number for help.
The system extracts what happened and where, scores how urgent and how vulnerable the
person is, ranks every open case in one queue, and shows that queue to a human
coordinator. The coordinator approves a case and it goes out — to nearby registered
volunteers, or as a complete handoff link to an official responder, or both.

**The honest framing, which must survive into the UI, the README and the pitch:**

> Dastak does not rescue anyone. It finds who needs help and gets that case to someone
> who can act, with everything they need. Rescue is done by people and organisations on
> the ground. Our job is the last mile.

**The one-line answer to "who actually helps?":**

> Dastak doesn't replace emergency services, it feeds them. It tells the person what to
> do immediately, mobilises registered neighbours who are nearest, and gives official
> responders a complete, ranked case so they spend their time rescuing instead of
> triaging. In this prototype the volunteer pool is our own phones, and the responder
> handoff is a link, not a live integration.

---

## 2. Non-negotiables

These are not preferences. Violating one is a bug.

### 2.1 Safety

1. **The first reply never promises rescue.** It says help has been alerted. Never "someone
   is coming", never an ETA.
2. **Fire and medical cases always surface the official emergency number first**, before any
   volunteer logic. Volunteers are an extra pair of hands, never the primary response.
3. **No medical advice.** Safety steps only, generic, sourced from official guidance.
4. **Every volunteer offer message includes:** assess from a safe place, do not enter
   floodwater or burning buildings.
5. **Personal data is released only after ACCEPT.** The offer message contains zone-level
   location and a one-line situation summary. Exact pin, first name and phone number are
   released only to the volunteer who accepts.
6. **Consent before sharing.** Before releasing the person's details to a volunteer, the bot
   tells them: "I'm sharing your location and number with a nearby volunteer." Asking for
   help is the trigger for contact; they can reply STOP at any time.
7. **Kill switch** stops all outbound messages including volunteer messages.
8. **Emergency numbers are never hardcoded from memory.** They live in config and must be
   filled from an official source by a human. Leave them empty and loudly broken until then.

### 2.2 Honesty in the product

Anything simulated must be labelled simulated **in the UI**, not just in the README:
- Demo volunteers (team phones) — labelled as such on the map and in the dispatch panel
- Seeded boats and ambulances — labelled simulated
- Responder handoff — a shareable link, not an integration with any service

Never present a relationship with Edhi, Chhipa, Alkhidmat, 1122, or any other organisation
unless a human on the team has actually spoken to them. Listing a public phone number as a
call target is fine. Calling it an "integration" is not.

### 2.3 Architecture

1. **The LLM is never on the critical path.** All command parsing, routing, matching,
   scoring, timers and message templates are plain deterministic code. The LLM does one
   job: turning free-text reports into structured fields. If the LLM is down, the system
   still accepts reports, still ranks, still dispatches.
2. **Every state change goes through `emit()`.** The timeline slider replays from the event
   log. If a state change doesn't emit, it didn't happen.
3. **Every outbound message goes through `send_message()`.** No direct API calls elsewhere.
   Window guards, rate limits, allowlist and kill switch live in that one function.
4. **Every phone number goes through `normalize_phone()`** on the way in and on the way to
   storage. This is the single most likely source of a silent demo failure.
5. **Mock mode must work end to end with no network.** `MOCK_MODE=1` fakes WhatsApp send
   and receive, fakes the LLM with canned extractions, and seeds the DB. You must be able
   to run the whole demo offline.

---

## 3. Stack and layout

**Decided:** Python 3.11+, FastAPI + uvicorn, SQLite. Control room is React + TypeScript
+ Vite + Tailwind CSS v4 + shadcn/ui. Citizen home and responder pages are server-rendered
Jinja2. Leaflet for maps, SSE for live updates. Packages added as needed.

Tailwind v4 is CSS-first: there is NO tailwind.config.js. Theme tokens live in
src/index.css. Do not create a Tailwind config file.

UI components come from shadcn/ui. Do not introduce a second component library for
buttons, dialogs or inputs — two theme systems will conflict. Self-contained widgets
(Leaflet, charts) are fine.

No React Router. The control room is a single screen.

```
code-connect/
  app/
    main.py              # FastAPI app, route registration, SSE hub
    config.py            # env loading, all constants, emergency numbers
    db.py                # connection, migrations runner, query helpers
    schema.sql           # all tables (section 5)
    seed.py              # zones, demo volunteers, simulated resources, sample cases
    events.py            # emit(), event type enum, SSE fan-out
    whatsapp.py          # send_message(), webhook verify, Meta API client, mock sender
    intake.py            # webhook handler, command router, slot-filling conversation
    agent.py             # LLM entry point, proposal generation
    tools.py             # LLM tool schemas
    extract.py           # extract_report() — the one LLM call on the report path
    protocol.py          # protocol graph traversal, safety-step lookup
    protocol_graph.json  # category -> steps, questions, escalation
    risk.py              # scoring, ranking, confidence
    hazards.py           # weather and USGS feeds
    merge.py             # duplicate report merging
    dispatch.py          # volunteer matching, rings, offers, lifecycle
    silence.py           # background loop: timeouts, re-escalation, silence detection
    phone.py             # normalize_phone() and tests
    templates/
      base.html
      control_room.html  # map + queue + case drawer + timeline
      responder.html     # /r/<token>
      home.html          # citizen-facing, WhatsApp-first
    static/
  tests/
  .env.example
  README.md
  AGENTS.md
```

---

## 4. The help ladder (the product, in four steps)

### Step 1 — Tell the person what to do right now
Automatic, instant, fires **before** any LLM call, built from config and the protocol graph.

Contains:
- The official emergency number for the category (fire / ambulance / police)
- Two or three short safety steps for that category
- The nearest shelter, if they can move
- "We've flagged your case. Reply with updates."

This is the only part of the ladder that works with zero other humans involved, so it
must never be cut.

### Step 2 — Send the nearest volunteer
Volunteers are ordinary people who registered through the same WhatsApp number.

- Volunteer registers: `VOLUNTEER <area>` + a location pin + capabilities
- Coordinator approves a case → system offers it to the 3 nearest **on-duty, not-busy**
  volunteers
- First `ACCEPT <case id>` wins; others get "Case N was taken, thanks."
- Only on accept does the volunteer get the exact location link, first name and contact
- No accept within the timeout → widen to the next ring, alert the coordinator
- `ARRIVED <id>` then `DONE <id>` advance the case

### Step 3 — Hand off to people with real equipment
We cannot command a boat or an ambulance. We make the handoff effortless instead.

Each case can mint a responder link `/r/<token>`: one read-only mobile page with map,
Navigate button, vulnerability summary, plain-language reason, report count, time since
first report, live status, and a Call button for the configured target.

The coordinator sends that link to a WhatsApp group, an NGO desk, or a phone number.

### Step 4 — Close the loop
After `DONE`, the person is asked "Did help reach you?" A `2` re-opens the case at the top
of the queue. Silence after being marked helped also re-opens it.

---

## 5. Data model

> Tables marked **PROPOSED** are reconstructions. Confirm with Salman before building
> dependent logic on them.

### 5.1 Core tables — PROPOSED

```sql
-- A person we know about. Created on first contact, registered or not.
CREATE TABLE people (
  id              INTEGER PRIMARY KEY,
  phone           TEXT UNIQUE,          -- normalized, no +, no leading zero
  first_name      TEXT,
  zone_id         TEXT,
  lat             REAL,
  lng             REAL,
  is_registered   INTEGER DEFAULT 0,    -- came through the website form
  wants_alerts    INTEGER DEFAULT 0,
  person_vuln     TEXT,                 -- JSON, see 5.4
  window_open_until TEXT,               -- ISO8601, 24h WhatsApp window
  created_at      TEXT NOT NULL
);

-- One inbound report. Several reports can merge into one incident.
CREATE TABLE reports (
  id              INTEGER PRIMARY KEY,
  person_id       INTEGER REFERENCES people(id),
  incident_id     INTEGER REFERENCES incidents(id),
  raw_text        TEXT,
  source          TEXT NOT NULL,        -- 'whatsapp' | 'web'
  source_factor   REAL NOT NULL,        -- whatsapp 1.0, web 0.7
  category        TEXT,                 -- flood|fire|medical|trapped|other
  lat             REAL,
  lng             REAL,
  zone_id         TEXT,
  location_known  INTEGER DEFAULT 0,
  extraction      TEXT,                 -- JSON, raw extract_report output
  created_at      TEXT NOT NULL
);

-- A real-world situation. Reports merge into it.
CREATE TABLE incidents (
  id              INTEGER PRIMARY KEY,
  category        TEXT NOT NULL,
  lat             REAL,
  lng             REAL,
  zone_id         TEXT,
  location_known  INTEGER DEFAULT 0,
  report_count    INTEGER DEFAULT 1,
  confidence      REAL,
  urgency         REAL,
  priority_score  REAL,
  status          TEXT DEFAULT 'open',
  dispatch_status TEXT DEFAULT 'none',
  reopened        INTEGER DEFAULT 0,
  reopen_reason   TEXT,
  first_report_at TEXT NOT NULL,
  last_update_at  TEXT NOT NULL
);

-- A coordinator-facing unit of work. One per incident in this prototype.
CREATE TABLE cases (
  id              INTEGER PRIMARY KEY,
  incident_id     INTEGER REFERENCES incidents(id),
  person_id       INTEGER REFERENCES people(id),
  priority_score  REAL,
  reason          TEXT,                 -- plain-language justification, shown to judges
  vuln_summary    TEXT,
  protocol_path   TEXT,                 -- JSON array of protocol nodes traversed
  status          TEXT DEFAULT 'proposed',
  dispatch_status TEXT DEFAULT 'none',
  reopened        INTEGER DEFAULT 0,
  reopen_reason   TEXT,
  created_at      TEXT NOT NULL,
  closed_at       TEXT
);

CREATE TABLE events (
  id              INTEGER PRIMARY KEY,
  type            TEXT NOT NULL,
  case_id         INTEGER,
  payload         TEXT NOT NULL,        -- JSON
  created_at      TEXT NOT NULL
);
```

`cases.dispatch_status` values: `none`, `offered`, `accepted`, `on_way`, `arrived`,
`confirmed`, `closed`, `reopened`.

### 5.2 New tables — from the addendum, these are confirmed

```sql
CREATE TABLE volunteers (
  id                INTEGER PRIMARY KEY,
  name              TEXT NOT NULL,
  phone             TEXT NOT NULL,      -- normalized; several demo rows may share one
  zone_ids          TEXT NOT NULL,      -- JSON array
  capabilities      TEXT NOT NULL,      -- JSON array: foot|car|boat|first_aid
  lat               REAL,
  lng               REAL,
  status            TEXT DEFAULT 'off_duty',  -- off_duty|on_duty|busy
  window_open_until TEXT,
  is_demo           INTEGER DEFAULT 1
);

CREATE TABLE dispatches (
  id            INTEGER PRIMARY KEY,
  case_id       INTEGER NOT NULL REFERENCES cases(id),
  volunteer_id  INTEGER NOT NULL REFERENCES volunteers(id),
  ring          INTEGER NOT NULL,
  status        TEXT NOT NULL,          -- offered|accepted|on_way|arrived|done|declined|expired
  offered_at    TEXT,
  accepted_at   TEXT,
  arrived_at    TEXT,
  done_at       TEXT
);

CREATE TABLE responder_links (
  token         TEXT PRIMARY KEY,       -- unguessable, secrets.token_urlsafe(16)
  case_id       INTEGER NOT NULL REFERENCES cases(id),
  target_label  TEXT,
  created_at    TEXT NOT NULL,
  expires_at    TEXT NOT NULL
);
```

### 5.3 Event types

All written through `emit()`:

```
ReportReceived, ReportMerged, IncidentCreated, CaseProposed, CaseApproved,
VolunteerRegistered, VolunteerOnDuty, VolunteerOffered, VolunteerAccepted,
VolunteerArrived, VolunteerDone, DispatchExpired, ResponderLinkSent,
PersonConfirmedHelp, CaseReopened, CaseClosed, KillSwitchToggled
```

### 5.4 `person_vuln` shape — PROPOSED

```json
{
  "elderly": true,
  "alone": true,
  "mobility_limited": false,
  "floor": "ground",
  "children_present": false,
  "chronic_illness": null
}
```

`null` means unknown. Unknown must score as a **neutral default**, never as zero risk and
never as maximum risk. Record which fields were actually answered — the coordinator needs
to see that a high score rests on two answers, not six.

---

## 6. Core contracts

Freeze these first. Everything else is written against them.

```python
def normalize_phone(raw: str) -> str:
    """International format, no +, no spaces, no leading zero.
    03xx xxxxxxx        -> 923xxxxxxxxx
    92 3xx xxxxxxx      -> 923xxxxxxxxx
    +923xxxxxxxxx       -> 923xxxxxxxxx
    Raises ValueError on anything it cannot confidently normalize.
    """

def send_message(to: str, text: str) -> bool:
    """The ONLY outbound path. Applies, in order:
    1. kill switch check
    2. global message cap
    3. per-number rate limit
    4. DEMO_ALLOWLIST check when ALLOWLIST_ONLY=1
    5. 24h window check (skip and log if closed)
    6. MOCK_MODE -> write to console + mock_outbox table, return True
    Returns False and logs if the send was suppressed. Never raises.
    """

def emit(type: str, payload: dict, case_id: int | None = None) -> None:
    """Append to events, push to SSE subscribers. Never raises."""
```

### `extract_report()` output — PROPOSED

```json
{
  "category": "flood",
  "category_confidence": 0.9,
  "urgency": "high",
  "people_count": 3,
  "location_text": "Gulshan 13-D near the masjid",
  "zone_guess": "gulshan",
  "vulnerability": { "elderly": true, "alone": null, "floor": "ground" },
  "needs": ["evacuation"],
  "missing_fields": ["exact_location"],
  "next_question": "Can you send your location pin, or tell me the nearest landmark?"
}
```

`category` is one of: `flood`, `fire`, `medical`, `trapped`, `structural`, `other`.
`urgency` is one of: `low`, `medium`, `high`, `critical`.

### Scoring — PROPOSED

```
priority = (0.40 * vulnerability_score
          + 0.30 * urgency_score
          + 0.20 * hazard_exposure      # from hazards.py for that location
          + 0.10 * time_decay)          # older unhelped cases rise
          * confidence

confidence = clamp(source_factor * (0.6 + 0.1 * min(report_count, 4)), 0, 1)
```

Every case must carry a **plain-language `reason`** string explaining its rank. Judges will
ask why case 14 is above case 9, and "the model said so" loses. Example:
"Elderly person alone on a ground floor, water rising, 3 separate reports in 20 minutes."

### Merging

Reports of the same category within ~300 m and 30 minutes join one incident and raise its
confidence. Merging never lowers urgency — take the max.

---

## 7. WhatsApp protocol

All parsing is plain code. Case-insensitive. Always require the case ID on case commands —
one phone holds several cases during the demo, and a bare `ACCEPT` is ambiguous.

| Who | Command | Effect |
|---|---|---|
| Volunteer | `VOLUNTEER <area>` + pin | Register or update location, ask capabilities |
| Volunteer | `ON DUTY` / `OFF DUTY` | Start or end shift; `ON DUTY` reopens the 24h window |
| Volunteer | `ACCEPT <id>` | Claim the case, first wins |
| Volunteer | `DECLINE <id>` | Pass, trigger next volunteer sooner |
| Volunteer | `ARRIVED <id>` / `DONE <id>` | Advance lifecycle |
| Person | `1` / `2` after "Did help reach you?" | Confirm or re-open |
| Person | `STOP` | Opt out of all messages |
| Anyone | anything else | Treated as a help request → slot-filling |

A bare `ACCEPT` is rejected with: `Reply ACCEPT <case id>`.

### Message templates

**Offer** (no exact location, no contact):
```
Case 14 near Gulshan 13-D. Elderly person alone, ground floor, water rising.
Reply ACCEPT 14 to take it.
Assess from a safe place. Do not enter floodwater or burning buildings.
```

**After ACCEPT** (location and contact released here, and only here):
```
Case 14 is yours. Name: <first name>. Contact: <phone>. Location: <map link>.
Reply ARRIVED 14 when you get there, DONE 14 when finished.
```

**To the others:** `Case 14 was taken, thanks.`
**To the person on dispatch:** `A volunteer is on the way.`
**To the person after DONE:** `Did help reach you? Reply 1 yes, 2 no.`

---

## 8. Case lifecycle

```
proposed → approved → offered → accepted → on the way → arrived
         → person confirms → closed
```

Every arrow is an `emit()`. The timeline slider replays the whole chain.

**Re-escalation triggers** — case jumps to the top of the queue, tagged `re-opened`,
coordinator alerted:
- Nobody accepts within `VOLUNTEER_ACCEPT_TIMEOUT_S` (60–90 s in demo mode)
- Person replies `2` to "Did help reach you?"
- Person goes silent again after being marked helped
- A volunteer accepts but never sends `ARRIVED` within the set time

**Matching:**
1. Rank on-duty volunteers by straight-line distance to the case. Primary ring = 3 nearest.
2. In demo mode, the zone's primary phone is offered first; the other phone is ring 2.
3. First ring expires → offer ring 2 and alert the coordinator.
4. A volunteer already holding an active case is `busy` and skipped.

Straight-line distance, not routed travel time. This is a named trade-off in the README.

---

## 9. Two ways in — registration is optional

**This is a change from the original plan and it affects the root of `intake.py`.
Build it this way from the start or the webhook gets written twice.**

Website registration and `JOIN <code>` exist **only** to receive proactive alerts about
your area. They are optional. Anyone can message the Dastak number and get the full help
ladder with no account, no code, no area.

| | Registered (optional) | Direct help (default) |
|---|---|---|
| How | Website form, then `JOIN <code>` | Just message: "I need help" |
| Proactive check-ins | Yes | No |
| Can ask for help | Yes | Yes, same full ladder |
| Vulnerability data | From the form | Asked in chat, or unknown |
| Silence detection | Yes | Only after a case is opened |

**Direct-message flow:**
1. Any number can message first. They are a verified WhatsApp number, so the 24h window is
   open and we can reply.
2. Instant first reply — before the LLM, before any location: emergency number for the
   category, two or three safety steps, "Send your location pin or tell me your area."
3. `extract_report` with slot-filling works out category and missing details.
   **Ask at most 2 short questions. Location first.**
4. Optional vulnerability questions, only if the situation is not already urgent: anyone
   elderly or unable to move, are you alone, which floor. Unanswered = unknown = neutral.
5. Create the incident, enter the same ranked queue as everyone else.
6. After the case closes, one line inviting them to register for area alerts. Never pushy.

**No area, no pin:**
- They still get emergency numbers and safety steps immediately
- After 2 questions with no usable location → incident created as `location_unknown`, low
  confidence, flagged on the card
- A `location_unknown` case **cannot** be sent to volunteers or minted as a responder link
- Coordinator sees it at the top for a phone call; the bot keeps asking for a pin
- If a pin arrives later, the case upgrades in place and re-ranks

---

## 10. Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/webhook/whatsapp` | Verify + inbound. All command branching lives here via `intake.py` |
| POST | `/proposals/{id}/approve` | Body takes `channel`: `volunteers` \| `responder` \| `both` |
| GET | `/r/{token}` | Public read-only responder page |
| POST | `/cases/{id}/responderlink` | Create or refresh the link |
| GET | `/volunteers` | Coordinator view, unmasked numbers |
| GET | `/cases/{id}/dispatches` | Offers and their status |
| POST | `/cases/{id}/reopen` | Manual re-open |
| GET | `/` | Citizen home: "Need help? Message us on WhatsApp" + QR |
| GET | `/control` | Control room |
| GET | `/events` | SSE stream |
| POST | `/admin/killswitch` | Toggle |

### Responder page `/r/<token>` contents
Map with exact pin + Navigate button · category, urgency, report count, time since first
report, confidence · vulnerability summary and plain-language reason · protocol path used ·
live case status · Call button for the configured target.

No login. Token unguessable, expires after the event. First name only, unless the
coordinator explicitly opted to include a phone number for that handoff.

---

## 11. Coordinator UI

`Approve` means "send this out" and takes a channel choice:
- **Notify nearby volunteers** (default for non-critical)
- **Send to responder** (mints the link, copies or sends it)
- **Both**

The case drawer has a dispatch panel: who was offered, who accepted, timestamps. The map
shows volunteer pins **labelled as demo volunteers**.

Fire and medical are never volunteer-only — they always go to official numbers first.

The only manual steps in the whole loop are the approval and, if needed, a phone call.

---

## 12. Config

```bash
MOCK_MODE=1
DEMO_MODE=1
ALLOWLIST_ONLY=1
KILL_SWITCH=0

DEMO_VOLUNTEERS=            # JSON, prod only, NEVER committed
DEMO_ALLOWLIST=             # comma-separated normalized numbers
VOLUNTEER_OFFER_RING_SIZE=3
VOLUNTEER_ACCEPT_TIMEOUT_S=300   # demo mode: 60 to 90
VOLUNTEER_ARRIVE_TIMEOUT_S=900

EMERGENCY_FIRE=             # TODO: fill from an official source. Do not guess.
EMERGENCY_AMBULANCE=        # TODO
EMERGENCY_POLICE=           # TODO

WHATSAPP_TOKEN=
WHATSAPP_PHONE_ID=
WHATSAPP_VERIFY_TOKEN=
LLM_API_KEY=
GLOBAL_MESSAGE_CAP=500
```

`DEMO_VOLUNTEERS` format:
```json
[
 {"name":"Volunteer A","phone":"<A, normalized>","zones":["johar","gulshan","surjani"]},
 {"name":"Volunteer B","phone":"<B, normalized>","zones":["lyari","gujjar","korangi","dha"]}
]
```

**The repo is public. Real phone numbers live only in the prod environment variable, held
by Salman. In dev and mock mode use obviously fake numbers.** If you ever find a real
number in a file that is about to be committed, stop and say so.

---

## 13. Demo setup

A real volunteer network cannot exist in 24 hours. The volunteer pool is two team phones,
and we say so openly.

- Phone A covers Johar, Gulshan, Surjani. Phone B covers Lyari, Gujjar, Korangi, DHA.
  Each is the other's fallback ring.
- Seed several named volunteer profiles per zone, all routed to the two phones, so the map
  looks populated without lying. Label them "Demo volunteers (team phones)" in the UI.
- Both phone owners must agree to receive test messages.
- Both phones send `ON DUTY` right before presenting, to reopen the 24h window.

### Pre-demo checklist
- [ ] Both volunteer phones agreed to receive test messages
- [ ] Both numbers in `DEMO_VOLUNTEERS` on prod only, and in `DEMO_ALLOWLIST`
- [ ] Both numbers added as approved recipients in Meta, if still on a test number
- [ ] Both phones sent `ON DUTY`
- [ ] Both phones messaged the Dastak number within the last 24 hours
- [ ] Demo mode on, 60–90 s accept timeout
- [ ] Emergency numbers filled from official sources
- [ ] Responder link opened and tested on a phone
- [ ] Dry run of ACCEPT / ARRIVED / DONE with case IDs, including one forced timeout

### Demo script — dispatch section
1. Coordinator picks **Notify nearby volunteers** (or Both) and clicks Approve
2. A teammate's phone buzzes: "Case 14 near Gulshan 13-D…" They reply `ACCEPT 14`
3. The judge's phone shows "A volunteer is on the way"
4. Teammate replies `ARRIVED 14`, then `DONE 14`. Judge's phone asks "Did help reach you?"
5. Judge replies `1`. The timeline shows every step and the case closes
6. Optional: on a second case nobody accepts, the other phone gets it after the timeout,
   and the coordinator sees the re-escalation alert
7. Open the responder link on a phone to show the handoff artifact

Earlier in the script, a judge texts "I need help" from their own phone with **no setup, no
registration**, and appears in the queue. Registration is shown afterwards as the alerts
option, not the front door.

---

## 14. Definition of done

- [ ] A stranger with no registration gets the emergency number, is asked for a location,
      and appears in the ranked queue
- [ ] A volunteer can send `ON DUTY` and receive an offer
- [ ] `ACCEPT <id>` releases location and contact **only** to the accepting volunteer
- [ ] `ARRIVED` and `DONE` update the case and notify the person
- [ ] The person is asked "Did help reach you?" and a `2` re-opens the case
- [ ] An unaccepted offer expires, goes to the next ring, and alerts the coordinator
- [ ] The responder link opens on a phone with map, Navigate and case summary
- [ ] No volunteer phone number appears in the repo or on any public page
- [ ] Location-unknown cases are flagged and cannot be dispatched to volunteers
- [ ] The whole demo runs in `MOCK_MODE=1` with no network

---

## 15. Cut order

If time runs short, cut in this order:
1. Volunteer map pins
2. Multi-volunteer-per-zone seeding
3. The "Both" approve option
4. Hazard feeds (`hazards.py`) — fall back to a constant
5. Timeline slider → plain reverse-chronological event list

**Never cut:** the instant guidance reply, ACCEPT/ARRIVED/DONE, the responder link,
the honest labelling of simulated things.

---

## 16. README trade-offs (must ship)

- The volunteer pool is seeded with team phones. No real volunteer network was recruited,
  and the UI labels them as demo volunteers.
- Responder handoff is a shareable link, not a live integration with any emergency service
  or NGO.
- Seeded boats and ambulances are simulated.
- Matching is nearest-first by straight-line distance, not routed travel time.
- Volunteers are not vetted or trained in this prototype. A real deployment would need
  vetting, training and insurance.
- Fire and medical cases always point to official emergency numbers first.
- Scoring weights are hand-tuned, not learned. They are visible and adjustable.
- Connectivity: the system assumes WhatsApp reaches the person. It has no SMS or USSD
  fallback, which is a real gap given networks fail during disasters.

---

## 17. Rules for you, the coding agent

1. **Do not invent what you can ask about.** Anything marked PROPOSED in this file is a
   guess. Flag it, don't quietly build three modules on top of it.
2. **Do not put real phone numbers anywhere.** Not in seeds, not in tests, not in comments.
3. **Do not fill in emergency service numbers from memory.** Leave the config empty.
4. **Write `phone.py` and its tests first.** Normalization failures are silent and they
   will eat the demo.
5. **Mock mode is not an afterthought.** Every feature you add must work with
   `MOCK_MODE=1` and no network, on the same commit.
6. **Small commits with working state.** This is a hackathon; a broken main branch at
   hour 18 with one developer is fatal.
7. **When you touch `intake.py`, re-read section 9.** The unregistered path is the default
   path, not a special case.
8. **Prefer finishing a vertical slice over starting a horizontal layer.** One case moving
   end to end beats four half-built subsystems.
9. **Abdul Rehman's tickets** should be self-contained: tables, seed data, read-only
   endpoints, tests. Nothing that touches the webhook or the dispatch timers.
10. **If asked to make the system sound more capable than it is, refuse.** The honesty is
    the pitch.