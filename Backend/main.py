from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Load variables from .env
load_dotenv()

BASE = Path(__file__).parent
STATIC_DIR = BASE / "static"

app = FastAPI(title="Dastak")


@app.get("/api/hello")
def hello():
    return {"message": "Backend Setup done! Waiting for the task"}


# API routers FIRST — mounts and the SPA catch-all are greedy.
# app.include_router(webhook_router)
# app.include_router(api_router)     # /api/*
# app.include_router(public_router)  # /api/... JSON only; UI is React

# Built React app: hashed assets first, then a catch-all so deep links work.
if STATIC_DIR.exists():
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        root = STATIC_DIR.resolve()
        candidate = (root / full_path).resolve()
        if candidate.is_file() and root in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(root / "index.html")
