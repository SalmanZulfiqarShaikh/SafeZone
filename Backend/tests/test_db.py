import pytest

import core.db as db
from core.db import DbError, execute, get_db


@pytest.fixture(autouse=True)
def reset_client(monkeypatch):
    """Never reuse a cached client (and never touch the network) in tests."""
    monkeypatch.setattr(db, "_supabase_client", None)


def test_get_db_raises_without_credentials(monkeypatch):
    monkeypatch.setattr(db, "SUPABASE_URL", "")
    monkeypatch.setattr(db, "SUPABASE_SERVICE_KEY", "")

    with pytest.raises(DbError, match="SUPABASE_URL"):
        get_db()


def test_get_db_raises_without_service_key(monkeypatch):
    monkeypatch.setattr(db, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(db, "SUPABASE_SERVICE_KEY", "")

    with pytest.raises(DbError, match="SUPABASE_SERVICE_KEY"):
        get_db()


def test_get_db_creates_and_caches_client(monkeypatch):
    monkeypatch.setattr(db, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(db, "SUPABASE_SERVICE_KEY", "test-service-key")

    calls = []

    def fake_create_client(url, key):
        calls.append((url, key))
        return object()

    monkeypatch.setattr(db, "_create_client", fake_create_client)

    first = get_db()
    second = get_db()

    assert first is second
    assert calls == [("https://example.supabase.co", "test-service-key")]


def test_execute_wraps_client_errors():
    class BrokenQuery:
        def execute(self):
            raise ValueError("boom")

    with pytest.raises(DbError, match="boom"):
        execute(BrokenQuery())


def test_execute_returns_query_result():
    class WorkingQuery:
        def execute(self):
            return "result"

    assert execute(WorkingQuery()) == "result"
