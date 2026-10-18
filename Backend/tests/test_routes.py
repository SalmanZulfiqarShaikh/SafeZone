"""Route-level tests without a server: the handlers are plain functions.

Every route is exercised against the query-builder double, so the tests check
the JSON shape and the guard rails (404s, no person phone, token expiry)
without a network.
"""

from datetime import timedelta

import pytest
from fastapi import HTTPException

from core import config
from routes import admin, cases, responder, store, volunteers
from services import approval, silence
from tests.fake_db import FakeDB


@pytest.fixture
def world(monkeypatch):
    db = FakeDB()
    sent = []
    events = []
    offers = []

    # Routes reach the database through routes.store.
    monkeypatch.setattr(store, "get_db", lambda: db)
    monkeypatch.setattr(store, "execute", lambda query: query.execute())

    # Dispatch runs for real in the approve test unless stubbed there.
    monkeypatch.setattr(cases.dispatch, "get_db", lambda: db)
    monkeypatch.setattr(cases.dispatch, "execute", lambda query: query.execute())
    monkeypatch.setattr(
        cases.dispatch, "send_message", lambda to, text: sent.append((to, text)) or True
    )
    monkeypatch.setattr(cases.dispatch, "emit", lambda *args, **kwargs: None)

    monkeypatch.setattr(silence, "get_db", lambda: db)
    monkeypatch.setattr(silence, "execute", lambda query: query.execute())
    monkeypatch.setattr(silence, "emit", lambda *args, **kwargs: None)

    # Approval work moved into services/approval; it emits and reads there.
    monkeypatch.setattr(
        approval,
        "emit",
        lambda event_type, payload=None, case_id=None: events.append(
            (event_type, payload or {}, case_id)
        ),
    )
    monkeypatch.setattr(
        cases,
        "emit",
        lambda event_type, payload=None, case_id=None: events.append(
            (event_type, payload or {}, case_id)
        ),
    )
    monkeypatch.setattr(
        admin,
        "emit",
        lambda event_type, payload=None, case_id=None: events.append(
            (event_type, payload or {}, case_id)
        ),
    )
    return {"db": db, "tables": db.tables, "sent": sent, "events": events, "offers": offers}


def _incident(**overrides):
    row = {
        "id": 1,
        "category": "flood",
        "lat": 24.92,
        "lng": 67.09,
        "zone_id": "gulshan",
        "location_known": True,
        "status": "open",
        "dispatch_status": "none",
        "urgency": 0.75,
        "confidence": 0.7,
    }
    row.update(overrides)
    return row


def _case(**overrides):
    row = {
        "id": 10,
        "incident_id": 1,
        "person_id": 5,
        "priority_score": 0.9,
        "reason": "Flood, location known",
        "vuln_summary": "elderly",
        "protocol_path": ["category:flood"],
        "status": "proposed",
        "dispatch_status": "none",
        "reopened": False,
        "reopen_reason": None,
    }
    row.update(overrides)
    return row


def _person(**overrides):
    row = {
        "id": 5,
        "phone": "923001234567",
        "first_name": "Sara",
        "person_vuln": {"elderly": True},
    }
    row.update(overrides)
    return row


def test_queue_is_ranked_and_never_exposes_the_person_phone(world):
    world["tables"]["incidents"].append(_incident())
    world["tables"]["people"].append(_person())
    world["tables"]["zones"].append({"id": "gulshan", "name": "Gulshan-e-Iqbal"})
    world["tables"]["cases"].extend(
        [_case(id=10, priority_score=0.4), _case(id=11, priority_score=0.95)]
    )

    queue = cases.list_cases()

    assert [row["id"] for row in queue] == [11, 10]
    assert queue[0]["person"] == {
        "id": 5,
        "first_name": "Sara",
        "person_vuln": {"elderly": True},
    }
    assert "phone" not in queue[0]["person"]
    assert "923001234567" not in str(queue)


def test_approving_with_volunteers_offers_the_case(world):
    world["tables"]["incidents"].append(_incident())
    world["tables"]["people"].append(_person())
    world["tables"]["cases"].append(_case())
    world["tables"]["volunteers"].append(
        {
            "id": 3,
            "name": "Ali",
            "phone": "923003333333",
            "status": "on_duty",
            "zone_ids": ["gulshan"],
            "lat": 24.93,
            "lng": 67.10,
        }
    )

    result = cases.approve(10, cases.ApproveRequest(channel="volunteers"))

    assert world["tables"]["cases"][0]["status"] == "approved"
    assert any(event[0] == "CaseApproved" for event in world["events"])
    assert result["channel"] == "volunteers"
    assert result["offered"] == [
        {"id": 3, "name": "Ali", "phone_masked": "********3333"}
    ]
    assert world["tables"]["dispatches"][0]["status"] == "offered"


def test_approving_a_missing_case_is_404(world):
    with pytest.raises(HTTPException) as exc:
        cases.approve(99, cases.ApproveRequest(channel="volunteers"))

    assert exc.value.status_code == 404


def test_resolved_cases_cannot_be_approved_again(world):
    world["tables"]["cases"].append(_case(status="resolved"))

    with pytest.raises(HTTPException) as exc:
        cases.approve(10, cases.ApproveRequest(channel="volunteers"))

    assert exc.value.status_code == 409


def test_responder_channel_mints_a_token_without_offering(world, monkeypatch):
    world["tables"]["incidents"].append(_incident())
    world["tables"]["people"].append(_person())
    world["tables"]["cases"].append(_case())
    monkeypatch.setattr(config, "PUBLIC_BASE_URL", "https://safezone.example")

    result = cases.approve(
        10, cases.ApproveRequest(channel="responder", target_label="Edhi Control")
    )

    link = result["responder_link"]
    assert link["url"] == f"https://safezone.example/r/{link['token']}"
    assert len(link["token"]) >= 16
    assert world["tables"]["responder_links"][0]["case_id"] == 10
    assert not world["offers"]
    assert any(event[0] == "ResponderLinkSent" for event in world["events"])


def test_both_channel_offers_and_mints(world):
    world["tables"]["incidents"].append(_incident())
    world["tables"]["people"].append(_person())
    world["tables"]["cases"].append(_case())

    result = cases.approve(10, cases.ApproveRequest(channel="both"))

    assert "responder_link" in result
    # The offer is stubbed to return no ids, so the warning is surfaced.
    assert "dispatch_warning" in result


def test_unknown_location_warning_is_reported(world):
    world["tables"]["incidents"].append(_incident(location_known=False))
    world["tables"]["people"].append(_person())
    world["tables"]["cases"].append(_case())

    result = cases.approve(10, cases.ApproveRequest(channel="volunteers"))

    assert result["offered"] == []
    assert "dispatch_warning" in result


def test_reopen_delegates_to_silence(world, monkeypatch):
    world["tables"]["cases"].append(_case(status="approved", dispatch_status="closed"))
    calls = []
    monkeypatch.setattr(
        cases.silence, "reopen", lambda case_id, reason, reoffer=True: calls.append(
            (case_id, reason, reoffer)
        )
        or True
    )

    result = cases.reopen(10, cases.ReopenRequest(reason="Coordinator retry"))

    assert result["reopened"] is True
    assert calls == [(10, "Coordinator retry", True)]


def test_reopen_refuses_cases_silence_will_not_open(world, monkeypatch):
    world["tables"]["cases"].append(_case(status="resolved", dispatch_status="closed"))
    monkeypatch.setattr(cases.silence, "reopen", lambda *args, **kwargs: False)

    with pytest.raises(HTTPException) as exc:
        cases.reopen(10, cases.ReopenRequest())

    assert exc.value.status_code == 409


def test_responder_view_shows_first_name_and_call_number_only(world, monkeypatch):
    # _incident() is a flood, and flooding routes to the relief organisation,
    # not the ambulance.
    monkeypatch.setattr(config, "EMERGENCY_NGO", "9100")
    world["tables"]["incidents"].append(_incident())
    world["tables"]["people"].append(_person())
    world["tables"]["zones"].append({"id": "gulshan", "name": "Gulshan-e-Iqbal"})
    world["tables"]["cases"].append(_case())
    world["tables"]["reports"].extend(
        [{"id": 1, "incident_id": 1}, {"id": 2, "incident_id": 1}]
    )
    world["tables"]["responder_links"].append(
        {
            "id": 1,
            "token": "unguessable-token",
            "case_id": 10,
            "target_label": "Edhi Control",
            "expires_at": (store.now() + timedelta(hours=1)).isoformat(),
        }
    )

    view = responder.responder_view("unguessable-token")

    assert view["person"] == {"first_name": "Sara"}
    assert "phone" not in str(view)
    assert view["incident"]["report_count"] == 2
    # A reader-facing label, not the internal key: "Ngo" is not a thing to put
    # in front of someone deciding whether to call.
    assert view["call"] == {"label": "Relief organisation", "number": "9100"}
    assert view["case"]["protocol_path"] == ["category:flood"]


def test_missing_call_number_degrades_to_null(world, monkeypatch):
    monkeypatch.setattr(config, "EMERGENCY_NGO", "")
    world["tables"]["incidents"].append(_incident())
    world["tables"]["cases"].append(_case())
    world["tables"]["responder_links"].append(
        {
            "id": 1,
            "token": "tok",
            "case_id": 10,
            "expires_at": (store.now() + timedelta(hours=1)).isoformat(),
        }
    )

    view = responder.responder_view("tok")

    assert view["call"]["number"] is None


def test_expired_responder_link_is_410(world):
    world["tables"]["responder_links"].append(
        {
            "id": 1,
            "token": "old",
            "case_id": 10,
            "expires_at": "2020-01-01T00:00:00+00:00",
        }
    )

    with pytest.raises(HTTPException) as exc:
        responder.responder_view("old")

    assert exc.value.status_code == 410


def test_unknown_responder_token_is_404(world):
    with pytest.raises(HTTPException) as exc:
        responder.responder_view("nope")

    assert exc.value.status_code == 404


def test_volunteer_list_keeps_numbers_unmasked(world):
    world["tables"]["volunteers"].extend(
        [
            {"id": 2, "name": "Zara", "phone": "923001111111", "status": "on_duty"},
            {
                "id": 1,
                "name": "Ali",
                "phone": "923002222222",
                "status": "off_duty",
                "zone_ids": ["gulshan"],
                "is_demo": True,
            },
        ]
    )

    rows = volunteers.list_volunteers()

    assert [row["name"] for row in rows] == ["Ali", "Zara"]
    assert rows[0]["phone"] == "923002222222"
    assert rows[0]["is_demo"] is True


def test_kill_switch_toggles_and_emits(world, monkeypatch):
    monkeypatch.setattr(config, "KILL_SWITCH", False)

    first = admin.killswitch(admin.KillSwitchRequest(enabled=None))
    assert first == {"kill_switch": True}
    assert config.KILL_SWITCH is True

    second = admin.killswitch(admin.KillSwitchRequest(enabled=False))
    assert second == {"kill_switch": False}
    assert [event[1]["enabled"] for event in world["events"]] == [True, False]


def test_status_reports_switches_and_problems(world):
    status = admin.status()

    assert {"kill_switch", "mock_mode", "demo_mode", "allowlist_only", "problems"} <= set(status)
    assert isinstance(status["problems"], list)
