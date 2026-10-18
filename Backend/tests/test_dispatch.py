import pytest

from core import config, geo
from services import dispatch
from tests.fake_db import FakeDB


def _volunteer(db, volunteer_id, phone, lat, lng, zone_ids=("gulshan",), status="on_duty"):
    db.tables["volunteers"].append(
        {
            "id": volunteer_id,
            "name": f"Volunteer {volunteer_id}",
            "phone": phone,
            "status": status,
            "lat": lat,
            "lng": lng,
            "zone_ids": list(zone_ids),
            "capabilities": [],
        }
    )


def _case(db, case_id=1, category="flood", status="approved", location_known=True):
    db.tables["zones"].append({"id": "gulshan", "name": "Gulshan-e-Iqbal"})
    db.tables["incidents"].append(
        {
            "id": 10,
            "category": category,
            "lat": 24.92,
            "lng": 67.09,
            "zone_id": "gulshan",
            "location_known": location_known,
            "first_report_at": "2026-10-17T10:00:00+00:00",
            "dispatch_status": "none",
        }
    )
    db.tables["people"].append(
        {"id": 20, "phone": "923009999999", "first_name": "Amina"}
    )
    db.tables["cases"].append(
        {
            "id": case_id,
            "incident_id": 10,
            "person_id": 20,
            "status": status,
            "dispatch_status": "none",
            "vuln_summary": "elderly, alone",
        }
    )


@pytest.fixture
def world(monkeypatch):
    db = FakeDB()
    sent = []
    events = []

    monkeypatch.setattr(dispatch, "get_db", lambda: db)
    monkeypatch.setattr(dispatch, "execute", lambda query: query.execute())
    monkeypatch.setattr(
        dispatch, "send_message", lambda to, text: sent.append((to, text)) or True
    )
    monkeypatch.setattr(
        dispatch,
        "emit",
        lambda event_type, payload=None, case_id=None: events.append(
            (event_type, payload or {}, case_id)
        ),
    )
    monkeypatch.setattr(dispatch, "RING_SIZE", 3)
    monkeypatch.setattr(dispatch.config, "DEMO_MODE", False)
    return {"db": db, "sent": sent, "events": events, "tables": db.tables}


def test_offer_goes_to_the_nearest_three_on_duty_volunteers(world):
    _case(world["db"])
    _volunteer(world["db"], 1, "923000000001", 24.9201, 67.0901)
    _volunteer(world["db"], 2, "923000000002", 24.9202, 67.0902)
    _volunteer(world["db"], 3, "923000000003", 24.9203, 67.0903)
    _volunteer(world["db"], 4, "923000000004", 24.9300, 67.1000)

    offered = dispatch.offer_case(1, ring=1)

    assert offered == [1, 2, 3]
    assert len(world["tables"]["dispatches"]) == 3
    assert {row["status"] for row in world["tables"]["dispatches"]} == {"offered"}


def test_offer_message_has_no_contact_or_exact_location(world):
    _case(world["db"])
    _volunteer(world["db"], 1, "923000000001", 24.9201, 67.0901)

    dispatch.offer_case(1)

    text = world["sent"][0][1]
    assert "Case 1 near Gulshan-e-Iqbal" in text
    assert "ACCEPT 1" in text
    assert "923009999999" not in text
    assert "maps.google.com" not in text
    assert "24.92" not in text


def test_offer_skips_busy_volunteers_and_previous_offers(world, monkeypatch):
    """At the shipped cap of one case each, a volunteer mid-case is skipped.

    Pinned explicitly because VOLUNTEER_MAX_CASES is configurable: a demo
    .env raises it so two handsets can stand in for a neighbourhood, and
    without this the test would read that deployment choice as a regression.
    """
    monkeypatch.setattr(config, "VOLUNTEER_MAX_CASES", 1)
    _case(world["db"])
    _volunteer(world["db"], 1, "923000000001", 24.9201, 67.0901)
    _volunteer(world["db"], 2, "923000000002", 24.9202, 67.0902)
    _volunteer(world["db"], 3, "923000000003", 24.9203, 67.0903)
    world["tables"]["dispatches"].append(
        {"id": 50, "case_id": 9, "volunteer_id": 1, "status": "accepted"}
    )
    world["tables"]["dispatches"].append(
        {"id": 51, "case_id": 1, "volunteer_id": 2, "status": "declined"}
    )

    offered = dispatch.offer_case(1, ring=2)

    assert offered == [3]


def test_a_proposed_case_is_offered_without_waiting_for_approval(world):
    """Volunteers are asked the moment a case arrives.

    They are neighbours being offered a case, not a crew being dispatched --
    the message carries an area and a summary, never a name or a number, and
    anyone can decline. Waiting for a coordinator to wake up costs the
    minutes that decide most outcomes. The official handoff is the step that
    still waits for a human.
    """
    _case(world["db"], status="proposed")
    _volunteer(world["db"], 1, "923000000001", 24.9201, 67.0901)

    assert dispatch.offer_case(1) == [1]


@pytest.mark.parametrize("status", ["resolved", "rejected"])
def test_a_finished_case_is_never_offered(world, status):
    """The other half of the rule. Offering a resolved or rejected case
    would send a neighbour to an emergency that is over."""
    _case(world["db"], status=status)
    _volunteer(world["db"], 1, "923000000001", 24.9201, 67.0901)

    assert dispatch.offer_case(1) == []
    assert world["tables"]["dispatches"] == []


def test_offer_requires_a_known_location(world):
    _case(world["db"], status="proposed")
    _volunteer(world["db"], 1, "923000000001", 24.9201, 67.0901)
    world["tables"]["incidents"][0]["location_known"] = False
    world["tables"]["incidents"][0]["location_source"] = None

    assert dispatch.offer_case(1) == []


def test_structural_damage_is_not_offered_to_volunteers(world):
    _case(world["db"], category="structural")
    _volunteer(world["db"], 1, "923000000001", 24.9201, 67.0901)

    assert dispatch.offer_case(1) == []
    assert world["tables"]["dispatches"] == []


def test_accept_releases_contact_only_to_the_accepting_volunteer(world):
    _case(world["db"])
    _volunteer(world["db"], 1, "923000000001", 24.9201, 67.0901)
    _volunteer(world["db"], 2, "923000000002", 24.9202, 67.0902)
    dispatch.offer_case(1)
    world["sent"].clear()

    assert dispatch.accept(1, 1) is True

    by_recipient = {}
    for to, text in world["sent"]:
        by_recipient.setdefault(to, []).append(text)

    winner_text = "\n".join(by_recipient["923000000001"])
    assert "Case 1 is yours" in winner_text
    assert "Amina" in winner_text
    assert "923009999999" in winner_text
    assert "maps.google.com" in winner_text

    other_text = "\n".join(by_recipient["923000000002"])
    assert "was taken" in other_text
    assert "923009999999" not in other_text

    person_text = "\n".join(by_recipient["923009999999"])
    assert "on the way" in person_text

    winner = world["tables"]["volunteers"][0]
    assert winner["status"] == "busy"
    assert world["tables"]["cases"][0]["dispatch_status"] == "accepted"


def test_second_accept_loses_and_offer_is_expired(world):
    _case(world["db"])
    _volunteer(world["db"], 1, "923000000001", 24.9201, 67.0901)
    _volunteer(world["db"], 2, "923000000002", 24.9202, 67.0902)
    dispatch.offer_case(1)

    assert dispatch.accept(1, 1) is True

    world["sent"].clear()
    assert dispatch.accept(1, 2) is False
    assert world["sent"] == []
    assert world["tables"]["dispatches"][1]["status"] == "expired"


def test_accept_without_an_offer_does_nothing(world):
    _case(world["db"])
    _volunteer(world["db"], 1, "923000000001", 24.9201, 67.0901)

    assert dispatch.accept(1, 1) is False
    assert world["sent"] == []


def test_decline_marks_the_offer_and_replies(world):
    _case(world["db"])
    _volunteer(world["db"], 1, "923000000001", 24.9201, 67.0901)
    dispatch.offer_case(1)

    assert dispatch.decline(1, 1) is True
    assert world["tables"]["dispatches"][0]["status"] == "declined"
    assert "someone else" in world["sent"][-1][1]


def test_arrive_requires_an_accepted_dispatch(world):
    _case(world["db"])
    _volunteer(world["db"], 1, "923000000001", 24.9201, 67.0901)
    dispatch.offer_case(1)

    assert dispatch.arrive(1, 1) is False

    dispatch.accept(1, 1)
    assert dispatch.arrive(1, 1) is True
    assert world["tables"]["dispatches"][0]["status"] == "arrived"
    assert world["tables"]["cases"][0]["dispatch_status"] == "arrived"


def test_finish_closes_the_case_and_frees_the_volunteer(world):
    _case(world["db"])
    _volunteer(world["db"], 1, "923000000001", 24.9201, 67.0901)
    dispatch.offer_case(1)
    dispatch.accept(1, 1)

    assert dispatch.finish(1, 1) is True

    assert world["tables"]["dispatches"][0]["status"] == "done"
    assert world["tables"]["volunteers"][0]["status"] == "on_duty"
    assert world["tables"]["cases"][0]["dispatch_status"] == "confirmed"
    assert "Did help reach you?" in world["sent"][-1][1]


def test_offer_emits_one_event_per_volunteer(world):
    _case(world["db"])
    _volunteer(world["db"], 1, "923000000001", 24.9201, 67.0901)
    _volunteer(world["db"], 2, "923000000002", 24.9202, 67.0902)

    dispatch.offer_case(1)

    offered = [event for event in world["events"] if event[0] == "VolunteerOffered"]
    assert len(offered) == 2
    assert all(event[2] == 1 for event in offered)
    assert "923000000001" not in str(offered[0][1])


def test_demo_mode_offers_one_phone_per_ring(world, monkeypatch):
    monkeypatch.setattr(dispatch.config, "DEMO_MODE", True)
    _case(world["db"])
    _volunteer(world["db"], 1, "923000000001", 24.9201, 67.0901)
    _volunteer(world["db"], 2, "923000000002", 24.9202, 67.0902)
    _volunteer(world["db"], 3, "923000000001", 24.9203, 67.0903)
    _volunteer(world["db"], 4, "923000000002", 24.9204, 67.0904)

    assert dispatch.offer_case(1, ring=1) == [1]
    assert world["sent"][0][0] == "923000000001"

    assert dispatch.offer_case(1, ring=2) == [2]
    assert world["sent"][1][0] == "923000000002"

    # Both phones have had their turn; nobody else is left.
    assert dispatch.offer_case(1, ring=3) == []


def test_distance_maths_is_sane():
    # Two points about 1 km apart in Karachi.
    assert 0.9 < geo.distance_km(24.92, 67.09, 24.929, 67.09) < 1.1


def test_person_is_told_before_their_details_are_released(world):
    """AGENTS.md 2.1 #6 -- consent, and it must come first.

    The ordering is the rule: the person learns their location and number are
    being shared *before* dispatch sends them to a volunteer, not after.
    """
    _case(world["db"])
    _volunteer(world["db"], 1, "923000000001", 24.9201, 67.0901)
    dispatch.offer_case(1)
    world["sent"].clear()

    assert dispatch.accept(1, 1) is True

    order = [to for to, _text in world["sent"]]
    person_index = order.index("923009999999")
    volunteer_index = order.index("923000000001")
    assert person_index < volunteer_index

    consent_text = world["sent"][person_index][1]
    assert "sharing your location and number" in consent_text.lower()
    assert "stop" in consent_text.lower()
