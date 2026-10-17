import hashlib
import hmac
import json
from collections import defaultdict, deque
from types import SimpleNamespace

import pytest

from services import whatsapp

# Captured before the autouse fixture replaces it with a stub.
_REAL_WINDOW_OPEN = whatsapp._window_open


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def insert(self, row):
        self.rows.append(row)
        return self

    def select(self, *_args):
        return self

    def eq(self, *_args):
        return self

    def limit(self, *_args):
        return self


class FakeClient:
    def __init__(self):
        self.rows = []

    def table(self, _name):
        return FakeQuery(self.rows)


@pytest.fixture(autouse=True)
def safe_defaults(monkeypatch):
    monkeypatch.setattr(whatsapp, "_total_sends", 0)
    monkeypatch.setattr(whatsapp, "_number_sends", defaultdict(deque))
    monkeypatch.setattr(whatsapp, "_window_open", lambda _phone: True)

    monkeypatch.setattr(whatsapp.config, "MOCK_MODE", True)
    monkeypatch.setattr(whatsapp.config, "KILL_SWITCH", False)
    monkeypatch.setattr(whatsapp.config, "ALLOWLIST_ONLY", False)
    monkeypatch.setattr(whatsapp.config, "DEMO_ALLOWLIST", [])
    monkeypatch.setattr(whatsapp.config, "PER_NUMBER_RATE_LIMIT", 10)
    monkeypatch.setattr(whatsapp.config, "PER_NUMBER_RATE_WINDOW_S", 300)
    monkeypatch.setattr(whatsapp.config, "GLOBAL_MESSAGE_CAP", 500)
    monkeypatch.setattr(whatsapp.config, "WHATSAPP_TOKEN", "test-token")
    monkeypatch.setattr(whatsapp.config, "WHATSAPP_PHONE_ID", "123456")
    monkeypatch.setattr(whatsapp.config, "WHATSAPP_APP_SECRET", "")


def install_fake_db(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(whatsapp, "get_db", lambda: client)
    monkeypatch.setattr(whatsapp, "execute", lambda _query: None)
    return client.rows


def test_mock_send_writes_outbox_row_and_returns_true(monkeypatch):
    rows = install_fake_db(monkeypatch)

    assert whatsapp.send_message("03001234567", "hello") is True

    assert len(rows) == 1
    assert rows[0]["to_phone"] == "923001234567"
    assert rows[0]["mode"] == "mock"
    assert rows[0]["status"] == "sent"
    assert rows[0]["suppressed_reason"] is None


def test_kill_switch_suppresses_everything(monkeypatch):
    rows = install_fake_db(monkeypatch)
    monkeypatch.setattr(whatsapp.config, "KILL_SWITCH", True)

    assert whatsapp.send_message("03001234567", "hello") is False
    assert rows[0]["status"] == "suppressed"
    assert rows[0]["suppressed_reason"] == "kill_switch"


def test_global_cap_suppresses(monkeypatch):
    rows = install_fake_db(monkeypatch)
    monkeypatch.setattr(whatsapp.config, "GLOBAL_MESSAGE_CAP", 0)

    assert whatsapp.send_message("03001234567", "hello") is False
    assert rows[0]["suppressed_reason"] == "global_cap"


def test_per_number_rate_limit_suppresses_second_send(monkeypatch):
    rows = install_fake_db(monkeypatch)
    monkeypatch.setattr(whatsapp.config, "PER_NUMBER_RATE_LIMIT", 1)

    assert whatsapp.send_message("03001234567", "first") is True
    assert whatsapp.send_message("03001234567", "second") is False

    assert rows[1]["suppressed_reason"] == "rate_limited"


def test_allowlist_suppresses_unknown_number(monkeypatch):
    rows = install_fake_db(monkeypatch)
    monkeypatch.setattr(whatsapp.config, "ALLOWLIST_ONLY", True)
    monkeypatch.setattr(whatsapp.config, "DEMO_ALLOWLIST", ["03009999999"])

    assert whatsapp.send_message("03001234567", "hello") is False
    assert rows[0]["suppressed_reason"] == "not_allowlisted"


def test_allowlist_accepts_matching_number_in_any_format(monkeypatch):
    install_fake_db(monkeypatch)
    monkeypatch.setattr(whatsapp.config, "ALLOWLIST_ONLY", True)
    monkeypatch.setattr(whatsapp.config, "DEMO_ALLOWLIST", ["+92 300 1234567"])

    assert whatsapp.send_message("03001234567", "hello") is True


def test_closed_window_suppresses(monkeypatch):
    rows = install_fake_db(monkeypatch)
    monkeypatch.setattr(whatsapp, "_window_open", lambda _phone: False)

    assert whatsapp.send_message("03001234567", "hello") is False
    assert rows[0]["suppressed_reason"] == "window_closed"


def test_invalid_phone_is_suppressed_not_raised(monkeypatch):
    rows = install_fake_db(monkeypatch)

    assert whatsapp.send_message("not-a-number", "hello") is False
    assert rows[0]["suppressed_reason"] == "invalid_phone"


def test_live_send_posts_to_meta_and_records_live_mode(monkeypatch):
    rows = install_fake_db(monkeypatch)
    monkeypatch.setattr(whatsapp.config, "MOCK_MODE", False)
    calls = []

    class Response:
        status_code = 200
        text = "ok"

    def fake_post(url, headers, json, timeout):
        calls.append({"url": url, "headers": headers, "json": json})
        return Response()

    monkeypatch.setattr(whatsapp.httpx, "post", fake_post)

    assert whatsapp.send_message("03001234567", "hello") is True

    assert calls[0]["url"].endswith("/123456/messages")
    assert calls[0]["headers"]["Authorization"] == "Bearer test-token"
    assert calls[0]["json"]["to"] == "923001234567"
    assert rows[0]["mode"] == "live"
    assert rows[0]["status"] == "sent"


def test_live_failure_returns_false_and_records_reason(monkeypatch):
    rows = install_fake_db(monkeypatch)
    monkeypatch.setattr(whatsapp.config, "MOCK_MODE", False)

    class Response:
        status_code = 400
        text = "bad request"

    monkeypatch.setattr(whatsapp.httpx, "post", lambda *a, **k: Response())

    assert whatsapp.send_message("03001234567", "hello") is False
    assert rows[0]["status"] == "failed"
    assert rows[0]["suppressed_reason"] == "http_400"


def test_outbox_write_failure_does_not_raise(monkeypatch):
    def broken_execute(_query):
        raise RuntimeError("db down")

    monkeypatch.setattr(whatsapp, "execute", broken_execute)

    assert whatsapp.send_message("03001234567", "hello") is True


def test_window_open_reads_people_and_volunteers(monkeypatch):
    install_fake_db(monkeypatch)
    monkeypatch.setattr(whatsapp, "_window_open", _REAL_WINDOW_OPEN)
    future = "2999-01-01T00:00:00+00:00"
    monkeypatch.setattr(
        whatsapp, "execute", lambda _query: SimpleNamespace(data=[{"window_open_until": future}])
    )

    assert whatsapp._window_open("923001234567") is True


def test_window_closed_when_record_exists_and_expired(monkeypatch):
    install_fake_db(monkeypatch)
    monkeypatch.setattr(whatsapp, "_window_open", _REAL_WINDOW_OPEN)
    past = "2000-01-01T00:00:00+00:00"
    monkeypatch.setattr(
        whatsapp, "execute", lambda _query: SimpleNamespace(data=[{"window_open_until": past}])
    )

    assert whatsapp._window_open("923001234567") is False


def test_verify_signature_accepts_valid_hmac(monkeypatch):
    monkeypatch.setattr(whatsapp.config, "WHATSAPP_APP_SECRET", "secret")
    body = b'{"hello":"world"}'
    digest = hmac.new(b"secret", body, hashlib.sha256).hexdigest()

    assert whatsapp.verify_signature(body, f"sha256={digest}") is True
    assert whatsapp.verify_signature(body, "sha256=deadbeef") is False
    assert whatsapp.verify_signature(body, None) is False


def test_verify_signature_skipped_without_secret(monkeypatch):
    monkeypatch.setattr(whatsapp.config, "WHATSAPP_APP_SECRET", "")

    assert whatsapp.verify_signature(b"anything", None) is True
