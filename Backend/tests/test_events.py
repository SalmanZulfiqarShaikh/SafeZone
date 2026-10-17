import asyncio
import json

import pytest

from core import events


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def insert(self, row):
        self.rows.append(row)
        return self


class FakeClient:
    def __init__(self):
        self.rows = []

    def table(self, name):
        assert name == "events"
        return FakeQuery(self.rows)


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    monkeypatch.setattr(events, "_subscribers", set())
    monkeypatch.setattr(events, "_loop", None)
    yield
    monkeypatch.setattr(events, "_subscribers", set())
    monkeypatch.setattr(events, "_loop", None)


def test_emit_inserts_event(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(events.db, "get_db", lambda: client)
    monkeypatch.setattr(events.db, "execute", lambda query: None)

    events.emit(events.REPORT_RECEIVED, {"category": "flood"}, case_id=7)

    assert client.rows == [
        {"type": "ReportReceived", "case_id": 7, "payload": {"category": "flood"}}
    ]


def test_emit_never_raises_when_db_is_unavailable(monkeypatch):
    def broken_get_db():
        raise RuntimeError("no database")

    monkeypatch.setattr(events.db, "get_db", broken_get_db)

    events.emit(events.CASE_APPROVED, {"case_id": 1}, case_id=1)  # must not raise


def test_unknown_event_type_is_logged(monkeypatch, caplog):
    monkeypatch.setattr(events.db, "get_db", lambda: FakeClient())
    monkeypatch.setattr(events.db, "execute", lambda query: None)

    with caplog.at_level("WARNING", logger="safezone.events"):
        events.emit("CaseAproved", {})

    assert "Unknown event type" in caplog.text


def test_sse_format_contains_event_and_data():
    frame = events.sse_format(
        {
            "type": "CaseApproved",
            "case_id": 14,
            "payload": {"channel": "volunteers"},
            "created_at": "2026-10-17T18:30:00+00:00",
        }
    )

    assert frame.startswith("event: CaseApproved\n")
    assert frame.endswith("\n\n")
    data = json.loads(frame.split("data: ", 1)[1].strip())
    assert data["case_id"] == 14
    assert data["payload"] == {"channel": "volunteers"}


def test_emit_fans_out_to_subscriber(monkeypatch):
    monkeypatch.setattr(events.db, "get_db", lambda: FakeClient())
    monkeypatch.setattr(events.db, "execute", lambda query: None)

    async def scenario():
        events.set_loop(asyncio.get_running_loop())
        queue = events.subscribe()
        try:
            events.emit(events.VOLUNTEER_ACCEPTED, {"volunteer_id": 3}, case_id=14)
            return await asyncio.wait_for(queue.get(), timeout=1)
        finally:
            events.unsubscribe(queue)

    frame = asyncio.run(scenario())

    assert "event: VolunteerAccepted" in frame
    assert '"case_id": 14' in frame


def test_fan_out_still_happens_when_persist_fails(monkeypatch):
    def broken_get_db():
        raise RuntimeError("no database")

    monkeypatch.setattr(events.db, "get_db", broken_get_db)

    async def scenario():
        events.set_loop(asyncio.get_running_loop())
        queue = events.subscribe()
        try:
            events.emit(events.CASE_CLOSED, {}, case_id=2)
            return await asyncio.wait_for(queue.get(), timeout=1)
        finally:
            events.unsubscribe(queue)

    assert "event: CaseClosed" in asyncio.run(scenario())
