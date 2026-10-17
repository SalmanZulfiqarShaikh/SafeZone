import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from core import config, events
from core.db import get_db
from routes.admin import router as admin_router
from routes.cases import router as cases_router
from routes.events import router as events_router
from routes.register import router as register_router
from routes.responder import router as responder_router
from routes.volunteers import router as volunteers_router
from routes.webhook import router as webhook_router
from services import silence

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
app.include_router(webhook_router)
app.include_router(cases_router)
app.include_router(volunteers_router)
app.include_router(responder_router)
app.include_router(register_router)
app.include_router(admin_router)
app.include_router(events_router)


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
