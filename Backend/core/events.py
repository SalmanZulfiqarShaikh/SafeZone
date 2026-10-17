"""Event log and SSE fan-out for SafeZone.

Every state change goes through :func:`emit`. If a state change does not emit,
it did not happen: the control-room timeline replays from the ``events`` table.

Two rules:
  - ``emit`` never raises. A failed audit insert must not break a help request.
  - Frames are dropped, never blocked on. A slow browser tab must not stall the
    webhook.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from core import db

logger = logging.getLogger("safezone.events")

# ─── Event types (AGENTS.md 5.3) ────────────────────────────────────────────
REPORT_RECEIVED = "ReportReceived"
REPORT_MERGED = "ReportMerged"
INCIDENT_CREATED = "IncidentCreated"
CASE_PROPOSED = "CaseProposed"
CASE_APPROVED = "CaseApproved"
VOLUNTEER_REGISTERED = "VolunteerRegistered"
VOLUNTEER_ON_DUTY = "VolunteerOnDuty"
VOLUNTEER_OFFERED = "VolunteerOffered"
VOLUNTEER_ACCEPTED = "VolunteerAccepted"
VOLUNTEER_ARRIVED = "VolunteerArrived"
VOLUNTEER_DONE = "VolunteerDone"
DISPATCH_EXPIRED = "DispatchExpired"
RESPONDER_LINK_SENT = "ResponderLinkSent"
PERSON_CONFIRMED_HELP = "PersonConfirmedHelp"
CASE_REOPENED = "CaseReopened"
CASE_CLOSED = "CaseClosed"
KILL_SWITCH_TOGGLED = "KillSwitchToggled"

EVENT_TYPES = frozenset(
    {
        REPORT_RECEIVED,
        REPORT_MERGED,
        INCIDENT_CREATED,
        CASE_PROPOSED,
        CASE_APPROVED,
        VOLUNTEER_REGISTERED,
        VOLUNTEER_ON_DUTY,
        VOLUNTEER_OFFERED,
        VOLUNTEER_ACCEPTED,
        VOLUNTEER_ARRIVED,
        VOLUNTEER_DONE,
        DISPATCH_EXPIRED,
        RESPONDER_LINK_SENT,
        PERSON_CONFIRMED_HELP,
        CASE_REOPENED,
        CASE_CLOSED,
        KILL_SWITCH_TOGGLED,
    }
)

# ─── SSE subscribers ────────────────────────────────────────────────────────
# emit() may run in a worker thread (FastAPI runs sync endpoints there), so the
# event loop is captured at startup and used via call_soon_threadsafe().
_subscribers: set[asyncio.Queue[str]] = set()
_loop: Optional[asyncio.AbstractEventLoop] = None

SUBSCRIBER_QUEUE_SIZE = 100


def set_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Capture the running event loop. Called once from the FastAPI lifespan."""
    global _loop
    _loop = loop


def subscribe() -> asyncio.Queue[str]:
    """Register an SSE subscriber. Returns the queue to drain."""
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=SUBSCRIBER_QUEUE_SIZE)
    _subscribers.add(queue)
    return queue


def unsubscribe(queue: asyncio.Queue[str]) -> None:
    """Remove an SSE subscriber. Safe to call twice."""
    _subscribers.discard(queue)


def sse_format(record: Mapping[str, Any]) -> str:
    """Render one event as a Server-Sent Events frame."""
    event_type = str(record.get("type") or "message")
    data = {
        "type": event_type,
        "case_id": record.get("case_id"),
        "payload": record.get("payload") or {},
        "at": record.get("created_at") or datetime.now(timezone.utc).isoformat(),
    }
    return f"event: {event_type}\ndata: {json.dumps(data, default=str)}\n\n"


def emit(event_type: str, payload: Optional[dict] = None, case_id: Optional[int] = None) -> None:
    """Append an event and fan it out to SSE subscribers.

    Never raises. Unknown event types are logged loudly but still recorded, so
    a typo shows up in the timeline instead of silently vanishing.
    """
    try:
        body = payload if isinstance(payload, dict) else {}
        if event_type not in EVENT_TYPES:
            logger.warning("Unknown event type %r emitted", event_type)

        record = {
            "type": event_type,
            "case_id": case_id,
            "payload": body,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            db.execute(
                db.get_db()
                .table("events")
                .insert({"type": event_type, "case_id": case_id, "payload": body})
            )
        except Exception as exc:  # DbError or anything the client throws
            logger.error("Could not persist event %s: %s", event_type, exc)

        _fan_out(sse_format(record))
    except Exception:  # noqa: BLE001 - emit must never break the caller
        logger.exception("Unexpected failure while emitting event %r", event_type)


def _fan_out(frame: str) -> None:
    """Push a frame to every subscriber, dropping it if their queue is full."""
    loop = _loop
    if loop is None or loop.is_closed():
        return

    for queue in list(_subscribers):
        try:
            loop.call_soon_threadsafe(_put_nowait_drop, queue, frame)
        except RuntimeError:
            # Loop closed between the check and the call.
            logger.debug("Event loop unavailable; dropping SSE frame")
            return


def _put_nowait_drop(queue: asyncio.Queue[str], frame: str) -> None:
    try:
        queue.put_nowait(frame)
    except asyncio.QueueFull:
        logger.warning("SSE subscriber queue full; dropping frame")
