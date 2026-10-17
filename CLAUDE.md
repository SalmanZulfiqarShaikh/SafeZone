Work in the SafeZone repo. Do this in the order given. Commit at each marked checkpoint. Do not skip the verification steps.

Part A — Move files into the new structure

Target layout:

Backend/
  main.py
  core/
    __init__.py
    config.py
    db.py
    events.py
    phone.py
  routes/
    __init__.py
  services/
    __init__.py
  data/
    schema.sql
  tests/
    __init__.py
    test_phone.py
    test_db.py

Moves:

Backend/config.py → Backend/core/config.py
Backend/db.py → Backend/core/db.py
Backend/phone.py → Backend/core/phone.py
Backend/schema.sql → Backend/data/schema.sql
test files → Backend/tests/

Use git mv, not copy-delete, so history is preserved.

Delete Backend/__init__.py. The Backend directory is the working directory, not a package. Create empty __init__.py in core/, routes/, services/, data/, tests/.

Rewrite every import to the new paths. db.py currently has from Backend.config import ... — that is wrong and will fail. It becomes from core.config import ....

The app runs as uvicorn main:app --reload from inside Backend/. Update README if it says otherwise.

Checkpoint: cd Backend && python -c "import main" must succeed. Commit: chore: reorganise backend into core/routes/services/data

Part B — Remove the in-memory database

core/db.py currently implements a parallel dict-based database used when MOCK_MODE=1. Delete it entirely: InMemoryDB, InMemoryTable, InMemoryQueryBuilder, InMemoryInsertBuilder, InMemoryUpdateBuilder, and the _in_memory_db_instance global.

Reason: it is a second data layer with different semantics from PostgreSQL — no foreign keys, no constraints, no joins, and eq() as its only filter. Ranking a queue and finding nearest on-duty volunteers both need more than that. Two data layers means the demo rehearses code that is not the code that ships.

Replacement: get_db() returns a Supabase client, always. MOCK_MODE no longer affects the database — it only means fake WhatsApp sends and fake LLM extractions. Two Supabase projects (dev and prod) handle environment separation via SUPABASE_URL.

get_db() must raise a clear error at startup if SUPABASE_URL or SUPABASE_SERVICE_KEY is missing, rather than silently falling back.

Also remove the dead class Response defined inside InMemoryTable.insert.

Add a thin error-handling wrapper so a failing Supabase call raises a typed DbError rather than leaking the client’s exception. The webhook handler must always return HTTP 200 — Meta retries anything else, producing duplicate messages.

Checkpoint: commit refactor(db): remove in-memory store, Supabase only

Part C — Fix core/config.py

Bug — get_emergency_number() raises RuntimeError. The instant guidance reply fires before the LLM and before location is known. If emergency numbers are unconfigured, this crashes the first reply to someone in an emergency. The message must degrade; the system must not fall over.

Rewrite so it returns Optional[str], never raises, and logs an error when a number is missing. Map every category: fire and structural → fire number; medical, trapped, flood → ambulance; other → police. The current version maps only three categories and silently falls through to ambulance for everything else.

Add missing config specified in AGENTS.md section 12: LLM_PROVIDER (default "groq"), LLM_MODEL, PER_NUMBER_RATE_LIMIT (default 10), PER_NUMBER_RATE_WINDOW_S (default 300). The provider split matters: when the LLM provider rate-limits during the event, swapping must be a config change, not a code change.

Add startup_report() -> list[str] returning human-readable problems: emergency numbers missing, KILL_SWITCH on, MOCK_MODE off with empty WHATSAPP_TOKEN, ALLOWLIST_ONLY on with empty DEMO_ALLOWLIST. These are the settings that silently break a demo.

Part D — Fix core/phone.py

Pakistani numbers only is a deliberate decision — keep rejecting foreign numbers.

Add:

mask(phone: str) -> str — all but last four digits replaced with *. Use it in every log line. Full numbers must never reach logs or terminal scrollback.
try_normalize(raw: str) -> str | None — non-raising variant. The webhook must not 500 on a malformed number.
A PhoneError(ValueError) subclass instead of bare ValueError, so callers can catch precisely.

Expand tests/test_phone.py to cover: 0092 prefix, parenthesised input (0300) 123 4567, whitespace-padded input, idempotency (normalising twice gives the same result), non-string input, and that mask() keeps the last four digits.

Part E — Fix main.py

Three changes:

Wrap the SPA catch-all in def mount_spa(app: FastAPI) -> None and call it as the last line of the file, after every include_router. FastAPI resolves routes in registration order; the catch-all is greedy, so any router registered after it is silently dead with no error.
Inside the catch-all, return 404 for paths starting with api/, webhook/, or events. Currently a mistyped API path returns index.html with status 200, which is very hard to debug under time pressure.
On startup, log every line from config.startup_report() as a warning.
Part F — Fix data/schema.sql

Add row-level security. Supabase exposes every table over PostgREST, and the anon key ships in frontend code. Without RLS, anyone can read the people table including phone numbers. Append:

sql
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

Define no policies. RLS enabled with zero policies blocks the anon key completely while the backend’s service key bypasses RLS — all access goes through FastAPI, nothing from the browser.

Add CHECK constraints on cases.status, cases.dispatch_status, incidents.status, dispatches.status, volunteers.status using the value lists already in the comments. Without them a typo writes an invalid status and a case silently stalls with no error.

Add CREATE UNIQUE INDEX ON dispatches(case_id, volunteer_id); so re-escalation cannot offer the same case to the same volunteer twice.

Add CREATE INDEX ON incidents(priority_score DESC); — the queue sorts on it.

Rename mock_outbox to outbox. It is the message audit log in both modes, not a mock artifact. Add columns: mode TEXT NOT NULL ('mock' or 'live') and suppressed_reason TEXT so send_message() can record why a message was not sent. That is the primary debugging surface when the demo misbehaves.

Part G — Rewrite requirements.txt

It is currently a raw pip freeze, so chosen packages are indistinguishable from transitive ones. Replace with direct dependencies only, unpinned:

fastapi
uvicorn[standard]
httpx
python-dotenv
supabase
openai
pytest

Separately, report back (do not change): the current file lists httpx2, httpcore2, annotated-doc, and strenum alongside the genuine httpx and httpcore. For each, state the PyPI publisher and recent download count. Those names resemble typosquats and this repo will handle phone numbers.

Part H — Final verification
cd Backend && python -m pytest -q — all pass
cd Backend && python -c "import main" — no import errors
cd Frontend && npm run build && npm run lint — clean
git status — no .env, no *.db, no Backend/static/ staged

Report anything you changed that is not listed above, and anything listed that you could not do.