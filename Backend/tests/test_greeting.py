"""The greeting filter.

The filter exists so "hi" does not open a case. It is deterministic rather
than LLM-driven on purpose: AGENTS.md 2.3 #1 keeps the LLM off the critical
path, and a model must never be the reason someone in an emergency gets no
reply. The most important tests here are the negative ones -- anything that
could be a report must fall through to the full help ladder.
"""

import pytest

from core import config
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
    monkeypatch.setattr(config, "GREETING_REPLY", True)
    return {"db": db, "sent": sent, "events": events, "tables": db.tables}


@pytest.mark.parametrize(
    "text",
    [
        "hi",
        "Hi!",
        "hello",
        "Hello.",
        "hey",
        "salam",
        "Assalam o Alaikum",
        "assalamualaikum",
        "AOA",
        "good morning",
        "test",
        "Testing",
        "ok",
        "thanks",
        "Thank you",
        "shukriya",
        "  hello   ",
    ],
)
def test_greetings_are_recognised(text):
    assert intake.is_greeting(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "hi there is a fire in my kitchen",
        "hello water is rising",
        "salam I am trapped on the roof",
        "my house is flooded",
        "I need help",
        "help",
        "bleeding badly",
        "hello hello hello hello hello",
        "",
        "   ",
        "ok but the building is collapsing",
    ],
)
def test_real_messages_are_not_greetings(text):
    assert intake.is_greeting(text) is False


def test_greeting_opens_no_case(world):
    intake.handle_inbound("923001234567", "hi")

    assert world["tables"]["cases"] == []
    assert world["tables"]["incidents"] == []
    assert world["tables"]["reports"] == []


def test_greeting_still_gets_one_orientation_reply(world):
    intake.handle_inbound("923001234567", "salam")

    assert len(world["sent"]) == 1
    _to, text = world["sent"][0]
    assert "tell me what is happening" in text.lower()


def test_greeting_reply_can_be_switched_off(world, monkeypatch):
    monkeypatch.setattr(config, "GREETING_REPLY", False)

    intake.handle_inbound("923001234567", "hi")

    assert world["sent"] == []
    assert world["tables"]["cases"] == []


def test_greeting_still_opens_the_24h_window(world):
    """The person row is touched even for a greeting, so we can reply later."""
    intake.handle_inbound("923001234567", "hi")

    assert len(world["tables"]["people"]) == 1
    assert world["tables"]["people"][0]["window_open_until"]


def test_a_report_after_a_greeting_is_handled_normally(world):
    intake.handle_inbound("923001234567", "hello")
    intake.handle_inbound("923001234567", "there is a fire in my kitchen")

    assert len(world["tables"]["cases"]) == 1
    assert world["tables"]["incidents"][0]["category"] == "fire"


def test_commands_are_not_mistaken_for_greetings(world):
    """STOP and ON DUTY are commands; the filter must not swallow them."""
    assert intake.is_greeting("STOP") is False
    assert intake.is_greeting("ON DUTY") is False
    assert intake.is_greeting("ACCEPT 14") is False
