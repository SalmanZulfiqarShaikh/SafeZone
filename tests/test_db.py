import pytest
from Backend.db import InMemoryDB, get_db
from Backend.config import MOCK_MODE


def test_in_memory_db_crud():
    db = InMemoryDB()

    # Insert test
    res = db.table("cases").insert({"category": "flood", "priority_score": 0.85, "reason": "Elderly alone on ground floor"}).execute()
    assert len(res.data) == 1
    assert res.data[0]["id"] == 1
    assert res.data[0]["category"] == "flood"

    # Select test
    res_select = db.table("cases").select().eq("category", "flood").execute()
    assert len(res_select.data) == 1
    assert res_select.data[0]["priority_score"] == 0.85

    # Update test
    res_update = db.table("cases").update({"priority_score": 0.95}).eq("id", 1).execute()
    assert len(res_update.data) == 1
    assert res_update.data[0]["priority_score"] == 0.95

    # Verify updated state
    res_final = db.table("cases").select().eq("id", 1).execute()
    assert res_final.data[0]["priority_score"] == 0.95


def test_get_db_respects_mock_mode():
    client = get_db()
    assert client is not None
    # Insert and select through get_db()
    client.table("volunteers").insert({"name": "Ali", "phone": "923001234567"}).execute()
    res = client.table("volunteers").select().eq("phone", "923001234567").execute()
    assert len(res.data) == 1
    assert res.data[0]["name"] == "Ali"
