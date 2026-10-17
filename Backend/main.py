import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from core import config
from core.db import get_db

logger = logging.getLogger("dastak.main")

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


app = FastAPI(title="Dastak", lifespan=lifespan)


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
