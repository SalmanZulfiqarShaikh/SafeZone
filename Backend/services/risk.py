"""Deterministic priority scoring for the coordinator queue.

No LLM, no network. Weights are hand-tuned and visible (AGENTS.md 7), and every
score ships with a plain-language reason. Judges will ask why case 14 outranks
case 9; "the model said so" loses.

Formula (AGENTS.md 7):

    priority = (0.40 * vulnerability_score
              + 0.30 * urgency_score
              + 0.20 * hazard_exposure
              + 0.10 * time_decay) * confidence

    confidence = clamp(source_factor * (0.6 + 0.1 * min(report_count, 4)), 0, 1)

Unknown vulnerability fields score their neutral midpoint (half weight), never
zero and never maximum, so an unanswered question cannot make someone look
safe.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Optional

CATEGORY_LABELS = {
    "flood": "Flood",
    "fire": "Fire",
    "medical": "Medical emergency",
    "trapped": "Trapped or stranded",
    "structural": "Building damage",
    "other": "Emergency",
}

URGENCY_SCORES = {
    "low": 0.25,
    "medium": 0.50,
    "high": 0.75,
    "critical": 1.00,
}
DEFAULT_URGENCY_SCORE = 0.50

# Weights sum to 1.0. A fully unknown profile therefore scores 0.5.
VULN_WEIGHTS = {
    "elderly": 0.25,
    "alone": 0.20,
    "mobility_limited": 0.20,
    "children_present": 0.15,
    "chronic_illness": 0.10,
    "floor": 0.10,
}

DEFAULT_HAZARD_EXPOSURE = 0.50
DEFAULT_TIME_DECAY = 0.50
TIME_TO_FULL_DECAY_MIN = 120.0


def vulnerability_score(person_vuln: Optional[Mapping[str, Any]]) -> float:
    """Score vulnerability in [0, 1]. Unknown fields contribute half weight."""
    vuln = person_vuln or {}
    total = 0.0

    for field, weight in VULN_WEIGHTS.items():
        value = vuln.get(field)
        if value is None:
            total += weight / 2
        elif field == "floor":
            total += weight if _is_ground_floor(value) else 0.0
        elif bool(value):
            total += weight

    return _clamp(total)


def urgency_score(urgency: Any) -> float:
    """Accept the extractor's words or the numeric value stored in incidents."""
    if isinstance(urgency, (int, float)) and not isinstance(urgency, bool):
        return _clamp(float(urgency))
    return URGENCY_SCORES.get(
        str(urgency).strip().lower() if urgency else "", DEFAULT_URGENCY_SCORE
    )


def hazard_exposure(incident: Mapping[str, Any]) -> float:
    """Hazard weight for the incident's location.

    Until ``services/hazards.py`` lands, callers may pass ``hazard_exposure``
    explicitly; otherwise the neutral default is used.
    """
    value = incident.get("hazard_exposure")
    try:
        return _clamp(float(value)) if value is not None else DEFAULT_HAZARD_EXPOSURE
    except (TypeError, ValueError):
        return DEFAULT_HAZARD_EXPOSURE


def time_decay(incident: Mapping[str, Any]) -> float:
    """Older unhelped cases rise. Reaches 1.0 after two hours."""
    first_report = _parse_timestamp(incident.get("first_report_at"))
    if first_report is None:
        return DEFAULT_TIME_DECAY

    age_minutes = (datetime.now(timezone.utc) - first_report).total_seconds() / 60.0
    return _clamp(max(age_minutes, 0.0) / TIME_TO_FULL_DECAY_MIN)


def confidence(incident: Mapping[str, Any]) -> float:
    source_factor = _as_float(incident.get("source_factor"), default=1.0)
    report_count = incident.get("report_count") or 1
    try:
        report_count = int(report_count)
    except (TypeError, ValueError):
        report_count = 1

    raw = source_factor * (0.6 + 0.1 * min(max(report_count, 0), 4))
    return _clamp(raw)


def score(
    incident: Mapping[str, Any], person_vuln: Optional[Mapping[str, Any]] = None
) -> tuple[float, str]:
    """Return ``(priority_score, plain_language_reason)``."""
    vuln = vulnerability_score(person_vuln)
    urgency = urgency_score(incident.get("urgency"))
    hazard = hazard_exposure(incident)
    decay = time_decay(incident)
    conf = confidence(incident)

    priority = (
        0.40 * vuln + 0.30 * urgency + 0.20 * hazard + 0.10 * decay
    ) * conf
    priority = round(_clamp(priority), 4)

    return priority, _reason(incident, person_vuln, urgency, conf)


def _reason(
    incident: Mapping[str, Any],
    person_vuln: Optional[Mapping[str, Any]],
    urgency: float,
    conf: float,
) -> str:
    category = (incident.get("category") or "other").strip().lower()
    label = CATEGORY_LABELS.get(category, "Emergency")

    parts = [f"{label}, {_urgency_word(urgency)} urgency"]

    vuln_text = _describe_vulnerability(person_vuln)
    if vuln_text:
        parts.append(vuln_text)

    if not incident.get("location_known", True):
        parts.append("location unknown — needs a phone call")

    report_count = incident.get("report_count") or 1
    try:
        report_count = int(report_count)
    except (TypeError, ValueError):
        report_count = 1
    if report_count > 1:
        parts.append(f"{report_count} separate reports")

    parts.append(f"{round(conf * 100)}% confidence")
    return "; ".join(parts)


def _describe_vulnerability(person_vuln: Optional[Mapping[str, Any]]) -> str:
    vuln = person_vuln or {}
    known = {key: value for key, value in vuln.items() if value is not None}
    if not known:
        return ""

    labels = []
    if known.get("elderly"):
        labels.append("elderly")
    if known.get("mobility_limited"):
        labels.append("mobility limited")
    if known.get("children_present"):
        labels.append("children present")
    if known.get("chronic_illness"):
        labels.append("chronic illness")
    if known.get("alone"):
        labels.append("alone")
    if _is_ground_floor(known.get("floor")):
        labels.append("ground floor")
    elif known.get("floor") not in (None, "", "unknown"):
        labels.append(f"floor {known['floor']}")

    return ", ".join(labels)


def _urgency_word(score_value: float) -> str:
    for name, value in URGENCY_SCORES.items():
        if abs(score_value - value) < 1e-9:
            return name
    return "medium"


def _is_ground_floor(value: Any) -> bool:
    return str(value).strip().lower() in ("ground", "0", "g")


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_timestamp(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
