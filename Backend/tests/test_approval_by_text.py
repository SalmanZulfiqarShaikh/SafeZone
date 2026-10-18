"""Approving a case over WhatsApp.

A coordinator with only a phone must be able to act, because that is the
realistic state at 3am. The rule that matters most here is authorisation:
"APPROVE 14" from anyone else would dispatch volunteers to a stranger's
emergency, so most of these tests are about who is refused.
"""

import pytest

from core import config
from services import alerts, approval, coordinator, dispatch, intake, merge, silence
from tests.fake_db import FakeDB

COORDINATOR = "923009999999"
STRANGER = "923001234567"


@pytest.fixture
def world(monkeypatch):
    db = FakeDB()
    sent = []
    events = []

    from services import officials

    for module in (
        intake,
        dispatch,
        merge,
        silence,
        alerts,
        coordinator,
        approval,
        officials,
    ):
        if hasattr(module, "get_db"):
            monkeypatch.setattr(module, "get_db", lambda: db)
        if hasattr(module, "execute"):
            monkeypatch.setattr(module, "execute", lambda query: query.execute())
        if hasattr(module, "emit"):
            monkeypatch.setattr(
                module,
                "emit",
                lambda event_type, payload=None, case_id=None: events.append(
                    (event_type, payload or {}, case_id)
                ),
            )
        if hasattr(module, "send_message"):
            monkeypatch.setattr(
                module, "send_message", lambda to, text: sent.append((to, text)) or True
            )

    from routes import store

    monkeypatch.setattr(store, "get_db", lambda: db)
    monkeypatch.setattr(store, "execute", lambda query: query.execute())

    monkeypatch.setattr(config, "MOCK_MODE", True)
    monkeypatch.setattr(config, "COORDINATOR_NUMBERS", [COORDINATOR])
    monkeypatch.setattr(config, "COORDINATOR_DEFAULT_CHANNEL", "both")
    monkeypatch.setattr(config, "EMERGENCY_AMBULANCE", "923000000001")
    monkeypatch.setattr(config, "EMERGENCY_FIRE", "923000000001")
    monkeypatch.setattr(config, "EMERGENCY_NGO", "923000000001")

    db.tables["zones"].append(
        {"id": "gulshan", "name": "Gulshan-e-Iqbal", "lat": 24.92, "lng": 67.09}
    )
    return {"db": db, "sent": sent, "events": events, "tables": db.tables}


def a_case(db, status="proposed", category="flood"):
    incident = {
        "id": db.next_id(),
        "category": category,
        "status": "open",
        "zone_id": "gulshan",
        "lat": 24.92,
        "lng": 67.09,
        "location_known": True,
        "location_source": "pin",
    }
    db.tables["incidents"].append(incident)
    case = {
        "id": db.next_id(),
        "incident_id": incident["id"],
        "status": status,
        "dispatch_status": "none",
        "priority_score": 0.5,
        "reason": "Flood, high urgency; elderly, alone",
        "vuln_summary": "elderly, alone",
    }
    db.tables["cases"].append(case)
    return case["id"]


# ─── Authorisation ─────────────────────────────────────────────────────────


def test_a_coordinator_can_approve_by_text(world):
    case_id = a_case(world["db"])

    intake.handle_inbound(COORDINATOR, f"APPROVE {case_id}")

    assert world["tables"]["cases"][0]["status"] == "approved"


def test_a_stranger_cannot_approve(world):
    """The whole point. This would dispatch people to someone else's emergency."""
    case_id = a_case(world["db"])

    intake.handle_inbound(STRANGER, f"APPROVE {case_id}")

    assert world["tables"]["cases"][0]["status"] == "proposed"
    reply = [t for to, t in world["sent"] if to == STRANGER][0]
    assert "Only a coordinator" in reply


def test_a_stranger_learns_nothing_about_the_case(world):
    """Refusal must not confirm whether case 14 exists."""
    intake.handle_inbound(STRANGER, "APPROVE 14")

    reply = [t for to, t in world["sent"] if to == STRANGER][0]
    assert "not found" not in reply.lower()
    assert "14" not in reply


def test_a_volunteer_is_not_a_coordinator(world):
    world["db"].tables["volunteers"].append(
        {"id": 1, "name": "Ali", "phone": STRANGER, "status": "on_duty"}
    )
    case_id = a_case(world["db"])

    intake.handle_inbound(STRANGER, f"APPROVE {case_id}")

    assert world["tables"]["cases"][0]["status"] == "proposed"


# ─── What approving does ───────────────────────────────────────────────────


def test_approving_offers_the_case_to_a_volunteer(world):
    case_id = a_case(world["db"])
    world["db"].tables["volunteers"].append(
        {
            "id": 50,
            "name": "Demo volunteer A",
            "phone": "923007777777",
            "zone_ids": ["gulshan"],
            "capabilities": ["foot"],
            "lat": 24.921,
            "lng": 67.091,
            "status": "on_duty",
        }
    )

    intake.handle_inbound(COORDINATOR, f"APPROVE {case_id}")

    assert any(to == "923007777777" for to, _t in world["sent"])


def test_approving_sends_the_official_handoff(world):
    case_id = a_case(world["db"])

    intake.handle_inbound(COORDINATOR, f"APPROVE {case_id}")

    assert any(to == "923000000001" for to, _t in world["sent"])


def test_the_coordinator_gets_told_what_happened(world):
    case_id = a_case(world["db"])

    intake.handle_inbound(COORDINATOR, f"APPROVE {case_id}")

    reply = [t for to, t in world["sent"] if to == COORDINATOR][0]
    assert f"Case {case_id} approved" in reply


def test_no_volunteer_available_is_said_plainly(world):
    case_id = a_case(world["db"])

    intake.handle_inbound(COORDINATOR, f"APPROVE {case_id}")

    reply = [t for to, t in world["sent"] if to == COORDINATOR][0]
    assert "nobody on duty" in reply.lower()


def test_the_event_log_records_who_approved(world):
    case_id = a_case(world["db"])

    intake.handle_inbound(COORDINATOR, f"APPROVE {case_id}")

    approved = [e for e in world["events"] if e[0] == "CaseApproved"]
    assert approved
    # Masked, never the full number.
    assert approved[0][1]["approved_by"].endswith("9999")
    assert COORDINATOR not in str(approved[0][1])


# ─── Rejecting ─────────────────────────────────────────────────────────────


def test_a_coordinator_can_reject(world):
    case_id = a_case(world["db"])

    intake.handle_inbound(COORDINATOR, f"REJECT {case_id}")

    assert world["tables"]["cases"][0]["status"] == "rejected"


def test_a_rejected_case_cannot_then_be_approved(world):
    case_id = a_case(world["db"], status="rejected")

    intake.handle_inbound(COORDINATOR, f"APPROVE {case_id}")

    assert world["tables"]["cases"][0]["status"] == "rejected"


# ─── Parsing ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text", ["APPROVE 14", "approve 14", "Approve #14", "APPROVE  14", "REJECT 3"]
)
def test_accepted_spellings(text):
    assert intake.COORDINATOR_COMMAND.match(text) is not None


@pytest.mark.parametrize("text", ["APPROVE", "APPROVE all", "approved 14", "14"])
def test_rejected_spellings(text):
    assert intake.COORDINATOR_COMMAND.match(text) is None


def test_an_unknown_case_says_so(world):
    intake.handle_inbound(COORDINATOR, "APPROVE 999")

    reply = [t for to, t in world["sent"] if to == COORDINATOR][0]
    assert "not found" in reply.lower()


def test_approve_still_works_inside_a_stacked_message(world):
    case_id = a_case(world["db"])

    intake.handle_inbound(COORDINATOR, f"ON DUTY\nAPPROVE {case_id}")

    assert world["tables"]["cases"][0]["status"] == "approved"
