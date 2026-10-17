from datetime import datetime, timezone

import pytest

from core import config
from services import dispatch, silence
from tests.fake_db import FakeDB

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)


def _case(db, case_id=1, dispatch_status="offered", status="approved"):
    db.tables["zones"].append({"id": "gulshan", "name": "Gulshan-e-Iqbal"})
    db.tables["incidents"].append(
        {
            "id": 10,
            "category": "flood",
            "lat": 24.92,
            "lng": 67.09,
            "zone_id": "gulshan",
            "location_known": True,
            "priority_score": 0.5,
            "dispatch_status": dispatch_status,
            "first_report_at": "2026-10-17T11:40:00+00:00",
        }
    )
    db.tables["people"].append({"id": 20, "phone": "923009999999", "first_name": "Amina"})
    db.tables["cases"].append(
        {
            "id": case_id,
            "incident_id": 10,
            "person_id": 20,
            "status": status,
            "dispatch_status": dispatch_status,
            "priority_score": 0.5,
            "reopened": False,
        }
    )


def _volunteer(db, volunteer_id, phone, lat, lng, status="on_duty"):
    db.tables["volunteers"].append(
        {
            "id": volunteer_id,
            "name": f"Volunteer {volunteer_id}",
            "phone": phone,
            "status": status,
            "lat": lat,
            "lng": lng,
            "zone_ids": ["gulshan"],
        }
    )


@pytest.fixture
def world(monkeypatch):
    db = FakeDB()
    sent = []
    events = []

    def fake_emit(event_type, payload=None, case_id=None):
        events.append((event_type, payload or {}, case_id))

    for module in (silence, dispatch):
        monkeypatch.setattr(module, "get_db", lambda: db)
        monkeypatch.setattr(module, "execute", lambda query: query.execute())
        monkeypatch.setattr(module, "emit", fake_emit)

    monkeypatch.setattr(
        dispatch, "send_message", lambda to, text: sent.append((to, text)) or True
    )

    monkeypatch.setattr(dispatch, "RING_SIZE", 3)
    monkeypatch.setattr(dispatch.config, "DEMO_MODE", False)
    monkeypatch.setattr(config, "VOLUNTEER_ACCEPT_TIMEOUT_S", 60)
    monkeypatch.setattr(config, "VOLUNTEER_ARRIVE_TIMEOUT_S", 300)
    monkeypatch.setattr(config, "PERSON_SILENCE_TIMEOUT_S", 600)

    return {"db": db, "sent": sent, "events": events, "tables": db.tables}


def test_unaccepted_offer_expires_and_next_ring_is_offered(world):
    _case(world["db"], dispatch_status="offered")
    _volunteer(world["db"], 1, "923000000001", 24.9201, 67.0901)
    _volunteer(world["db"], 2, "923000000002", 24.9202, 67.0902)
    world["tables"]["dispatches"].append(
        {
            "id": 30,
            "case_id": 1,
            "volunteer_id": 1,
            "ring": 1,
            "status": "offered",
            "offered_at": "2026-10-17T11:50:00+00:00",
        }
    )

    counts = silence.sweep(NOW)

    assert counts["expired_offers"] == 1
    assert world["tables"]["dispatches"][0]["status"] == "expired"
    assert world["tables"]["dispatches"][1]["status"] == "offered"
    assert world["tables"]["dispatches"][1]["ring"] == 2
    assert world["tables"]["dispatches"][1]["volunteer_id"] == 2

    case = world["tables"]["cases"][0]
    assert case["reopened"] is True
    assert case["reopen_reason"] == "No volunteer accepted in time"
    assert case["priority_score"] > 0.5
    assert case["dispatch_status"] == "offered"

    types = [event[0] for event in world["events"]]
    assert "DispatchExpired" in types
    assert "CaseReopened" in types
    assert "VolunteerOffered" in types


def test_fresh_offer_is_left_alone(world):
    _case(world["db"], dispatch_status="offered")
    _volunteer(world["db"], 1, "923000000001", 24.9201, 67.0901)
    world["tables"]["dispatches"].append(
        {
            "id": 30,
            "case_id": 1,
            "volunteer_id": 1,
            "ring": 1,
            "status": "offered",
            "offered_at": "2026-10-17T11:59:30+00:00",
        }
    )

    counts = silence.sweep(NOW)

    assert counts == {"expired_offers": 0, "expired_accepts": 0, "silent_people": 0}
    assert world["tables"]["dispatches"][0]["status"] == "offered"
    assert world["tables"]["cases"][0]["reopened"] is False


def test_volunteer_who_never_arrives_is_freed_and_case_reopened(world):
    _case(world["db"], dispatch_status="accepted")
    _volunteer(world["db"], 1, "923000000001", 24.9201, 67.0901, status="busy")
    world["tables"]["dispatches"].append(
        {
            "id": 30,
            "case_id": 1,
            "volunteer_id": 1,
            "ring": 1,
            "status": "accepted",
            "accepted_at": "2026-10-17T11:40:00+00:00",
        }
    )

    counts = silence.sweep(NOW)

    assert counts["expired_accepts"] == 1
    assert world["tables"]["dispatches"][0]["status"] == "expired"
    assert world["tables"]["volunteers"][0]["status"] == "on_duty"
    assert world["tables"]["cases"][0]["reopened"] is True
    assert any(event[0] == "DispatchExpired" for event in world["events"])


def test_unanswered_help_question_reopens_the_case(world):
    _case(world["db"], dispatch_status="confirmed")
    _volunteer(world["db"], 1, "923000000001", 24.9201, 67.0901)
    world["tables"]["dispatches"].append(
        {
            "id": 30,
            "case_id": 1,
            "volunteer_id": 1,
            "ring": 1,
            "status": "done",
            "done_at": "2026-10-17T11:30:00+00:00",
        }
    )

    counts = silence.sweep(NOW)

    assert counts["silent_people"] == 1
    assert world["tables"]["cases"][0]["reopened"] is True


def test_a_person_who_answered_yes_is_not_reopened(world):
    _case(world["db"], dispatch_status="confirmed")
    _volunteer(world["db"], 1, "923000000001", 24.9201, 67.0901)
    world["tables"]["dispatches"].append(
        {
            "id": 30,
            "case_id": 1,
            "volunteer_id": 1,
            "ring": 1,
            "status": "done",
            "done_at": "2026-10-17T11:30:00+00:00",
        }
    )
    world["tables"]["events"].append(
        {
            "id": 40,
            "type": "PersonConfirmedHelp",
            "case_id": 1,
            "created_at": "2026-10-17T11:31:00+00:00",
        }
    )

    counts = silence.sweep(NOW)

    assert counts["silent_people"] == 0
    assert world["tables"]["cases"][0]["reopened"] is False


def test_confirm_closes_the_case(world):
    _case(world["db"], dispatch_status="confirmed")

    assert silence.confirm(1) is True

    case = world["tables"]["cases"][0]
    assert case["status"] == "resolved"
    assert case["dispatch_status"] == "closed"
    assert case["closed_at"]
    assert world["tables"]["incidents"][0]["status"] == "resolved"
    assert [event[0] for event in world["events"]] == [
        "PersonConfirmedHelp",
        "CaseClosed",
    ]


def test_a_closed_case_cannot_be_reopened(world):
    _case(world["db"], dispatch_status="closed")
    world["tables"]["cases"][0]["status"] = "resolved"

    assert silence.reopen(1, "late message") is False
    assert world["tables"]["cases"][0]["dispatch_status"] == "closed"


def test_latest_case_returns_the_newest_reopenable_one(world):
    _case(world["db"], case_id=1, dispatch_status="confirmed")
    world["tables"]["cases"].append(
        {
            "id": 2,
            "incident_id": 10,
            "person_id": 20,
            "status": "approved",
            "dispatch_status": "arrived",
        }
    )
    world["tables"]["cases"].append(
        {
            "id": 3,
            "incident_id": 10,
            "person_id": 20,
            "status": "proposed",
            "dispatch_status": "none",
        }
    )

    assert silence.latest_case(20)["id"] == 2
    assert silence.latest_case(999) is None


def test_reopening_with_no_volunteers_still_alerts(world):
    _case(world["db"], dispatch_status="offered")

    counts = silence.sweep(NOW)

    assert counts["expired_offers"] == 0
    assert silence.reopen(1, "manual") is True
    assert world["tables"]["cases"][0]["dispatch_status"] == "reopened"
    assert any(event[0] == "CaseReopened" for event in world["events"])
