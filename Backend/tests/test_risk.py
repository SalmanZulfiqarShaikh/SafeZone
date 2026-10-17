from datetime import datetime, timedelta, timezone

import pytest

from services import risk


def incident(**overrides):
    base = {
        "category": "flood",
        "urgency": "medium",
        "report_count": 1,
        "source_factor": 1.0,
        "location_known": True,
        "first_report_at": datetime.now(timezone.utc).isoformat(),
    }
    base.update(overrides)
    return base


def test_unknown_vulnerability_is_neutral_not_zero():
    assert risk.vulnerability_score(None) == pytest.approx(0.5)
    assert risk.vulnerability_score({}) == pytest.approx(0.5)
    assert risk.vulnerability_score({"elderly": None, "alone": None}) == pytest.approx(0.5)


def test_all_answered_false_scores_zero():
    profile = {
        "elderly": False,
        "alone": False,
        "mobility_limited": False,
        "children_present": False,
        "chronic_illness": False,
        "floor": "upper",
    }

    assert risk.vulnerability_score(profile) == pytest.approx(0.0)


def test_elderly_alone_ground_floor_scores_higher_than_unknown():
    known = {"elderly": True, "alone": True, "floor": "ground"}

    assert risk.vulnerability_score(known) > risk.vulnerability_score({})
    # 0.25 elderly + 0.20 alone + 0.10 ground floor, plus half weight for the
    # three unanswered fields (0.45 / 2 = 0.225).
    assert risk.vulnerability_score(known) == pytest.approx(0.775)


def test_urgency_mapping():
    assert risk.urgency_score("low") == 0.25
    assert risk.urgency_score("medium") == 0.50
    assert risk.urgency_score("high") == 0.75
    assert risk.urgency_score("critical") == 1.0
    assert risk.urgency_score("nonsense") == 0.50
    assert risk.urgency_score(None) == 0.50


def test_confidence_rises_with_reports_and_is_capped():
    one = risk.confidence(incident(report_count=1))
    three = risk.confidence(incident(report_count=3))
    ten = risk.confidence(incident(report_count=10))

    assert one < three < ten
    assert one == pytest.approx(0.7)
    assert ten == pytest.approx(1.0)


def test_web_reports_are_less_confident_than_whatsapp():
    assert risk.confidence(incident(source_factor=0.7)) < risk.confidence(
        incident(source_factor=1.0)
    )


def test_critical_outranks_low_when_everything_else_matches():
    critical_score, _ = risk.score(incident(urgency="critical"), {})
    low_score, _ = risk.score(incident(urgency="low"), {})

    assert critical_score > low_score


def test_more_reports_raise_priority():
    quiet, _ = risk.score(incident(report_count=1), {"elderly": True})
    corroborated, _ = risk.score(incident(report_count=4), {"elderly": True})

    assert corroborated > quiet


def test_location_unknown_is_flagged_in_the_reason():
    _score, reason = risk.score(incident(location_known=False), {})

    assert "location unknown" in reason
    assert "phone call" in reason


def test_reason_names_the_factors_a_judge_would_ask_about():
    _score, reason = risk.score(
        incident(urgency="high", report_count=3),
        {"elderly": True, "alone": True, "floor": "ground"},
    )

    assert "Flood" in reason
    assert "high urgency" in reason
    assert "elderly" in reason
    assert "alone" in reason
    assert "ground floor" in reason
    assert "3 separate reports" in reason
    assert "confidence" in reason


def test_hazard_exposure_can_be_supplied_explicitly():
    low, _ = risk.score(incident(hazard_exposure=0.1), {})
    high, _ = risk.score(incident(hazard_exposure=1.0), {})

    assert high > low


def test_older_unhelped_cases_rise():
    young = incident(first_report_at=datetime.now(timezone.utc).isoformat())
    old = incident(
        first_report_at=(datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    )

    young_score, _ = risk.score(young, {})
    old_score, _ = risk.score(old, {})

    assert old_score > young_score
    assert risk.time_decay(old) == pytest.approx(1.0)


def test_score_is_bounded_and_rounded():
    best, _ = risk.score(
        incident(
            urgency="critical",
            report_count=10,
            hazard_exposure=1.0,
            first_report_at=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        ),
        {
            "elderly": True,
            "alone": True,
            "mobility_limited": True,
            "children_present": True,
            "chronic_illness": True,
            "floor": "ground",
        },
    )

    assert 0.0 <= best <= 1.0
    assert round(best, 4) == best
