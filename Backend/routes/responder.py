"""Public responder handoff page data.

One read-only view behind an unguessable token. No login, no phone numbers:
first name only, exact pin, and the number to call. The token expires so a
link forwarded after the event stops working.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from core import config
from routes import store
from services import protocol

router = APIRouter(tags=["responder"])


@router.get("/api/r/{token}")
def responder_view(token: str) -> Dict[str, Any]:
    link = store.select_one("responder_links", token=token)
    if link is None:
        raise HTTPException(status_code=404, detail="This link is not valid.")

    expires_at = store.parse_timestamp(link.get("expires_at"))
    if expires_at is not None and store.now() > expires_at:
        raise HTTPException(status_code=410, detail="This link has expired.")

    case = store.select_one("cases", id=link.get("case_id"))
    if case is None:
        raise HTTPException(status_code=404, detail="The case behind this link is gone.")

    incident = (
        store.select_one("incidents", id=case.get("incident_id"))
        if case.get("incident_id") is not None
        else None
    )
    person = (
        store.select_one("people", id=case.get("person_id"))
        if case.get("person_id") is not None
        else None
    )
    zone = (
        store.select_one("zones", id=incident.get("zone_id"))
        if incident and incident.get("zone_id")
        else None
    )
    reports = (
        store.select("reports", incident_id=incident.get("id")) if incident else []
    )

    category = (incident or {}).get("category") or "other"
    emergency_kind = protocol.node(category).get("emergency_kind", "ngo")
    call_number = config.get_emergency_number(emergency_kind)

    return {
        "token": token,
        "target_label": link.get("target_label"),
        "expires_at": link.get("expires_at"),
        "case": {
            "id": case.get("id"),
            "status": case.get("status"),
            "dispatch_status": case.get("dispatch_status"),
            "priority_score": case.get("priority_score"),
            "reason": case.get("reason"),
            "vuln_summary": case.get("vuln_summary"),
            "protocol_path": case.get("protocol_path"),
            "reopened": bool(case.get("reopened")),
            "reopen_reason": case.get("reopen_reason"),
            "created_at": case.get("created_at"),
        },
        "incident": (
            {
                "id": incident.get("id"),
                "category": incident.get("category"),
                "urgency": incident.get("urgency"),
                "confidence": incident.get("confidence"),
                "location_known": bool(incident.get("location_known")),
                "lat": incident.get("lat"),
                "lng": incident.get("lng"),
                "area": incident.get("area"),
                "status": incident.get("status"),
                "dispatch_status": incident.get("dispatch_status"),
                "created_at": incident.get("created_at"),
                "report_count": len(reports),
            }
            if incident
            else None
        ),
        "person": (
            {"first_name": person.get("first_name")} if person else None
        ),
        "zone": (
            {"id": zone.get("id"), "name": zone.get("name"), "risk_level": zone.get("risk_level")}
            if zone
            else None
        ),
        "call": {
            "label": emergency_kind.capitalize(),
            "number": call_number,
        },
    }
