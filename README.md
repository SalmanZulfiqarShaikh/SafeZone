# SafeZone

**WhatsApp-first emergency triage for Karachi.**

SafeZone finds who needs help during a disaster and gets that case to someone who can act, with everything they need. It is a prototype built by Team Nova Strike (Department of Computer Science, UBIT, University of Karachi) for CODE//CONNECT'26.


> **SafeZone does not rescue anyone.** It is not an emergency service. We have never pulled anyone out of anything, and we are not going to pretend otherwise. Fire and medical cases always point to the official number in the very first reply.

---

## The problem

During monsoon flooding, a fire, or a building collapse, people message whoever they can, and most of those messages reach nobody in a position to act. Official services are out there and overloaded. The bottleneck is not only a shortage of hands. It is sorting hundreds of messy, multilingual messages fast enough to know who needs help first.

SafeZone's job is to hand responders a complete case, not to compete with them.

## How it works

A person messages one WhatsApp number in English, Urdu, Roman Urdu, or a mix. No account, no form, nothing to install.

1. **Instant reply.** Safety steps and the official emergency number are sent straight away, before any AI step runs, so the first reply never waits on a model or a human.
2. **Neighbours are asked.** The nearest on-duty volunteers for that area get a short, privacy-safe brief. No name, no number.
3. **A coordinator is alerted.** The case is scored on urgency and who is at risk. Duplicate reports from the same street are merged into one case.
4. **A coordinator approves the handoff.** This is the one step that waits for a human. On approval, a case link (details plus a map) is sent to the relevant service, such as Rescue 1122 for medical, fire, and trapped-person cases.
5. **The loop is closed.** Volunteers reply `ACCEPT <case>`, `ARRIVED <case>`, and `DONE <case>`. When a case is marked done, SafeZone checks back with the original reporter on WhatsApp. If help did not arrive, the case goes back to the top of the queue.

### Area alerts (optional)

Anyone can sign up on the website with a first name and an area (78 areas to choose from). A code is sent through WhatsApp, and after that SafeZone warns them early when something is reported nearby. Reply `STOP` at any time to stop alerts. None of this is needed to ask for help.

### Control room

Coordinators log in to a live dashboard with a map of open cases, urgency scores with plain-language reasoning, volunteer status and area assignments, and the approve-and-dispatch step.

## What this is not

Worth knowing now, rather than finding out in the middle of something.

- **Not an emergency service.** We cannot send a boat or an ambulance ourselves.
- **Volunteers are neighbours, not professionals.** In this prototype they are not vetted, trained, or insured, and they are asked to assess from a safe place.
- **The handoff is a link, not an integration.** Responders get a page with everything on it. That is a message we send them, not a live connection into any organisation's system.
- **The volunteer pool is our own phones.** In the prototype, volunteers are the team, labelled as demo volunteers everywhere they appear. The emergency number shown in demos is a teammate's phone, not a real service.
- **Rescue 1122 is not affiliated with this project.** It is where cases are routed.

## Design notes

- **The AI is off the critical path.** The LLM only converts free text into structured fields. If the provider goes down, the system still accepts, ranks, locates, and routes cases.
- **One outbound gateway.** All outbound messages go through a single function with a kill switch, rate limiting, a domain allowlist, and WhatsApp's 24-hour delivery window checks.
- **Event sourcing.** Every state change is logged as an event, so a case's timeline can be replayed from the logs.
- **Offline tests.** The backend test suite runs without network access or API keys.

Coverage is 78 areas across all seven districts of Karachi, built from OpenStreetMap data.

## Tech stack

- **Backend:** Python 3.11+, FastAPI, Supabase (PostgreSQL), WhatsApp Cloud API
- **Frontend:** React 19, TypeScript, Vite, Tailwind CSS v4, Server-Sent Events
- **Deploy:** Docker on Fly.io

## Getting started

Create a `.env` file at the repository root from `.env.example` with your WhatsApp credentials, Supabase endpoints, and secrets.

### Backend

```bash
cd Backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

On startup the backend checks your configuration and prints any problems it finds.

### Frontend

```bash
cd Frontend
npm install
npm run dev
```

The dev server runs on port 5173 and proxies `/api` to the backend on port 8000.

### Tests

```bash
cd Backend
python -m pytest -q
```

### Utilities

```bash
python -m scripts.hash_password      # hash a control room password
python -m scripts.build_localities   # rebuild the OpenStreetMap locality data
```

## Team

Team Nova Strike, Department of Computer Science, UBIT, University of Karachi.

- Salman: [@SalmanZulfiqarShaikh](https://github.com/SalmanZulfiqarShaikh)
- Hussain: [@hussainabbas6706](https://github.com/hussainabbas6706)
- Abdul Rehman: [@mabdulrehmankhan666](https://github.com/mabdulrehmankhan666)
- Usaim: [@usaim35](https://github.com/usaim35)

For the community, by the community.


## Attribution

Locality and boundary data © OpenStreetMap contributors, available under the Open Database License (ODbL).
