"""Inbound WhatsApp message handling.

The order here is deliberate and load-bearing:

1. Normalize the sender. A malformed ``from`` is ignored, never raised.
2. Open the 24h window by touching the person row.
3. Send instant guidance from the static protocol graph -- before the LLM and
   before location is known. This is the reply someone in an emergency gets.
4. Only then extract structured fields and write report -> incident -> case.
5. Emit events so the control room can render the case without polling.

Every function is defensive: ``handle_inbound`` never raises. The webhook must
always answer Meta with HTTP 200, because Meta retries anything else and the
retry becomes a duplicate report.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Mapping, Optional

from core import config
from core.db import execute, get_db
from data import areas
from core.phone import mask, try_normalize
from core.events import (
    CASE_PROPOSED,
    INCIDENT_CREATED,
    REPORT_MERGED,
    REPORT_RECEIVED,
    VOLUNTEER_ON_DUTY,
    VOLUNTEER_REGISTERED,
    emit,
)
from services import (
    alerts,
    approval,
    coordinator,
    dispatch,
    extract,
    merge,
    protocol,
    registration,
    risk,
    silence,
)
from services.whatsapp import send_message

logger = logging.getLogger("safezone.intake")

WINDOW_HOURS = 24
SOURCE_WHATSAPP = "whatsapp"
SOURCE_FACTOR_WHATSAPP = 1.0

CASE_COMMAND = re.compile(r"^(ACCEPT|DECLINE|ARRIVED|DONE)\s+(\d+)$", re.I)
STRAY_REPLY = re.compile(r"^[12]$")
# Coordinators act by text so no laptop is needed at 3am.
COORDINATOR_COMMAND = re.compile(r"^(APPROVE|REJECT)\s+#?(\d+)$", re.I)

# Dispatchable cases need coordinates, so a case that opened without a pin is
# left upgradeable: a pin arriving later re-ranks it in place rather than
# opening a second case for the same emergency (AGENTS.md 9).
UPGRADEABLE_CASE_STATUSES = ("proposed", "approved")

# ─── Greeting filter ───────────────────────────────────────────────────────
# Deterministic by design. AGENTS.md 2.3 #1 keeps the LLM off the critical
# path, and that rule cuts both ways: a model must never be the reason someone
# in an emergency gets no reply. An exact-match list fails safe -- it behaves
# identically when the provider is down, and anything not on it gets the full
# help ladder. Multi-word greetings are matched after whitespace is collapsed.
GREETINGS = frozenset(
    {
        "hi", "hii", "hiii", "hello", "helo", "hey", "heyy", "yo",
        "salam", "salaam", "slam", "asalam", "assalam", "assalamualaikum",
        "assalam o alaikum", "assalam u alaikum", "asalam o alaikum",
        "aoa", "walaikum assalam", "walaikum salam",
        "good morning", "good afternoon", "good evening", "good night",
        "test", "testing", "test message",
        "ok", "okay", "k", "hmm", "hm",
        "thanks", "thank you", "thanx", "thx", "shukriya", "shukria",
        "jazakallah", "bye", "goodbye", "khuda hafiz",
    }
)

GREETING_PUNCTUATION = re.compile(r"[^\w\s]+", re.UNICODE)
GREETING_MAX_WORDS = 4

GREETING_REPLY_TEXT = (
    "Hello. If you need help, tell me what is happening and where you are "
    "-- for example: \"water is rising in my house in Gulshan\". "
    "You can also share your location pin."
)


def handle_inbound(
    sender: str,
    text: str,
    *,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    location_name: Optional[str] = None,
) -> None:
    """Process one inbound message. Never raises, never returns a status."""
    try:
        _handle(sender, text, lat=lat, lng=lng, location_name=location_name)
    except Exception:  # noqa: BLE001 - a webhook must not fail this path
        logger.exception("Inbound message handling failed")


def _handle(
    sender: str,
    text: str,
    *,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    location_name: Optional[str] = None,
) -> None:
    phone = try_normalize(sender)
    if phone is None:
        # We cannot reply to something we cannot address.
        logger.warning("Ignoring inbound from a malformed number %s", mask(str(sender)))
        return

    body = (text or "").strip()
    has_pin = lat is not None and lng is not None
    # Do not log message bodies: they can contain names and addresses.
    logger.info("Inbound from %s (%d chars, pin=%s)", mask(phone), len(body), has_pin)

    person = _touch_person(phone)
    if person is None:
        return

    if has_pin:
        _handle_location(phone, person, body, lat, lng, location_name)
        return

    if not body:
        send_message(
            phone,
            "Tell me what is happening and where you are, and I will give you "
            "safety steps right away.",
        )
        return

    # People stack commands in one message -- "VOLUNTEER Ali" on the first
    # line, "ON DUTY" on the second. Read line by line when any line is a
    # command, or the whole thing is taken as one and the name comes out as
    # "Ali\nON DUTY" while the second command is silently lost.
    for part in _split_commands(body):
        _dispatch_one(phone, person, part)
        # A later line can depend on an earlier one -- register, then go on
        # duty -- so re-read the person rather than reuse a stale copy.
        person = _select_one("people", phone=phone) or person


def _dispatch_one(phone: str, person: Mapping[str, Any], body: str) -> None:
    """Route one message, or one command line out of a stacked message."""
    if _handle_command(phone, person, body):
        return

    if is_greeting(body):
        # Not a report: no case, no ladder. One orientation line keeps the
        # funnel open without inventing an emergency.
        logger.info("Treating message from %s as a greeting", mask(phone))
        if config.GREETING_REPLY:
            send_message(phone, GREETING_REPLY_TEXT)
        return

    _handle_help_request(phone, person, body)


def _split_commands(body: str) -> list[str]:
    """Split a stacked command message into lines, or keep it whole.

    Only splits when the message is several lines AND at least one of them is
    a recognised command. A multi-line report ("water is rising\\nin my
    house") has no command lines, so it stays one report rather than becoming
    two nonsense ones.
    """
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if len(lines) > 1 and any(looks_like_command(line) for line in lines):
        return lines
    return [body]


def looks_like_command(body: str) -> bool:
    """True when a line is one of the deterministic commands."""
    upper = body.strip().upper()
    if upper in ("STOP", "ON DUTY", "OFF DUTY", "JOIN", "VOLUNTEER"):
        return True
    if upper.startswith(("JOIN ", "VOLUNTEER ")):
        return True
    stripped = body.strip()
    return bool(
        CASE_COMMAND.match(stripped)
        or STRAY_REPLY.match(stripped)
        or COORDINATOR_COMMAND.match(stripped)
    )


def is_greeting(body: str) -> bool:
    """True for a bare greeting or acknowledgement with no report in it.

    Conservative on purpose. A message is only a greeting when it is short,
    matches the list exactly after normalisation, and contains no emergency
    keyword at all -- "hi my house is on fire" is a fire, not a hello.
    """
    text = (body or "").strip().lower()
    if not text:
        return False

    if extract.quick_category(text) != "other":
        return False

    cleaned = GREETING_PUNCTUATION.sub(" ", text)
    cleaned = " ".join(cleaned.split())
    if not cleaned or len(cleaned.split()) > GREETING_MAX_WORDS:
        return False

    return cleaned in GREETINGS


# ─── Commands ──────────────────────────────────────────────────────────────


def _handle_command(phone: str, person: Mapping[str, Any], body: str) -> bool:
    """Handle deterministic commands. Returns True when the message was one."""
    upper = body.strip().upper()

    if upper == "STOP":
        _update("people", {"wants_alerts": False}, phone=phone)
        send_message(phone, "You will not receive further alerts. Message me again if you need help.")
        return True

    if COORDINATOR_COMMAND.match(body.strip()):
        _handle_coordinator_command(phone, body.strip())
        return True

    if upper == "JOIN" or upper.startswith("JOIN "):
        _redeem_registration(phone, body[len("JOIN") :].strip())
        return True

    if upper == "VOLUNTEER" or upper.startswith("VOLUNTEER "):
        _register_volunteer(phone, _one_line(body[len("VOLUNTEER") :]))
        return True

    if upper in ("ON DUTY", "OFF DUTY"):
        _set_presence(phone, "on_duty" if upper == "ON DUTY" else "off_duty")
        return True

    if CASE_COMMAND.match(body):
        _handle_case_command(phone, body)
        return True

    if STRAY_REPLY.match(body):
        _handle_help_reply(phone, person, body)
        return True

    return False


def _handle_help_reply(phone: str, person: Mapping[str, Any], body: str) -> None:
    """Handle the yes/no after "Did help reach you?".

    ``1`` closes the case; ``2`` reopens it and offers the next ring. Any other
    context keeps the generic prompt, so a stray number never invents a case.
    """
    case = silence.latest_case(person.get("id"))
    if case is None:
        send_message(
            phone,
            "Got it. If you still need help, tell me what is happening and where you are.",
        )
        return

    if body == "1":
        silence.confirm(case.get("id"))
        send_message(
            phone,
            "Thank you. I have marked this case as resolved. Message me again if you need help.",
        )
    else:
        silence.reopen(case.get("id"), "Person said help did not arrive")
        send_message(
            phone,
            "I am sorry help has not reached you. I have alerted the coordinator "
            "and we are trying again.",
        )


def _handle_case_command(phone: str, body: str) -> None:
    """Route ACCEPT/DECLINE/ARRIVED/DONE to dispatch for the sender's row.

    Success needs no reply here: dispatch sends the appropriate confirmation.
    A failure is answered explicitly so the volunteer knows nothing happened.
    """
    match = CASE_COMMAND.match(body)
    if match is None:
        return

    action = match.group(1).upper()
    case_id = int(match.group(2))

    volunteer = _select_one("volunteers", phone=phone)
    if volunteer is None:
        send_message(
            phone,
            "You are not registered as a volunteer yet. Reply VOLUNTEER your name to join.",
        )
        return

    handlers = {
        "ACCEPT": dispatch.accept,
        "DECLINE": dispatch.decline,
        "ARRIVED": dispatch.arrive,
        "DONE": dispatch.finish,
    }
    if handlers[action](case_id, volunteer.get("id")):
        return

    if action in ("ACCEPT", "DECLINE"):
        send_message(
            phone,
            f"There is no open offer for case {case_id} right now. If you still "
            "need help, tell me what is happening.",
        )
    else:
        send_message(
            phone,
            f"I have no active case {case_id} assigned to you. Reply ON DUTY if "
            "you are available.",
        )


def _handle_coordinator_command(phone: str, body: str) -> None:
    """APPROVE / REJECT a case by text, so the coordinator needs no laptop.

    Authorisation is the whole point of this function. ``APPROVE 14`` sent by
    anyone else would dispatch volunteers to a stranger's emergency, so the
    sender is checked against ``COORDINATOR_NUMBERS`` before anything happens,
    and a non-coordinator is told nothing about whether the case exists.
    """
    match = COORDINATOR_COMMAND.match(body)
    if match is None:
        return

    action = match.group(1).upper()
    case_id = int(match.group(2))

    if phone not in coordinator.numbers():
        logger.warning(
            "Rejected %s for case %s from %s: not a coordinator",
            action,
            case_id,
            mask(phone),
        )
        send_message(
            phone,
            "Only a coordinator can approve or reject a case. If you need help, "
            "tell me what is happening and where you are.",
        )
        return

    try:
        if action == "REJECT":
            approval.reject(case_id, rejected_by=mask(phone))
            send_message(phone, f"Case {case_id} rejected. Nobody was dispatched.")
            return

        result = approval.approve(
            case_id, config.COORDINATOR_DEFAULT_CHANNEL, approved_by=mask(phone)
        )
        send_message(phone, approval.summarise(result))
    except approval.ApprovalError as exc:
        send_message(phone, str(exc))
    except Exception:  # noqa: BLE001 - a bad approval must not kill the webhook
        logger.exception("Coordinator %s could not %s case %s", mask(phone), action, case_id)
        send_message(
            phone,
            f"Something went wrong approving case {case_id}. Try the control room.",
        )


def _redeem_registration(phone: str, code: str) -> None:
    """Finish a website registration started at the form.

    The reply never says *why* a code failed. An attacker guessing codes
    learns nothing from "expired" versus "already used", and a real person
    only needs to know to start again.
    """
    if not code:
        send_message(
            phone,
            "To finish signing up, reply with the code from the website. "
            "Example: JOIN ABC123",
        )
        return

    record = registration.redeem(code, phone)
    if record is None:
        send_message(
            phone,
            "That code is not valid any more. Please register again on the "
            "website for a new one.\n"
            "You do not need a code to ask for help -- just tell me what is "
            "happening and where you are.",
        )
        return

    updates: Dict[str, Any] = {
        "is_registered": True,
        "wants_alerts": bool(record.get("wants_alerts", True)),
    }
    if record.get("first_name"):
        updates["first_name"] = record["first_name"]
    if record.get("zone_id"):
        updates["zone_id"] = record["zone_id"]
    _update("people", updates, phone=phone)

    area = record.get("zone_id")
    where = f" for {area.title()}" if area else ""
    send_message(
        phone,
        f"Thank you{', ' + record['first_name'] if record.get('first_name') else ''}. "
        f"You are registered{where} and will get area alerts.\n"
        "If you ever need help, just message me what is happening and where you are.",
    )


def _one_line(value: str) -> str:
    """First line only. A name is never multi-line, whatever was typed."""
    return (value or "").strip().splitlines()[0].strip() if (value or "").strip() else ""


def _register_volunteer(phone: str, name: str) -> None:
    if not name:
        send_message(
            phone,
            "To join as a volunteer, reply: VOLUNTEER your name. "
            "Example: VOLUNTEER Ali",
        )
        return

    existing = _select_one("volunteers", phone=phone)
    now = _now_iso()
    if existing:
        _update(
            "volunteers",
            {"name": name[:80], "status": "off_duty", "window_open_until": now},
            phone=phone,
        )
    else:
        _insert(
            "volunteers",
            {
                "name": name[:80],
                "phone": phone,
                "zone_ids": [],
                "capabilities": [],
                "status": "off_duty",
                "window_open_until": now,
            },
        )

    emit(VOLUNTEER_REGISTERED, {"phone_masked": mask(phone), "name": name[:80]})
    send_message(
        phone,
        f"Thank you, {name[:40]}. You are registered as a volunteer.\n"
        "Reply ON DUTY when you are available to help, and OFF DUTY when you are not.",
    )


def _set_presence(phone: str, status: str) -> None:
    existing = _select_one("volunteers", phone=phone)
    if not existing:
        send_message(
            phone,
            "You are not registered as a volunteer yet. Reply VOLUNTEER your name to join.",
        )
        return

    _update(
        "volunteers",
        {"status": status, "window_open_until": _now_iso()},
        phone=phone,
    )
    emit(VOLUNTEER_ON_DUTY, {"phone_masked": mask(phone), "status": status})

    if status == "on_duty":
        send_message(
            phone,
            "You are on duty. I will send you nearby cases that match what you can help with.",
        )
    else:
        send_message(phone, "You are off duty. Reply ON DUTY when you are available again.")


# ─── Location pin path ─────────────────────────────────────────────────────


def _handle_location(
    phone: str,
    person: Mapping[str, Any],
    label: str,
    lat: float,
    lng: float,
    location_name: Optional[str],
) -> None:
    """Attach a shared pin to the person's open case, or open one with it.

    A pin is the only exact location SafeZone gets. Upgrading in place matters:
    a second case for the same emergency double-counts in the queue and splits
    the report history that ``risk.confidence`` reads.
    """
    person_id = person.get("id")
    if person_id is not None:
        _update("people", {"lat": lat, "lng": lng}, id=person_id)

    case = _upgradeable_case(person_id)
    if case is None:
        # A pin with no open case is still a report: run the normal ladder so
        # the person gets guidance, and keep the coordinates.
        _handle_help_request(phone, person, label, lat=lat, lng=lng)
        return

    incident_id = case.get("incident_id")
    incident = _select_one("incidents", id=incident_id) if incident_id is not None else None
    if incident is None:
        _handle_help_request(phone, person, label, lat=lat, lng=lng)
        return

    _update(
        "incidents",
        {
            "lat": lat,
            "lng": lng,
            "location_known": True,
            "location_source": "pin",
            "last_update_at": _now_iso(),
        },
        id=incident_id,
    )

    # Location is an input to the reason string, so the case re-ranks on
    # upgrade. ``risk.urgency_score`` accepts the stored numeric urgency.
    scoring_view = {
        **incident,
        "lat": lat,
        "lng": lng,
        "location_known": True,
    }
    priority_score, reason = risk.score(scoring_view, person.get("person_vuln") or {})
    _update(
        "cases",
        {"priority_score": priority_score, "reason": reason},
        id=case.get("id"),
    )

    emit(
        REPORT_RECEIVED,
        {
            "channel": SOURCE_WHATSAPP,
            "kind": "location_pin",
            "location_known": True,
            "location_name": location_name,
            "priority_score": priority_score,
        },
        case_id=case.get("id"),
    )

    logger.info("Upgraded case %s with a location pin", case.get("id"))
    send_message(
        phone,
        "Thank you, I have your location. Your case is now with the "
        "coordinator and nearby volunteers can be sent to you.",
    )


def _upgradeable_case(person_id: Any) -> Optional[Mapping[str, Any]]:
    """The person's newest open case that is still missing a location."""
    if person_id is None:
        return None

    candidates = []
    for case in _select_all("cases", person_id=person_id):
        if case.get("status") not in UPGRADEABLE_CASE_STATUSES:
            continue
        incident_id = case.get("incident_id")
        if incident_id is None:
            continue
        incident = _select_one("incidents", id=incident_id)
        if incident and not incident.get("location_known"):
            candidates.append(case)

    if not candidates:
        return None
    return max(candidates, key=lambda row: row.get("id") or 0)


# ─── Help request path ─────────────────────────────────────────────────────


def _handle_help_request(
    phone: str,
    person: Mapping[str, Any],
    body: str,
    *,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
) -> None:
    # Step 3 of the ladder: static guidance, before the LLM and before location.
    quick = extract.quick_category(body)
    guidance, protocol_path = protocol.guidance_reply(quick)
    send_message(phone, guidance)

    extraction = extract.extract_report(body)
    category = extraction["category"]

    person_id = person.get("id")
    person_vuln = _merge_vulnerability(person.get("person_vuln"), extraction["vulnerability"])
    if person_vuln != (person.get("person_vuln") or {}) and person_id is not None:
        _update("people", {"person_vuln": person_vuln}, id=person_id)

    # A typed neighbourhood name is a zone guess; only a shared pin is exact.
    location_known = lat is not None and lng is not None
    now = datetime.now(timezone.utc)
    zone_guess = _known_zone(extraction.get("zone_guess"))

    # Without coordinates a case cannot be ranked against volunteers or offered
    # to anyone, so naming an area substitutes that area's approximate centre.
    # ``location_known`` stays False -- this is not the person's location, and
    # location_source records which it is so a responder is never shown an
    # area centre as though someone were standing on it.
    location_source = "pin" if location_known else None
    if not location_known and zone_guess:
        centre = areas.centroid(zone_guess)
        if centre:
            lat, lng = centre
            location_source = "area"

    # Ten neighbours reporting one flooded street is one incident. Merging has
    # to happen before the insert, or the duplicate is already in the queue.
    existing = merge.find_match(
        category, lat=lat, lng=lng, zone_id=zone_guess, now=now
    )
    if existing is not None:
        _merge_into_existing(
            phone=phone,
            person=person,
            person_id=person_id,
            person_vuln=person_vuln,
            incident=existing,
            extraction=extraction,
            body=body,
            lat=lat,
            lng=lng,
            zone_guess=zone_guess,
            location_known=location_known,
            now=now,
        )
        return

    report_count = 1

    incident_row: Dict[str, Any] = {
        "category": category,
        "lat": lat,
        "lng": lng,
        "zone_id": zone_guess,
        "location_known": location_known,
        "location_source": location_source,
        "report_count": report_count,
        "confidence": risk.confidence(
            {"source_factor": SOURCE_FACTOR_WHATSAPP, "report_count": report_count}
        ),
        "urgency": risk.urgency_score(extraction["urgency"]),
        "status": "open",
        "dispatch_status": "none",
        "first_report_at": now.isoformat(),
        "last_update_at": now.isoformat(),
    }
    incident = _insert_returning("incidents", incident_row)
    incident_id = incident.get("id")

    _insert(
        "reports",
        {
            "person_id": person_id,
            "incident_id": incident_id,
            "raw_text": body,
            "source": SOURCE_WHATSAPP,
            "source_factor": SOURCE_FACTOR_WHATSAPP,
            "category": category,
            "lat": lat,
            "lng": lng,
            "zone_id": zone_guess,
            "location_known": location_known,
            "extraction": extraction,
        },
    )

    scoring_view = {
        **incident_row,
        "category": category,
        "urgency": extraction["urgency"],
        "report_count": report_count,
        "source_factor": SOURCE_FACTOR_WHATSAPP,
        "first_report_at": now,
        "location_known": location_known,
    }
    priority_score, reason = risk.score(scoring_view, person_vuln)

    case = _insert_returning(
        "cases",
        {
            "incident_id": incident_id,
            "person_id": person_id,
            "priority_score": priority_score,
            "reason": reason,
            "vuln_summary": _summarise_vulnerability(person_vuln),
            "protocol_path": protocol_path,
            "status": "proposed",
            "dispatch_status": "none",
        },
    )
    case_id = case.get("id")

    emit(
        REPORT_RECEIVED,
        {
            "channel": SOURCE_WHATSAPP,
            "category": category,
            "urgency": extraction["urgency"],
            "location_known": location_known,
        },
        case_id=case_id,
    )
    emit(
        INCIDENT_CREATED,
        {
            "incident_id": incident_id,
            "category": category,
            "priority_score": priority_score,
        },
        case_id=case_id,
    )
    emit(
        CASE_PROPOSED,
        {
            "priority_score": priority_score,
            "reason": reason,
            "location_known": location_known,
            "needs": extraction.get("needs", []),
        },
        case_id=case_id,
    )

    logger.info(
        "Created case %s for %s (category=%s, priority=%s)",
        case_id,
        mask(phone),
        category,
        priority_score,
    )

    # Nothing dispatches until a human approves, so tell them it is waiting.
    _alert_coordinators(
        case_id=case_id,
        category=category,
        priority_score=priority_score,
        reason=reason,
        vuln_summary=_summarise_vulnerability(person_vuln),
        zone_id=zone_guess,
        location_known=location_known,
        report_count=report_count,
    )

    # Warn registered neighbours. Gated on severity inside alerts, and the
    # reporter is excluded -- they already have the full guidance reply.
    _alert_area({**incident_row, "id": incident_id}, person_id)


def _merge_into_existing(
    *,
    phone: str,
    person: Mapping[str, Any],
    person_id: Any,
    person_vuln: Mapping[str, Any],
    incident: Mapping[str, Any],
    extraction: Mapping[str, Any],
    body: str,
    lat: Optional[float],
    lng: Optional[float],
    zone_guess: Optional[str],
    location_known: bool,
    now: datetime,
) -> None:
    """Record this report against an existing incident and re-rank its case.

    The person still got their guidance reply from the caller. What they do
    not get is a second case competing with their own first one.
    """
    incident_id = incident.get("id")

    updates = merge.merge_report(
        incident,
        urgency=extraction.get("urgency"),
        lat=lat,
        lng=lng,
        zone_id=zone_guess,
        source_factor=SOURCE_FACTOR_WHATSAPP,
        now=now,
    )
    merged = {**incident, **updates}

    _insert(
        "reports",
        {
            "person_id": person_id,
            "incident_id": incident_id,
            "raw_text": body,
            "source": SOURCE_WHATSAPP,
            "source_factor": SOURCE_FACTOR_WHATSAPP,
            "category": merged.get("category"),
            "lat": lat,
            "lng": lng,
            "zone_id": zone_guess,
            "location_known": location_known,
            "extraction": extraction,
        },
    )

    case = _select_one("cases", incident_id=incident_id)
    priority_score = None
    if case is not None:
        # A corroborated report raises confidence, which raises priority.
        priority_score, reason = risk.score(merged, person_vuln)
        _update(
            "cases",
            {"priority_score": priority_score, "reason": reason},
            id=case.get("id"),
        )

    emit(
        REPORT_MERGED,
        {
            "incident_id": incident_id,
            "report_count": merged.get("report_count"),
            "confidence": merged.get("confidence"),
            "priority_score": priority_score,
            "location_known": bool(merged.get("location_known")),
        },
        case_id=case.get("id") if case else None,
    )

    logger.info(
        "Merged report from %s into incident %s (%s reports)",
        mask(phone),
        incident_id,
        merged.get("report_count"),
    )

    # Corroboration can push an incident over the alert threshold even when the
    # first report did not reach it. Dedup lives in alerts, so re-checking is
    # safe: nobody is told twice about the same incident.
    _alert_area(merged, person_id)


def _known_zone(zone_guess: Any) -> Optional[str]:
    """Keep a zone only if it exists in ``zones``, otherwise drop it.

    ``incidents.zone_id`` is a foreign key. Writing a zone name we can
    recognise in text but have never seeded fails the whole insert, and the
    person disappears from the queue *after* being told help was alerted --
    the worst possible failure mode. An unknown area is simply unknown: the
    case still opens, and the coordinator sees it needs a phone call.
    """
    if not zone_guess:
        return None

    zone_id = str(zone_guess).strip().lower()
    if not zone_id:
        return None

    try:
        if _select_one("zones", id=zone_id) is not None:
            return zone_id
    except Exception:  # noqa: BLE001 - a lookup failure must not lose the report
        logger.exception("Could not verify zone %r; dropping it", zone_id)
        return None

    logger.warning(
        "Extracted zone %r is not in the zones table; storing the case without "
        "a zone. Seed it in data/seed.py if SafeZone should cover it.",
        zone_id,
    )
    return None


def _alert_coordinators(*, zone_id: Optional[str] = None, **fields: Any) -> None:
    """Tell the coordinators a case is waiting. Never breaks the help path."""
    try:
        zone = _select_one("zones", id=zone_id) if zone_id else None
        coordinator.notify_new_case(area=(zone or {}).get("name"), **fields)
    except Exception:  # noqa: BLE001 - a notification must not lose the case
        logger.exception("Could not alert coordinators about case %s", fields.get("case_id"))


def _alert_area(incident: Mapping[str, Any], reporter_id: Any) -> None:
    """Fan out an area warning. Never lets an alert failure break intake."""
    try:
        alerts.alert_for_incident(incident, exclude_person_id=reporter_id)
    except Exception:  # noqa: BLE001 - a warning must not cost us the report
        logger.exception("Zone alert failed for incident %s", incident.get("id"))


# ─── Small Supabase helpers ────────────────────────────────────────────────


def _touch_person(phone: str) -> Optional[Mapping[str, Any]]:
    """Upsert the person and keep their 24h WhatsApp window open."""
    now = datetime.now(timezone.utc)
    window_until = (now + timedelta(hours=WINDOW_HOURS)).isoformat()

    try:
        result = execute(
            get_db()
            .table("people")
            .upsert({"phone": phone, "window_open_until": window_until}, on_conflict="phone")
        )
        rows = _rows(result)
        if rows:
            return rows[0]
    except Exception as exc:  # fall through to a plain lookup
        logger.warning("Could not upsert person %s: %s", mask(phone), exc)

    row = _select_one("people", phone=phone)
    if row is None:
        logger.error("Person row for %s disappeared after upsert", mask(phone))
    return row


def _insert(table: str, row: Mapping[str, Any]) -> Any:
    return execute(get_db().table(table).insert(dict(row)))


def _insert_returning(table: str, row: Mapping[str, Any]) -> Mapping[str, Any]:
    """Insert and return the new row, or ``{}`` if the client returned none."""
    result = _insert(table, row)
    rows = _rows(result)
    return rows[0] if rows and isinstance(rows[0], Mapping) else {}


def _select_one(table: str, **filters: Any) -> Optional[Mapping[str, Any]]:
    rows = _select(table, **filters)
    return rows[0] if rows else None


def _select(table: str, **filters: Any) -> list[Mapping[str, Any]]:
    """Single-row lookup. Use :func:`_select_all` when every match matters."""
    query = get_db().table(table).select("*")
    for column, value in filters.items():
        query = query.eq(column, value)
    rows = _rows(execute(query.limit(1)))
    return [row for row in rows if isinstance(row, Mapping)]


def _select_all(table: str, **filters: Any) -> list[Mapping[str, Any]]:
    query = get_db().table(table).select("*")
    for column, value in filters.items():
        query = query.eq(column, value)
    rows = _rows(execute(query))
    return [row for row in rows if isinstance(row, Mapping)]


def _update(table: str, values: Mapping[str, Any], **filters: Any) -> Any:
    query = get_db().table(table).update(dict(values))
    for column, value in filters.items():
        query = query.eq(column, value)
    return execute(query)


def _rows(result: Any) -> list:
    data = getattr(result, "data", result)
    return list(data or [])


def _merge_vulnerability(
    existing: Optional[Mapping[str, Any]], extracted: Mapping[str, Any]
) -> Dict[str, Any]:
    """Keep every answered field; never overwrite an answer with ``None``."""
    merged: Dict[str, Any] = dict(existing or {})
    for field, value in (extracted or {}).items():
        if value is not None:
            merged[field] = value
    return merged


def _summarise_vulnerability(person_vuln: Mapping[str, Any]) -> str:
    labels = []
    if person_vuln.get("elderly"):
        labels.append("elderly")
    if person_vuln.get("mobility_limited"):
        labels.append("mobility limited")
    if person_vuln.get("children_present"):
        labels.append("children present")
    if person_vuln.get("chronic_illness"):
        labels.append("chronic illness")
    if person_vuln.get("alone"):
        labels.append("alone")
    floor = str(person_vuln.get("floor") or "").strip().lower()
    if floor in ("ground", "0", "g"):
        labels.append("ground floor")
    elif floor:
        labels.append(f"floor {floor}")
    return ", ".join(labels)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
