"""Coordinator-facing case routes: queue, approve, dispatch panel, reopen.

Approval is the only thing that sends a case out. The channel choice decides
whether nearby volunteers are offered it, a responder handoff link is minted,
or both happen. Contact details never appear here: the person's phone leaves
the backend only in ``services/dispatch.accept``.
"""

from __future__ import annotations

import logging
import secrets
from datetime import timedelta
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core import config
from core.events import CASE_APPROVED, RESPONDER_LINK_SENT, emit
from core.phone import mask
from routes import store
from services import approval, dispatch, officials, silence

logger = logging.getLogger("safezone.routes.cases")

router = APIRouter(tags=["cases"])

Channel = Literal["volunteers", "responder", "both"]


class ApproveRequest(BaseModel):
    channel: Channel = "volunteers"
    target_label: Optional[str] = Field(default=None, max_length=120)


class ReopenRequest(BaseModel):
    reason: str = Field(default="Manual re-open by coordinator", max_length=200)
    reoffer: bool = True


class ResponderLinkRequest(BaseModel):
    target_label: Optional[str] = Field(default=None, max_length=120)


@router.get("/api/cases")
def list_cases() -> List[Dict[str, Any]]:
    """The ranked queue. Open work first, then everything for the timeline.

    Five queries, whatever the queue length. The obvious version -- build each
    case's view on its own -- costs four round trips per case, and against a
    hosted database that is seconds of dead air on the one screen a
    coordinator is staring at while deciding what to do next.
    """
    cases = store.by_priority(store.select("cases"))
    if not cases:
        return []

    incidents = store.index_by(
        store.select_in("incidents", "id", (c.get("incident_id") for c in cases))
    )
    people = store.index_by(
        store.select_in("people", "id", (c.get("person_id") for c in cases))
    )
    zones = store.index_by(
        store.select_in(
            "zones", "id", (i.get("zone_id") for i in incidents.values())
        )
    )

    # One query for every dispatch across the whole queue, counted in memory.
    counts: Dict[Any, int] = {}
    for row in store.select_in("dispatches", "case_id", (c.get("id") for c in cases)):
        counts[row.get("case_id")] = counts.get(row.get("case_id"), 0) + 1

    views = []
    for case in cases:
        incident = incidents.get(case.get("incident_id"))
        person = people.get(case.get("person_id"))
        zone = zones.get(incident.get("zone_id")) if incident else None
        views.append(
            _assemble(case, incident, person, zone, counts.get(case.get("id"), 0))
        )
    return views


def _assemble(
    case: Dict[str, Any],
    incident: Optional[Dict[str, Any]],
    person: Optional[Dict[str, Any]],
    zone: Optional[Dict[str, Any]],
    dispatch_count: int,
) -> Dict[str, Any]:
    """Build one case view from rows already in hand.

    The single source of truth for the shape of a case as the frontend sees
    it. ``_case_view`` fetches the rows and calls this; the queue endpoint
    fetches them in bulk and calls this. Two assemblers would drift.
    """
    view: Dict[str, Any] = dict(case)
    view["incident"] = incident
    # First name only: the phone number is released on ACCEPT, not here.
    view["person"] = (
        {
            "id": person.get("id"),
            "first_name": person.get("first_name"),
            "person_vuln": person.get("person_vuln") or {},
        }
        if person
        else None
    )
    view["zone"] = zone
    view["dispatch_count"] = dispatch_count
    return view


@router.get("/api/cases/{case_id}")
def get_case(case_id: int) -> Dict[str, Any]:
    case = _require_case(case_id)
    view = _case_view(case, include_children=True)
    view["dispatches"] = _dispatch_rows(case_id)
    view["events"] = _event_rows(case_id)
    return view


@router.post("/api/proposals/{case_id}/approve")
def approve(case_id: int, body: ApproveRequest) -> Dict[str, Any]:
    """Approve a proposal and send it out on the chosen channel.

    The work lives in ``services/approval`` so that approving from the control
    room and approving by WhatsApp cannot drift apart.
    """
    try:
        return approval.approve(case_id, body.channel, body.target_label)
    except approval.ApprovalError as exc:
        status = 404 if "not found" in str(exc) else 409
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.post("/api/cases/{case_id}/responderlink")
def responder_link(case_id: int, body: ResponderLinkRequest) -> Dict[str, Any]:
    _require_case(case_id)
    return _mint_link(case_id, body.target_label)


@router.get("/api/cases/{case_id}/dispatches")
def dispatches(case_id: int) -> List[Dict[str, Any]]:
    _require_case(case_id)
    return _dispatch_rows(case_id)


@router.post("/api/cases/{case_id}/reopen")
def reopen(case_id: int, body: ReopenRequest) -> Dict[str, Any]:
    _require_case(case_id)
    if not silence.reopen(case_id, body.reason, reoffer=body.reoffer):
        raise HTTPException(
            status_code=409, detail=f"Case {case_id} cannot be reopened."
        )
    return {
        "case_id": case_id,
        "reopened": True,
        "reason": body.reason,
        "case": _case_view(_require_case(case_id), include_children=False),
    }


# ─── Views ─────────────────────────────────────────────────────────────────


def _require_case(case_id: int) -> Dict[str, Any]:
    case = store.select_one("cases", id=case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")
    return case


def _case_view(case: Dict[str, Any], include_children: bool) -> Dict[str, Any]:
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

    view = _assemble(
        case,
        incident,
        person,
        zone,
        len(store.select("dispatches", case_id=case.get("id"))),
    )
    if include_children:
        view["responder_links"] = [
            {key: link.get(key) for key in ("token", "target_label", "created_at", "expires_at")}
            for link in store.select("responder_links", case_id=case.get("id"))
        ]
    return view


def _dispatch_rows(case_id: int) -> List[Dict[str, Any]]:
    rows = []
    for row in store.select("dispatches", case_id=case_id):
        volunteer = store.select_one("volunteers", id=row.get("volunteer_id")) or {}
        rows.append(
            {
                **row,
                "volunteer": {
                    "id": volunteer.get("id"),
                    "name": volunteer.get("name"),
                    "phone_masked": mask(volunteer.get("phone") or ""),
                    "is_demo": volunteer.get("is_demo"),
                },
            }
        )
    rows.sort(key=lambda row: int(row.get("id") or 0))
    return rows


def _event_rows(case_id: int, limit: int = 100) -> List[Dict[str, Any]]:
    rows = store.select("events", case_id=case_id)
    rows.sort(key=lambda row: int(row.get("id") or 0), reverse=True)
    return rows[:limit]


def _offered_view(volunteer_ids: List[int]) -> List[Dict[str, Any]]:
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


def _mint_link(
    case_id: int, target_label: Optional[str], service: Optional[str] = None
) -> Dict[str, Any]:
    """Thin passthrough; the minting itself lives in services/approval."""
    return approval.mint_link(case_id, target_label, service)
