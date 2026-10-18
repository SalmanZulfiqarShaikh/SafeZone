"""Proactive area alerts.

Most of these tests are about silence. A system that messages people about
every report trains them to ignore it, and an ignored alert during a flood is
worse than no alert at all -- so the gates, the dedup and the opt-out matter
more than the happy path.
"""

import pytest

from core import config
from services import alerts, dispatch, intake, merge, silence
from tests.fake_db import FakeDB


@pytest.fixture
def db(monkeypatch):
    store = FakeDB()
    sent = []

    monkeypatch.setattr(alerts, "get_db", lambda: store)
    monkeypatch.setattr(alerts, "execute", lambda query: query.execute())
    monkeypatch.setattr(
        alerts, "send_message", lambda to, text: sent.append((to, text)) or True
    )

    monkeypatch.setattr(config, "ZONE_ALERTS_ENABLED", True)
    monkeypatch.setattr(config, "ZONE_ALERT_MIN_URGENCY", 0.75)
    monkeypatch.setattr(config, "ZONE_ALERT_MIN_REPORTS", 3)
    monkeypatch.setattr(config, "ZONE_ALERT_MAX_RECIPIENTS", 50)
    monkeypatch.setattr(config, "EMERGENCY_FIRE", "1000000")
    monkeypatch.setattr(config, "EMERGENCY_AMBULANCE", "2000000")
    monkeypatch.setattr(config, "EMERGENCY_NGO", "3000000")

    store.sent = sent
    return store


def person(
    store,
    phone,
    *,
    zone_id="gulshan",
    is_registered=True,
    wants_alerts=True,
):
    row = {
        "id": store.next_id(),
        "phone": phone,
        "zone_id": zone_id,
        "is_registered": is_registered,
        "wants_alerts": wants_alerts,
    }
    store.tables["people"].append(row)
    return row


def incident(store, *, category="flood", zone_id="gulshan", urgency=1.0, report_count=1):
    return {
        "id": store.next_id(),
        "category": category,
        "zone_id": zone_id,
        "urgency": urgency,
        "report_count": report_count,
        "status": "open",
    }


# ─── Who gets alerted ──────────────────────────────────────────────────────


def test_registered_people_in_the_zone_are_alerted(db):
    neighbour = person(db, "923001111111")

    alerted = alerts.alert_for_incident(incident(db))

    assert alerted == [neighbour["id"]]
    assert db.sent[0][0] == "923001111111"


def test_the_reporter_is_not_alerted_about_their_own_emergency(db):
    reporter = person(db, "923001111111")

    alerted = alerts.alert_for_incident(incident(db), exclude_person_id=reporter["id"])

    assert alerted == []


def test_people_in_other_zones_are_not_alerted(db):
    person(db, "923001111111", zone_id="korangi")

    assert alerts.alert_for_incident(incident(db, zone_id="gulshan")) == []


def test_unregistered_people_are_not_alerted(db):
    """Alerts are the one thing registration actually buys."""
    person(db, "923001111111", is_registered=False)

    assert alerts.alert_for_incident(incident(db)) == []


def test_opting_out_is_respected(db):
    """STOP sets wants_alerts false; it has to actually stop them."""
    person(db, "923001111111", wants_alerts=False)

    assert alerts.alert_for_incident(incident(db)) == []


def test_people_without_a_phone_are_skipped(db):
    person(db, None)

    assert alerts.alert_for_incident(incident(db)) == []


# ─── When alerts fire at all ───────────────────────────────────────────────


def test_a_low_urgency_incident_does_not_alert(db):
    person(db, "923001111111")

    assert alerts.alert_for_incident(incident(db, urgency=0.25)) == []
    assert db.sent == []


def test_corroboration_can_cross_the_threshold_on_its_own(db):
    """Many people reporting one thing is its own kind of severity."""
    neighbour = person(db, "923001111111")

    alerted = alerts.alert_for_incident(incident(db, urgency=0.5, report_count=3))

    assert alerted == [neighbour["id"]]


def test_an_incident_with_no_zone_alerts_nobody(db):
    person(db, "923001111111")

    assert alerts.alert_for_incident(incident(db, zone_id=None)) == []


def test_alerts_can_be_switched_off_entirely(db, monkeypatch):
    monkeypatch.setattr(config, "ZONE_ALERTS_ENABLED", False)
    person(db, "923001111111")

    assert alerts.alert_for_incident(incident(db)) == []


def test_nobody_is_alerted_twice_about_the_same_incident(db):
    person(db, "923001111111")
    event = incident(db)

    first = alerts.alert_for_incident(event)
    second = alerts.alert_for_incident(event)

    assert first and second == []
    assert len(db.sent) == 1


def test_recipients_are_capped_per_incident(db, monkeypatch):
    """One event must not be able to exhaust the global message cap."""
    monkeypatch.setattr(config, "ZONE_ALERT_MAX_RECIPIENTS", 2)
    for index in range(5):
        person(db, f"92300111111{index}")

    alerted = alerts.alert_for_incident(incident(db))

    assert len(alerted) == 2


def test_a_suppressed_send_still_counts_as_alerted(db, monkeypatch):
    """Window closed or kill switch on: we must not retry them forever."""
    monkeypatch.setattr(alerts, "send_message", lambda to, text: False)
    person(db, "923001111111")
    event = incident(db)

    assert alerts.alert_for_incident(event) == []
    # Recorded anyway, so a later alert for the same incident does not repeat.
    assert len(db.tables["zone_alerts"]) == 1


# ─── What the alert says ───────────────────────────────────────────────────


def test_the_alert_never_promises_rescue(db):
    text = alerts.compose("flood", "gulshan")

    lowered = text.lower()
    assert "on the way" not in lowered
    assert "someone is coming" not in lowered
    assert "we will rescue" not in lowered


def test_the_alert_carries_the_official_number(db):
    assert "1000000" in alerts.compose("fire", "gulshan")


def test_the_alert_uses_protocol_safety_steps_not_invented_advice(db):
    from services import protocol

    text = alerts.compose("flood", "gulshan")

    for step in protocol.safety_steps("flood"):
        assert step in text


def test_the_alert_explains_how_to_opt_out(db):
    assert "STOP" in alerts.compose("flood", "gulshan")


def test_the_alert_names_the_area(db):
    assert "Gulshan" in alerts.compose("flood", "gulshan")


def test_a_missing_emergency_number_degrades_the_alert(db, monkeypatch):
    monkeypatch.setattr(config, "EMERGENCY_FIRE", "")

    text = alerts.compose("fire", "gulshan")

    assert "Fire service:" not in text
    assert "SafeZone alert" in text


# ─── Through intake ────────────────────────────────────────────────────────


@pytest.fixture
def world(monkeypatch, db):
    sent = []
    events = []

    for module in (intake, dispatch, merge, silence):
        monkeypatch.setattr(module, "get_db", lambda: db)
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

    # Zones must exist: incidents.zone_id is a foreign key into zones, so a
    # fixture without them silently exercises a path Postgres would reject.
    for zone_id, name in (
        ("johar", "Gulistan-e-Jauhar"),
        ("gulshan", "Gulshan-e-Iqbal"),
        ("surjani", "Surjani Town"),
        ("lyari", "Lyari"),
        ("gujjar", "Gujjar Nala"),
        ("korangi", "Korangi"),
        ("dha", "DHA"),
    ):
        db.tables["zones"].append({"id": zone_id, "name": name})

    monkeypatch.setattr(config, "MOCK_MODE", True)
    return {"db": db, "sent": sent, "events": events, "tables": db.tables}


def test_a_serious_report_warns_registered_neighbours(world, db):
    person(db, "923009999999", zone_id="gulshan")

    intake.handle_inbound("923001234567", "there is a fire in my building in Gulshan, urgent")

    assert any(to == "923009999999" for to, _text in db.sent)


def test_an_alert_failure_never_costs_us_the_report(world, db, monkeypatch):
    def explode(*_args, **_kwargs):
        raise RuntimeError("alert subsystem down")

    monkeypatch.setattr(alerts, "alert_for_incident", explode)

    intake.handle_inbound("923001234567", "there is a fire in Gulshan, urgent")

    assert len(world["tables"]["cases"]) == 1
