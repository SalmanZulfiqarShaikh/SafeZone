"""Location pins: parsing, case upgrade, and the dispatchability they unlock.

A pin is the only exact location SafeZone ever receives, and
``services/dispatch.offer_case`` refuses any case without coordinates. These
tests cover the whole path from the Meta payload to a dispatchable case.
"""

import pytest

from core import config
from routes import webhook
from services import dispatch, intake, merge, silence
from tests.fake_db import FakeDB


@pytest.fixture
def world(monkeypatch):
    db = FakeDB()
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

    monkeypatch.setattr(config, "MOCK_MODE", True)
    return {"db": db, "sent": sent, "events": events, "tables": db.tables}


def location_payload(sender="923001234567", latitude=24.9056, longitude=67.0822, name="Gulshan 13-D"):
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "messages": [
                                {
                                    "from": sender,
                                    "id": "wamid.loc",
                                    "type": "location",
                                    "location": {
                                        "latitude": latitude,
                                        "longitude": longitude,
                                        "name": name,
                                    },
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


# ─── Parsing ───────────────────────────────────────────────────────────────


def test_location_message_is_parsed_with_coordinates():
    [message] = list(webhook.parse_messages(location_payload()))

    assert message.sender == "923001234567"
    assert message.lat == pytest.approx(24.9056)
    assert message.lng == pytest.approx(67.0822)
    assert message.location_name == "Gulshan 13-D"


def test_location_falls_back_to_address_when_there_is_no_name():
    payload = location_payload(name=None)
    payload["entry"][0]["changes"][0]["value"]["messages"][0]["location"]["address"] = (
        "Block 13-D, Gulshan-e-Iqbal"
    )

    [message] = list(webhook.parse_messages(payload))

    assert message.location_name == "Block 13-D, Gulshan-e-Iqbal"


def test_location_without_coordinates_is_dropped():
    payload = location_payload()
    payload["entry"][0]["changes"][0]["value"]["messages"][0]["location"] = {"name": "somewhere"}

    assert list(webhook.parse_messages(payload)) == []


def test_out_of_range_coordinates_are_rejected():
    # A malformed pin must never reach the database and be ranked as real.
    assert list(webhook.parse_messages(location_payload(latitude=999.0))) == []
    assert list(webhook.parse_messages(location_payload(longitude=-5000.0))) == []


def test_unsupported_message_types_are_still_ignored():
    payload = location_payload()
    payload["entry"][0]["changes"][0]["value"]["messages"][0]["type"] = "sticker"

    assert list(webhook.parse_messages(payload)) == []


# ─── Case upgrade ──────────────────────────────────────────────────────────


def test_pin_upgrades_the_open_case_in_place(world):
    intake.handle_inbound("923001234567", "water is rising in my house in Gulshan")
    assert len(world["tables"]["cases"]) == 1
    assert world["tables"]["incidents"][0]["location_known"] is False
    before = world["tables"]["cases"][0]["priority_score"]

    intake.handle_inbound("923001234567", "Gulshan 13-D", lat=24.9056, lng=67.0822)

    # Same case, now locatable -- not a second case for one emergency.
    assert len(world["tables"]["cases"]) == 1
    assert len(world["tables"]["incidents"]) == 1

    incident = world["tables"]["incidents"][0]
    assert incident["location_known"] is True
    assert incident["lat"] == pytest.approx(24.9056)
    assert incident["lng"] == pytest.approx(67.0822)

    case = world["tables"]["cases"][0]
    assert "location unknown" not in case["reason"]
    assert case["priority_score"] != before or case["reason"]


def test_pin_with_no_open_case_opens_one_with_coordinates(world):
    intake.handle_inbound("923001234567", "Gulshan 13-D", lat=24.9056, lng=67.0822)

    assert len(world["tables"]["incidents"]) == 1
    incident = world["tables"]["incidents"][0]
    assert incident["location_known"] is True
    assert incident["lat"] == pytest.approx(24.9056)


def test_pin_stores_coordinates_on_the_person(world):
    intake.handle_inbound("923001234567", "", lat=24.9056, lng=67.0822)

    person = world["tables"]["people"][0]
    assert person["lat"] == pytest.approx(24.9056)
    assert person["lng"] == pytest.approx(67.0822)


def test_pin_confirms_receipt_to_the_person(world):
    intake.handle_inbound("923001234567", "water is rising in Gulshan")
    world["sent"].clear()

    intake.handle_inbound("923001234567", "Gulshan 13-D", lat=24.9056, lng=67.0822)

    replies = [text for _to, text in world["sent"]]
    assert any("I have your location" in text for text in replies)


def test_upgraded_case_becomes_dispatchable(world):
    """The point of the upgrade: offer_case refuses a case with no pin."""
    intake.handle_inbound("923001234567", "water is rising in my house in Gulshan")
    case_id = world["tables"]["cases"][0]["id"]
    incident_id = world["tables"]["incidents"][0]["id"]

    world["db"].tables["cases"][0]["status"] = "approved"
    world["db"].tables["incidents"][0]["zone_id"] = "gulshan"
    world["db"].tables["volunteers"].append(
        {
            "id": 90,
            "name": "Demo volunteer",
            "phone": "923009999999",
            "zone_ids": ["gulshan"],
            "capabilities": ["foot"],
            "lat": 24.9060,
            "lng": 67.0830,
            "status": "on_duty",
            "is_demo": True,
        }
    )

    assert dispatch.offer_case(case_id) == []

    intake.handle_inbound("923001234567", "Gulshan 13-D", lat=24.9056, lng=67.0822)
    world["db"].tables["incidents"][0]["id"] = incident_id

    assert dispatch.offer_case(case_id) == [90]
