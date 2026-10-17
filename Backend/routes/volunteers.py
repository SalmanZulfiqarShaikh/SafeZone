"""Coordinator volunteer view.

Unmasked numbers are deliberate here: the coordinator calls these phones when a
case stalls, and the pool is the team's own devices. The browser never talks to
Supabase directly — this endpoint runs server-side with the service key.
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter

from routes import store

router = APIRouter(tags=["volunteers"])


@router.get("/api/volunteers")
def list_volunteers() -> List[Dict[str, Any]]:
    """Every volunteer, with duty status and the demo flag the UI labels."""
    rows = store.select("volunteers")
    rows.sort(key=lambda row: (str(row.get("name") or "").lower(), int(row.get("id") or 0)))
    return [
        {
            "id": row.get("id"),
            "name": row.get("name"),
            "phone": row.get("phone"),
            "status": row.get("status"),
            "zone_ids": row.get("zone_ids") or [],
            "capabilities": row.get("capabilities") or [],
            "lat": row.get("lat"),
            "lng": row.get("lng"),
            "is_demo": bool(row.get("is_demo")),
        }
        for row in rows
    ]
