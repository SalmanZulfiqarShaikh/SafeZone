"""Duplicate report merging (AGENTS.md 6).

Two failure modes are being guarded against, and they pull in opposite
directions:

* Not merging fills the queue with duplicates of the loudest street while a
  single-report emergency elsewhere sinks below them.
* Over-merging hides a real emergency inside someone else's case, where no
  coordinator will ever see it.

So the matching tests are mostly about what must *not* merge.
"""

from datetime import datetime, timedelta, timezone

import pytest

from core import config
from services import dispatch, intake, merge, silence
from tests.fake_db import FakeDB

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)

# Roughly 150 m and 2 km from the base point, in Karachi.
BASE_LAT, BASE_LNG = 24.9056, 67.0822
NEAR_LAT, NEAR_LNG = 24.9069, 67.0822
FAR_LAT, FAR_LNG = 24.9236, 67.0822


@pytest.fixture
def db(monkeypatch):
    store = FakeDB()
    monkeypatch.setattr(merge, "get_db", lambda: store)
    monkeypatch.setattr(merge, "execute", lambda query: query.execute())
    return store


def incident(
    store,
    *,
    category="flood",
    status="open",
    lat=None,
    lng=None,
    zone_id=None,
    urgency=0.5,
    report_count=1,
    minutes_ago=5,
):
    row = {
        "id": store.next_id(),
        "category": category,
        "status": status,
        "lat": lat,
        "lng": lng,
        "zone_id": zone_id,
        "location_known": lat is not None and lng is not None,
        "urgency": urgency,
        "report_count": report_count,
        "first_report_at": (NOW - timedelta(minutes=minutes_ago)).isoformat(),
        "last_update_at": (NOW - timedelta(minutes=minutes_ago)).isoformat(),
    }
    store.tables["incidents"].append(row)
    return row


# ─── What merges ───────────────────────────────────────────────────────────


def test_nearby_same_category_report_matches(db):
    existing = incident(db, lat=BASE_LAT, lng=BASE_LNG)

    match = merge.find_match("flood", lat=NEAR_LAT, lng=NEAR_LNG, now=NOW)

    assert match is not None
    assert match["id"] == existing["id"]


def test_same_zone_matches_when_neither_has_a_pin(db):
    existing = incident(db, zone_id="gulshan")

    match = merge.find_match("flood", zone_id="gulshan", now=NOW)

    assert match is not None
    assert match["id"] == existing["id"]


def test_nearest_incident_wins_when_several_match(db):
    incident(db, lat=FAR_LAT, lng=FAR_LNG, zone_id="gulshan")
    near = incident(db, lat=NEAR_LAT, lng=NEAR_LNG, zone_id="gulshan")

    match = merge.find_match("flood", lat=BASE_LAT, lng=BASE_LNG, zone_id="gulshan", now=NOW)

    assert match["id"] == near["id"]


def test_coordinate_match_beats_a_zone_match(db):
    zone_only = incident(db, zone_id="gulshan")
    with_pin = incident(db, lat=NEAR_LAT, lng=NEAR_LNG, zone_id="gulshan")

    match = merge.find_match("flood", lat=BASE_LAT, lng=BASE_LNG, zone_id="gulshan", now=NOW)

    assert match["id"] == with_pin["id"]
    assert match["id"] != zone_only["id"]


# ─── What must not merge ───────────────────────────────────────────────────


def test_different_category_never_merges(db):
    incident(db, category="flood", lat=BASE_LAT, lng=BASE_LNG)

    assert merge.find_match("fire", lat=BASE_LAT, lng=BASE_LNG, now=NOW) is None


def test_outside_the_time_window_never_merges(db):
    incident(db, lat=BASE_LAT, lng=BASE_LNG, minutes_ago=45)

    assert merge.find_match("flood", lat=BASE_LAT, lng=BASE_LNG, now=NOW) is None


def test_too_far_apart_never_merges(db):
    incident(db, lat=BASE_LAT, lng=BASE_LNG)

    assert merge.find_match("flood", lat=FAR_LAT, lng=FAR_LNG, now=NOW) is None


def test_resolved_incidents_do_not_absorb_new_reports(db):
    """A new report about a closed case is a new emergency, not an update."""
    incident(db, status="resolved", lat=BASE_LAT, lng=BASE_LNG)
    incident(db, status="closed", lat=BASE_LAT, lng=BASE_LNG)

    assert merge.find_match("flood", lat=BASE_LAT, lng=BASE_LNG, now=NOW) is None


def test_two_unknown_locations_do_not_merge(db):
    """Without evidence there is no match. "Both unknown" is not evidence."""
    incident(db, zone_id=None)

    assert merge.find_match("flood", now=NOW) is None


def test_different_zones_do_not_merge(db):
    incident(db, zone_id="gulshan")

    assert merge.find_match("flood", zone_id="korangi", now=NOW) is None


def test_pinned_incident_does_not_match_a_pinless_report_in_another_zone(db):
    incident(db, lat=BASE_LAT, lng=BASE_LNG, zone_id="gulshan")

    assert merge.find_match("flood", zone_id="lyari", now=NOW) is None


# ─── What merging does ─────────────────────────────────────────────────────


def test_merging_raises_report_count_and_confidence(db):
    existing = incident(db, lat=BASE_LAT, lng=BASE_LNG, report_count=1)
    before = 0.6 + 0.1 * 1

    updates = merge.merge_report(existing, urgency="medium", now=NOW)

    assert updates["report_count"] == 2
    assert updates["confidence"] > before
    assert db.tables["incidents"][0]["report_count"] == 2


def test_merging_never_lowers_urgency(db):
    """The calmest of ten messages must not talk the incident down."""
    existing = incident(db, urgency=1.0, lat=BASE_LAT, lng=BASE_LNG)

    updates = merge.merge_report(existing, urgency="low", now=NOW)

    assert updates["urgency"] == 1.0


def test_merging_raises_urgency_when_the_new_report_is_worse(db):
    existing = incident(db, urgency=0.25, lat=BASE_LAT, lng=BASE_LNG)

    updates = merge.merge_report(existing, urgency="critical", now=NOW)

    assert updates["urgency"] == 1.0


def test_a_later_pin_fills_in_a_missing_location(db):
    existing = incident(db, zone_id="gulshan")

    updates = merge.merge_report(
        existing, urgency="medium", lat=BASE_LAT, lng=BASE_LNG, now=NOW
    )

    assert updates["location_known"] is True
    assert updates["lat"] == pytest.approx(BASE_LAT)


def test_an_existing_pin_is_never_overwritten(db):
    existing = incident(db, lat=BASE_LAT, lng=BASE_LNG)

    updates = merge.merge_report(
        existing, urgency="medium", lat=FAR_LAT, lng=FAR_LNG, now=NOW
    )

    assert "lat" not in updates
    assert db.tables["incidents"][0]["lat"] == pytest.approx(BASE_LAT)


# ─── End to end through intake ─────────────────────────────────────────────


@pytest.fixture
def world(monkeypatch):
    store = FakeDB()
    sent = []
    events = []

    for module in (intake, dispatch, merge, silence):
        monkeypatch.setattr(module, "get_db", lambda: store)
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
        store.tables["zones"].append({"id": zone_id, "name": name})

    monkeypatch.setattr(config, "MOCK_MODE", True)
    return {"db": store, "sent": sent, "events": events, "tables": store.tables}


def test_two_neighbours_reporting_one_flood_make_one_case(world):
    intake.handle_inbound("923001111111", "water is rising in my street in Gulshan")
    intake.handle_inbound("923002222222", "flooding here in Gulshan, water everywhere")

    assert len(world["tables"]["incidents"]) == 1
    assert len(world["tables"]["cases"]) == 1
    assert len(world["tables"]["reports"]) == 2
    assert world["tables"]["incidents"][0]["report_count"] == 2


def test_merge_emits_report_merged(world):
    intake.handle_inbound("923001111111", "water is rising in Gulshan")
    intake.handle_inbound("923002222222", "flooding in Gulshan")

    merged = [event for event in world["events"] if event[0] == "ReportMerged"]
    assert len(merged) == 1
    assert merged[0][1]["report_count"] == 2


def test_the_second_reporter_still_gets_guidance(world):
    """Merging is a queue optimisation, never a reason to leave someone unanswered."""
    intake.handle_inbound("923001111111", "water is rising in Gulshan")
    world["sent"].clear()

    intake.handle_inbound("923002222222", "flooding in Gulshan")

    assert any(to == "923002222222" for to, _text in world["sent"])


def test_corroboration_raises_the_case_priority(world):
    intake.handle_inbound("923001111111", "water is rising in Gulshan")
    before = world["tables"]["cases"][0]["priority_score"]

    intake.handle_inbound("923002222222", "flooding in Gulshan")

    after = world["tables"]["cases"][0]["priority_score"]
    assert after > before
    assert "2 separate reports" in world["tables"]["cases"][0]["reason"]


def test_different_emergencies_stay_separate(world):
    intake.handle_inbound("923001111111", "water is rising in Gulshan")
    intake.handle_inbound("923002222222", "there is a fire in Gulshan")

    assert len(world["tables"]["incidents"]) == 2
    assert len(world["tables"]["cases"]) == 2


# ─── Zone integrity ────────────────────────────────────────────────────────


def test_an_unseeded_area_is_dropped_rather_than_written(world):
    """incidents.zone_id is a foreign key.

    Writing an area we can recognise in text but have never seeded fails the
    insert, and the person vanishes from the queue after being told help was
    alerted. The case must open regardless.
    """
    from services import extract

    # An area the resolver knows about but this database has never seeded.
    monkey = [("atlantis", "atlantis")]
    original = list(extract._AREA_INDEX)
    try:
        extract._AREA_INDEX[:] = monkey + original
        intake.handle_inbound("923001234567", "water is rising in Atlantis")
    finally:
        extract._AREA_INDEX[:] = original

    assert len(world["tables"]["cases"]) == 1
    assert world["tables"]["incidents"][0]["zone_id"] is None


def test_a_seeded_zone_is_kept(world):
    world["db"].tables["zones"].append({"id": "gulshan", "name": "Gulshan-e-Iqbal"})

    intake.handle_inbound("923001234567", "water is rising in Gulshan")

    assert world["tables"]["incidents"][0]["zone_id"] == "gulshan"
