"""Small read/write helpers shared by the JSON routes.

Every route goes through the service key, server-side. Nothing here is exposed
to the browser directly: RLS blocks the anon key on every table.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional

from core.db import execute, get_db

logger = logging.getLogger("safezone.routes")


def select(table: str, **filters: Any) -> List[Dict[str, Any]]:
    query = get_db().table(table).select("*")
    for column, value in filters.items():
        query = query.eq(column, value)
    rows = _rows(execute(query))
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def select_one(table: str, **filters: Any) -> Optional[Dict[str, Any]]:
    rows = select(table, **filters)
    return rows[0] if rows else None


def select_in(table: str, column: str, values: Any) -> List[Dict[str, Any]]:
    """Every row whose ``column`` is one of ``values``. One round trip.

    The queue endpoint used to fetch each case's incident, person and zone
    with its own query, which is four round trips per case to a database on
    the other side of the internet. Twenty cases meant eighty sequential
    waits, and the control room felt broken when it was only waiting.
    """
    wanted = [value for value in dict.fromkeys(values) if value is not None]
    if not wanted:
        return []
    query = get_db().table(table).select("*").in_(column, wanted)
    rows = _rows(execute(query))
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def index_by(rows: List[Dict[str, Any]], key: str = "id") -> Dict[Any, Dict[str, Any]]:
    """Rows keyed by one column, for assembling a view without more queries."""
    return {row.get(key): row for row in rows if row.get(key) is not None}


def insert(table: str, row: Mapping[str, Any]) -> Dict[str, Any]:
    rows = _rows(execute(get_db().table(table).insert(dict(row))))
    return dict(rows[0]) if rows and isinstance(rows[0], Mapping) else {}


def update(table: str, values: Mapping[str, Any], **filters: Any) -> List[Dict[str, Any]]:
    query = get_db().table(table).update(dict(values))
    for column, value in filters.items():
        query = query.eq(column, value)
    rows = _rows(execute(query))
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def upsert(table: str, row: Mapping[str, Any], on_conflict: str) -> Dict[str, Any]:
    rows = _rows(
        execute(get_db().table(table).upsert(dict(row), on_conflict=on_conflict))
    )
    return dict(rows[0]) if rows and isinstance(rows[0], Mapping) else {}


def _rows(result: Any) -> list:
    return list(getattr(result, "data", result) or [])


def by_priority(rows: List[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Newest-first fallback for equal scores; the queue sorts on score."""
    ordered = sorted(
        rows,
        key=lambda row: (
            float(row.get("priority_score") or 0.0),
            int(row.get("id") or 0),
        ),
        reverse=True,
    )
    return [dict(row) for row in ordered]


def now() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now().isoformat()


def parse_timestamp(value: Any) -> Optional[datetime]:
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
