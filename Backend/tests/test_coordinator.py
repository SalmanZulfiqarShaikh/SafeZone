"""Coordinator alerts.

Approval is the one manual step in the loop, so it is the one place the whole
system can stall silently. These tests cover the alert that stops that, and
the rule it must not break: a coordinator alert is a queue notification, not
a case file, so it carries no name and no phone number.
"""

import pytest

from core import config
from services import alerts, coordinator, dispatch, intake, merge, silence
from tests.fake_db import FakeDB


@pytest.fixture(autouse=True)
def coordinators(monkeypatch):
    monkeypatch.setattr(config, "COORDINATOR_NUMBERS", ["923009999999"])
    monkeypatch.setattr(config, "COORDINATOR_NOTIFY", True)
    monkeypatch.setattr(config, "PUBLIC_BASE_URL", "https://safezone.test")


@pytest.fixture
def sent(monkeypatch):
    outbox = []
    monkeypatch.setattr(
        coordinator, "send_message", lambda to, text: outbox.append((to, text)) or True
    )
    return outbox


# ─── Who gets told ─────────────────────────────────────────────────────────


def test_a_new_case_alerts_the_coordinator(sent):
    assert coordinator.notify_new_case(case_id=6, category="flood", priority_score=0.4) == 1
    assert sent[0][0] == "923009999999"


def test_numbers_are_normalised(monkeypatch, sent):
    monkeypatch.setattr(config, "COORDINATOR_NUMBERS", ["+92 300 9999999", "03009999999"])

    coordinator.notify_new_case(case_id=6, category="flood", priority_score=0.4)

    # Same number written two ways is one coordinator, not two messages.
    assert len(sent) == 1


def test_an_unusable_number_is_skipped_not_fatal(monkeypatch, sent):
    monkeypatch.setattr(config, "COORDINATOR_NUMBERS", ["nonsense", "923009999999"])

    assert coordinator.notify_new_case(case_id=6, category="flood", priority_score=0.4) == 1


def test_no_coordinators_configured_is_survivable(monkeypatch, sent):
    monkeypatch.setattr(config, "COORDINATOR_NUMBERS", [])

    assert coordinator.notify_new_case(case_id=6, category="flood", priority_score=0.4) == 0
    assert sent == []


def test_alerts_can_be_switched_off(monkeypatch, sent):
    monkeypatch.setattr(config, "COORDINATOR_NOTIFY", False)

    assert coordinator.notify_new_case(case_id=6, category="flood", priority_score=0.4) == 0


def test_a_suppressed_alert_is_counted_honestly(monkeypatch):
    monkeypatch.setattr(coordinator, "send_message", lambda to, text: False)

    assert coordinator.notify_new_case(case_id=6, category="flood", priority_score=0.4) == 0


def test_startup_warns_when_nobody_would_be_told(monkeypatch):
    monkeypatch.setattr(config, "COORDINATOR_NUMBERS", [])
    monkeypatch.setattr(config, "COORDINATOR_NOTIFY", True)

    assert any("COORDINATOR_NUMBERS is empty" in p for p in config.startup_report())


# ─── What it says ──────────────────────────────────────────────────────────


def test_the_alert_leads_with_the_case_and_the_ask():
    text = coordinator.compose(case_id=6, category="flood", priority_score=0.4)

    assert text.splitlines()[0] == "SafeZone: case 6 needs a handoff decision"


def test_the_alert_says_volunteers_already_have_it():
    """The distinction that matters at 3am. "Needs approval" on its own reads
    as "nobody has moved yet", which is no longer true: the neighbours were
    offered it on arrival. What is waiting is the official handoff."""
    text = coordinator.compose(case_id=6, category="flood", priority_score=0.4)

    assert "already been offered" in text
    assert "official service" in text


def test_the_alert_carries_enough_to_triage_without_opening_anything():
    text = coordinator.compose(
        case_id=6,
        category="flood",
        priority_score=0.4025,
        reason="Flood, high urgency; elderly, alone; 80% confidence",
        vuln_summary="elderly, alone",
        area="Gulistan-e-Jauhar",
        location_known=True,
        report_count=3,
    )

    assert "Gulistan-e-Jauhar" in text
    assert "elderly, alone" in text
    assert "3 separate reports" in text
    assert "Priority 0.40" in text
    assert "https://safezone.test/control" in text


def test_the_alert_never_carries_personal_data():
    """Name and number are released once, to the volunteer who accepts."""
    text = coordinator.compose(
        case_id=6,
        category="flood",
        priority_score=0.4,
        vuln_summary="elderly, alone",
        area="Korangi",
    )

    assert "923" not in text
    assert "Contact" not in text
    assert "Name:" not in text


def test_a_case_with_no_location_says_it_may_need_a_call():
    text = coordinator.compose(
        case_id=6, category="flood", priority_score=0.4, location_known=False
    )

    assert "may need a phone call" in text


def test_a_located_case_does_not_say_that():
    text = coordinator.compose(
        case_id=6, category="flood", priority_score=0.4, location_known=True
    )

    assert "phone call" not in text


# ─── Through intake ────────────────────────────────────────────────────────


@pytest.fixture
def world(monkeypatch):
    db = FakeDB()
    outbox = []
    events = []

    for module in (intake, dispatch, merge, silence, alerts, coordinator):
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
                module, "send_message", lambda to, text: outbox.append((to, text)) or True
            )

    db.tables["zones"].append({"id": "gulshan", "name": "Gulshan-e-Iqbal"})
    monkeypatch.setattr(config, "MOCK_MODE", True)
    return {"db": db, "sent": outbox, "events": events, "tables": db.tables}


def test_reporting_an_emergency_alerts_the_coordinator(world):
    intake.handle_inbound("923001234567", "water is rising in my house in Gulshan")

    to_coordinator = [t for to, t in world["sent"] if to == "923009999999"]
    assert to_coordinator
    assert "needs a handoff decision" in to_coordinator[0]
    assert "Gulshan-e-Iqbal" in to_coordinator[0]


def test_a_failed_coordinator_alert_never_costs_the_case(world, monkeypatch):
    def explode(**_kwargs):
        raise RuntimeError("coordinator service down")

    monkeypatch.setattr(coordinator, "notify_new_case", explode)

    intake.handle_inbound("923001234567", "water is rising in Gulshan")

    assert len(world["tables"]["cases"]) == 1


def test_a_greeting_alerts_nobody(world):
    intake.handle_inbound("923001234567", "hi")

    assert [t for to, t in world["sent"] if to == "923009999999"] == []


# ─── Who hears about a case, and when ──────────────────────────────────────


def _on_duty_volunteer(db, phone="923007777777"):
    db.tables["volunteers"].append(
        {
            "id": 70,
            "name": "Demo volunteer A",
            "phone": phone,
            "zone_ids": ["gulshan"],
            "capabilities": ["foot"],
            "lat": 24.9201,
            "lng": 67.0901,
            "status": "on_duty",
            "is_demo": True,
        }
    )
    return phone


def test_a_volunteer_hears_about_it_without_waiting_for_approval(world, monkeypatch):
    """The whole point of the split.

    Neighbours are *offered* a case on arrival -- they can decline, and the
    message carries no name and no number. Making them wait for a coordinator
    to wake up costs the minutes that decide most outcomes.
    """
    monkeypatch.setattr(config, "EMERGENCY_AMBULANCE", "923000000001")
    world["db"].tables["zones"][0].update({"lat": 24.92, "lng": 67.09})
    phone = _on_duty_volunteer(world["db"])

    intake.handle_inbound("923001234567", "water is rising in my house in Gulshan")

    assert any(to == phone for to, _text in world["sent"]), (
        "the nearest volunteer was not offered the case on arrival"
    )


def test_the_case_is_still_proposed_while_volunteers_are_looking(world):
    """Offering is not approving. The official handoff -- the expensive,
    irreversible half -- is still waiting for a human."""
    world["db"].tables["zones"][0].update({"lat": 24.92, "lng": 67.09})
    _on_duty_volunteer(world["db"])

    intake.handle_inbound("923001234567", "water is rising in my house in Gulshan")

    assert world["tables"]["cases"][0]["status"] == "proposed"


def test_the_official_service_is_not_told_before_approval(world, monkeypatch):
    """A misread message that reaches a neighbour costs a walk. One that
    reaches an ambulance spends a vehicle the city has few of."""
    monkeypatch.setattr(config, "EMERGENCY_AMBULANCE", "923000000099")
    monkeypatch.setattr(config, "EMERGENCY_FIRE", "923000000099")
    monkeypatch.setattr(config, "EMERGENCY_NGO", "923000000099")
    world["db"].tables["zones"][0].update({"lat": 24.92, "lng": 67.09})
    _on_duty_volunteer(world["db"])

    intake.handle_inbound("923001234567", "water is rising in my house in Gulshan")

    handoffs = [t for to, t in world["sent"] if to == "923000000099"]
    assert not handoffs, "the official service was told before anyone approved"


def test_a_volunteer_offer_never_carries_the_reporter_s_number(world):
    """AGENTS.md 9: contact details are released once, to whoever accepts."""
    world["db"].tables["zones"][0].update({"lat": 24.92, "lng": 67.09})
    phone = _on_duty_volunteer(world["db"])

    intake.handle_inbound("923001234567", "water is rising in my house in Gulshan")

    offers = [t for to, t in world["sent"] if to == phone]
    assert offers
    assert "923001234567" not in offers[0]
