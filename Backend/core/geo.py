"""Geographic helpers.

Straight-line distance only. SafeZone deliberately does no routing: there is
no map API on the critical path, and "nearest by straight line" is a named
trade-off in the README rather than a hidden approximation.

Lives in ``core`` because both ``services/dispatch.py`` (ranking volunteers)
and ``services/merge.py`` (deciding whether two reports are the same event)
need the same answer, and two copies of a haversine drift.
"""

from __future__ import annotations

import math
from typing import Any, Optional, Tuple

EARTH_RADIUS_KM = 6371.0


def distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two points, in kilometres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return EARTH_RADIUS_KM * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two points, in metres."""
    return distance_km(lat1, lng1, lat2, lng2) * 1000.0


def coordinates(row: Any) -> Optional[Tuple[float, float]]:
    """Pull ``(lat, lng)`` out of a row, or ``None`` when either is missing.

    Coordinates arrive from Meta payloads and from the database, so they may be
    strings, ``None``, or absent entirely. Anything unusable reads as "no
    location" rather than raising.
    """
    if row is None:
        return None
    try:
        lat = row.get("lat")
        lng = row.get("lng")
    except AttributeError:
        return None

    if lat is None or lng is None:
        return None
    try:
        return float(lat), float(lng)
    except (TypeError, ValueError):
        return None
