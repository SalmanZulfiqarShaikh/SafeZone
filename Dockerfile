# SafeZone, one image.
#
# The frontend is not deployed separately on purpose. The control-room session
# is an HttpOnly, SameSite=Lax cookie, and SameSite=Lax means the browser will
# not send it on a cross-site request -- so a frontend on one domain calling an
# API on another would 401 on every protected route. Serving the built SPA from
# the same FastAPI process keeps everything same-origin: no CORS, no cookie
# attributes to weaken, nothing to configure.
#
# It also matches how the app already works locally, so what runs here is what
# was rehearsed.

# ─── Stage 1: build the SPA ─────────────────────────────────────────────────
FROM node:22-alpine AS frontend
WORKDIR /app

# vite.config.ts writes the bundle to ../Backend/static, so that path has to
# exist before the build runs.
RUN mkdir -p Backend/static

COPY Frontend/package.json Frontend/package-lock.json Frontend/
RUN cd Frontend && npm ci

COPY Frontend/ Frontend/
RUN cd Frontend && npm run build


# ─── Stage 2: the app ───────────────────────────────────────────────────────
FROM python:3.12-slim
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

COPY Backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY Backend/ ./

# main.py checks for this directory at import time and mounts the SPA only if
# it exists, so the bundle has to land before uvicorn starts.
COPY --from=frontend /app/Backend/static ./static

EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
