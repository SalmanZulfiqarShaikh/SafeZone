"""The website assistant endpoint.

Public by design: the chat widget sits on the landing page and anyone can use
it without an account, exactly like the WhatsApp number it points at.

Public also means abusable, so this is the one route that talks to a paid API
with no login in front of it. Three things stand between a visitor and the
bill: a per-address message budget, a cap on how much text one request may
carry, and the fact that the key itself never leaves the server.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from threading import Lock
from typing import Any, Deque, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from services import assistant, llm

logger = logging.getLogger("safezone.chat")

router = APIRouter(prefix="/api", tags=["chat"])

# Generous for a person reading a page, useless for a script. The window is an
# hour because that is roughly how long a genuine visit lasts; a scraper hits
# the ceiling in under a minute and stays there.
RATE_LIMIT_MESSAGES = 30
RATE_LIMIT_WINDOW_S = 3600

# In process, not in Redis. One uvicorn worker serves this prototype, and a
# dependency added for a hackathon is a dependency that breaks during one.
# A restart clears the counters, which is an accepted trade-off.
_hits: Dict[str, Deque[float]] = {}
_hits_lock = Lock()


class ImagePayload(BaseModel):
    base64: str = Field(default="", max_length=8_000_000)
    mimeType: str = Field(default="image/jpeg", max_length=100)


class ChatTurn(BaseModel):
    role: str = Field(default="user", max_length=20)
    text: str = Field(default="", max_length=assistant.MAX_MESSAGE_CHARS)


class ChatRequest(BaseModel):
    message: str = Field(default="", max_length=assistant.MAX_MESSAGE_CHARS)
    history: list[ChatTurn] = Field(default_factory=list)
    image: Optional[ImagePayload] = None


class ChatResponse(BaseModel):
    reply: str


def _caller(request: Request) -> str:
    """Best-effort identity for rate limiting.

    Behind ngrok or any proxy the socket address is the tunnel, so the
    forwarded header is tried first. It is spoofable -- this is a spending
    limit, not an access control, and the budget is small enough that forging
    headers to beat it is more effort than the quota is worth.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _within_budget(caller: str) -> bool:
    now = time.time()
    with _hits_lock:
        seen = _hits.setdefault(caller, deque())
        while seen and now - seen[0] > RATE_LIMIT_WINDOW_S:
            seen.popleft()
        if len(seen) >= RATE_LIMIT_MESSAGES:
            return False
        seen.append(now)

        # Keep the table from growing forever on a long-running process.
        if len(_hits) > 5000:
            for key in [k for k, v in _hits.items() if not v]:
                _hits.pop(key, None)
    return True


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    """Answer one question about SafeZone.

    Every failure here returns something that points the visitor at WhatsApp.
    An assistant that is down must never read as a system that is down -- the
    number works whether or not this endpoint does.
    """
    caller = _caller(request)

    if not _within_budget(caller):
        logger.info("Chat rate limit hit by %s", caller)
        raise HTTPException(
            status_code=429,
            detail=(
                "You have reached the message limit for now. "
                "Message SafeZone on WhatsApp if you need help."
            ),
        )

    image: Optional[Dict[str, Any]] = None
    if payload.image and payload.image.base64:
        image = {"base64": payload.image.base64, "mimeType": payload.image.mimeType}

    try:
        answer = assistant.reply(
            payload.message,
            history=[turn.model_dump() for turn in payload.history],
            image=image,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Message was empty.")
    except llm.LLMUnavailable as exc:
        # Never the provider's error text: it can carry request details, and a
        # visitor needs an action rather than a diagnosis.
        logger.warning("Chat unavailable: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=(
                "The assistant is unavailable right now. "
                "Message SafeZone on WhatsApp and someone will see it."
            ),
        )
    except Exception:
        logger.exception("Chat failed for %s", caller)
        raise HTTPException(
            status_code=500,
            detail=(
                "Something went wrong answering that. "
                "Message SafeZone on WhatsApp if you need help."
            ),
        )

    return ChatResponse(reply=answer)
