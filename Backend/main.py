import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from core import config, events
from core.db import get_db
from core.phone import mask
from routes.admin import router as admin_router
from routes.auth import require_admin, router as auth_router
from routes.cases import router as cases_router
from routes.events import router as events_router
from routes.register import router as register_router
from routes.responder import router as responder_router
from routes.volunteers import router as volunteers_router
from routes.webhook import router as webhook_router
from routes.whatsapp_public import router as whatsapp_router
from routes.zones import router as zones_router
from services import silence

logger = logging.getLogger("safezone.main")

BASE = Path(__file__).parent
STATIC_DIR = BASE / "static"

# Path prefixes that must never fall through to index.html. A mistyped API
# path returning a 200 HTML page is very hard to debug under time pressure.
API_PREFIXES = {"api", "webhook", "events"}


def configure_logging() -> None:
    """Make SafeZone's own log lines visible.

    uvicorn configures its own loggers and leaves the root logger at WARNING,
    so without this the only app output is suppression warnings -- "created
    case 5 (category=flood, priority=0.42)" never appears, and neither does
    which provider answered. During a demo this log is the clearest view of
    the system actually reasoning, so it is on by default.

    httpx is pinned to WARNING because the Supabase client logs every single
    HTTP request at INFO, which buries everything else.
    """
    # force=True matters: uvicorn configures logging before it imports this
    # module, so the root logger already has handlers and a plain basicConfig
    # would silently do nothing. That is why app INFO lines stay invisible.
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)-22s %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    for problem in config.startup_report():
        logger.warning(problem)

    # The allowlist is the guard most likely to silently eat a demo, so say
    # out loud exactly which numbers can receive a message.
    if config.ALLOWLIST_ONLY:
        allowed = ", ".join(mask(number) for number in config.DEMO_ALLOWLIST) or "(none)"
        logger.info(
            "ALLOWLIST_ONLY is on. %d number(s) may receive messages: %s",
            len(config.DEMO_ALLOWLIST),
            allowed,
        )
    else:
        logger.warning("ALLOWLIST_ONLY is off — any number can receive messages.")

    # The control room is unreachable without a login, so a half-configured
    # one is a demo that cannot start rather than a quiet security hole. Say
    # which part is missing, at startup, not at the first 401.
    from core import auth as _auth

    if _auth.is_configured():
        logger.info("Control room login is on for %s.", config.ADMIN_EMAIL)
    else:
        missing = [
            name
            for name, value in (
                ("ADMIN_EMAIL", config.ADMIN_EMAIL),
                ("ADMIN_PASSWORD_HASH", config.ADMIN_PASSWORD_HASH),
                ("SESSION_SECRET", config.SESSION_SECRET),
            )
            if not value.strip()
        ]
        logger.warning(
            "Control room login is NOT configured (%s missing), so /control and "
            "/volunteers will refuse every sign-in. Run: python -m scripts.hash_password",
            ", ".join(missing),
        )

    # emit() may run in worker threads; capture the loop for SSE fan-out.
    events.set_loop(asyncio.get_running_loop())
    # Fail loudly here rather than silently switching data layers later.
    get_db()

    # Re-escalation runs in the background. A bad tick is logged, not fatal.
    silence_task = asyncio.create_task(silence.run_forever())
    try:
        yield
    finally:
        silence_task.cancel()
        with suppress(asyncio.CancelledError):
            await silence_task


app = FastAPI(title="SafeZone", lifespan=lifespan)


@app.get("/api/hello")
def hello():
    return {"message": "Backend Setup done! Waiting for the task"}


# API routers FIRST — mounts and the SPA catch-all are greedy. Anything
# registered after mount_spa() is silently dead.
# Public by design, and each one says why:
#   webhook   -- Meta calls it; it verifies an X-Hub-Signature-256 instead.
#   responder -- the link IS the credential, and it goes to a fire or
#                ambulance desk that will never have a SafeZone login.
#   register  -- the whole point is that anyone can ask for area alerts.
#   auth      -- you cannot require a session to create one.
#   zones     -- the public registration form needs the area list.
#   whatsapp  -- the number on the poster; the public page shows it.
app.include_router(webhook_router)
app.include_router(responder_router)
app.include_router(register_router)
app.include_router(auth_router)
app.include_router(zones_router)
app.include_router(whatsapp_router)

# Behind the login. These carry reporter names, numbers and exact locations
# (AGENTS.md 9), who is on duty and where, and the switch that stops every
# outbound message. The guard goes on at mount time rather than on each
# function, so a route added later is protected by default instead of by
# whoever remembers the decorator.
PROTECTED = [Depends(require_admin)]
app.include_router(cases_router, dependencies=PROTECTED)
app.include_router(volunteers_router, dependencies=PROTECTED)
app.include_router(admin_router, dependencies=PROTECTED)
app.include_router(events_router, dependencies=PROTECTED)


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
