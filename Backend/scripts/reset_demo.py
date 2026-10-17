"""Wipe the operational tables and re-seed. Destructive, on purpose.

Between demo runs the database fills with half-finished cases, volunteers who
are on duty from an hour ago, and people rows bound to phones that have since
changed role. Clearing it by hand in the Supabase UI is slow and easy to get
wrong -- the foreign keys mean order matters.

Run from ``Backend/``::

    python -m scripts.reset_demo --yes

What it does NOT touch: the schema itself. Only rows.

Zones are deleted and re-seeded from ``data/areas.py``, so the 50 areas and
the volunteer split come back exactly as configured. Volunteers are rebuilt
from ``DEMO_VOLUNTEERS``, so changing who covers which half is an .env edit
followed by this script.
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Any, List, Tuple

logger = logging.getLogger("safezone.reset")

# Children before parents: every one of these is referenced by something above
# it, and Postgres will refuse the delete otherwise. The second element is a
# column that exists on that table and is never null, used to build a
# "match everything" filter -- PostgREST refuses an unfiltered delete.
TABLES: Tuple[Tuple[str, str], ...] = (
    ("dispatches", "id"),
    ("responder_links", "token"),
    ("zone_alerts", "id"),
    ("events", "id"),
    ("reports", "id"),
    ("cases", "id"),
    ("incidents", "id"),
    ("registrations", "code"),
    ("outbox", "id"),
    ("people", "id"),
    ("volunteers", "id"),
    ("zones", "id"),
)


def clear(client, table: str, key: str) -> int:
    """Delete every row in one table. Returns how many went."""
    from core.db import execute

    try:
        before = execute(client.table(table).select(key))
        count = len(list(getattr(before, "data", None) or []))
    except Exception as exc:  # noqa: BLE001 - table may not exist yet
        logger.warning("Could not read %s: %s", table, exc)
        return 0

    if count == 0:
        return 0

    try:
        # PostgREST requires a filter on delete. "not null" matches every row
        # without assuming anything about the key's type.
        execute(client.table(table).delete().not_.is_(key, "null"))
    except Exception as exc:  # noqa: BLE001
        logger.error("Could not clear %s: %s", table, exc)
        return 0

    return count


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Wipe demo data and re-seed.")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Required. Confirms you mean to delete every row.",
    )
    parser.add_argument(
        "--keep-volunteers",
        action="store_true",
        help="Leave volunteers and their ON DUTY status alone.",
    )
    parser.add_argument(
        "--no-samples",
        action="store_true",
        help="Re-seed zones and volunteers but leave the case queue empty.",
    )
    parser.add_argument(
        "--no-seed",
        action="store_true",
        help="Clear without re-seeding zones and volunteers.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")

    from core import config
    from core.db import get_db

    if not args.yes:
        print("This deletes EVERY row in:")
        print("  " + ", ".join(table for table, _key in TABLES))
        print(f"\nTarget: {config.SUPABASE_URL}")
        print("\nRe-run with --yes if that is what you want.")
        return 1

    client = get_db()
    print(f"Clearing {config.SUPABASE_URL}\n")

    tables = TABLES
    if args.keep_volunteers:
        tables = tuple((t, k) for t, k in TABLES if t != "volunteers")
        print("Keeping volunteers and their duty status.\n")

    total = 0
    for table, key in tables:
        removed = clear(client, table, key)
        total += removed
        print(f"  {table:<18} {removed:>6} rows")

    print(f"\n{total} rows deleted.")

    if args.no_seed:
        print("Skipped re-seeding (--no-seed).")
        return 0

    from core.phone import mask
    from data import seed as seed_module

    print("\nRe-seeding...")
    counts = seed_module.seed(client, samples=not args.no_samples)
    print(
        f"  {counts['zones']} zones, {counts['volunteers']} volunteers, "
        f"{counts['incidents']} sample incidents"
    )
    for volunteer in seed_module.volunteer_plan():
        marker = "  (PLACEHOLDER — set DEMO_VOLUNTEERS)" if volunteer["is_placeholder"] else ""
        print(
            f"  group {volunteer['group']}: {mask(volunteer['phone'])} "
            f"covers {len(volunteer['zone_ids'])} areas{marker}"
        )

    if args.keep_volunteers:
        print("\nExisting volunteers kept their duty status. Check with GET /api/volunteers.")
    else:
        print("\nVolunteers are seeded OFF DUTY. Each phone must send ON DUTY.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
