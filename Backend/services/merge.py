"""Duplicate report merging.

Ten neighbours reporting one flooded street is one incident, not ten. Without
merging the queue fills with duplicates of the loudest street while a quieter
one with a single report sinks -- which is precisely the failure the problem
statement calls out as "reports will be late, duplicated, inaccurate or
missing entirely".

Rules (AGENTS.md 6):

* Same category, within ~300 m and 30 minutes, joins one incident.
* Merging raises ``report_count``, which raises ``confidence``.
* **Merging never lowers urgency** -- take the max. The calmest of ten
  messages must not talk the incident down.

Matching is deliberately conservative. Two reports merge only on evidence:
coordinates that are genuinely close, or a shared zone when neither has a pin.
A wrong merge hides a real emergency inside another case, which is far worse
than carrying a duplicate the coordinator can see and close.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional

from core import geo
from core.db import execute, get_db
from services import risk

logger = logging.getLogger("safezone.merge")

MERGE_RADIUS_M = 300.0
MERGE_WINDOW_MINUTES = 30.0

# Only a live incident absorbs new reports. A resolved or closed one stays
# closed: a fresh report about the same place is a genuinely new event.
MERGEABLE_STATUSES = ("open", "active")

URGENCY_ORDER = ("low", "medium", "high", "critical")


def find_match(
    category: str,
    *,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    zone_id: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Optional[Mapping[str, Any]]:
    """The open incident this report belongs to, or ``None`` for a new one."""
    moment = now or datetime.now(timezone.utc)
    category = (category or "").strip().lower()
    if not category:
        return None

    candidates: List[tuple[float, Mapping[str, Any]]] = []
    for incident in _select("incidents", category=category):
        if incident.get("status") not in MERGEABLE_STATUSES:
            continue
        if not _within_window(incident, moment):
            continue

        proximity = _proximity(incident, lat, lng, zone_id)
        if proximity is None:
            continue
        candidates.append((proximity, incident))

    if not candidates:
        return None

    # Nearest wins; ties fall to the most recent incident.
    candidates.sort(key=lambda item: (item[0], -(item[1].get("id") or 0)))
    return candidates[0][1]


def merge_report(
    incident: Mapping[str, Any],
    *,
    urgency: Any,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    zone_id: Optional[str] = None,
    source_factor: float = 1.0,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Fold one more report into ``incident`` and persist the result.

    Returns the fields that changed, so the caller can emit them.
    """
    moment = now or datetime.now(timezone.utc)
    incident_id = incident.get("id")

    report_count = _as_int(incident.get("report_count"), default=1) + 1
    updates: Dict[str, Any] = {
        "report_count": report_count,
        "confidence": risk.confidence(
            {"source_factor": source_factor, "report_count": report_count}
        ),
        "last_update_at": moment.isoformat(),
        # Merging never lowers urgency.
        "urgency": _max_urgency(incident.get("urgency"), urgency),
    }

    # A later report can supply the pin the first one lacked. It never
    # overwrites coordinates we already have -- the first pin stays canonical.
    if not incident.get("location_known") and lat is not None and lng is not None:
        updates["lat"] = lat
        updates["lng"] = lng
        updates["location_known"] = True

    if not incident.get("zone_id") and zone_id:
        updates["zone_id"] = zone_id

    if incident_id is not None:
        _update("incidents", updates, id=incident_id)

    logger.info(
        "Merged a report into incident %s (now %d reports)", incident_id, report_count
    )
    return updates


# ─── Matching ──────────────────────────────────────────────────────────────


def _proximity(
    incident: Mapping[str, Any],
    lat: Optional[float],
    lng: Optional[float],
    zone_id: Optional[str],
) -> Optional[float]:
    """Rank how well a report matches an incident; ``None`` means no match.

    Lower is a better match. Coordinate matches rank ahead of zone matches,
    because a shared zone is far weaker evidence than 300 m.
    """
    incident_point = geo.coordinates(incident)
    has_report_point = lat is not None and lng is not None

    if incident_point and has_report_point:
        metres = geo.distance_m(incident_point[0], incident_point[1], lat, lng)
        return metres if metres <= MERGE_RADIUS_M else None

    # Without two pins the only evidence left is the zone, and it has to be a
    # real zone on both sides. "Both unknown" is not a match.
    incident_zone = (incident.get("zone_id") or "").strip().lower()
    report_zone = (zone_id or "").strip().lower()
    if incident_zone and report_zone and incident_zone == report_zone:
        # Ranks behind every coordinate match.
        return MERGE_RADIUS_M + 1.0

    return None


def _within_window(incident: Mapping[str, Any], now: datetime) -> bool:
    last_update = _parse_timestamp(
        incident.get("last_update_at") or incident.get("first_report_at")
    )
    if last_update is None:
        return False
    age_minutes = (now - last_update).total_seconds() / 60.0
    return 0 <= age_minutes <= MERGE_WINDOW_MINUTES


def _max_urgency(existing: Any, incoming: Any) -> Any:
    """Return the higher of two urgencies, in whichever form they arrive.

    Urgency is stored numerically but extracted as a word, so both forms turn
    up here. Numbers win the comparison when either side is numeric, because
    that is what the database column holds.
    """
    existing_score = risk.urgency_score(existing) if existing is not None else 0.0
    incoming_score = risk.urgency_score(incoming) if incoming is not None else 0.0
    return max(existing_score, incoming_score)


# ─── Small Supabase helpers ────────────────────────────────────────────────


def _select(table: str, **filters: Any) -> List[Mapping[str, Any]]:
    query = get_db().table(table).select("*")
    for column, value in filters.items():
        query = query.eq(column, value)
    rows = _rows(execute(query))
    return [row for row in rows if isinstance(row, Mapping)]


def _update(table: str, values: Mapping[str, Any], **filters: Any) -> Any:
    query = get_db().table(table).update(dict(values))
    for column, value in filters.items():
        query = query.eq(column, value)
    return execute(query)


def _rows(result: Any) -> list:
    return list(getattr(result, "data", result) or [])


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
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
