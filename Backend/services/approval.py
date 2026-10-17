"""Approving a case, from wherever the coordinator happens to be.

Approval is the one manual step in the loop (AGENTS.md 11), so it has to be
reachable from whatever the coordinator has in their hand -- the control room
page, or a WhatsApp reply at 3am from a phone in a dark room. Both routes run
exactly the same code, because "approved from the UI" and "approved by text"
must not be able to behave differently.

The route layer (``routes/cases.py``) adds HTTP shapes and error codes. The
WhatsApp layer (``services/intake.py``) adds authorisation and a short reply.
What actually happens to the case lives here, once.
"""

from __future__ import annotations

import logging
import secrets
from datetime import timedelta
from typing import Any, Dict, Optional

from core import config
from core.events import CASE_APPROVED, RESPONDER_LINK_SENT, emit
from core.phone import mask
from routes import store
from services import dispatch, officials

logger = logging.getLogger("safezone.approval")

CHANNELS = ("volunteers", "responder", "both")

# A case in one of these states is finished; approving it again would offer a
# closed emergency to a volunteer.
UNAPPROVABLE_STATUSES = ("rejected", "resolved")


class ApprovalError(RuntimeError):
    """Raised when a case cannot be approved. The message is user-facing."""


def approve(
    case_id: int,
    channel: str = "volunteers",
    target_label: Optional[str] = None,
    *,
    approved_by: Optional[str] = None,
) -> Dict[str, Any]:
    """Approve a case and send it out. Returns what happened, for the caller.

    ``approved_by`` is a masked phone when this came over WhatsApp, so the
    event log shows who acted without storing a full number.

    Raises:
        ApprovalError: unknown case, or one already finished.
    """
    if channel not in CHANNELS:
        raise ApprovalError(f"Channel must be one of: {', '.join(CHANNELS)}.")

    case = store.select_one("cases", id=case_id)
    if case is None:
        raise ApprovalError(f"Case {case_id} not found.")

    status = case.get("status")
    if status in UNAPPROVABLE_STATUSES:
        raise ApprovalError(f"Case {case_id} is {status} and cannot be approved.")

    already_approved = status == "approved"

    store.update("cases", {"status": "approved"}, id=case_id)
    emit(
        CASE_APPROVED,
        {"channel": channel, "approved_by": approved_by, "reapproved": already_approved},
        case_id=case_id,
    )

    incident = (
        store.select_one("incidents", id=case.get("incident_id"))
        if case.get("incident_id") is not None
        else None
    )
    category = (incident or {}).get("category") or "other"

    result: Dict[str, Any] = {
        "case_id": case_id,
        "status": "approved",
        "channel": channel,
        "category": category,
    }

    if channel in ("volunteers", "both"):
        offered_ids = dispatch.offer_case(case_id, ring=1)
        result["offered"] = _offered_view(offered_ids)
        if not offered_ids:
            result["dispatch_warning"] = (
                "No volunteers could be offered this case right now. Check that it "
                "has a known location, is volunteer-eligible, and that someone is on duty."
            )

    # Fire and medical are never volunteer-only (AGENTS.md 11), so the official
    # handoff is forced here rather than left to whoever clicked Approve.
    official = officials.handoff(category, target_label)
    wants_responder = channel in ("responder", "both")
    if wants_responder or official["required"]:
        link = mint_link(case_id, official["target_label"], service=official["service"])
        result["responder_link"] = link
        result["official"] = official
        if official["required"] and not wants_responder:
            result["official_forced"] = (
                f"{official['label']} handoff was created automatically: a "
                f"{category} case is never volunteer-only."
            )

        zone = (
            store.select_one("zones", id=(incident or {}).get("zone_id"))
            if incident and incident.get("zone_id")
            else None
        )
        result["official_notified"] = officials.notify(
            official,
            case_id=case_id,
            url=link["url"],
            category=category,
            area=(zone or {}).get("name"),
            reason=case.get("reason"),
            vuln_summary=case.get("vuln_summary"),
        )

    logger.info(
        "Case %s approved on channel %s%s",
        case_id,
        channel,
        f" by {approved_by}" if approved_by else "",
    )
    return result


def reject(case_id: int, *, rejected_by: Optional[str] = None) -> Dict[str, Any]:
    """Mark a case rejected so it leaves the queue without dispatching anyone."""
    case = store.select_one("cases", id=case_id)
    if case is None:
        raise ApprovalError(f"Case {case_id} not found.")

    store.update("cases", {"status": "rejected"}, id=case_id)
    logger.info(
        "Case %s rejected%s", case_id, f" by {rejected_by}" if rejected_by else ""
    )
    return {"case_id": case_id, "status": "rejected"}


def mint_link(
    case_id: int, target_label: Optional[str], service: Optional[str] = None
) -> Dict[str, Any]:
    """Create a responder handoff link for a case."""
    token = secrets.token_urlsafe(16)
    expires_at = (store.now() + timedelta(hours=config.RESPONDER_LINK_TTL_HOURS)).isoformat()
    store.insert(
        "responder_links",
        {
            "token": token,
            "case_id": case_id,
            "target_label": target_label,
            "expires_at": expires_at,
        },
    )
    path = f"/r/{token}"
    url = f"{config.PUBLIC_BASE_URL}{path}" if config.PUBLIC_BASE_URL else path
    emit(
        RESPONDER_LINK_SENT,
        {
            "target_label": target_label,
            "expires_at": expires_at,
            "service": service,
            # Nothing was sent to any organisation. A link was created.
            "simulated": True,
        },
        case_id=case_id,
    )
    return {
        "token": token,
        "url": url,
        "expires_at": expires_at,
        "target_label": target_label,
    }


def summarise(result: Dict[str, Any]) -> str:
    """One short paragraph describing an approval, for a WhatsApp reply."""
    case_id = result["case_id"]
    lines = [f"Case {case_id} approved."]

    offered = result.get("offered") or []
    if offered:
        names = ", ".join(v.get("name") or "a volunteer" for v in offered)
        lines.append(f"Offered to {names}.")
    elif result.get("dispatch_warning"):
        lines.append("No volunteer could be offered — nobody on duty nearby.")

    if result.get("official_notified"):
        label = (result.get("official") or {}).get("label", "Emergency services")
        lines.append(f"{label} sent the case link.")
    elif result.get("official"):
        lines.append("Official handoff created but the message was not delivered.")

    return "\n".join(lines)


def _offered_view(volunteer_ids: list) -> list:
    offered = []
    for volunteer_id in volunteer_ids:
        volunteer = store.select_one("volunteers", id=volunteer_id) or {}
        offered.append(
            {
                "id": volunteer_id,
                "name": volunteer.get("name"),
                "phone_masked": mask(volunteer.get("phone") or ""),
            }
        )
    return offered
