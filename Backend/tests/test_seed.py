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

    # Counted from the area list, not written out: the list grows as districts
    # are filled in, and a hard-coded number would fail on a correct edit.
    assert counts == {
        "zones": len(areas.AREAS),
        "volunteers": 2,
        "incidents": 4,
        "cases": 4,
    }
    assert len(db.tables["zones"]) == len(areas.AREAS)
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
    assert len(db.tables["zones"]) == len(areas.AREAS)
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


def test_every_area_is_covered_by_exactly_one_volunteer(db):
    """The split is by whole district, so the halves are close but not equal.

    What matters is coverage, not symmetry: a gap means nobody is offered a
    case in that area, and an overlap means both phones ring for it.
    """
    seed_module.seed(db)

    # The zone row carries no group, so the plan says which half is whose.
    groups = {entry["phone"]: entry["group"] for entry in seed_module.volunteer_plan()}

    covered = []
    for volunteer in db.tables["volunteers"]:
        group = groups[volunteer["phone"]]
        assert volunteer["zone_ids"] == areas.by_group(group)
        covered.extend(volunteer["zone_ids"])

    # Every area covered exactly once: no gaps, no area owned by both phones.
    assert sorted(covered) == sorted(areas.AREA_IDS)


def test_the_two_halves_stay_roughly_even(db):
    """A wildly lopsided split means one volunteer is doing all the driving."""
    counts = [len(areas.by_group(group)) for group in (areas.GROUP_A, areas.GROUP_B)]

    assert all(counts)
    assert max(counts) - min(counts) <= len(areas.AREAS) // 4


def test_a_group_never_splits_a_district():
    """Whole districts move between volunteers; areas never move alone."""
    for district, district_group in areas.DISTRICT_GROUPS.items():
        groups = {areas.AREAS_BY_ID[area_id]["group"] for area_id in areas.by_district(district)}
        assert groups == {district_group}


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
