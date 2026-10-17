"""Silence detection and re-escalation.

A background sweep runs every ``SWEEP_INTERVAL_S`` seconds. Four things reopen
a case:

  - nobody accepts an offer within ``VOLUNTEER_ACCEPT_TIMEOUT_S``
  - a volunteer accepts but never sends ARRIVED within
    ``VOLUNTEER_ARRIVE_TIMEOUT_S``
  - the person replies ``2`` to "Did help reach you?"
  - the person says nothing at all after being marked helped

Reopening bumps the case to the top of the queue, sets the ``reopened`` flag
with a plain-language reason, emits ``CaseReopened`` (the coordinator alert)
and offers the next ring.

This loop is best-effort. A failure is logged and retried on the next tick; it
must never take down the webhook.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional

from core import config
from core.db import execute, get_db
from core.events import (
    CASE_CLOSED,
    CASE_REOPENED,
    DISPATCH_EXPIRED,
    PERSON_CONFIRMED_HELP,
    emit,
)
from services import dispatch

logger = logging.getLogger("safezone.silence")

SWEEP_INTERVAL_S = 15

# A case that reaches 'closed' is done, whatever else is on it.
CLOSED_DISPATCH_STATUSES = ("closed",)
REOPENABLE_DISPATCH_STATUSES = ("arrived", "confirmed", "closed", "reopened")


def sweep(now: Optional[datetime] = None) -> Dict[str, int]:
    """Run every silence check once. Returns counts for logging and tests."""
    moment = now or datetime.now(timezone.utc)
    counts = {"expired_offers": 0, "expired_accepts": 0, "silent_people": 0}

    counts["expired_offers"] = _expire_unaccepted(moment)
    counts["expired_accepts"] = _expire_unarrived(moment)
    counts["silent_people"] = _expire_silent_people(moment)

    if any(counts.values()):
        logger.warning("Silence sweep reopened cases: %s", counts)
    return counts


def reopen(case_id: int, reason: str, reoffer: bool = True) -> bool:
    """Push a case to the top of the queue and try the next ring."""
    case = _select_one("cases", id=case_id)
    if case is None:
        logger.warning("Cannot reopen missing case %s", case_id)
        return False
    if case.get("dispatch_status") in CLOSED_DISPATCH_STATUSES:
        return False

    top = _top_priority()
    _update(
        "cases",
        {
            "priority_score": top + 1.0,
            "reopened": True,
            "reopen_reason": reason,
            "dispatch_status": "reopened",
        },
        id=case_id,
    )

    incident = (
        _select_one("incidents", id=case.get("incident_id"))
        if case.get("incident_id") is not None
        else None
    )
    if incident and incident.get("id") is not None:
        _update(
            "incidents",
            {
                "priority_score": top + 1.0,
                "reopened": True,
                "reopen_reason": reason,
                "status": "open",
                "dispatch_status": "reopened",
            },
            id=incident["id"],
        )

    emit(
        CASE_REOPENED,
        {
            "reason": reason,
            "priority_score": round(top + 1.0, 3),
            "previous_dispatch_status": case.get("dispatch_status"),
        },
        case_id=case_id,
    )
    logger.warning("Case %s reopened: %s", case_id, reason)

    if reoffer:
        ring = _next_ring(case_id)
        offered = dispatch.offer_case(case_id, ring=ring)
        if not offered:
            logger.warning(
                "Case %s reopened but no volunteers were available for ring %s",
                case_id,
                ring,
            )

    return True


def confirm(case_id: int) -> bool:
    """The person said help arrived. Close the case."""
    case = _select_one("cases", id=case_id)
    if case is None:
        return False

    now = _now_iso()
    _update(
        "cases",
        {"status": "resolved", "dispatch_status": "closed", "closed_at": now},
        id=case_id,
    )
    if case.get("incident_id") is not None:
        _update(
            "incidents",
            {"status": "resolved", "dispatch_status": "closed"},
            id=case["incident_id"],
        )

    emit(PERSON_CONFIRMED_HELP, {"answer": "yes"}, case_id=case_id)
    emit(CASE_CLOSED, {"reason": "person confirmed help arrived"}, case_id=case_id)
    logger.info("Case %s confirmed and closed by the person", case_id)
    return True


def latest_case(person_id: Any) -> Optional[Mapping[str, Any]]:
    """The person's most recent reopenable case, or None."""
    if person_id is None:
        return None

    rows = _select("cases", person_id=person_id)
    reopenable = [
        row for row in rows if row.get("dispatch_status") in REOPENABLE_DISPATCH_STATUSES
    ]
    if not reopenable:
        return None
    return max(reopenable, key=lambda row: row.get("id") or 0)


# ─── Checks ────────────────────────────────────────────────────────────────


def _expire_unaccepted(now: datetime) -> int:
    stale: Dict[Any, List[Mapping[str, Any]]] = {}
    for row in _select("dispatches", status="offered"):
        offered_at = _parse_timestamp(row.get("offered_at"))
        if offered_at is None:
            continue
        if _age_seconds(now, offered_at) < config.VOLUNTEER_ACCEPT_TIMEOUT_S:
            continue
        stale.setdefault(row.get("case_id"), []).append(row)

    reopened = 0
    for case_id, rows in stale.items():
        case = _select_one("cases", id=case_id)
        if case is None or case.get("dispatch_status") != "offered":
            continue

        for row in rows:
            _update("dispatches", {"status": "expired"}, id=row["id"])
            emit(
                DISPATCH_EXPIRED,
                {
                    "volunteer_id": row.get("volunteer_id"),
                    "ring": row.get("ring"),
                    "reason": "accept timeout",
                },
                case_id=case_id,
            )

        if reopen(case_id, "No volunteer accepted in time"):
            reopened += 1

    return reopened


def _expire_unarrived(now: datetime) -> int:
    stale: Dict[Any, List[Mapping[str, Any]]] = {}
    for row in _select("dispatches", status="accepted"):
        accepted_at = _parse_timestamp(row.get("accepted_at"))
        if accepted_at is None:
            continue
        if _age_seconds(now, accepted_at) < config.VOLUNTEER_ARRIVE_TIMEOUT_S:
            continue
        stale.setdefault(row.get("case_id"), []).append(row)

    reopened = 0
    for case_id, rows in stale.items():
        case = _select_one("cases", id=case_id)
        if case is None or case.get("dispatch_status") in CLOSED_DISPATCH_STATUSES:
            continue

        for row in rows:
            _update("dispatches", {"status": "expired"}, id=row["id"])
            if row.get("volunteer_id") is not None:
                # They never arrived, so free them for another case.
                _update("volunteers", {"status": "on_duty"}, id=row["volunteer_id"])
            emit(
                DISPATCH_EXPIRED,
                {
                    "volunteer_id": row.get("volunteer_id"),
                    "ring": row.get("ring"),
                    "reason": "arrival timeout",
                },
                case_id=case_id,
            )

        if reopen(case_id, "Volunteer accepted but did not arrive"):
            reopened += 1

    return reopened


def _expire_silent_people(now: datetime) -> int:
    reopened = 0
    for row in _select("dispatches", status="done"):
        done_at = _parse_timestamp(row.get("done_at"))
        if done_at is None:
            continue
        if _age_seconds(now, done_at) < config.PERSON_SILENCE_TIMEOUT_S:
            continue

        case_id = row.get("case_id")
        case = _select_one("cases", id=case_id)
        if case is None or case.get("dispatch_status") != "confirmed":
            continue

        confirmations = _select("events", type=PERSON_CONFIRMED_HELP, case_id=case_id)
        answered_at = [
            parsed
            for parsed in (
                _parse_timestamp(event.get("created_at")) for event in confirmations
            )
            if parsed is not None
        ]
        if any(parsed >= done_at for parsed in answered_at):
            continue

        if reopen(case_id, "Person did not confirm that help arrived"):
            reopened += 1

    return reopened


# ─── Small Supabase helpers ────────────────────────────────────────────────


def _select(table: str, **filters: Any) -> List[Mapping[str, Any]]:
    query = get_db().table(table).select("*")
    for column, value in filters.items():
        query = query.eq(column, value)
    rows = _rows(execute(query))
    return [row for row in rows if isinstance(row, Mapping)]


def _select_one(table: str, **filters: Any) -> Optional[Mapping[str, Any]]:
    rows = _select(table, **filters)
    return rows[0] if rows else None


def _update(table: str, values: Mapping[str, Any], **filters: Any) -> Any:
    query = get_db().table(table).update(dict(values))
    for column, value in filters.items():
        query = query.eq(column, value)
    return execute(query)


def _rows(result: Any) -> list:
    return list(getattr(result, "data", result) or [])


def _top_priority() -> float:
    highest = 0.0
    for case in _select("cases"):
        value = case.get("priority_score")
        if isinstance(value, (int, float)):
            highest = max(highest, float(value))
    return highest


def _next_ring(case_id: int) -> int:
    rings = [
        row.get("ring")
        for row in _select("dispatches", case_id=case_id)
        if isinstance(row.get("ring"), int)
    ]
    return (max(rings) if rings else 0) + 1


def _parse_timestamp(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _age_seconds(now: datetime, then: datetime) -> float:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return max(0.0, (now - then).total_seconds())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Background loop ───────────────────────────────────────────────────────


async def run_forever(interval: int = SWEEP_INTERVAL_S) -> None:
    """Sweep forever. Cancelled by the FastAPI lifespan on shutdown."""
    while True:
        try:
            await asyncio.to_thread(sweep)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - one bad tick must not stop the loop
            logger.exception("Silence sweep failed; retrying next tick")
        await asyncio.sleep(interval)
