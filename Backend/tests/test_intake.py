import pytest

from core import config
from services import dispatch, intake, merge, silence
from tests.fake_db import FakeDB


@pytest.fixture
def world(monkeypatch):
    db = FakeDB()
    sent = []
    events = []

    monkeypatch.setattr(intake, "get_db", lambda: db)
    monkeypatch.setattr(intake, "execute", lambda query: query.execute())
    monkeypatch.setattr(intake, "send_message", lambda to, text: sent.append((to, text)) or True)
    monkeypatch.setattr(
        intake,
        "emit",
        lambda event_type, payload=None, case_id=None: events.append(
            (event_type, payload or {}, case_id)
        ),
    )
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
    monkeypatch.setattr(merge, "get_db", lambda: db)
    monkeypatch.setattr(merge, "execute", lambda query: query.execute())
    monkeypatch.setattr(silence, "get_db", lambda: db)
    monkeypatch.setattr(silence, "execute", lambda query: query.execute())
    monkeypatch.setattr(
        silence,
        "emit",
        lambda event_type, payload=None, case_id=None: events.append(
            (event_type, payload or {}, case_id)
        ),
    )
    monkeypatch.setattr(config, "MOCK_MODE", True)

    return {"db": db, "sent": sent, "events": events, "tables": db.tables}


def test_help_request_creates_person_incident_report_and_case(world):
    intake.handle_inbound("0300 123 4567", "Water is rising inside my house in Gulshan")

    assert len(world["tables"]["people"]) == 1
    person = world["tables"]["people"][0]
    assert person["phone"] == "923001234567"
    assert person["window_open_until"]

    assert len(world["tables"]["incidents"]) == 1
    incident = world["tables"]["incidents"][0]
    assert incident["category"] == "flood"
    assert incident["location_known"] is False
    assert incident["urgency"] == pytest.approx(0.75)

    assert len(world["tables"]["reports"]) == 1
    report = world["tables"]["reports"][0]
    assert report["person_id"] == person["id"]
    assert report["incident_id"] == incident["id"]
    assert report["source"] == "whatsapp"

    assert len(world["tables"]["cases"]) == 1
    case = world["tables"]["cases"][0]
    assert case["status"] == "proposed"
    assert case["incident_id"] == incident["id"]
    assert case["priority_score"] > 0
    assert "Flood" in case["reason"]
    assert "location unknown" in case["reason"]
    assert "category:flood" in case["protocol_path"]


def test_instant_guidance_is_sent_before_anything_else(world):
    intake.handle_inbound("03001234567", "There is a fire in the kitchen")

    assert len(world["sent"]) == 1
    to, text = world["sent"][0]
    assert to == "923001234567"
    assert "flagged your case" in text
    assert "location pin" in text


def test_event_stream_gets_the_three_events(world):
    intake.handle_inbound("03001234567", "I am trapped on the roof")

    types = [event_type for event_type, _payload, _case_id in world["events"]]
    assert types == ["ReportReceived", "IncidentCreated", "CaseProposed"]

    case_id = world["tables"]["cases"][0]["id"]
    assert world["events"][-1][2] == case_id


def test_malformed_sender_is_ignored(world):
    intake.handle_inbound("not-a-phone", "help")

    assert world["sent"] == []
    assert world["tables"]["people"] == []


def test_blank_message_asks_for_details_without_creating_a_case(world):
    intake.handle_inbound("03001234567", "   ")

    assert len(world["sent"]) == 1
    assert "Tell me what is happening" in world["sent"][0][1]
    assert world["tables"]["incidents"] == []


def test_stop_opts_out_and_does_not_create_a_case(world):
    intake.handle_inbound("03001234567", "STOP")

    assert world["tables"]["people"][0]["wants_alerts"] is False
    assert world["tables"]["incidents"] == []
    assert "will not receive" in world["sent"][0][1]


def test_volunteer_registration_then_on_duty(world):
    intake.handle_inbound("03001234567", "VOLUNTEER Ali")
    assert world["tables"]["volunteers"][0]["name"] == "Ali"
    assert world["tables"]["volunteers"][0]["status"] == "off_duty"
    assert any(event[0] == "VolunteerRegistered" for event in world["events"])

    intake.handle_inbound("03001234567", "ON DUTY")
    assert world["tables"]["volunteers"][0]["status"] == "on_duty"
    assert world["tables"]["incidents"] == []


def test_on_duty_without_registration_explains_how_to_join(world):
    intake.handle_inbound("03001234567", "ON DUTY")

    assert "not registered" in world["sent"][0][1]
    assert world["tables"]["volunteers"] == []


def test_case_commands_do_not_fall_into_the_help_flow(world):
    intake.handle_inbound("03001234567", "ACCEPT 12")

    assert "not registered as a volunteer" in world["sent"][0][1]
    assert world["tables"]["incidents"] == []


def test_registered_volunteer_without_an_offer_is_told_so(world):
    world["tables"]["volunteers"].append(
        {"id": 7, "phone": "923001234567", "name": "Ali", "status": "on_duty"}
    )

    intake.handle_inbound("03001234567", "ACCEPT 12")

    assert "no open offer for case 12" in world["sent"][0][1]
    assert world["tables"]["incidents"] == []


def test_accept_command_goes_through_dispatch(world):
    world["tables"]["volunteers"].append(
        {"id": 7, "phone": "923001234567", "name": "Ali", "status": "on_duty"}
    )
    world["tables"]["people"].append({"id": 8, "phone": "923005555555", "first_name": "Sara"})
    world["tables"]["incidents"].append(
        {
            "id": 9,
            "category": "flood",
            "lat": 24.92,
            "lng": 67.09,
            "zone_id": "gulshan",
            "location_known": True,
            "dispatch_status": "offered",
        }
    )
    world["tables"]["cases"].append(
        {
            "id": 12,
            "incident_id": 9,
            "person_id": 8,
            "status": "approved",
            "dispatch_status": "offered",
        }
    )
    world["tables"]["dispatches"].append(
        {"id": 30, "case_id": 12, "volunteer_id": 7, "status": "offered"}
    )

    intake.handle_inbound("03001234567", "ACCEPT 12")

    assert world["tables"]["dispatches"][0]["status"] == "accepted"
    assert world["tables"]["cases"][0]["dispatch_status"] == "accepted"
    assert any("Case 12 is yours" in text for _to, text in world["sent"])


def test_stray_one_or_two_does_not_create_an_incident(world):
    intake.handle_inbound("03001234567", "1")

    assert world["tables"]["incidents"] == []
    assert "still need help" in world["sent"][0][1]


def _confirmed_case(world):
    world["tables"]["people"].append(
        {"id": 5, "phone": "923001234567", "person_vuln": {}}
    )
    world["tables"]["incidents"].append(
        {"id": 6, "category": "flood", "status": "open", "dispatch_status": "confirmed"}
    )
    world["tables"]["cases"].append(
        {
            "id": 7,
            "incident_id": 6,
            "person_id": 5,
            "status": "approved",
            "dispatch_status": "confirmed",
            "priority_score": 0.8,
        }
    )


def test_reply_one_closes_the_case(world):
    _confirmed_case(world)

    intake.handle_inbound("03001234567", "1")

    case = world["tables"]["cases"][0]
    assert case["status"] == "resolved"
    assert case["dispatch_status"] == "closed"
    assert "resolved" in world["sent"][-1][1]
    types = [event[0] for event in world["events"]]
    assert "PersonConfirmedHelp" in types
    assert "CaseClosed" in types


def test_reply_two_reopens_the_case(world):
    _confirmed_case(world)

    intake.handle_inbound("03001234567", "2")

    case = world["tables"]["cases"][0]
    assert case["reopened"] is True
    assert case["dispatch_status"] == "reopened"
    assert "trying again" in world["sent"][-1][1]
    assert any(event[0] == "CaseReopened" for event in world["events"])


def test_answered_vulnerability_is_kept_and_not_overwritten_by_null(world):
    world["tables"]["people"].append(
        {"id": 99, "phone": "923001234567", "person_vuln": {"elderly": True}}
    )

    intake.handle_inbound("03001234567", "The flood water is rising")

    person = world["tables"]["people"][0]
    assert person["person_vuln"]["elderly"] is True
    assert world["tables"]["cases"][0]["vuln_summary"] == "elderly"


def test_database_failure_never_propagates(world, monkeypatch):
    def broken(_query):
        raise RuntimeError("db down")

    monkeypatch.setattr(intake, "execute", broken)

    intake.handle_inbound("03001234567", "there is a fire")
    # No exception escaped. Nothing else is guaranteed when the database is down.
