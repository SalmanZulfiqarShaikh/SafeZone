import pytest

from core import config
from data import areas
from data import seed as seed_module
from tests.fake_db import FakeDB


@pytest.fixture
def db(monkeypatch):
    fake = FakeDB()
    monkeypatch.setattr(seed_module, "get_db", lambda: fake)
    monkeypatch.setattr(seed_module, "execute", lambda query: query.execute())
    # Default to no configured volunteers, so tests exercise the placeholders.
    monkeypatch.setattr(config, "DEMO_VOLUNTEERS", [])
    return fake


def test_seed_creates_zones_volunteers_and_sample_cases(db):
    counts = seed_module.seed(db)

    assert counts == {"zones": 50, "volunteers": 2, "incidents": 4, "cases": 4}
    assert len(db.tables["zones"]) == 50
    assert len(db.tables["volunteers"]) == 2
    assert len(db.tables["incidents"]) == 4
    assert len(db.tables["cases"]) == 4


def test_seed_uses_only_fake_demo_phones(db):
    seed_module.seed(db)

    phones = {row["phone"] for row in db.tables["volunteers"]}
    assert phones == {"923000000001", "923000000002"}


def test_seed_is_idempotent(db):
    seed_module.seed(db)
    counts = seed_module.seed(db)

    assert counts["incidents"] == 0
    assert counts["cases"] == 0
    assert len(db.tables["zones"]) == 50
    assert len(db.tables["volunteers"]) == 2
    assert len(db.tables["incidents"]) == 4
    assert len(db.tables["reports"]) == 4
    assert len(db.tables["cases"]) == 4


def test_reseeding_does_not_take_volunteers_off_duty(db):
    seed_module.seed(db)
    db.tables["volunteers"][0]["status"] = "on_duty"

    seed_module.seed(db)

    assert db.tables["volunteers"][0]["status"] == "on_duty"


def test_sample_cases_carry_a_priority_and_a_reason(db):
    seed_module.seed(db)

    for case in db.tables["cases"]:
        assert case["priority_score"] > 0
        assert case["reason"]
        assert case["status"] == "proposed"


def test_every_seeded_zone_is_a_real_area(db):
    seed_module.seed(db)

    assert {zone["id"] for zone in db.tables["zones"]} == set(areas.AREA_IDS)


def test_the_fifty_areas_split_evenly_between_two_volunteers(db):
    seed_module.seed(db)

    covered = []
    for volunteer in db.tables["volunteers"]:
        assert len(volunteer["zone_ids"]) == 25
        covered.extend(volunteer["zone_ids"])

    # Every area covered exactly once: no gaps, no area owned by both phones.
    assert sorted(covered) == sorted(areas.AREA_IDS)


def test_every_zone_carries_a_centre_for_ranking(db):
    seed_module.seed(db)

    for zone in db.tables["zones"]:
        assert zone["lat"] and zone["lng"]
        assert zone["volunteer_group"] in ("a", "b")


def test_real_numbers_come_from_the_environment_not_the_repo(db, monkeypatch):
    """The repo is public: DEMO_VOLUNTEERS is the only route for real phones."""
    monkeypatch.setattr(
        config,
        "DEMO_VOLUNTEERS",
        [
            {"name": "Volunteer A", "phone": "923009876543", "group": "a"},
            {"name": "Volunteer B", "phone": "923004567890", "group": "b"},
        ],
    )

    seed_module.seed(db)

    phones = {row["phone"] for row in db.tables["volunteers"]}
    assert phones == {"923009876543", "923004567890"}
    assert not phones & set(seed_module.PLACEHOLDER_PHONES)


def test_configured_phones_are_normalised(db, monkeypatch):
    monkeypatch.setattr(
        config,
        "DEMO_VOLUNTEERS",
        [{"name": "A", "phone": "+92 300 9876543", "group": "a"}],
    )

    seed_module.seed(db)

    assert "923009876543" in {row["phone"] for row in db.tables["volunteers"]}
