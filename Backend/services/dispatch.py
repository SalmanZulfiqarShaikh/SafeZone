"""Volunteer dispatch: offer, accept, arrive, finish.

Only approved cases with a known location can be offered. Ranking is plain
straight-line distance with volunteers in the incident's own zone first. No
map API, no routing, no network.

The confidentiality rule is enforced here: the offer message contains no exact
location and no contact number. Contact is released in exactly one place --
:func:`accept`, to the volunteer who won the row.

``dispatches(case_id, volunteer_id)`` is unique in the schema, so every write
is an upsert. Re-escalation adds the next ring; it never offers the same case
to the same volunteer twice.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional

from core import config, geo
from core.db import execute, get_db
from core.events import (
    VOLUNTEER_ACCEPTED,
    VOLUNTEER_ARRIVED,
    VOLUNTEER_DONE,
    VOLUNTEER_OFFERED,
    emit,
)
from core.phone import mask
from services import protocol
from services.whatsapp import send_message

logger = logging.getLogger("safezone.dispatch")

ACTIVE_DISPATCH_STATUSES = ("offered", "accepted", "on_way", "arrived")
RING_SIZE = config.VOLUNTEER_OFFER_RING_SIZE


# A case may be offered to neighbours while it is still proposed: volunteers
# are *asked*, not dispatched, and waiting for a coordinator to wake up costs
# the minutes that decide most outcomes. What a volunteer receives carries an
# area and a one-line summary -- no name, no number, no exact pin -- and any
# of them can decline.
#
# A finished case is a different matter: once it is resolved or rejected,
# offering it again would send someone to an emergency that is over.
UNOFFERABLE_STATUSES = ("resolved", "rejected")


def offer_case(case_id: int, ring: int = 1) -> List[int]:
    """Offer a live case to the next ring of volunteers.

    Returns the volunteer ids that were offered it. Empty when the case cannot
    be dispatched (unknown location, structural damage, nobody available).

    The official handoff is the step that still waits for a human
    (``services/approval``). Sending an ambulance to a misread message spends
    a vehicle the city has few of; asking a neighbour to look does not.
    """
    context = _case_context(case_id)
    if context is None:
        return []

    case, incident, zone = context["case"], context["incident"], context["zone"]

    status = case.get("status")
    if status in UNOFFERABLE_STATUSES:
        logger.warning("Case %s is %s; refusing to offer it", case_id, status)
        return []

    # AGENTS.md 9 bars dispatching a case with no location at all. An area the
    # person named is a location -- enough to pick the volunteer who covers it
    # and to tell them where to go -- so area-level cases are offered, while a
    # case with nothing at all still is not. The offer message says which it is
    # (see _offer_text), so no volunteer is sent to a false pin.
    if not incident:
        return []

    if not incident.get("location_known") and not incident.get("location_source"):
        logger.warning("Case %s has no location at all; cannot offer it", case_id)
        return []

    if not protocol.is_volunteer_eligible(incident.get("category")):
        logger.info(
            "Case %s category %r is not volunteer-eligible",
            case_id,
            incident.get("category"),
        )
        return []

    lat, lng = incident.get("lat"), incident.get("lng")
    if lat is None or lng is None:
        logger.warning("Case %s has no coordinates; cannot rank volunteers", case_id)
        return []

    on_duty = _select("volunteers", status="on_duty")
    if not on_duty:
        logger.warning("No volunteers are on duty for case %s", case_id)
        return []

    busy_ids = {
        row.get("volunteer_id")
        for row in _select("dispatches")
        if row.get("status") in ACTIVE_DISPATCH_STATUSES
    }
    case_dispatches = _select("dispatches", case_id=case_id)
    already_offered = {row.get("volunteer_id") for row in case_dispatches}

    # One row per phone in the demo: re-offering must reach the *other* phone,
    # not a second row that shares the first phone's number.
    offered_phones = set()
    if config.DEMO_MODE:
        for row in case_dispatches:
            other = _select_one("volunteers", id=row.get("volunteer_id"))
            if other and other.get("phone"):
                offered_phones.add(other["phone"])

    zone_id = incident.get("zone_id")
    candidates = []
    for volunteer in on_duty:
        volunteer_id = volunteer.get("id")
        if volunteer_id in busy_ids or volunteer_id in already_offered:
            continue
        if volunteer.get("phone") in offered_phones:
            continue
        v_lat, v_lng = volunteer.get("lat"), volunteer.get("lng")
        if v_lat is None or v_lng is None:
            continue
        in_zone = zone_id in (volunteer.get("zone_ids") or [])
        candidates.append(
            (
                0 if in_zone else 1,
                geo.distance_km(lat, lng, v_lat, v_lng),
                volunteer,
            )
        )

    candidates.sort(key=lambda item: (item[0], item[1]))
    if config.DEMO_MODE:
        # The demo has only two real phones, but many volunteer rows sharing
        # them. Offer each phone once: ring 1 is the nearest phone, ring 2 is
        # the other one.
        chosen = _demo_ring(candidates)
    else:
        chosen = candidates[: max(RING_SIZE, 1)]

    offered: List[int] = []
    for _zone_rank, distance, volunteer in chosen:
        volunteer_id = volunteer.get("id")
        _upsert(
            "dispatches",
            {
                "case_id": case_id,
                "volunteer_id": volunteer_id,
                "ring": ring,
                "status": "offered",
                "offered_at": _now_iso(),
            },
            on_conflict="case_id,volunteer_id",
        )
        send_message(volunteer["phone"], _offer_text(case_id, case, incident, zone))
        emit(
            VOLUNTEER_OFFERED,
            {
                "case_id": case_id,
                "volunteer_id": volunteer_id,
                "phone_masked": mask(volunteer["phone"]),
                "ring": ring,
                "distance_km": round(distance, 2),
            },
            case_id=case_id,
        )
        offered.append(volunteer_id)

    if offered:
        _update("cases", {"dispatch_status": "offered"}, id=case_id)
        if incident.get("id") is not None:
            _update("incidents", {"dispatch_status": "offered"}, id=incident["id"])
        logger.info("Offered case %s (ring %s) to %d volunteers", case_id, ring, len(offered))

    return offered


def accept(case_id: int, volunteer_id: int) -> bool:
    """Claim an offered case. First caller wins; contact goes only to them."""
    context = _case_context(case_id)
    if context is None:
        return False

    dispatch_row = _select_one(
        "dispatches", case_id=case_id, volunteer_id=volunteer_id
    )
    if dispatch_row is None or dispatch_row.get("status") != "offered":
        return False

    volunteer = _select_one("volunteers", id=volunteer_id)
    if volunteer is None:
        logger.warning("Volunteer %s accepted case %s but has no row", volunteer_id, case_id)
        return False

    _update(
        "dispatches",
        {"status": "accepted", "accepted_at": _now_iso()},
        case_id=case_id,
        volunteer_id=volunteer_id,
    )
    _update("volunteers", {"status": "busy"}, id=volunteer_id)
    _update("cases", {"dispatch_status": "accepted"}, id=case_id)
    incident = context["incident"]
    if incident and incident.get("id") is not None:
        _update("incidents", {"dispatch_status": "accepted"}, id=incident["id"])

    # AGENTS.md 2.1 #6: the person is told before their details leave the
    # backend, not after. The order of these two calls is the consent rule.
    _notify_person(
        context,
        "I am sharing your location and number with a nearby volunteer so they "
        "can reach you. A volunteer is on the way.\n"
        "Reply STOP at any time to opt out.",
    )
    _release_contact(context, volunteer)
    _notify_other_volunteers(case_id, volunteer_id)

    emit(
        VOLUNTEER_ACCEPTED,
        {
            "case_id": case_id,
            "volunteer_id": volunteer_id,
            "phone_masked": mask(volunteer["phone"]),
        },
        case_id=case_id,
    )
    logger.info("Volunteer %s accepted case %s", volunteer_id, case_id)
    return True


def decline(case_id: int, volunteer_id: int) -> bool:
    """Mark an offer declined. Re-offering the next ring is silence.py's job."""
    dispatch_row = _select_one(
        "dispatches", case_id=case_id, volunteer_id=volunteer_id
    )
    if dispatch_row is None or dispatch_row.get("status") != "offered":
        return False

    _update(
        "dispatches",
        {"status": "declined"},
        case_id=case_id,
        volunteer_id=volunteer_id,
    )

    volunteer = _select_one("volunteers", id=volunteer_id)
    if volunteer:
        send_message(volunteer["phone"], f"Thanks for responding. Case {case_id} will go to someone else.")
    return True


def arrive(case_id: int, volunteer_id: int) -> bool:
    dispatch_row = _select_one(
        "dispatches", case_id=case_id, volunteer_id=volunteer_id
    )
    if dispatch_row is None or dispatch_row.get("status") not in ("accepted", "on_way"):
        return False

    _update(
        "dispatches",
        {"status": "arrived", "arrived_at": _now_iso()},
        case_id=case_id,
        volunteer_id=volunteer_id,
    )
    _set_status("cases", case_id, "arrived")
    context = _case_context(case_id)
    if context and context["incident"]:
        _set_status("incidents", context["incident"]["id"], "arrived")

    volunteer = _select_one("volunteers", id=volunteer_id)
    if volunteer:
        send_message(
            volunteer["phone"],
            f"Thank you for reaching case {case_id}. Reply DONE {case_id} when you have finished.",
        )

    emit(
        VOLUNTEER_ARRIVED,
        {"case_id": case_id, "volunteer_id": volunteer_id},
        case_id=case_id,
    )
    return True


def finish(case_id: int, volunteer_id: int) -> bool:
    dispatch_row = _select_one(
        "dispatches", case_id=case_id, volunteer_id=volunteer_id
    )
    if dispatch_row is None or dispatch_row.get("status") not in (
        "accepted",
        "on_way",
        "arrived",
    ):
        return False

    _update(
        "dispatches",
        {"status": "done", "done_at": _now_iso()},
        case_id=case_id,
        volunteer_id=volunteer_id,
    )
    _update("volunteers", {"status": "on_duty"}, id=volunteer_id)
    _set_status("cases", case_id, "confirmed")
    context = _case_context(case_id)
    if context and context["incident"]:
        _set_status("incidents", context["incident"]["id"], "confirmed")

    volunteer = _select_one("volunteers", id=volunteer_id)
    if volunteer:
        send_message(
            volunteer["phone"],
            f"Case {case_id} closed. Thank you for helping. You are back on duty.",
        )

    _notify_person(context, "Did help reach you? Reply 1 yes, 2 no.")

    emit(
        VOLUNTEER_DONE,
        {"case_id": case_id, "volunteer_id": volunteer_id},
        case_id=case_id,
    )
    return True


def _demo_ring(candidates: List[tuple]) -> List[tuple]:
    """Offer exactly one phone. Already-offered phones are excluded upstream,
    so the first remaining candidate is ring 2 on a re-escalation."""
    for item in candidates:
        if item[2].get("phone"):
            return [item]
    return []


# ─── Message composition ───────────────────────────────────────────────────


def _offer_text(
    case_id: int,
    case: Mapping[str, Any],
    incident: Mapping[str, Any],
    zone: Optional[Mapping[str, Any]],
) -> str:
    area = zone["name"] if zone else "the reported area"
    vuln = (case.get("vuln_summary") or "").strip()
    vulnerability = f" {vuln[0].upper() + vuln[1:]}." if vuln else ""
    minutes = _minutes_since(incident.get("first_report_at"))
    age = f" Reported {minutes} min ago." if minutes is not None else ""
    category = (incident.get("category") or "emergency").replace("_", " ")

    # Never let an area centre read as the person's doorstep.
    if incident.get("location_source") == "area":
        precision = " Exact location not shared yet — area only."
    else:
        precision = ""

    return (
        f"Case {case_id} near {area}.{vulnerability} {category.capitalize()}.{age}"
        f"{precision}\n"
        f"Reply ACCEPT {case_id} to take it.\n"
        "Assess from a safe place. Do not enter floodwater or burning buildings."
    )


def _release_contact(context: Mapping[str, Any], volunteer: Mapping[str, Any]) -> None:
    """The one place a person's phone number leaves the backend."""
    case_id = context["case"]["id"]
    person = context["person"]
    incident = context["incident"]
    zone = context["zone"]

    lines = [f"Case {case_id} is yours."]
    if person:
        first_name = (person.get("first_name") or "").strip() or "the person who reported"
        lines.append(f"Name: {first_name}.")
        if person.get("phone"):
            lines.append(f"Contact: {person['phone']}.")
    if incident and incident.get("lat") is not None and incident.get("lng") is not None:
        lines.append(
            f"Location: https://maps.google.com/?q={incident['lat']},{incident['lng']}"
        )
    elif zone:
        lines.append(f"Area: {zone['name']}.")
    lines.append(
        f"Reply ARRIVED {case_id} when you get there, DONE {case_id} when finished."
    )

    send_message(volunteer["phone"], "\n".join(lines))


def _notify_other_volunteers(case_id: int, winner_id: int) -> None:
    for row in _select("dispatches", case_id=case_id, status="offered"):
        if row.get("volunteer_id") == winner_id:
            continue
        _update(
            "dispatches",
            {"status": "expired"},
            case_id=case_id,
            volunteer_id=row["volunteer_id"],
        )
        other = _select_one("volunteers", id=row["volunteer_id"])
        if other:
            send_message(other["phone"], f"Case {case_id} was taken, thanks.")


def _notify_person(context: Optional[Mapping[str, Any]], text: str) -> None:
    if not context:
        return
    person = context.get("person")
    if person and person.get("phone"):
        send_message(person["phone"], text)


# ─── Small Supabase helpers ────────────────────────────────────────────────


def _case_context(case_id: int) -> Optional[Dict[str, Any]]:
    case = _select_one("cases", id=case_id)
    if case is None:
        logger.warning("Case %s not found", case_id)
        return None

    incident = (
        _select_one("incidents", id=case.get("incident_id"))
        if case.get("incident_id") is not None
        else None
    )
    person = (
        _select_one("people", id=case.get("person_id"))
        if case.get("person_id") is not None
        else None
    )
    zone = (
        _select_one("zones", id=incident.get("zone_id"))
        if incident and incident.get("zone_id")
        else None
    )
    return {"case": case, "incident": incident, "person": person, "zone": zone}


def _set_status(table: str, row_id: Any, status: str) -> None:
    if row_id is None:
        return
    _update(table, {"dispatch_status": status}, id=row_id)


def _select(table: str, **filters: Any) -> List[Mapping[str, Any]]:
    query = get_db().table(table).select("*")
    for column, value in filters.items():
        query = query.eq(column, value)
    rows = _rows(execute(query))
    return [row for row in rows if isinstance(row, Mapping)]


def _select_one(table: str, **filters: Any) -> Optional[Mapping[str, Any]]:
    rows = _select(table, **filters)
    return rows[0] if rows else None


def _insert(table: str, row: Mapping[str, Any]) -> Any:
    return execute(get_db().table(table).insert(dict(row)))


def _upsert(table: str, row: Mapping[str, Any], on_conflict: str) -> Any:
    return execute(get_db().table(table).upsert(dict(row), on_conflict=on_conflict))


def _update(table: str, values: Mapping[str, Any], **filters: Any) -> Any:
    query = get_db().table(table).update(dict(values))
    for column, value in filters.items():
        query = query.eq(column, value)
    return execute(query)


def _rows(result: Any) -> list:
    return list(getattr(result, "data", result) or [])


def _minutes_since(timestamp: Any) -> Optional[int]:
    parsed = _parse_timestamp(timestamp)
    if parsed is None:
        return None
    return max(0, int((datetime.now(timezone.utc) - parsed).total_seconds() // 60))


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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
