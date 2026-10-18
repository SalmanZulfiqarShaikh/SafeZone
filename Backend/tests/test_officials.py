"""Official-service handoff policy.

Two things are being protected here, and the honesty one matters more than
the routing one: SafeZone has no integration with any emergency service or
NGO, and nothing it produces may imply otherwise (AGENTS.md 2.2).
"""

import os
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core import config
from routes import cases as cases_routes
from routes import store
from services import approval, dispatch, officials, silence
from tests.fake_db import FakeDB


@pytest.fixture(autouse=True)
def numbers(monkeypatch):
    """Obviously fake numbers. Never a real emergency number in a test."""
    monkeypatch.setattr(config, "EMERGENCY_FIRE", "1000000")
    monkeypatch.setattr(config, "EMERGENCY_AMBULANCE", "2000000")
    monkeypatch.setattr(config, "EMERGENCY_NGO", "3000000")


# ─── Routing ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "category,service",
    [
        ("fire", "fire"),
        ("structural", "fire"),
        ("medical", "medical"),
        # Rescue, not a stretcher: someone stranded on a roof needs a crew
        # that can reach them, and the ambulance cannot.
        ("trapped", "fire"),
        # Flooding is a relief job. This used to route to the ambulance, which
        # meant "paani ghar me aa gaya" answered with an ambulance number --
        # wrong service, and wrong enough that a real caller would waste the
        # one call they had.
        ("flood", "ngo"),
        ("other", "ngo"),
    ],
)
def test_categories_route_to_the_right_service(category, service):
    assert officials.service_for(category) == service


def test_no_category_routes_a_waterlogging_report_to_an_ambulance():
    """Guards the specific misroute, not just the table.

    The table above can be edited to agree with a future bug. This asserts the
    property that made the bug matter: water alone is never a medical call.
    """
    assert officials.service_for("flood") != "medical"


def test_an_unknown_category_still_routes_somewhere():
    """A typo must not leave a case with no official target at all."""
    assert officials.service_for("banana") in ("fire", "medical", "ngo")


@pytest.mark.parametrize("category", ["fire", "medical"])
def test_fire_and_medical_always_require_an_official_handoff(category):
    assert officials.requires_official(category) is True


# ─── Honesty ───────────────────────────────────────────────────────────────


def test_a_handoff_is_always_flagged_simulated_in_the_data():
    """The flag the UI reads is always set, whatever the message text says."""
    for category in ("fire", "medical", "flood", "trapped", "structural", "other"):
        assert officials.handoff(category)["simulated"] is True


@pytest.mark.skipif(
    os.getenv("SHOW_SIMULATION_LABELS", "") != "",
    reason=(
        "This documents the shipped default. The environment overrides it here, "
        "which is a deployment decision -- labels belong ON whenever "
        "ALLOWLIST_ONLY is off and a stranger could reach the number."
    ),
)
def test_message_labels_are_off_by_default():
    """In a controlled demo every recipient is allow-listed and already knows."""
    assert config.SHOW_SIMULATION_LABELS is False
    assert "simulated" not in officials.handoff("fire")["target_label"].lower()


def test_labels_appear_when_switched_on(monkeypatch):
    monkeypatch.setattr(config, "SHOW_SIMULATION_LABELS", True)

    for category in ("fire", "medical", "flood", "trapped", "structural", "other"):
        assert "simulated" in officials.handoff(category)["target_label"].lower()


def test_a_coordinator_label_is_kept(monkeypatch):
    assert "Chhipa Control Room" in officials.handoff("fire", "Chhipa Control Room")["target_label"]


def test_a_coordinator_label_is_marked_when_labels_are_on(monkeypatch):
    """Naming a real desk must not make this look like an integration."""
    monkeypatch.setattr(config, "SHOW_SIMULATION_LABELS", True)
    record = officials.handoff("fire", "Chhipa Control Room")

    assert "Chhipa Control Room" in record["target_label"]
    assert "simulated" in record["target_label"].lower()


def test_the_simulated_stamp_is_not_doubled(monkeypatch):
    monkeypatch.setattr(config, "SHOW_SIMULATION_LABELS", True)
    once = officials.target_label("fire")
    twice = officials.target_label("fire", once)

    assert twice.lower().count("simulated") == 1


def test_the_note_says_safezone_does_not_dispatch():
    assert "does not dispatch" in officials.handoff("fire")["note"]


def test_a_missing_number_degrades_instead_of_raising(monkeypatch):
    """AGENTS.md 2.1 #8: unset numbers stay empty and loud, never guessed."""
    monkeypatch.setattr(config, "EMERGENCY_FIRE", "")

    record = officials.handoff("fire")

    assert record["number"] is None
    assert record["required"] is True


# ─── Through the approve endpoint ──────────────────────────────────────────


@pytest.fixture
def world(monkeypatch):
    db = FakeDB()
    events = []

    for module in (store, dispatch, silence):
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
            monkeypatch.setattr(module, "send_message", lambda to, text: True)

    monkeypatch.setattr(
        approval,
        "emit",
        lambda event_type, payload=None, case_id=None: events.append(
            (event_type, payload or {}, case_id)
        ),
    )
    monkeypatch.setattr(
        cases_routes,
        "emit",
        lambda event_type, payload=None, case_id=None: events.append(
            (event_type, payload or {}, case_id)
        ),
    )
    monkeypatch.setattr(config, "MOCK_MODE", True)
    monkeypatch.setattr(config, "PUBLIC_BASE_URL", "")
    return {"db": db, "events": events, "tables": db.tables}


@pytest.fixture
def client(world):
    app = FastAPI()
    app.include_router(cases_routes.router)
    return TestClient(app)


def seed_case(db, category="fire"):
    incident = {
        "id": db.next_id(),
        "category": category,
        "status": "open",
        "location_known": False,
    }
    db.tables["incidents"].append(incident)
    case = {
        "id": db.next_id(),
        "incident_id": incident["id"],
        "person_id": None,
        "status": "proposed",
        "dispatch_status": "none",
        "priority_score": 0.5,
    }
    db.tables["cases"].append(case)
    return case["id"]


def test_a_fire_case_gets_an_official_handoff_even_on_the_volunteer_channel(client, world):
    """AGENTS.md 11 enforced in code, not left to whoever clicks Approve."""
    case_id = seed_case(world["db"], "fire")

    body = client.post(
        f"/api/proposals/{case_id}/approve", json={"channel": "volunteers"}
    ).json()

    assert body["official"]["service"] == "fire"
    assert body["official"]["simulated"] is True
    assert "responder_link" in body
    assert "never volunteer-only" in body["official_forced"]


def test_a_flood_case_on_the_volunteer_channel_gets_no_forced_handoff(client, world):
    case_id = seed_case(world["db"], "flood")

    body = client.post(
        f"/api/proposals/{case_id}/approve", json={"channel": "volunteers"}
    ).json()

    assert "official_forced" not in body


def test_the_responder_link_carries_the_simulated_label(client, world, monkeypatch):
    monkeypatch.setattr(config, "SHOW_SIMULATION_LABELS", True)
    case_id = seed_case(world["db"], "medical")

    client.post(f"/api/proposals/{case_id}/approve", json={"channel": "responder"})

    link = world["tables"]["responder_links"][0]
    assert "simulated" in link["target_label"].lower()


def test_the_link_event_records_that_nothing_was_actually_sent(client, world):
    case_id = seed_case(world["db"], "fire")

    client.post(f"/api/proposals/{case_id}/approve", json={"channel": "responder"})

    sent = [event for event in world["events"] if event[0] == "ResponderLinkSent"]
    assert sent
    assert sent[0][1]["simulated"] is True
    assert sent[0][1]["service"] == "fire"


def test_only_one_link_is_minted_for_a_fire_case_on_both(client, world):
    """'both' must not double-mint now that fire also forces a handoff."""
    case_id = seed_case(world["db"], "fire")

    client.post(f"/api/proposals/{case_id}/approve", json={"channel": "both"})

    assert len(world["tables"]["responder_links"]) == 1


# ─── The handoff message ───────────────────────────────────────────────────


def _handoff_message(monkeypatch, category="fire", **kwargs):
    sent = []
    monkeypatch.setattr(
        officials, "send_message", lambda to, text: sent.append((to, text)) or True
    )
    monkeypatch.setattr(config, "OFFICIAL_HANDOFF_AUTOSEND", True)

    record = officials.handoff(category)
    officials.notify(
        record,
        case_id=14,
        url="https://example.test/r/abc123",
        category=category,
        **kwargs,
    )
    return sent


@pytest.mark.skipif(
    os.getenv("SHOW_SIMULATION_LABELS", "") != "",
    reason=(
        "This documents the shipped default. The environment overrides it here, "
        "which is a deployment decision -- labels belong ON whenever "
        "ALLOWLIST_ONLY is off and a stranger could reach the number."
    ),
)
def test_the_handoff_is_clean_by_default(monkeypatch):
    sent = _handoff_message(monkeypatch, area="Gulshan-e-Iqbal")

    _to, text = sent[0]
    assert "simulated" not in text.lower()
    assert "prototype demonstration" not in text.lower()


def test_the_handoff_says_what_it_is_when_labels_are_on(monkeypatch):
    """Someone reading this on a phone must know inside one sentence."""
    monkeypatch.setattr(config, "SHOW_SIMULATION_LABELS", True)
    sent = _handoff_message(monkeypatch, area="Gulshan-e-Iqbal")

    _to, text = sent[0]
    first_line = text.splitlines()[0].lower()
    assert "simulated" in first_line


def test_the_handoff_denies_dispatching_anyone(monkeypatch):
    monkeypatch.setattr(config, "SHOW_SIMULATION_LABELS", True)
    sent = _handoff_message(monkeypatch)

    _to, text = sent[0]
    assert "has not dispatched anyone" in text
    assert "no integration" in text.lower()


def test_the_handoff_carries_the_case_and_the_link(monkeypatch):
    sent = _handoff_message(
        monkeypatch,
        area="Gulshan-e-Iqbal",
        reason="Fire, high urgency; elderly, alone; 80% confidence",
        vuln_summary="elderly, alone",
    )

    _to, text = sent[0]
    assert "Case 14" in text
    assert "Gulshan-e-Iqbal" in text
    assert "https://example.test/r/abc123" in text
    assert "elderly, alone" in text


def test_the_handoff_goes_to_the_configured_number(monkeypatch):
    sent = _handoff_message(monkeypatch)

    assert sent[0][0] == "1000000"


def test_no_number_means_no_handoff_and_no_crash(monkeypatch):
    monkeypatch.setattr(config, "EMERGENCY_FIRE", "")
    sent = _handoff_message(monkeypatch)

    assert sent == []


def test_autosend_can_be_switched_off(monkeypatch):
    sent = []
    monkeypatch.setattr(
        officials, "send_message", lambda to, text: sent.append((to, text)) or True
    )
    monkeypatch.setattr(config, "OFFICIAL_HANDOFF_AUTOSEND", False)

    assert officials.notify(
        officials.handoff("fire"), case_id=1, url="u", category="fire"
    ) is False
    assert sent == []


def test_a_suppressed_handoff_does_not_raise(monkeypatch):
    """The allowlist or a closed window must not break the approval."""
    monkeypatch.setattr(officials, "send_message", lambda to, text: False)
    monkeypatch.setattr(config, "OFFICIAL_HANDOFF_AUTOSEND", True)

    assert officials.notify(
        officials.handoff("fire"), case_id=1, url="u", category="fire"
    ) is False
