import pytest

from core import config
from services import extract


@pytest.fixture(autouse=True)
def mock_mode(monkeypatch):
    monkeypatch.setattr(config, "MOCK_MODE", True)
    monkeypatch.setattr(config, "LLM_API_KEY", "")
    monkeypatch.setattr(config, "LLM_MODEL", "")


def test_flood_message_is_classified_with_safety_question_first():
    result = extract.extract_report("Water is rising inside my house in Gulshan")

    assert result["category"] == "flood"
    assert result["zone_guess"] == "gulshan"
    assert result["missing_fields"] == ["exact_location"]
    assert "location pin" in result["next_question"]


def test_fire_beats_flood_when_both_words_appear():
    result = extract.extract_report("The flood water reached the wires and now there is fire")

    assert result["category"] == "fire"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("my father is unconscious and not breathing", "medical"),
        ("we are trapped on the roof", "trapped"),
        ("the building collapsed after the rain", "structural"),
        ("there is a cat in the tree", "other"),
    ],
)
def test_category_keywords(text, expected):
    assert extract.extract_report(text)["category"] == expected


def test_critical_urgency_is_recognised():
    assert extract.extract_report("he is unconscious, not breathing")["urgency"] == "critical"


def test_high_urgency_for_trapped_child():
    assert extract.extract_report("my child is trapped inside")["urgency"] == "high"


def test_low_urgency_only_when_nothing_alarming_is_present():
    assert extract.extract_report("everyone is safe, no one hurt")["urgency"] == "low"


def test_vulnerability_is_null_when_not_stated():
    vuln = extract.extract_report("there is flooding")["vulnerability"]

    assert vuln["elderly"] is None
    assert vuln["alone"] is None
    assert vuln["floor"] is None


def test_vulnerability_is_flagged_when_stated():
    vuln = extract.extract_report(
        "My elderly mother is alone on the ground floor and uses a wheelchair"
    )["vulnerability"]

    assert vuln["elderly"] is True
    assert vuln["alone"] is True
    assert vuln["mobility_limited"] is True
    assert vuln["floor"] == "ground"


def test_people_count_and_needs():
    result = extract.extract_report("There are 4 people trapped and we need rescue")

    assert result["people_count"] == 4
    assert "rescue" in result["needs"]


def test_coordinates_count_as_a_known_location():
    result = extract.extract_report("we are at 24.8607, 67.0011 please help")

    assert result["location_text"] == "24.8607,67.0011"
    assert result["missing_fields"] == []


def test_landmark_is_recorded_but_not_treated_as_exact():
    result = extract.extract_report("our house near the masjid in Korangi is flooded")

    assert "near the masjid" in result["location_text"]
    assert result["zone_guess"] == "korangi"
    assert "exact_location" in result["missing_fields"]


def test_mock_mode_never_calls_the_llm(monkeypatch):
    def explode(_text):
        raise AssertionError("LLM must not be called in MOCK_MODE")

    monkeypatch.setattr(extract, "_llm_extract", explode)

    assert extract.extract_report("fire in the kitchen")["category"] == "fire"


def test_llm_failure_falls_back_to_keywords(monkeypatch):
    monkeypatch.setattr(config, "MOCK_MODE", False)
    monkeypatch.setattr(config, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(config, "LLM_MODEL", "test-model")
    monkeypatch.setattr(extract, "_llm_extract", lambda _text: (_ for _ in ()).throw(RuntimeError("429")))

    result = extract.extract_report("my neighbour is trapped in the flood")

    assert result["category"] == "trapped"


def test_llm_response_is_normalised():
    result = extract._normalise(
        {
            "category": "earthquake",
            "urgency": "apocalyptic",
            "category_confidence": "0.9",
            "vulnerability": {"elderly": "yes", "floor": "Ground"},
            "needs": ["evacuation"],
        }
    )

    assert result["category"] == "other"
    assert result["urgency"] == "medium"
    assert result["category_confidence"] == 0.9
    assert result["vulnerability"]["elderly"] is None  # "yes" is not a bool
    assert result["vulnerability"]["floor"] == "ground"
    assert "exact_location" in result["missing_fields"]


def test_empty_text_returns_the_default_shape():
    result = extract.extract_report("")

    assert result["category"] == "other"
    assert result["urgency"] == "medium"
    assert set(result) == {
        "category",
        "category_confidence",
        "urgency",
        "people_count",
        "location_text",
        "zone_guess",
        "vulnerability",
        "needs",
        "missing_fields",
        "next_question",
    }


# ─── Zone coverage ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text,zone",
    [
        ("water is rising in Gulistan-e-Jauhar", "johar"),
        ("flooding in Jauhar block 14", "johar"),
        ("fire in Gulshan-e-Iqbal", "gulshan"),
        ("stuck in Gulshan 13-D", "gulshan"),
        ("water in Surjani Town", "surjani"),
        ("trapped in Gujjar Nala", "gujjar"),
        ("flooding in Korangi", "korangi"),
        ("fire in Lyari", "lyari"),
        ("water in DHA phase 6", "dha"),
    ],
)
def test_every_covered_zone_is_recognised(text, zone):
    """All seven zones SafeZone covers, in the words people actually type."""
    assert extract._zone(text) == zone


def test_every_recognisable_area_is_a_real_area_id():
    """An area we can name but have not seeded breaks the incident insert."""
    from data import areas

    for _phrase, area_id in areas.search_index():
        assert area_id in areas.AREAS_BY_ID


@pytest.mark.parametrize(
    "typed,area_id",
    [
        ("Guilstan e Jauhar", "johar"),   # misspelled
        ("gulistan-e-johar", "johar"),    # variant spelling
        ("GULSHAN E IQBAL", "gulshan"),   # shouting
        ("lalukhet", "liaquatabad"),      # local name
        ("defence", "dha"),
        ("hawks bay", "hawksbay"),
        ("north nazimabad", "north-nazimabad"),
        ("nazimabad", "nazimabad"),
        ("atlantis", None),
        ("", None),
    ],
)
def test_area_resolution_survives_spelling(typed, area_id):
    assert extract.resolve_area(typed) == area_id


def test_longer_area_names_win_over_shorter_ones():
    """"North Nazimabad" must not be swallowed by "Nazimabad"."""
    assert extract._zone("flooding in North Nazimabad") == "north-nazimabad"
