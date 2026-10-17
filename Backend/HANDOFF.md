# SafeZone / SafeZone — Backend Handoff Guide

**Audience:** another Claude instance picking up the backend of this repository.
**Last verified:** 2026-10-17.
**Verification host:** Windows 10, Python 3.14.2 in `Backend/.venv`, Node 24.12.0.

Read this document completely before editing anything. It supersedes guesses. When
this document and your instincts disagree, this document wins. When this document is
silent, `AGENTS.md` is the source of truth.

---

## 0. TL;DR — the state of the backend

The backend is a **skeleton with hardened foundations and no business logic yet**.

- Folder restructure: **done**.
- In-memory database removal: **done**.
- Config hardening: **done**.
- Phone normalization: **done**, with tests.
- Database adapter: **done**, Supabase-only, typed errors.
- Schema: **done**, with RLS, CHECK constraints, indexes, and an `outbox` audit table.
- `main.py` SPA mounting: **done**, with API-prefix 404s.
- Backend tests: **17 passed** (`python -m pytest -q`).
- `python -c "import main"`: **passes**.
- Frontend `npm run build` and `npm run lint`: **pass**.
- **Routes: empty.** Only `/api/hello` exists.
- **Services: empty.**
- **`core/events.py`: does not exist** — even though `AGENTS.md` says it should be built first.
- **The app cannot currently boot** because `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` are
  absent from the root `.env`, and the `supabase` package is not installed in the venv.

The next piece of work is the vertical slice described in section 11:
`core/events.py` → `services/whatsapp.py` → `services/intake.py` → `routes/webhook.py`
→ one report reaching the ranked queue.

---

## 1. What the product is

**SafeZone** (renamed from Dastak on 2026-10-17; the new name is now used
consistently across the backend, docs and UI) is a WhatsApp-first disaster triage
system built for CODE//CONNECT'26,
Problem Statement 01 — Disaster Response. Target context: Karachi, Pakistan; flooding
is the primary scenario. Zones: Johar, Gulshan, Surjani, Lyari, Gujjar, Korangi, DHA.

The honest one-paragraph framing, which must survive into the UI, README and pitch:

> SafeZone does not rescue anyone. It finds who needs help and gets that case to someone
> who can act, with everything they need. Rescue is done by people and organisations on
> the ground. Our job is the last mile.

The help ladder:

1. **Instant guidance** — emergency number + safety steps, before the LLM and before
   location is known. Must never fail.
2. **Nearest volunteer** — coordinator approves; the 3 nearest on-duty, not-busy
   volunteers receive an offer; first `ACCEPT <case id>` wins.
3. **Responder handoff** — an unguessable read-only `/r/<token>` link for official
   responders/NGO desks. No integration is claimed.
4. **Close the loop** — "Did help reach you?" A `2` reopens the case at the top.

The LLM is **never** on the critical path. It only turns free-text reports into
structured fields. Every parser, router, matcher, timer and template is plain code.

---

## 2. Non-negotiables

These are bugs if violated. Condensed from `AGENTS.md` §2.

1. The first reply never promises rescue. It says help has been alerted. No ETA.
2. Fire and medical cases always surface the official emergency number first.
3. No medical advice — safety steps only.
4. Every volunteer offer says: assess from a safe place; do not enter floodwater or
   burning buildings.
5. Personal data (exact pin, first name, phone) is released **only after ACCEPT**.
6. Consent before sharing: tell the person their location and number are being shared.
7. `KILL_SWITCH` stops every outbound message.
8. Emergency numbers are never hardcoded from memory. Empty config must degrade
   loudly, not crash.
9. Every state change goes through `emit()`.
10. Every outbound message goes through `send_message()`.
11. Every phone number goes through `normalize_phone()` on the way in and to storage.
12. `MOCK_MODE` fakes WhatsApp sends and LLM extraction. Storage is **always**
    Supabase. There is no offline fallback database.
13. Do not put real phone numbers anywhere in the repo. Use obviously fake numbers in
    dev and tests. Never commit `.env`, `*.db`, or `Backend/static/`.
14. The webhook must always return HTTP 200. Meta retries anything else, which creates
    duplicate reports.

---

## 3. Verified state right now

Commands run from the repo root unless stated.

| Check | Result |
|---|---|
| `cd Backend && python -c "import main"` | **passes** |
| `cd Backend && python -m pytest -q` | **17 passed** |
| `cd Frontend && npm run build` | **passes** (writes `Backend/static/`) |
| `cd Frontend && npm run lint` | **passes** |
| `git status --short` | only 3 pre-existing frontend changes (see below) |
| `.env` tracked? | **no** — ignored correctly |
| `Backend/static/` tracked? | **no** — ignored correctly |
| `Backend/.venv/` tracked? | **no** — ignored correctly |

Pre-existing uncommitted frontend changes, not made by this review:

```
 M Frontend/index.html              # <title> changed from Dastak to SafeZone
 D Frontend/public/favicon.svg
 D Frontend/public/icons.svg
```

`Frontend/index.html` still references `/favicon.svg`, which is now deleted. That is a
404 in the browser, not a build failure.

### 3.1 Critical blockers to running the backend

1. **No Supabase configuration.** The root `.env` contains only:
   `WHATSAPP_PHONE_ID`, `WHATSAPP_TOKEN`, `WHATSAPP_VERIFY_TOKEN`.
   It does **not** contain `SUPABASE_URL` or `SUPABASE_SERVICE_KEY`.
   `core.db.get_db()` therefore raises `DbError` during FastAPI lifespan startup, and
   uvicorn will fail to start. This is deliberate fail-loud behavior, but it means the
   app is not runnable as-is.
2. **`supabase` is not installed** in `Backend/.venv` (verified:
   `ModuleNotFoundError: No module named 'supabase'`). Run
   `python -m pip install -r requirements.txt`.
3. **`pytest` was not installed** in the venv either. This review installed it so the
   suite could be verified. `requirements.txt` lists it, so a fresh
   `pip install -r requirements.txt` fixes that.
4. **No `core/events.py`.** `AGENTS.md` requires it before other modules.
5. **Routes and services are empty.** No webhook, no WhatsApp send, no intake, no
   dispatch, no scoring.

### 3.2 Startup report currently produced

`config.startup_report()` returns these warnings at boot (verified):

```
EMERGENCY_FIRE is not set — fire guidance will omit the official number.
EMERGENCY_AMBULANCE is not set — medical, trapped and flood guidance will omit the official number.
EMERGENCY_POLICE is not set — other guidance will omit the official number.
ALLOWLIST_ONLY is on but DEMO_ALLOWLIST is empty — every outbound message will be suppressed.
SUPABASE_URL or SUPABASE_SERVICE_KEY is missing — database access will raise DbError.
```

`MOCK_MODE` is true, so the WhatsApp-token warning is correctly absent. `KILL_SWITCH`
is off.

> Windows console note: em dashes in log strings render as `�` under the default
> codepage. If terminal output matters for the demo, change log strings to ASCII.

---

## 4. Repository layout

```
code-connect/
  .env                      # ignored; local secrets only
  .env.example              # STALE — see section 9
  .gitignore
  AGENTS.md                 # full product spec; source of truth
  CLAUDE.md                 # one-off task instructions used for the refactor
  CONTRIBUTING.md
  README.md                 # team table only; no setup instructions
  Backend/
    main.py
    requirements.txt
    HANDOFF.md              # this document
    core/
      __init__.py           # empty
      config.py
      db.py
      phone.py
      # events.py MISSING
    routes/
      __init__.py           # empty
    services/
      __init__.py           # empty
    data/
      __init__.py           # empty
      schema.sql
      # seed.py, protocol_graph.json MISSING
    tests/
      __init__.py           # empty
      test_phone.py
      test_db.py
    static/                 # generated by frontend build, gitignored
    .venv/                  # local, gitignored
  Frontend/
    index.html
    package.json
    vite.config.ts          # build outDir -> ../Backend/static
    src/
      main.tsx
      App.tsx               # routes: /, /control, /r/:token, /volunteers
      pages/{Home,ControlRoom,Responder,Volunteers}.tsx
      components/ui/button.tsx
      lib/utils.ts
```

`Backend/` is the **working directory**, not a Python package. There is deliberately
no `Backend/__init__.py`. Imports are absolute from inside `Backend/`:
`from core.config import ...`, never `from Backend.config import ...`.

---

## 5. How to run it

### 5.1 Backend

```bash
cd Backend
python -m pip install -r requirements.txt
# add SUPABASE_URL and SUPABASE_SERVICE_KEY to the repo-root .env first
uvicorn main:app --reload
```

The server must be started from inside `Backend/`, otherwise `main:app` is not
importable. The SPA is mounted only if `Backend/static/` exists **at import time**.

### 5.2 Frontend

```bash
cd Frontend
npm install
npm run dev      # Vite dev server, proxies /api and /events to 127.0.0.1:8000
npm run build    # tsc -b && vite build -> ../Backend/static
npm run lint
```

After `npm run build`, **restart uvicorn**. `mount_spa(app)` runs at import time, so a
server started before the build will not serve the SPA until restarted.

### 5.3 Environment variables

Loaded by `core/config.py` via `load_dotenv()`; `find_dotenv` walks up from
`Backend/core/` and finds the repo-root `.env`. Real values live only in `.env`
(ignored). Never print them.

| Variable | Default | Effect |
|---|---|---|
| `SUPABASE_URL` | `""` | Required. Dev/prod separation is just a different project URL. |
| `SUPABASE_SERVICE_KEY` | `""` | Required. Service key bypasses RLS; never ship to browser. |
| `MOCK_MODE` | `true` | Fakes WhatsApp sends and LLM extraction. Does not affect storage. |
| `DEMO_MODE` | `true` | Demo restrictions (volunteer rings, no real responder contact). |
| `ALLOWLIST_ONLY` | `true` | Only `DEMO_ALLOWLIST` numbers receive outbound messages. |
| `KILL_SWITCH` | `false` | Suppresses every outbound message. |
| `VOLUNTEER_OFFER_RING_SIZE` | `3` | Volunteers per offer ring. |
| `VOLUNTEER_ACCEPT_TIMEOUT_S` | `300` | Offer expiry; use 60–90 in a demo. |
| `VOLUNTEER_ARRIVE_TIMEOUT_S` | `900` | Accepted-but-never-arrived timeout. |
| `GLOBAL_MESSAGE_CAP` | `500` | Hard cap on messages. |
| `PER_NUMBER_RATE_LIMIT` | `10` | Messages per number per window. |
| `PER_NUMBER_RATE_WINDOW_S` | `300` | Rate-limit window. |
| `DEMO_ALLOWLIST` | `""` | Comma-separated normalized numbers. |
| `DEMO_VOLUNTEERS` | `[]` | JSON array; prod only; never commit real numbers. |
| `EMERGENCY_FIRE` | `""` | Official fire number; human must fill from official source. |
| `EMERGENCY_AMBULANCE` | `""` | Official ambulance number. |
| `EMERGENCY_POLICE` | `""` | Official police number. |
| `WHATSAPP_TOKEN` | `""` | Meta Cloud API token. |
| `WHATSAPP_PHONE_ID` | `""` | Meta phone number id. |
| `WHATSAPP_VERIFY_TOKEN` | `""` | Webhook GET verification token. |
| `LLM_API_KEY` | `""` | Provider API key. |
| `LLM_PROVIDER` | `groq` | Config, not code — swap on rate limits without a deploy. |
| `LLM_MODEL` | `""` | Provider model id. |

---

## 6. File-by-file walkthrough (full source)

Everything below is the exact current content. Treat it as the baseline. If you change
a file, update this document in the same commit, or note the delta in your commit
message.

### 6.1 `Backend/main.py`

```python
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from core import config
from core.db import get_db

logger = logging.getLogger("safezone.main")

BASE = Path(__file__).parent
STATIC_DIR = BASE / "static"

# Path prefixes that must never fall through to index.html. A mistyped API
# path returning a 200 HTML page is very hard to debug under time pressure.
API_PREFIXES = {"api", "webhook", "events"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    for problem in config.startup_report():
        logger.warning(problem)
    # Fail loudly here rather than silently switching data layers later.
    get_db()
    yield


app = FastAPI(title="SafeZone", lifespan=lifespan)


@app.get("/api/hello")
def hello():
    return {"message": "Backend Setup done! Waiting for the task"}


# API routers FIRST — mounts and the SPA catch-all are greedy.
# app.include_router(webhook_router)
# app.include_router(api_router)     # /api/*
# app.include_router(public_router)  # /api/... JSON only; UI is React


def mount_spa(app: FastAPI) -> None:
    """Serve the built React app and its client-side routes.

    Must be called last, after every ``include_router``. FastAPI resolves
    routes in registration order, so anything registered after the catch-all
    is silently unreachable.
    """
    if not STATIC_DIR.exists():
        logger.warning("Static build not found at %s; SPA is not served.", STATIC_DIR)
        return

    assets_dir = STATIC_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        first_segment = full_path.split("/", 1)[0]
        if first_segment in API_PREFIXES:
            raise HTTPException(status_code=404, detail="Not Found")

        root = STATIC_DIR.resolve()
        candidate = (root / full_path).resolve()
        if candidate.is_file() and root in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(root / "index.html")


mount_spa(app)
```

**What it does**

- Creates the FastAPI app with a lifespan that logs every `startup_report()` problem,
  then calls `get_db()` so a missing Supabase configuration fails at startup.
- Registers `/api/hello` before anything greedy.
- `mount_spa()` is called **last**, after every `include_router`. This is a hard rule:
  FastAPI matches routes in registration order and `/{full_path:path}` is greedy, so
  any router registered after it is silently dead.
- Inside the catch-all, paths whose first segment is `api`, `webhook`, or `events`
  return **404** rather than `index.html` with status 200.
- Real files inside `static/` are served; everything else gets `index.html` so React
  Router deep links work. The `root in candidate.parents` check prevents path
  traversal.

**Watch out**

- `STATIC_DIR.exists()` is evaluated when `main` is imported. Build the frontend
  before starting uvicorn, or restart after building.
- Only the `static/` existence is checked, not `index.html`. An empty `static/`
  directory makes unknown SPA routes raise a 500 from `FileResponse`, not a 404.
- No CORS middleware is installed. Development works because Vite proxies `/api` and
  `/events`; production is same-origin. Add CORS only if a cross-origin client appears.
- No webhook router exists yet. The always-200 rule is a contract for the future
  handler, not current behavior.

### 6.2 `Backend/core/config.py`

```python
"""Application configuration for SafeZone.

Handles environment loading, defaults and the checks that catch a demo-killing
misconfiguration before it happens. Values follow AGENTS.md §12; the unsafe
defaults (real WhatsApp sends, unset emergency numbers) are opt-in only.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Dict, List, Optional

from dotenv import load_dotenv

# Load .env from the project root (find_dotenv walks up from this file).
load_dotenv()

logger = logging.getLogger("safezone.config")


def _get_bool(key: str, default: bool) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _get_int(key: str, default: int) -> int:
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return int(val.strip())
    except ValueError:
        return default


# ─── DATABASE / SUPABASE ───────────────────────────────────────
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "").strip()

# ─── CORE FLAGS ────────────────────────────────────────────────
# MOCK_MODE fakes WhatsApp sends and LLM extraction. It does NOT select a
# database: storage is always Supabase (see core/db.py).
MOCK_MODE: bool = _get_bool("MOCK_MODE", True)

# DEMO_MODE restricts volunteer rings to the demo phones and disables real
# responder contact.
DEMO_MODE: bool = _get_bool("DEMO_MODE", True)

# ALLOWLIST_ONLY means only numbers in DEMO_ALLOWLIST receive outbound WhatsApp.
ALLOWLIST_ONLY: bool = _get_bool("ALLOWLIST_ONLY", True)

# KILL_SWITCH: emergency stop for all outbound messaging.
KILL_SWITCH: bool = _get_bool("KILL_SWITCH", False)

# ─── DISPATCH SETTINGS ─────────────────────────────────────────
VOLUNTEER_OFFER_RING_SIZE: int = _get_int("VOLUNTEER_OFFER_RING_SIZE", 3)
VOLUNTEER_ACCEPT_TIMEOUT_S: int = _get_int("VOLUNTEER_ACCEPT_TIMEOUT_S", 300)
VOLUNTEER_ARRIVE_TIMEOUT_S: int = _get_int("VOLUNTEER_ARRIVE_TIMEOUT_S", 900)
GLOBAL_MESSAGE_CAP: int = _get_int("GLOBAL_MESSAGE_CAP", 500)

# Per-number rate limiting, enforced inside send_message().
PER_NUMBER_RATE_LIMIT: int = _get_int("PER_NUMBER_RATE_LIMIT", 10)
PER_NUMBER_RATE_WINDOW_S: int = _get_int("PER_NUMBER_RATE_WINDOW_S", 300)

# ─── PHONE ALLOWLIST & DEMO VOLUNTEERS ─────────────────────────
_raw_allowlist = os.getenv("DEMO_ALLOWLIST", "").strip()
DEMO_ALLOWLIST: List[str] = [
    num.strip() for num in _raw_allowlist.split(",") if num.strip()
]

_raw_demo_volunteers = os.getenv("DEMO_VOLUNTEERS", "").strip()
DEMO_VOLUNTEERS: List[Dict] = []
if _raw_demo_volunteers:
    try:
        DEMO_VOLUNTEERS = json.loads(_raw_demo_volunteers)
    except Exception:
        logger.error("DEMO_VOLUNTEERS is not valid JSON; ignoring it.")

# ─── EMERGENCY NUMBERS ─────────────────────────────────────────
# Never hardcoded from memory: a human must fill these from an official
# source. When missing, guidance degrades rather than crashing the first reply.
EMERGENCY_FIRE: str = os.getenv("EMERGENCY_FIRE", "").strip()
EMERGENCY_AMBULANCE: str = os.getenv("EMERGENCY_AMBULANCE", "").strip()
EMERGENCY_POLICE: str = os.getenv("EMERGENCY_POLICE", "").strip()


def get_emergency_number(category: str) -> Optional[str]:
    """Return the official emergency number for ``category``, or ``None``.

    This is called from the instant guidance reply, which fires before the LLM
    and before location is known. It must never raise: a missing setting is a
    degraded message, not a failed emergency response.

    Category mapping:
        fire, structural      -> fire service
        medical, trapped, flood -> ambulance
        other / unknown       -> police
    """
    cat = (category or "").strip().lower()

    if cat in ("fire", "structural"):
        number, setting = EMERGENCY_FIRE, "EMERGENCY_FIRE"
    elif cat in ("medical", "trapped", "flood"):
        number, setting = EMERGENCY_AMBULANCE, "EMERGENCY_AMBULANCE"
    else:
        number, setting = EMERGENCY_POLICE, "EMERGENCY_POLICE"

    if not number:
        logger.error(
            "%s is not configured; %s guidance will omit the official number.",
            setting,
            cat or "unknown",
        )
        return None

    return number


# ─── WHATSAPP (Meta Cloud API) ─────────────────────────────────
WHATSAPP_TOKEN: str = os.getenv("WHATSAPP_TOKEN", "").strip()
WHATSAPP_PHONE_ID: str = os.getenv("WHATSAPP_PHONE_ID", "").strip()
WHATSAPP_VERIFY_TOKEN: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "").strip()

# ─── LLM ───────────────────────────────────────────────────────
LLM_API_KEY: str = os.getenv("LLM_API_KEY", "").strip()
# Provider is configuration, not code: swapping it when a provider rate-limits
# during the event must not require a deploy.
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "groq").strip().lower()
LLM_MODEL: str = os.getenv("LLM_MODEL", "").strip()


def startup_report() -> List[str]:
    """Return human-readable problems with the current configuration.

    These are the settings that silently break a demo. main.py logs every line
    as a warning at startup; none of them should be discovered live.
    """
    problems: List[str] = []

    if not EMERGENCY_FIRE:
        problems.append("EMERGENCY_FIRE is not set — fire guidance will omit the official number.")
    if not EMERGENCY_AMBULANCE:
        problems.append(
            "EMERGENCY_AMBULANCE is not set — medical, trapped and flood guidance "
            "will omit the official number."
        )
    if not EMERGENCY_POLICE:
        problems.append("EMERGENCY_POLICE is not set — other guidance will omit the official number.")

    if KILL_SWITCH:
        problems.append("KILL_SWITCH is on — every outbound message will be suppressed.")

    if not MOCK_MODE and not WHATSAPP_TOKEN:
        problems.append("MOCK_MODE is off but WHATSAPP_TOKEN is empty — WhatsApp sends will fail.")

    if ALLOWLIST_ONLY and not DEMO_ALLOWLIST:
        problems.append(
            "ALLOWLIST_ONLY is on but DEMO_ALLOWLIST is empty — every outbound "
            "message will be suppressed."
        )

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        problems.append(
            "SUPABASE_URL or SUPABASE_SERVICE_KEY is missing — database access "
            "will raise DbError."
        )

    return problems
```

**Rules encoded here**

- `get_emergency_number()` returns `Optional[str]` and **never raises**. It logs an
  error and degrades. Full mapping:
  - `fire`, `structural` → fire service
  - `medical`, `trapped`, `flood` → ambulance
  - everything else, including unknown/empty → police
- `MOCK_MODE` defaults to `true` (safe). Real sends are opt-in.
- `LLM_PROVIDER` defaults to `groq`; swapping providers is an env change.
- `startup_report()` covers exactly the demo-killing settings: missing emergency
  numbers, kill switch on, live mode without a token, allowlist-only with an empty
  allowlist, and missing Supabase config.

**Watch out**

- Values are read **once at import time**. Changing `.env` requires a process restart.
- `_get_int` silently falls back to the default on a malformed value. If you need
  loud validation, add it deliberately; do not assume a typo will be caught.
- `DEMO_VOLUNTEERS` parse failures are logged but do not stop startup. That is
  intentional for a demo, but it can leave the volunteer pool empty.

### 6.3 `Backend/core/db.py`

```python
"""Supabase database access for SafeZone.

One data layer only: PostgreSQL via Supabase. ``MOCK_MODE`` affects WhatsApp
sends and LLM extraction, never storage. Environment separation (dev vs prod)
is handled by pointing ``SUPABASE_URL`` at a different project.

A second, dict-based store used to live here. It was removed because it had
different semantics from PostgreSQL (no foreign keys, no constraints, no
joins, ``eq()`` as its only filter), so the demo rehearsed code that was not
the code that shipped.
"""

from __future__ import annotations

import logging
from typing import Any

from core.config import SUPABASE_SERVICE_KEY, SUPABASE_URL

logger = logging.getLogger("safezone.db")

_supabase_client = None


class DbError(RuntimeError):
    """Raised when Supabase is misconfigured or a database call fails."""


def _create_client(url: str, key: str):
    """Import and construct the Supabase client lazily (keeps imports cheap)."""
    from supabase import create_client

    return create_client(url, key)


def get_db():
    """Return the shared Supabase client.

    Raises:
        DbError: if ``SUPABASE_URL`` or ``SUPABASE_SERVICE_KEY`` is missing.
            There is deliberately no fallback store: a missing configuration
            must fail loudly rather than silently change the data semantics.
    """
    global _supabase_client

    if _supabase_client is not None:
        return _supabase_client

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise DbError(
            "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set. "
            "SafeZone has no in-memory fallback database."
        )

    try:
        _supabase_client = _create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    except Exception as exc:  # pragma: no cover - depends on the client lib
        raise DbError(f"Could not create Supabase client for {SUPABASE_URL}: {exc}") from exc

    logger.info("Supabase client initialized: %s", SUPABASE_URL)
    return _supabase_client


def execute(query: Any):
    """Execute a Supabase query builder, translating failures to ``DbError``.

    Callers should let ``DbError`` propagate and decide how to degrade. The
    WhatsApp webhook in particular must always answer HTTP 200 — Meta retries
    any other status, which produces duplicate reports.
    """
    try:
        return query.execute()
    except DbError:
        raise
    except Exception as exc:
        raise DbError(f"Supabase query failed: {exc}") from exc
```

**Rules encoded here**

- There is exactly **one** data layer. The old `InMemoryDB`, `InMemoryTable`,
  `InMemoryQueryBuilder`, `InMemoryInsertBuilder`, `InMemoryUpdateBuilder` and
  `_in_memory_db_instance` are gone. Do not reintroduce a fallback store. A second
  data layer means the demo rehearses code that is not the code that ships.
- `get_db()` returns a Supabase client, always. Missing `SUPABASE_URL` or
  `SUPABASE_SERVICE_KEY` raises `DbError`; there is no silent fallback.
- `execute(query)` is the only sanctioned way to run a query. It translates any
  client exception into `DbError`.

**Watch out**

- `get_db()` validates **configuration only**. Creating a client makes no network
  call, so a wrong URL or revoked key will not fail at startup — it fails on the first
  query. Do not claim startup proves connectivity.
- `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` are imported by value from `core.config`
  at module import. Runtime env changes do not propagate. Tests monkeypatch
  `core.db.SUPABASE_URL`, not `core.config.SUPABASE_URL`.
- Nothing enforces use of `execute()`. Code that calls `.execute()` on a builder
  directly bypasses the typed-error boundary. Review for this.
- The Supabase service key bypasses RLS. It must only exist server-side.

### 6.4 `Backend/core/phone.py`

```python
"""Phone normalization contract for SafeZone.

Strictly follows AGENTS.md §2.3 Rule 4 and §6.
Every phone number goes through normalize_phone() on the way in and on the way
to storage. Format: international, no '+', no spaces, no leading zero.

Pakistani mobile numbers only. Rejecting foreign numbers is deliberate: it is
one less silent failure on a demo that handles real numbers badly.
"""

import re
from typing import Optional


class PhoneError(ValueError):
    """Raised when a phone number cannot be confidently normalized."""


def normalize_phone(raw: str) -> str:
    """Normalize a phone number to standard international format.

    Accepts formats such as:
      03xx xxxxxxx        -> 923xxxxxxxxx
      03xxxxxxxxx         -> 923xxxxxxxxx
      92 3xx xxxxxxx      -> 923xxxxxxxxx
      +923xxxxxxxxx       -> 923xxxxxxxxx
      923xxxxxxxxx        -> 923xxxxxxxxx
      (0300) 123 4567     -> 923001234567

    Raises:
        PhoneError: On anything it cannot confidently normalize.
    """
    if not raw or not isinstance(raw, str):
        raise PhoneError("Phone number must be a non-empty string")

    # Strip whitespace, hyphens, parentheses and plus signs.
    cleaned = re.sub(r"[\s\-\(\)\+]", "", raw.strip())

    # Only digits should remain.
    if not cleaned.isdigit():
        raise PhoneError(f"Phone number contains invalid non-numeric characters: '{raw}'")

    # Case 1: Local Pakistani format starting with 03 (e.g. 03001234567, 11 digits)
    if cleaned.startswith("03") and len(cleaned) == 11:
        return "92" + cleaned[1:]

    # Case 2: International format starting with 923 (e.g. 923001234567, 12 digits)
    if cleaned.startswith("923") and len(cleaned) == 12:
        return cleaned

    # Case 3: International format with 00923 (e.g. 00923001234567, 14 digits)
    if cleaned.startswith("00923") and len(cleaned) == 14:
        return cleaned[2:]

    # Case 4: 10-digit number starting with 3 (missing country code and leading 0)
    if cleaned.startswith("3") and len(cleaned) == 10:
        return "92" + cleaned

    raise PhoneError(f"Cannot confidently normalize phone number: '{raw}' (cleaned: '{cleaned}')")


def try_normalize(raw: str) -> Optional[str]:
    """Non-raising variant of :func:`normalize_phone`.

    The webhook must not return a 500 for a malformed number; it answers with a
    clarification question instead. Returns ``None`` on any failure.
    """
    try:
        return normalize_phone(raw)
    except PhoneError:
        return None


def mask(phone: str) -> str:
    """Mask every digit except the last four, for logs and terminal output.

    ``923001234567`` becomes ``********4567``. Full numbers must never reach
    logs or terminal scrollback.
    """
    digits = "".join(ch for ch in phone if ch.isdigit()) if isinstance(phone, str) else ""
    if not digits:
        return "****"
    visible = digits[-4:]
    return "*" * (len(digits) - len(visible)) + visible
```

**Contract**

- Output is international, no `+`, no spaces, no leading zero: `923xxxxxxxxx`.
- Accepted shapes: `03xxxxxxxxx` (11), `923xxxxxxxxx` (12), `00923...` (14),
  `3xxxxxxxxx` (10), with whitespace, `-`, `(`, `)`, `+` ignored.
- Pakistani mobile numbers only. Foreign numbers are deliberately rejected.
- `PhoneError` subclasses `ValueError`, so older `except ValueError` code still works.
- `try_normalize()` returns `None` instead of raising. The webhook uses this.
- `mask()` keeps the last four digits and replaces the rest with `*`. Use it in
  **every** log line. `mask("")` returns `"****"`.
- Idempotency: normalizing an already-normalized number returns it unchanged.

**Watch out**

- The cleaner only strips whitespace, hyphens, parentheses and `+`. Dots, slashes
  and Unicode digits are not accepted. Keep it strict unless a real input source
  requires more.
- `mask()` masks digits in place, so `mask("+92 300 123-4567")` is `"********4567"`
  (punctuation is dropped). That is intended for logs.
- Never log the raw `raw` value in an error message that reaches a user or a shared
  log. The existing `PhoneError` messages include the raw input; either keep those
  internal or switch to `mask()` when logging them.

### 6.5 `Backend/data/schema.sql`

```sql
-- ─────────────────────────────────────────────────────────────────────────────
-- SafeZone Database Schema for Supabase (PostgreSQL)
-- Strictly implements AGENTS.md §5 (Data model) and §2 (Non-negotiables)
-- ─────────────────────────────────────────────────────────────────────────────

-- Enable pgcrypto / uuid if needed
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ─── 1. ZONES ────────────────────────────────────────────────────────────────
-- Karachi priority flood zones: Johar, Gulshan, Surjani, Lyari, Gujjar, Korangi, DHA
CREATE TABLE IF NOT EXISTS zones (
    id TEXT PRIMARY KEY,                       -- e.g. 'gulshan', 'surjani', 'lyari'
    name TEXT NOT NULL,                        -- e.g. 'Gulshan-e-Iqbal'
    risk_level TEXT DEFAULT 'normal',          -- 'normal' | 'elevated' | 'critical'
    boundary_geojson JSONB,                    -- GeoJSON polygon/multipolygon
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── 2. PEOPLE ───────────────────────────────────────────────────────────────
-- A person we know about. Created on first contact, registered or not.
CREATE TABLE IF NOT EXISTS people (
    id BIGSERIAL PRIMARY KEY,
    phone TEXT UNIQUE NOT NULL,                -- Normalized (923xxxxxxxxx), no +, no leading zero
    first_name TEXT,
    zone_id TEXT REFERENCES zones(id) ON DELETE SET NULL,
    lat DOUBLE PRECISION,
    lng DOUBLE PRECISION,
    is_registered BOOLEAN DEFAULT FALSE,       -- Registered via web portal
    wants_alerts BOOLEAN DEFAULT FALSE,
    person_vuln JSONB DEFAULT '{}'::jsonb,     -- {"elderly": bool, "alone": bool, "floor": "ground", ...}
    window_open_until TIMESTAMPTZ,             -- ISO8601, 24h WhatsApp window expiration
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_people_phone ON people(phone);
CREATE INDEX IF NOT EXISTS idx_people_zone ON people(zone_id);

-- ─── 3. INCIDENTS ────────────────────────────────────────────────────────────
-- A real-world situation. Reports merge into it.
CREATE TABLE IF NOT EXISTS incidents (
    id BIGSERIAL PRIMARY KEY,
    category TEXT NOT NULL,                    -- flood | fire | medical | trapped | structural | other
    lat DOUBLE PRECISION,
    lng DOUBLE PRECISION,
    zone_id TEXT REFERENCES zones(id) ON DELETE SET NULL,
    location_known BOOLEAN DEFAULT FALSE,
    report_count INT DEFAULT 1,
    confidence DOUBLE PRECISION DEFAULT 0.6,
    urgency DOUBLE PRECISION DEFAULT 0.5,
    priority_score DOUBLE PRECISION DEFAULT 0.0,
    status TEXT DEFAULT 'open',                -- 'open' | 'active' | 'resolved' | 'closed'
    dispatch_status TEXT DEFAULT 'none',       -- 'none' | 'offered' | 'accepted' | 'on_way' | 'arrived' | 'confirmed' | 'closed' | 'reopened'
    reopened BOOLEAN DEFAULT FALSE,
    reopen_reason TEXT,
    first_report_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_update_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);
CREATE INDEX IF NOT EXISTS idx_incidents_zone ON incidents(zone_id);

-- ─── 4. REPORTS ──────────────────────────────────────────────────────────────
-- One inbound report. Multiple reports merge into one incident.
CREATE TABLE IF NOT EXISTS reports (
    id BIGSERIAL PRIMARY KEY,
    person_id BIGINT REFERENCES people(id) ON DELETE SET NULL,
    incident_id BIGINT REFERENCES incidents(id) ON DELETE SET NULL,
    raw_text TEXT,
    source TEXT NOT NULL DEFAULT 'whatsapp',   -- 'whatsapp' | 'web'
    source_factor DOUBLE PRECISION NOT NULL DEFAULT 1.0, -- whatsapp 1.0, web 0.7
    category TEXT,                             -- flood | fire | medical | trapped | other
    lat DOUBLE PRECISION,
    lng DOUBLE PRECISION,
    zone_id TEXT REFERENCES zones(id) ON DELETE SET NULL,
    location_known BOOLEAN DEFAULT FALSE,
    extraction JSONB DEFAULT '{}'::jsonb,      -- Raw structured output from extract_report
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reports_incident ON reports(incident_id);
CREATE INDEX IF NOT EXISTS idx_reports_person ON reports(person_id);

-- ─── 5. CASES ────────────────────────────────────────────────────────────────
-- Coordinator-facing unit of work. One per incident in this prototype.
CREATE TABLE IF NOT EXISTS cases (
    id BIGSERIAL PRIMARY KEY,
    incident_id BIGINT REFERENCES incidents(id) ON DELETE CASCADE,
    person_id BIGINT REFERENCES people(id) ON DELETE SET NULL,
    priority_score DOUBLE PRECISION DEFAULT 0.0,
    reason TEXT,                               -- Plain-language justification shown to judges & coordinators
    vuln_summary TEXT,
    protocol_path JSONB DEFAULT '[]'::jsonb,   -- Array of protocol nodes traversed
    status TEXT DEFAULT 'proposed',            -- 'proposed' | 'approved' | 'rejected' | 'resolved'
    dispatch_status TEXT DEFAULT 'none',       -- none | offered | accepted | on_way | arrived | confirmed | closed | reopened
    reopened BOOLEAN DEFAULT FALSE,
    reopen_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status);
CREATE INDEX IF NOT EXISTS idx_cases_dispatch_status ON cases(dispatch_status);
CREATE INDEX IF NOT EXISTS idx_cases_priority ON cases(priority_score DESC);

-- ─── 6. EVENTS ───────────────────────────────────────────────────────────────
-- Immutable audit log for SSE and replay slider. Every state change goes through emit().
CREATE TABLE IF NOT EXISTS events (
    id BIGSERIAL PRIMARY KEY,
    type TEXT NOT NULL,                        -- ReportReceived, CaseApproved, VolunteerAccepted, etc.
    case_id BIGINT REFERENCES cases(id) ON DELETE SET NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
CREATE INDEX IF NOT EXISTS idx_events_case_id ON events(case_id);
CREATE INDEX IF NOT EXISTS idx_events_created_at ON events(created_at);

-- ─── 7. VOLUNTEERS ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS volunteers (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,                       -- Normalized (923xxxxxxxxx); multiple demo rows may share one
    zone_ids JSONB NOT NULL DEFAULT '[]'::jsonb, -- e.g. ["gulshan", "johar"]
    capabilities JSONB NOT NULL DEFAULT '[]'::jsonb, -- ["foot", "car", "boat", "first_aid"]
    lat DOUBLE PRECISION,
    lng DOUBLE PRECISION,
    status TEXT DEFAULT 'off_duty',            -- 'off_duty' | 'on_duty' | 'busy'
    window_open_until TIMESTAMPTZ,
    is_demo BOOLEAN DEFAULT TRUE,              -- Demo volunteers labelled as simulated in UI
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_volunteers_phone ON volunteers(phone);
CREATE INDEX IF NOT EXISTS idx_volunteers_status ON volunteers(status);

-- ─── 8. DISPATCHES ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dispatches (
    id BIGSERIAL PRIMARY KEY,
    case_id BIGINT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    volunteer_id BIGINT NOT NULL REFERENCES volunteers(id) ON DELETE CASCADE,
    ring INT NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'offered',    -- offered | accepted | on_way | arrived | done | declined | expired
    offered_at TIMESTAMPTZ DEFAULT NOW(),
    accepted_at TIMESTAMPTZ,
    arrived_at TIMESTAMPTZ,
    done_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_dispatches_case ON dispatches(case_id);
CREATE INDEX IF NOT EXISTS idx_dispatches_volunteer ON dispatches(volunteer_id);
CREATE INDEX IF NOT EXISTS idx_dispatches_status ON dispatches(status);

-- ─── 9. RESPONDER LINKS ──────────────────────────────────────────────────────
-- Unguessable tokenized links for official emergency service / NGO desk handoffs.
CREATE TABLE IF NOT EXISTS responder_links (
    token TEXT PRIMARY KEY,                    -- Unguessable urlsafe token
    case_id BIGINT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    target_label TEXT,                         -- e.g. 'Edhi Ambulance Central Desk'
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

-- ─── 10. OUTBOX ──────────────────────────────────────────────────────────────
-- Every outbound message in both modes. This is the message audit log and the
-- primary debugging surface when the demo misbehaves.
-- Rename the old mock-only table first, so CREATE IF NOT EXISTS below does not
-- create an empty replacement alongside it.
DO $$
BEGIN
    IF to_regclass('public.mock_outbox') IS NOT NULL
       AND to_regclass('public.outbox') IS NULL THEN
        ALTER TABLE public.mock_outbox RENAME TO outbox;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS outbox (
    id BIGSERIAL PRIMARY KEY,
    to_phone TEXT NOT NULL,
    text TEXT NOT NULL,
    status TEXT DEFAULT 'sent',
    mode TEXT NOT NULL DEFAULT 'mock',         -- 'mock' | 'live'
    suppressed_reason TEXT,                    -- why send_message() did not send
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Bring pre-existing outbox tables up to the current shape.
ALTER TABLE outbox ADD COLUMN IF NOT EXISTS mode TEXT NOT NULL DEFAULT 'mock';
ALTER TABLE outbox ADD COLUMN IF NOT EXISTS suppressed_reason TEXT;

DROP INDEX IF EXISTS idx_mock_outbox_phone;
CREATE INDEX IF NOT EXISTS idx_outbox_phone ON outbox(to_phone);

-- ─── 11. CONSTRAINT HARDENING ────────────────────────────────────────────────
-- A typo in a status column otherwise writes an invalid value and the case
-- silently stalls with no error. DO blocks keep this re-runnable.
DO $$
BEGIN
    ALTER TABLE incidents ADD CONSTRAINT chk_incidents_status
        CHECK (status IN ('open', 'active', 'resolved', 'closed'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE cases ADD CONSTRAINT chk_cases_status
        CHECK (status IN ('proposed', 'approved', 'rejected', 'resolved'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE cases ADD CONSTRAINT chk_cases_dispatch_status
        CHECK (dispatch_status IN (
            'none', 'offered', 'accepted', 'on_way', 'arrived',
            'confirmed', 'closed', 'reopened'
        ));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE dispatches ADD CONSTRAINT chk_dispatches_status
        CHECK (status IN (
            'offered', 'accepted', 'on_way', 'arrived',
            'done', 'declined', 'expired'
        ));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE volunteers ADD CONSTRAINT chk_volunteers_status
        CHECK (status IN ('off_duty', 'on_duty', 'busy'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE outbox ADD CONSTRAINT chk_outbox_mode
        CHECK (mode IN ('mock', 'live'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Re-escalation must never offer the same case to the same volunteer twice.
CREATE UNIQUE INDEX IF NOT EXISTS idx_dispatches_case_volunteer
    ON dispatches(case_id, volunteer_id);

-- The queue sorts on this.
CREATE INDEX IF NOT EXISTS idx_incidents_priority_score
    ON incidents(priority_score DESC);

-- ─── 12. ROW LEVEL SECURITY ──────────────────────────────────────────────────
-- Supabase exposes every table over PostgREST, and the anon key ships in
-- frontend code. RLS with zero policies blocks the anon key completely, while
-- the backend's service key bypasses RLS. All access goes through FastAPI;
-- nothing is read from the browser. Do not add policies without re-reading this.
ALTER TABLE zones            ENABLE ROW LEVEL SECURITY;
ALTER TABLE people           ENABLE ROW LEVEL SECURITY;
ALTER TABLE incidents        ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports          ENABLE ROW LEVEL SECURITY;
ALTER TABLE cases            ENABLE ROW LEVEL SECURITY;
ALTER TABLE events           ENABLE ROW LEVEL SECURITY;
ALTER TABLE volunteers       ENABLE ROW LEVEL SECURITY;
ALTER TABLE dispatches       ENABLE ROW LEVEL SECURITY;
ALTER TABLE responder_links  ENABLE ROW LEVEL SECURITY;
ALTER TABLE outbox           ENABLE ROW LEVEL SECURITY;
```

**Why the hardening exists**

- **RLS with zero policies** blocks the anon key entirely. The browser never talks
  to PostgREST. All access is through FastAPI with the service key. Without this,
  anyone with the anon key could read `people`, including phone numbers.
- **CHECK constraints** stop a typo from writing an invalid status and silently
  stalling a case:
  - `incidents.status`: `open | active | resolved | closed`
  - `cases.status`: `proposed | approved | rejected | resolved`
  - `cases.dispatch_status`: `none | offered | accepted | on_way | arrived | confirmed | closed | reopened`
  - `dispatches.status`: `offered | accepted | on_way | arrived | done | declined | expired`
  - `volunteers.status`: `off_duty | on_duty | busy`
  - `outbox.mode`: `mock | live`
- **Unique index `dispatches(case_id, volunteer_id)`** prevents re-escalation from
  offering the same case to the same volunteer twice.
- **`incidents(priority_score DESC)`** supports the ranked queue.
- **`outbox`** (renamed from `mock_outbox`) is the audit log in both modes, with
  `mode` and `suppressed_reason` for debugging why a message was not sent.

**Watch out**

- The unique index means dispatch code must **update** the existing `(case_id,
  volunteer_id)` row when re-offering, or use an upsert. A blind insert will now
  raise a uniqueness error.
- The CHECK constraints are added with `DO ... EXCEPTION WHEN duplicate_object`.
  If a table already contains a value outside the allowed list, the `ALTER TABLE`
  fails with a check violation and the script aborts. Clean data first, or split
  the constraint migration from the table creation.
- If both `mock_outbox` and `outbox` exist, the rename block does nothing and leaves
  `mock_outbox` in place. Inspect and migrate manually.
- RLS is enabled on all ten tables. **Do not add policies** unless the architecture
  changes to allow browser access. The backend service key is the only reader.
- `reports.category`'s comment omits `structural`; `incidents.category` includes it.
  No CHECK on category exists yet. Add one only after confirming the value list.
- No CHECK on `incidents.dispatch_status`, although it mirrors `cases`. Not in scope
  for the previous task; consider adding it.
- `people.phone` has both `UNIQUE` and a separate index; the index is redundant.
  Harmless.

### 6.6 `Backend/tests/test_phone.py`

```python
import pytest

from core.phone import PhoneError, mask, normalize_phone, try_normalize


def test_standard_pakistan_mobile_with_leading_zero():
    assert normalize_phone("03001234567") == "923001234567"
    assert normalize_phone("0345-9876543") == "923459876543"
    assert normalize_phone("0321 1122334") == "923211122334"


def test_plus_92_format():
    assert normalize_phone("+923001234567") == "923001234567"
    assert normalize_phone("+92 345 9876543") == "923459876543"
    assert normalize_phone("+92 (300) 123-4567") == "923001234567"


def test_already_normalized():
    assert normalize_phone("923001234567") == "923001234567"


def test_double_zero_prefix():
    assert normalize_phone("00923001234567") == "923001234567"


def test_short_ten_digit_pakistan():
    assert normalize_phone("3001234567") == "923001234567"


def test_parenthesised_input():
    assert normalize_phone("(0300) 123 4567") == "923001234567"


def test_whitespace_padded_input():
    assert normalize_phone("   0300 123 4567   ") == "923001234567"


def test_idempotency():
    once = normalize_phone("+92 (300) 123-4567")
    assert normalize_phone(once) == once


def test_invalid_formats_raise_phone_error():
    with pytest.raises(PhoneError):
        normalize_phone("")

    with pytest.raises(PhoneError):
        normalize_phone("   ")

    with pytest.raises(PhoneError):
        normalize_phone("03001234")  # too short

    with pytest.raises(PhoneError):
        normalize_phone("0300123456789")  # too long

    with pytest.raises(PhoneError):
        normalize_phone("02131234567")  # landline, not mobile starting with 3

    with pytest.raises(PhoneError):
        normalize_phone("abc03001234567")

    with pytest.raises(PhoneError):
        normalize_phone(None)

    with pytest.raises(PhoneError):
        normalize_phone(923001234567)  # non-string input


def test_phone_error_is_a_value_error():
    # Callers written against the old contract still catch it.
    with pytest.raises(ValueError):
        normalize_phone("nope")


def test_try_normalize_returns_none_instead_of_raising():
    assert try_normalize("03001234567") == "923001234567"
    assert try_normalize("not a number") is None
    assert try_normalize("") is None
    assert try_normalize(None) is None


def test_mask_keeps_only_last_four_digits():
    assert mask("923001234567") == "********4567"
    assert mask("+92 300 123-4567") == "********4567"
    assert mask("03001234567").endswith("4567")
    assert mask("03001234567").count("*") == 7
    assert mask("") == "****"
```

### 6.7 `Backend/tests/test_db.py`

```python
import pytest

import core.db as db
from core.db import DbError, execute, get_db


@pytest.fixture(autouse=True)
def reset_client(monkeypatch):
    """Never reuse a cached client (and never touch the network) in tests."""
    monkeypatch.setattr(db, "_supabase_client", None)


def test_get_db_raises_without_credentials(monkeypatch):
    monkeypatch.setattr(db, "SUPABASE_URL", "")
    monkeypatch.setattr(db, "SUPABASE_SERVICE_KEY", "")

    with pytest.raises(DbError, match="SUPABASE_URL"):
        get_db()


def test_get_db_raises_without_service_key(monkeypatch):
    monkeypatch.setattr(db, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(db, "SUPABASE_SERVICE_KEY", "")

    with pytest.raises(DbError, match="SUPABASE_SERVICE_KEY"):
        get_db()


def test_get_db_creates_and_caches_client(monkeypatch):
    monkeypatch.setattr(db, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(db, "SUPABASE_SERVICE_KEY", "test-service-key")

    calls = []

    def fake_create_client(url, key):
        calls.append((url, key))
        return object()

    monkeypatch.setattr(db, "_create_client", fake_create_client)

    first = get_db()
    second = get_db()

    assert first is second
    assert calls == [("https://example.supabase.co", "test-service-key")]


def test_execute_wraps_client_errors():
    class BrokenQuery:
        def execute(self):
            raise ValueError("boom")

    with pytest.raises(DbError, match="boom"):
        execute(BrokenQuery())


def test_execute_returns_query_result():
    class WorkingQuery:
        def execute(self):
            return "result"

    assert execute(WorkingQuery()) == "result"
```

**Coverage note:** `test_phone.py` covers `0092`, parenthesised input, whitespace,
idempotency, non-string input, `PhoneError` inheritance, `try_normalize`, and
`mask()` keeping the last four. `test_db.py` never touches the network. Add tests for
`core/config.py` when you change emergency mapping or `startup_report()`.

### 6.8 `Backend/requirements.txt`

```
# Direct dependencies only. Run `pip freeze` for a lock file; do not commit it here.
fastapi
uvicorn[standard]
httpx
python-dotenv
supabase
openai
pytest
```

Direct dependencies only, deliberately unpinned. Do not add transitive packages here.

### 6.9 Empty package files

These are intentionally empty and must exist so the directories are importable:

```
Backend/core/__init__.py
Backend/routes/__init__.py
Backend/services/__init__.py
Backend/data/__init__.py
Backend/tests/__init__.py
```

There is **no** `Backend/__init__.py`. `Backend/` is the working directory, not a
package.

---

## 7. Contracts to preserve

Signatures other modules will be written against. Freeze them before adding callers.

```python
# core/phone.py
def normalize_phone(raw: str) -> str: ...        # raises PhoneError(ValueError)
def try_normalize(raw: str) -> str | None: ...
def mask(phone: str) -> str: ...

# core/db.py
def get_db(): ...                                # Supabase client; raises DbError
def execute(query: Any): ...                     # query.execute() with DbError wrapping

# core/config.py
def get_emergency_number(category: str) -> str | None: ...
def startup_report() -> list[str]: ...
```

Still to be written (agree the signature before two agents build against it):

```python
# core/events.py
def emit(type: str, payload: dict, case_id: int | None = None) -> None:
    """Append to events, push to SSE subscribers. Never raises."""

# services/whatsapp.py
def send_message(to: str, text: str) -> bool:
    """The ONLY outbound path. Guards, in order: kill switch, global cap,
    per-number rate limit, allowlist, 24h window, MOCK_MODE. Returns False and
    logs when suppressed. Never raises."""

# services/dispatch.py
def offer_case(case_id: int, ring: int) -> list[int]:
    """Return volunteer ids offered the case."""
```

Rules that ride on these contracts:

- Every state change calls `emit()`. If it does not emit, it did not happen.
- Every outbound message calls `send_message()`. No direct Meta API calls elsewhere.
- Every inbound and stored phone goes through `normalize_phone()`.
- The webhook handler always returns 200, even on internal failure. Log the failure
  and answer 200 so Meta does not retry and duplicate the report.

---

## 8. Data model invariants

Tables: `zones`, `people`, `incidents`, `reports`, `cases`, `events`, `volunteers`,
`dispatches`, `responder_links`, `outbox`.

- `people.phone` is unique and normalized. `volunteers.phone` is **not** unique:
  several named demo volunteers intentionally share the two team phones.
- `incidents` merge reports; `cases` are the coordinator-facing unit (one per incident
  in this prototype).
- Case lifecycle: `proposed → approved → offered → accepted → on_way → arrived →
  person confirms → closed`.
- Re-escalation triggers: offer timeout, person replies `2`, silence after being
  marked helped, accepted-but-never-arrived.
- A `location_unknown` case cannot be sent to volunteers or minted as a responder
  link.
- `dispatches(case_id, volunteer_id)` is unique. Re-offer must update, not insert.
- `outbox` records every outbound message in both modes. `mode` is `mock` or `live`;
  `suppressed_reason` explains a non-send. This is the first place to look when the
  demo misbehaves.
- `events` is the immutable audit log and the source for the timeline replay.
- RLS is enabled on all tables with zero policies. Only the service key reads/writes.

Event types expected from `AGENTS.md` §5.3:

```
ReportReceived, ReportMerged, IncidentCreated, CaseProposed, CaseApproved,
VolunteerRegistered, VolunteerOnDuty, VolunteerOffered, VolunteerAccepted,
VolunteerArrived, VolunteerDone, DispatchExpired, ResponderLinkSent,
PersonConfirmedHelp, CaseReopened, CaseClosed, KillSwitchToggled
```

---

## 9. Review findings and gotchas

Ordered roughly by how likely they are to waste time.

1. **App boot is blocked by missing Supabase config.** Add `SUPABASE_URL` and
   `SUPABASE_SERVICE_KEY` to the root `.env`, then `pip install -r requirements.txt`.
   Without this, `get_db()` raises in lifespan and uvicorn exits.
2. **`supabase` and `pytest` were missing from the venv.** This review installed
   `pytest` to verify the suite. Install the full requirements file to get
   `supabase`.
3. **`core/events.py` does not exist.** `AGENTS.md` says nothing proceeds until it
   lands, because almost every module imports `emit()`.
4. **Routes and services are empty.** No webhook, WhatsApp client, intake, dispatch,
   risk, merge, silence, hazards, seed, or protocol graph. The backend currently
   serves one hardcoded `/api/hello` plus the SPA.
5. **`.env.example` is stale.** It contains only `GROQ_API_KEY = ...`, which is not a
   variable the code reads. It should document the section 5.3 variables (with empty
   values, no secrets).
6. **README has no setup or run instructions.** It is only a team table. Add the
   commands from section 5, and state that the app runs as
   `uvicorn main:app --reload` from inside `Backend/`.
7. **`execute()` is defined but unused.** New code must use it instead of calling
   `builder.execute()` directly, or the typed-error boundary is lost.
8. **`get_db()` does not prove connectivity.** It only checks that config strings
   exist. A bad URL or key fails on the first query, not at startup.
9. **Static mount is import-time.** Build the frontend before starting uvicorn, or
   restart after building. An empty `static/` directory results in a 500 from
   `FileResponse` for unknown SPA routes, because only the directory is checked.
10. **Brand renamed.** The earlier inconsistency is resolved: the name is now
    `SafeZone` in the FastAPI title, logger names (`safezone.*`), docs, schema header
    and UI. The Supabase project names in the docs were changed to `safezone-dev` /
    `safezone-prod` to match.
11. **Deleted favicon.** `Frontend/index.html` references `/favicon.svg`, but
    `Frontend/public/favicon.svg` and `icons.svg` are deleted in the working tree.
    Restore them or remove the reference.
12. **Frontend dependency review.** `package.json` includes `cn` as a runtime
    dependency and `shadcn` as a dependency rather than a dev tool. shadcn/ui
    normally uses `clsx` + `tailwind-merge` via a local `cn()` helper. Confirm these
    are intentional; a package named `cn` on npm is not automatically the helper you
    want. Also note the app uses `@base-ui/react` rather than Radix, so the shadcn
    component set must match that choice.
13. **Unusual names in the venv are legitimate, not typosquats.** The previous task
    asked about `httpx2`, `httpcore2`, `annotated-doc`, and `strenum`:
    - `httpx2` 2.13.1 — Tom Christie, maintained by Pydantic Services Inc.,
      `github.com/pydantic/httpx2`; ~11.7M downloads/day, ~234M/month.
    - `httpcore2` 2.13.1 — same publisher and project; ~11.7M/day, ~234M/month.
    - `annotated-doc` 0.0.5 — Sebastián Ramírez (tiangolo),
      `github.com/fastapi/annotated-doc`; ~17.9M/day, ~398M/month.
    - `strenum` 0.4.15 — James Sinclair, `github.com/irgeek/StrEnum`;
      ~1.4M/day, ~30.5M/month. Not installed in this venv.
    These arrived as transitive dependencies, not from `requirements.txt`. Do not add
    them as direct dependencies. The deliberate typo-adjacent names are the
    publisher's choice; the metadata and download volume match the genuine projects.
14. **The venv contains unrelated tooling** (`agent-detector`, `detect-installer`,
    `fastapi-cloud-cli`, `sentry-sdk`, `Jinja2`, etc.) that is not in
    `requirements.txt`. Recreate the venv from `requirements.txt` if reproducibility
    matters; do not treat the current 62-package freeze as the project definition.
15. **Windows console mojibake.** Em dashes in log strings show as `�`. Use ASCII in
    log messages if terminal output is part of the demo.
16. **No logging configuration.** The app relies on uvicorn defaults. `logger.warning`
    from `safezone.main` and `safezone.config` will appear, but structured logging and
    request IDs are absent.
17. **No CORS middleware.** Fine for the Vite proxy and same-origin production. Add
    only if a genuinely cross-origin client appears.
18. **Schema migration ordering.** Tables are created with `IF NOT EXISTS`; constraints
    are added afterward. On a database with pre-existing bad rows, the constraint
    blocks fail and abort the script. Run against a clean dev project first.

---

## 10. What is missing, in the order it should be built

From `AGENTS.md` §18 "Build order":

1. **`core/events.py`** — `emit()`, event type constants, SSE fan-out. `AGENTS.md`
   says it is imported by almost every module and must land first. It must never
   raise; a failed event insert must not break the request path.
2. **Apply `data/schema.sql` to both Supabase projects** (`safezone-dev` and prod) and
   confirm RLS is enabled with zero policies.
3. **`services/whatsapp.py`** — `send_message()` with all six guards in this order:
   kill switch → global cap → per-number rate limit → allowlist (when
   `ALLOWLIST_ONLY`) → 24h window → mock/live send. Every path writes `outbox`,
   including suppressions (`suppressed_reason`, `mode`). Never raises.
4. **`services/intake.py`** — command router (`VOLUNTEER`, `ON DUTY`, `OFF DUTY`,
   `ACCEPT <id>`, `DECLINE <id>`, `ARRIVED <id>`, `DONE <id>`, `STOP`, `1`, `2`) and
   the unregistered direct-help flow. Re-read `AGENTS.md` §9 before touching it: the
   unregistered path is the default, not a special case. Require case IDs on case
   commands.
5. **`routes/webhook.py`** — `GET` verification and `POST` inbound. Always answer
   HTTP 200. Use `try_normalize()` so a malformed number asks for clarification
   instead of 500ing.
6. **`services/extract.py`** — the single LLM call, with `LLM_PROVIDER`/`LLM_MODEL`
   configurable. Mock mode returns a deterministic fake extraction. The system must
   accept, rank and dispatch when the LLM is down.
7. **`services/risk.py`**, **`merge.py`**, **`protocol.py`**, **`dispatch.py`**,
   **`silence.py`**, **`hazards.py`**, **`data/seed.py`**.
8. **Routes**: cases, volunteers, responder, admin. Remember: register every router
   before `mount_spa(app)` in `main.py`.

Scoring reference (`AGENTS.md`, hand-tuned and visible):

```
priority = (0.40 * vulnerability_score
          + 0.30 * urgency_score
          + 0.20 * hazard_exposure
          + 0.10 * time_decay) * confidence

confidence = clamp(source_factor * (0.6 + 0.1 * min(report_count, 4)), 0, 1)
```

Every case needs a plain-language `reason` explaining its rank. "The model said so"
loses the pitch.

---

## 11. Verification checklist

Run from `Backend/` unless noted. These are the checks the previous task required;
all currently pass except the boot check, which cannot pass without Supabase config.

```bash
cd Backend
python -m pytest -q                 # 17 passed
python -c "import main"             # no output after a frontend build
```

```bash
cd Frontend
npm run build                       # tsc -b && vite build
npm run lint                        # eslint .
```

```bash
cd ..                               # repo root
git status                          # no .env, no *.db, no Backend/static/ staged
```

To verify the SPA and 404 behavior after building and starting uvicorn:

```bash
curl -i http://127.0.0.1:8000/api/hello        # 200 JSON
curl -i http://127.0.0.1:8000/api/does-not-exist  # 404 (not index.html)
curl -i http://127.0.0.1:8000/control          # 200 index.html
curl -i http://127.0.0.1:8000/assets/<file>    # built asset
```

Before committing, also confirm:

- No real phone numbers in any file. Use obviously fake numbers.
- No `.env`, `*.db`, `Backend/static/`, or `.venv/` in the diff.
- Emergency numbers remain empty until a human fills them from an official source.
- Any new module imports `emit()`/`send_message()` rather than bypassing them.
- Every new `log` line that mentions a phone uses `mask()`.

---

## 12. Commit conventions

Format: `type(scope): short description`, lowercase after the colon, imperative mood,
under ~72 characters, one logical change per commit. See `CONTRIBUTING.md`.

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `chore`, `test`.
Scopes: `phone`, `config`, `db`, `schema`, `events`, `whatsapp`, `intake`, `tools`,
`agent`, `protocol`, `risk`, `hazards`, `dispatch`, `silence`, `seed`, `ui`, `map`,
`queue`, `responder`, `deps`, `readme`.

Recent history for reference:

```
38fb5f3 docs(agents): resolve Supabase/SQLite and offline-mode contradictions
b12932d fix(backend): harden startup, phone handling and schema
a629ea8 refactor(db): remove in-memory store, Supabase only
4d35ac6 chore: reorganise backend into core/routes/services/data
```

---

## 13. Rules for the next agent

1. **Read `AGENTS.md` fully before writing code.** This document summarizes it; it
   does not replace it. Anything marked PROPOSED in `AGENTS.md` is a guess — flag it,
   do not silently build on it.
2. **Do not invent what you can ask about.** If a contract or data shape is unclear,
   ask before adding dependents.
3. **Never introduce a second data layer.** Supabase only. Fail loudly when
   configuration is missing.
4. **Never hardcode emergency numbers.** Leave them empty until a human supplies them
   from an official source.
5. **Never put real phone numbers anywhere** — not in seeds, tests, comments, or
   fixtures. The repo is public.
6. **Every feature must work with `MOCK_MODE=1`** and no WhatsApp or LLM network call,
   on the same commit.
7. **The webhook always returns 200.** Log failures; do not let Meta retry.
8. **Register routers before `mount_spa(app)`.** Anything after it is dead.
9. **Use `mask()` in logs.** Full phone numbers must never reach terminal scrollback.
10. **Commit small, working states.** A broken `main` at hour 18 with one developer is
    fatal. Run the checks in section 11 before every commit.
11. **Stay in your lane on shared files.** `AGENTS.md` §18 assigns ownership. Two
    agents editing the same file in parallel produces conflicts nobody has time to
    resolve. If a file is owned by someone else, say so and suggest messaging the
    owner.
12. **Refuse to overstate the system.** Rescue is done by people on the ground.
    Simulated volunteers and handoff links must be labelled as simulated in the UI.
