"""Server-Sent Events stream for the control room.

One subscriber per open control-room tab. Frames are dropped for a slow tab
(see ``core/events``); the timeline can always be rebuilt from the events
table, so a missed frame is an inconvenience, not data loss.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from core import events

router = APIRouter(tags=["events"])

PING_INTERVAL_S = 15


@router.get("/events")
async def stream(request: Request) -> StreamingResponse:
    queue = events.subscribe()

    async def frames():
        try:
            # Comment frame flushes headers through proxies immediately.
            yield ": connected\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    frame = await asyncio.wait_for(queue.get(), timeout=PING_INTERVAL_S)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    continue
                yield frame
        finally:
            events.unsubscribe(queue)

    return StreamingResponse(
        frames(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            # nginx buffers proxied responses unless told otherwise.
            "X-Accel-Buffering": "no",
        },
    )
