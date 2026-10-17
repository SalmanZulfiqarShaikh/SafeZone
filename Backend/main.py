from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Load variables from .env
load_dotenv()

BASE = Path(__file__).parent
app = FastAPI(title="Dastak")
templates = Jinja2Templates(directory=BASE / "templates")


@app.get("/api/hello")
def hello():
    return {"message": "Backend Setup done! Waiting for the task"}


# Routes FIRST — mounts are greedy and will swallow anything registered after them.
# app.include_router(webhook_router)
# app.include_router(api_router)     # /api/*
# app.include_router(public_router)  # / and /r/{token}, Jinja

# Control room bundle last.
static_dir = BASE / "static"
if static_dir.exists():
    app.mount("/app", StaticFiles(directory=static_dir, html=True), name="control")
