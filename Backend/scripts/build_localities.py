"""Build ``data/localities.json`` from OpenStreetMap.

Run this once, on a machine with internet. It writes a file that is committed
to the repo, so the running system never calls OpenStreetMap at all.

    python -m scripts.build_localities

Why this exists
---------------
``data/areas.py`` holds 78 areas. Nobody in an emergency writes the name of an
area: they write "Muskan", "Hussainabad", "Sindhi Muslim" -- the locality they
actually live in. Before this, those resolved to nothing, the incident was
created ``location_unknown``, and AGENTS.md 9 bars an unlocated case from
reaching a volunteer at all.

The landmark lists in ``areas.py`` fix the names somebody thought of in
advance. This fixes the rest, and it does it with data rather than memory:
every entry here is an OSM node with its own coordinates, so no human and no
model is guessing which area a place belongs to. We compute it.

Why it is a build step and not a runtime call
---------------------------------------------
A geocoding API during a flood is a network dependency at exactly the moment
networks fail, on the path that decides whether someone is reachable. A file
in the repo has no such failure mode. It is also faster, free, and works with
``MOCK_MODE=1`` and no network, which AGENTS.md 17 #5 requires of every
feature.

The cost is staleness: a locality added to OSM next month is not here until
someone re-runs this. For a city whose neighbourhood names change on a scale
of decades, that is the right trade.

Licensing
---------
OSM data is ODbL. The attribution belongs in the README alongside the other
trade-offs: "Locality names from OpenStreetMap contributors, ODbL."
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.geo import distance_km  # noqa: E402
from data import areas  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "data" / "localities.json"

# Mirrors, tried in order. Overpass instances rate-limit and go down; this is a
# one-off build step, so a slow retry is fine and a hard failure is not.
ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
)

# Karachi Division, generously. Anything outside is dropped: a node that
# geocodes to Hyderabad must never answer a Karachi message.
BBOX = (24.70, 66.60, 25.20, 67.50)  # south, west, north, east

# place=* values that name somewhere a person would say they live. Deliberately
# excludes shops, schools and amenities: "near the KFC" is not an area, and a
# POI name that collides with a locality name would route someone wrongly.
PLACES = "suburb|neighbourhood|quarter|hamlet|village|town|city_block|residential"

QUERY = f"""
[out:json][timeout:180];
(
  node["place"~"^({PLACES})$"]["name"]({BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]});
  way["place"~"^({PLACES})$"]["name"]({BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]});
  relation["place"~"^({PLACES})$"]["name"]({BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]});
);
out center tags;
"""


def fetch() -> Dict[str, Any]:
    """Ask Overpass for every named place in the box, trying each mirror."""
    body = urllib.parse.urlencode({"data": QUERY}).encode()
    last = ""
    for endpoint in ENDPOINTS:
        for attempt in (1, 2):
            try:
                print(f"  {endpoint} (attempt {attempt}) ...", flush=True)
                request = urllib.request.Request(
                    endpoint,
                    data=body,
                    # Overpass asks for a real identifier. A stock urllib
                    # User-Agent gets throttled or refused.
                    headers={"User-Agent": "SafeZone/1.0 (CODE-CONNECT-26 student project)"},
                )
                with urllib.request.urlopen(request, timeout=240) as response:
                    return json.loads(response.read().decode())
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last = f"{endpoint}: {exc}"
                print(f"    failed: {exc}", flush=True)
                time.sleep(5)
    raise SystemExit(f"Every Overpass mirror failed. Last error -- {last}")


def normalise(name: str) -> str:
    """Lowercase, punctuation-free form used for matching."""
    return "".join(ch for ch in name.lower() if ch.isalnum() or ch == " ").strip()


def main() -> None:
    print("Fetching named places in Karachi from OpenStreetMap ...")
    payload = fetch()
    elements = payload.get("elements", [])
    print(f"  {len(elements)} raw elements")

    # Area centroids, to decide which of the 78 covers each locality.
    centres: List[Tuple[str, float, float]] = []
    for area in areas.AREAS:
        centres.append((area["id"], float(area["lat"]), float(area["lng"])))

    # Everything already matchable. A locality that duplicates one of these
    # would make the offline matcher ambiguous, which is the failure the
    # areas.py docstring warns about, so existing entries always win.
    taken = {normalise(text) for text, _ in areas.search_index()}

    rows: Dict[str, Dict[str, Any]] = {}
    skipped_outside = skipped_dupe = skipped_short = 0

    for element in elements:
        tags = element.get("tags") or {}
        name = (tags.get("name:en") or tags.get("name") or "").strip()
        if not name:
            continue

        point = element.get("center") or element
        lat, lng = point.get("lat"), point.get("lon")
        if lat is None or lng is None:
            continue
        lat, lng = float(lat), float(lng)

        if not (BBOX[0] <= lat <= BBOX[2] and BBOX[1] <= lng <= BBOX[3]):
            skipped_outside += 1
            continue

        key = normalise(name)
        # Two characters matches half the messages in the queue.
        if len(key) < 4:
            skipped_short += 1
            continue
        if key in taken:
            skipped_dupe += 1
            continue
        if key in rows:
            continue

        nearest_id, nearest_km = min(
            ((aid, distance_km(lat, lng, alat, alng)) for aid, alat, alng in centres),
            key=lambda pair: pair[1],
        )

        rows[key] = {
            "name": name,
            "lat": round(lat, 5),
            "lng": round(lng, 5),
            "area": nearest_id,
            # How far the locality sits from the centre of the area we assigned
            # it to. Kept so a human can eyeball the doubtful ones: a locality
            # 8 km from its area's centre is probably mis-assigned, or the area
            # centroid is rough.
            "km": round(nearest_km, 2),
            "place": tags.get("place", ""),
        }

    out = {
        "source": "OpenStreetMap contributors, ODbL",
        "built_from": "Overpass API",
        "count": len(rows),
        "localities": dict(sorted(rows.items())),
    }
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")

    print(f"\nWrote {OUT}")
    print(f"  {len(rows)} localities")
    print(f"  skipped: {skipped_dupe} already matchable, {skipped_outside} outside Karachi, {skipped_short} too short")

    far = [r for r in rows.values() if r["km"] > 8]
    if far:
        print(f"\n  {len(far)} sit more than 8 km from their assigned area centre.")
        print("  Worth a glance -- these are the likeliest mis-assignments:")
        for row in sorted(far, key=lambda r: -r["km"])[:15]:
            print(f"    {row['name']:34} -> {row['area']:20} {row['km']:5.1f} km")


if __name__ == "__main__":
    main()
