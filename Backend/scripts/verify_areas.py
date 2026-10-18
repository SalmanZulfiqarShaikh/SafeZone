"""Check ``data/areas.py`` for the mistakes that break dispatch silently.

Run from ``Backend/``::

    python -m scripts.verify_areas

Every check here guards something that fails quietly rather than loudly:

* A duplicate id makes the last one win, so an area vanishes from the map.
* An alias that matches two areas makes the offline matcher pick one at
  random, and the case goes to the wrong volunteer.
* A missing key breaks the zone insert at seed time, long after the edit.
* A coordinate outside Karachi sends a responder across the province.
* An empty group means one phone owns the whole city.

Exits non-zero on any finding, so it can run in CI.
"""

from __future__ import annotations

import sys
from typing import Dict, List, Tuple

from data import areas

REQUIRED_KEYS = ("id", "name", "lat", "lng", "group", "district", "risk_level", "aliases")
RISK_LEVELS = ("normal", "elevated", "critical")

# The Karachi bounding box. Deliberately loose: these are neighbourhood
# midpoints, not survey points, and the box only has to catch a typo that
# moves an area to another city.
LAT_RANGE = (24.78, 25.05)
LNG_RANGE = (66.85, 67.35)


def check() -> List[str]:
    problems: List[str] = []

    seen_ids: Dict[str, int] = {}
    for index, area in enumerate(areas.AREAS):
        label = area.get("id") or f"<area #{index}>"

        missing = [key for key in REQUIRED_KEYS if key not in area]
        if missing:
            problems.append(f"{label}: missing key(s) {', '.join(missing)}")
            continue

        if area["id"] in seen_ids:
            problems.append(f"{label}: duplicate id (also at #{seen_ids[area['id']]})")
        seen_ids[area["id"]] = index

        if area["id"] != area["id"].strip().lower():
            problems.append(f"{label}: id must be lowercase and unpadded")

        if area["district"] not in areas.DISTRICTS:
            problems.append(f"{label}: district {area['district']!r} is not in DISTRICTS")
        elif area["group"] != areas.DISTRICT_GROUPS[area["district"]]:
            problems.append(
                f"{label}: group {area['group']!r} disagrees with district "
                f"{area['district']!r} (whole districts move, not areas)"
            )

        if area["group"] not in (areas.GROUP_A, areas.GROUP_B):
            problems.append(f"{label}: group {area['group']!r} is not a known group")

        if area["risk_level"] not in RISK_LEVELS:
            problems.append(f"{label}: risk_level {area['risk_level']!r} is not one of {RISK_LEVELS}")

        lat, lng = float(area["lat"]), float(area["lng"])
        if not LAT_RANGE[0] <= lat <= LAT_RANGE[1]:
            problems.append(f"{label}: lat {lat} outside Karachi {LAT_RANGE}")
        if not LNG_RANGE[0] <= lng <= LNG_RANGE[1]:
            problems.append(f"{label}: lng {lng} outside Karachi {LNG_RANGE}")

        if not isinstance(area["aliases"], tuple):
            problems.append(f"{label}: aliases must be a tuple")
        else:
            for alias in area["aliases"]:
                if alias != alias.strip().lower():
                    problems.append(f"{label}: alias {alias!r} must be lowercase and unpadded")

    # Every searchable phrase -- id, display name and alias alike -- must point
    # at exactly one area, which is the whole premise of the offline matcher.
    owners: Dict[str, List[str]] = {}
    for phrase, area_id in areas.search_index():
        owners.setdefault(phrase, [])
        if area_id not in owners[phrase]:
            owners[phrase].append(area_id)
    for phrase, ids in sorted(owners.items()):
        if len(ids) > 1:
            problems.append(f"alias/name collision: {phrase!r} matches {', '.join(sorted(ids))}")

    for group in (areas.GROUP_A, areas.GROUP_B):
        if not areas.by_group(group):
            problems.append(f"group {group!r} covers no areas")

    for district in areas.DISTRICTS:
        if not areas.by_district(district):
            problems.append(f"district {district!r} has no areas")

    covered = sorted(
        area_id for group in (areas.GROUP_A, areas.GROUP_B) for area_id in areas.by_group(group)
    )
    if covered != sorted(areas.AREA_IDS):
        problems.append("the two groups do not cover every area exactly once")

    return problems


def summary() -> str:
    by_district: Dict[str, int] = {
        district: len(areas.by_district(district)) for district in areas.DISTRICTS
    }
    by_group: Dict[str, int] = {
        group: len(areas.by_group(group)) for group in (areas.GROUP_A, areas.GROUP_B)
    }
    lines = [f"{len(areas.AREAS)} areas"]
    for district, count in by_district.items():
        lines.append(
            f"  {areas.DISTRICTS[district]:<16} ({district:<8}) {count:>3}"
            f"  group {areas.DISTRICT_GROUPS[district]}"
        )
    for group, count in by_group.items():
        lines.append(f"  group {group}: {count} areas")
    return "\n".join(lines)


def main() -> int:
    problems = check()
    print(summary())
    if problems:
        print(f"\n{len(problems)} problem(s):")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("\nOK: ids and aliases unique, keys present, coordinates in Karachi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
