"""The list of areas SafeZone covers.

Public on purpose. The registration form on the public page needs it to show
a dropdown, and that form is open to anyone -- requiring a login to find out
which parts of Karachi are covered would be absurd.

What it does *not* carry is anything operational: ``volunteer_group`` says
which of the two demo phones covers an area, and the risk level is a signal
about live conditions. Neither belongs on an open endpoint, so this returns
the id, the name and the centre, and nothing else.

The centre is deliberately included: it is an area centroid, accurate to a
neighbourhood, and never a person's location (``data/areas.py``).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter

from routes import store

logger = logging.getLogger("safezone.routes.zones")

router = APIRouter(tags=["zones"])


@router.get("/api/zones")
def zones() -> List[Dict[str, Any]]:
    """Every area, sorted by name so the dropdown reads alphabetically."""
    rows = store.select("zones")

    areas = [
        {
            "id": row.get("id"),
            "name": row.get("name"),
            "lat": row.get("lat"),
            "lng": row.get("lng"),
        }
        for row in rows
        if row.get("id") and row.get("name")
    ]

    if not areas:
        # An empty dropdown on the public page means the seed never ran, not
        # that Karachi has no areas. Worth a log line rather than silence.
        logger.warning("No zones in the database. Run: python -m data.seed")

    return sorted(areas, key=lambda area: str(area["name"]).lower())
