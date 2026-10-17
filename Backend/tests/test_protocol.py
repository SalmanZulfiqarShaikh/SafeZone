from core import config
import pytest

from services import protocol

CATEGORIES = ["flood", "fire", "medical", "trapped", "structural", "other"]


@pytest.fixture(autouse=True)
def configured_numbers(monkeypatch):
    monkeypatch.setattr(protocol, "get_emergency_number", lambda kind: {
        "fire": "16001",
        "medical": "1122",
        "police": "15",
    }[kind])


def test_all_six_categories_exist():
    assert sorted(protocol.categories()) == sorted(CATEGORIES)


@pytest.mark.parametrize("category", CATEGORIES)
def test_guidance_reply_renders_for_every_category(category):
    text, path = protocol.guidance_reply(category)

    assert text
    assert f"category:{category}" in path
    assert "safety_steps" in path
    assert "alerted help nearby" in text
    assert "someone is coming" not in text.lower()
    assert "rescue is on the way" not in text.lower()


@pytest.mark.parametrize("category", ["fire", "medical", "structural"])
def test_official_first_categories_lead_with_the_number(category):
    text, path = protocol.guidance_reply(category)

    assert text.splitlines()[0].startswith("Call ")
    assert "official_first" in path


@pytest.mark.parametrize("category", ["flood", "trapped", "other"])
def test_other_categories_still_show_the_number(category):
    text, _path = protocol.guidance_reply(category)

    assert any(line.startswith(("Ambulance:", "Police:", "Fire service:")) for line in text.splitlines())


def test_missing_emergency_number_degrades_instead_of_crashing(monkeypatch):
    monkeypatch.setattr(protocol, "get_emergency_number", lambda _kind: None)

    text, path = protocol.guidance_reply("fire")

    assert "emergency_number_missing" in path
    assert text  # still a usable message
    assert "16001" not in text


def test_structural_cases_are_not_volunteer_eligible():
    assert protocol.is_volunteer_eligible("structural") is False
    assert protocol.is_volunteer_eligible("flood") is True


def test_next_question_is_location_first_and_stops_after_two():
    assert "location pin" in protocol.next_question("flood", asked=0)
    assert protocol.next_question("flood", asked=1) is not None
    assert protocol.next_question("flood", asked=2) is None


def test_unknown_category_falls_back_to_other(caplog):
    with caplog.at_level("WARNING", logger="safezone.protocol"):
        node = protocol.node("earthquake")

    assert node["id"] == "other"
    assert "Unknown category" in caplog.text


def test_shelter_is_included_when_given():
    text, path = protocol.guidance_reply("flood", shelter="Government School, Block 6")

    assert "Government School, Block 6" in text
    assert "shelter" in path


# ─── Simulated emergency numbers ───────────────────────────────────────────


def test_a_demo_number_is_labelled_as_one(monkeypatch):
    """Telling a stranger to call a teammate's phone without saying so is the
    single most dangerous thing this system could do."""
    monkeypatch.setattr(config, "EMERGENCY_NUMBERS_SIMULATED", True)

    text, path = protocol.guidance_reply("fire")

    assert "16001" in text  # whatever number is configured
    assert "demo number" in text.lower()
    assert "not the real emergency service" in text.lower()
    assert "simulated_emergency_number" in path


def test_a_real_number_carries_no_caveat(monkeypatch):
    monkeypatch.setattr(config, "EMERGENCY_NUMBERS_SIMULATED", False)

    text, path = protocol.guidance_reply("fire")

    assert "demo number" not in text.lower()
    assert "simulated_emergency_number" not in path


def test_simulation_defaults_on_so_the_unsafe_state_is_deliberate():
    """Forgetting a flag must not strip the caveat off a demo number."""
    import importlib

    from core import config as config_module

    reloaded = importlib.reload(config_module)
    try:
        assert reloaded.EMERGENCY_NUMBERS_SIMULATED == reloaded.DEMO_MODE
    finally:
        importlib.reload(config_module)
