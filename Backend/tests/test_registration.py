"""Website registration and the ``JOIN <code>`` handshake.

Registration exists for one reason: Meta only lets us message a number that
messaged us first, and a web form cannot open that window. So the tests that
matter are the ones proving registration stays *optional* -- a failed or
missing code must never stand between someone and the help ladder.
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core import config
from routes import register as register_routes
from routes import store
from services import dispatch, intake, merge, registration, silence
from tests.fake_db import FakeDB

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def db(monkeypatch):
    store_db = FakeDB()
    for module in (registration, store):
        if hasattr(module, "get_db"):
            monkeypatch.setattr(module, "get_db", lambda: store_db)
        if hasattr(module, "execute"):
            monkeypatch.setattr(module, "execute", lambda query: query.execute())
    monkeypatch.setattr(config, "REGISTRATION_CODE_TTL_MINUTES", 30)
    monkeypatch.setattr(config, "WHATSAPP_PUBLIC_NUMBER", "")
    return store_db


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

    monkeypatch.setattr(config, "MOCK_MODE", True)
    return {"db": db, "sent": sent, "events": events, "tables": db.tables}


# ─── Code minting ──────────────────────────────────────────────────────────


def test_create_returns_a_usable_code(db):
    result = registration.create("Ayesha", "gulshan", now=NOW)

    assert len(result["code"]) == registration.CODE_LENGTH
    assert result["code"].isupper()
    assert f"JOIN {result['code']}" in result["instructions"]


def test_codes_avoid_lookalike_characters(db):
    for _ in range(40):
        code = registration.create("Ayesha", "gulshan", now=NOW)["code"]
        assert not set(code) & set("01OIL")


def test_no_phone_number_is_captured_at_the_form(db):
    registration.create("Ayesha", "gulshan", now=NOW)

    assert db.tables["registrations"][0]["phone"] is None


def test_a_blank_name_is_rejected(db):
    with pytest.raises(registration.RegistrationError):
        registration.create("   ", "gulshan", now=NOW)


def test_whatsapp_url_is_none_without_a_configured_number(db):
    assert registration.whatsapp_url("ABC123") is None


def test_whatsapp_url_prefills_the_join_message(db, monkeypatch):
    monkeypatch.setattr(config, "WHATSAPP_PUBLIC_NUMBER", "920000000000")

    url = registration.whatsapp_url("ABC123")

    assert url == "https://wa.me/920000000000?text=JOIN%20ABC123"


# ─── Redemption ────────────────────────────────────────────────────────────


def test_a_valid_code_binds_the_sending_phone(db):
    code = registration.create("Ayesha", "gulshan", now=NOW)["code"]

    record = registration.redeem(code, "923001234567", now=NOW)

    assert record is not None
    assert record["phone"] == "923001234567"
    assert record["first_name"] == "Ayesha"


def test_codes_are_single_use(db):
    code = registration.create("Ayesha", "gulshan", now=NOW)["code"]
    registration.redeem(code, "923001234567", now=NOW)

    assert registration.redeem(code, "923009999999", now=NOW) is None


def test_expired_codes_are_refused(db):
    code = registration.create("Ayesha", "gulshan", now=NOW)["code"]
    later = NOW + timedelta(minutes=31)

    assert registration.redeem(code, "923001234567", now=later) is None


def test_unknown_codes_are_refused(db):
    assert registration.redeem("ZZZZZZ", "923001234567", now=NOW) is None


def test_redemption_tolerates_spacing_and_case(db):
    code = registration.create("Ayesha", "gulshan", now=NOW)["code"]
    messy = f" {code[:3]}-{code[3:].lower()} "

    assert registration.redeem(messy, "923001234567", now=NOW) is not None


# ─── Status polling ────────────────────────────────────────────────────────


def test_status_reports_verification_without_leaking_the_number(db):
    code = registration.create("Ayesha", "gulshan", now=NOW)["code"]
    assert registration.status(code) == {
        "found": True,
        "verified": False,
        "first_name": "Ayesha",
        "zone_id": "gulshan",
    }

    registration.redeem(code, "923001234567", now=NOW)
    after = registration.status(code)

    assert after["verified"] is True
    assert "phone" not in after


def test_status_of_an_unknown_code(db):
    assert registration.status("ZZZZZZ") == {"found": False, "verified": False}


# ─── The JOIN command over WhatsApp ────────────────────────────────────────


def test_join_marks_the_person_registered(world):
    code = registration.create("Ayesha", "gulshan")["code"]

    intake.handle_inbound("923001234567", f"JOIN {code}")

    person = world["tables"]["people"][0]
    assert person["is_registered"] is True
    assert person["wants_alerts"] is True
    assert person["first_name"] == "Ayesha"
    assert person["zone_id"] == "gulshan"


def test_join_is_case_insensitive(world):
    code = registration.create("Ayesha", "gulshan")["code"]

    intake.handle_inbound("923001234567", f"join {code.lower()}")

    assert world["tables"]["people"][0]["is_registered"] is True


def test_join_opens_no_case(world):
    """Signing up is not an emergency."""
    code = registration.create("Ayesha", "gulshan")["code"]

    intake.handle_inbound("923001234567", f"JOIN {code}")

    assert world["tables"]["cases"] == []


def test_bare_join_explains_itself(world):
    intake.handle_inbound("923001234567", "JOIN")

    text = world["sent"][0][1]
    assert "code from the website" in text


def test_a_bad_code_still_points_at_the_help_path(world):
    """The whole point of AGENTS.md 9: no code is ever required to get help."""
    intake.handle_inbound("923001234567", "JOIN ZZZZZZ")

    text = world["sent"][0][1]
    assert "do not need a code" in text.lower()
    assert world["tables"]["cases"] == []


def test_a_bad_code_does_not_say_why(world):
    """Expired and already-used look identical to a code guesser."""
    code = registration.create("Ayesha", "gulshan")["code"]
    registration.redeem(code, "923009999999")

    intake.handle_inbound("923001234567", f"JOIN {code}")

    text = world["sent"][0][1].lower()
    assert "expired" not in text
    assert "already" not in text


def test_registration_is_not_required_to_ask_for_help(world):
    """An unregistered stranger gets the whole ladder."""
    intake.handle_inbound("923005555555", "water is rising in my house in Gulshan")

    assert len(world["tables"]["cases"]) == 1
    assert world["tables"]["people"][0].get("is_registered") in (None, False)


# ─── HTTP surface ──────────────────────────────────────────────────────────


@pytest.fixture
def client(db):
    app = FastAPI()
    app.include_router(register_routes.router)
    return TestClient(app)


def test_register_endpoint_returns_a_code(client):
    response = client.post("/api/register", json={"first_name": "Ayesha", "zone_id": "gulshan"})

    assert response.status_code == 200
    body = response.json()
    assert len(body["code"]) == registration.CODE_LENGTH
    assert "JOIN" in body["instructions"]


def test_register_endpoint_rejects_a_blank_name(client):
    response = client.post("/api/register", json={"first_name": ""})

    assert response.status_code == 422


def test_register_endpoint_ignores_a_submitted_phone_number(client, db):
    """A number typed into the form proves nothing and is not stored."""
    response = client.post(
        "/api/register",
        json={"first_name": "Ayesha", "zone_id": "gulshan", "phone": "923001234567"},
    )

    assert response.status_code == 200
    assert db.tables["registrations"][0]["phone"] is None


def test_status_endpoint_tracks_verification(client, db):
    code = client.post("/api/register", json={"first_name": "Ayesha"}).json()["code"]

    assert client.get(f"/api/register/{code}").json()["verified"] is False

    registration.redeem(code, "923001234567", now=NOW)
    assert client.get(f"/api/register/{code}").json()["verified"] is True
