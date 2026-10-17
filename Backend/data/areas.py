"""The Karachi areas SafeZone covers, with approximate centres.

One list, read by three places, because three copies drift:

* ``data/seed.py`` writes these into the ``zones`` table.
* ``services/extract.py`` puts the names in the prompt so the model picks a
  real area instead of inventing a spelling.
* ``services/intake.py`` falls back to an area's centre when someone names
  their area but never shares a pin -- without coordinates a case cannot be
  dispatched to anyone at all.

**The centres are approximate.** They are rough neighbourhood midpoints good
enough to choose which volunteer is nearer and to drop a map pin. They are not
survey data and must never be shown to a responder as the location of a
person. An exact location only ever comes from a shared pin.

**The split.** Two volunteers cover 25 areas each, grouped so that each
volunteer's areas are roughly contiguous -- "nearest" is meaningless if one
phone owns scattered areas across the city. Group A is the south, east and
Malir corridor; group B is the centre-north, west and the far north. The
phone numbers themselves are NOT here: they live in ``DEMO_VOLUNTEERS`` in the
environment, because this repository is public (AGENTS.md 12).
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Tuple

GROUP_A = "a"
GROUP_B = "b"

# id, display name, latitude, longitude, group, risk level.
# Aliases carry the spellings people actually type, for the offline fallback
# matcher; the model handles the rest, including typos.
AREAS: Tuple[Dict[str, Any], ...] = (
    # ─── Group A — south, east, Malir corridor ──────────────────────────────
    {"id": "saddar", "name": "Saddar", "lat": 24.8607, "lng": 67.0104, "group": GROUP_A, "risk_level": "normal", "aliases": ("sadar",)},
    {"id": "clifton", "name": "Clifton", "lat": 24.8138, "lng": 67.0300, "group": GROUP_A, "risk_level": "elevated", "aliases": ()},
    {"id": "dha", "name": "DHA", "lat": 24.8008, "lng": 67.0518, "group": GROUP_A, "risk_level": "normal", "aliases": ("defence", "defence housing", "d.h.a")},
    {"id": "lyari", "name": "Lyari", "lat": 24.8730, "lng": 66.9970, "group": GROUP_A, "risk_level": "critical", "aliases": ("liyari",)},
    {"id": "kharadar", "name": "Kharadar", "lat": 24.8520, "lng": 66.9950, "group": GROUP_A, "risk_level": "elevated", "aliases": ("khara dar",)},
    {"id": "mithadar", "name": "Mithadar", "lat": 24.8545, "lng": 66.9930, "group": GROUP_A, "risk_level": "elevated", "aliases": ("mitha dar",)},
    {"id": "garden", "name": "Garden", "lat": 24.8740, "lng": 67.0220, "group": GROUP_A, "risk_level": "normal", "aliases": ("garden east", "garden west")},
    {"id": "soldier-bazaar", "name": "Soldier Bazaar", "lat": 24.8720, "lng": 67.0320, "group": GROUP_A, "risk_level": "normal", "aliases": ("soldier bazar",)},
    {"id": "civil-lines", "name": "Civil Lines", "lat": 24.8480, "lng": 67.0240, "group": GROUP_A, "risk_level": "normal", "aliases": ()},
    {"id": "gulshan", "name": "Gulshan-e-Iqbal", "lat": 24.9200, "lng": 67.0970, "group": GROUP_A, "risk_level": "critical", "aliases": ("gulshan e iqbal", "gulshan iqbal")},
    {"id": "johar", "name": "Gulistan-e-Jauhar", "lat": 24.9180, "lng": 67.1300, "group": GROUP_A, "risk_level": "elevated", "aliases": ("gulistan e jauhar", "gulistan e johar", "jauhar", "johar")},
    {"id": "gulzar-e-hijri", "name": "Gulzar-e-Hijri", "lat": 24.9400, "lng": 67.1300, "group": GROUP_A, "risk_level": "elevated", "aliases": ("gulzar hijri",)},
    {"id": "safoora", "name": "Safoora Goth", "lat": 24.9400, "lng": 67.1500, "group": GROUP_A, "risk_level": "elevated", "aliases": ("safora", "safoora chowrangi")},
    {"id": "scheme-33", "name": "Scheme 33", "lat": 24.9300, "lng": 67.1400, "group": GROUP_A, "risk_level": "elevated", "aliases": ("scheme33", "scheme thirty three")},
    {"id": "pechs", "name": "PECHS", "lat": 24.8700, "lng": 67.0600, "group": GROUP_A, "risk_level": "normal", "aliases": ("p.e.c.h.s", "pech society")},
    {"id": "bahadurabad", "name": "Bahadurabad", "lat": 24.8800, "lng": 67.0650, "group": GROUP_A, "risk_level": "normal", "aliases": ("bahadrabad",)},
    {"id": "tariq-road", "name": "Tariq Road", "lat": 24.8730, "lng": 67.0620, "group": GROUP_A, "risk_level": "normal", "aliases": ()},
    {"id": "jamshed", "name": "Jamshed Town", "lat": 24.8790, "lng": 67.0480, "group": GROUP_A, "risk_level": "normal", "aliases": ("jamshed quarters",)},
    {"id": "kda-scheme-1", "name": "KDA Scheme 1", "lat": 24.8900, "lng": 67.0700, "group": GROUP_A, "risk_level": "normal", "aliases": ("kda scheme one",)},
    {"id": "korangi", "name": "Korangi", "lat": 24.8400, "lng": 67.1300, "group": GROUP_A, "risk_level": "elevated", "aliases": ("korangi crossing", "korangi industrial area")},
    {"id": "landhi", "name": "Landhi", "lat": 24.8500, "lng": 67.1900, "group": GROUP_A, "risk_level": "elevated", "aliases": ()},
    {"id": "shah-faisal", "name": "Shah Faisal Colony", "lat": 24.8800, "lng": 67.1600, "group": GROUP_A, "risk_level": "elevated", "aliases": ("shah faisal",)},
    {"id": "malir-cantt", "name": "Malir Cantt", "lat": 24.8900, "lng": 67.1900, "group": GROUP_A, "risk_level": "normal", "aliases": ("malir cantonment", "malir")},
    {"id": "model-colony", "name": "Model Colony", "lat": 24.9000, "lng": 67.1700, "group": GROUP_A, "risk_level": "normal", "aliases": ()},
    {"id": "ibrahim-hyderi", "name": "Ibrahim Hyderi", "lat": 24.7800, "lng": 67.1800, "group": GROUP_A, "risk_level": "critical", "aliases": ("ibrahim haidari",)},

    # ─── Group B — centre-north, west, far north ────────────────────────────
    {"id": "nazimabad", "name": "Nazimabad", "lat": 24.9100, "lng": 67.0300, "group": GROUP_B, "risk_level": "elevated", "aliases": ()},
    {"id": "north-nazimabad", "name": "North Nazimabad", "lat": 24.9400, "lng": 67.0400, "group": GROUP_B, "risk_level": "elevated", "aliases": ("nnazimabad",)},
    {"id": "liaquatabad", "name": "Liaquatabad", "lat": 24.9000, "lng": 67.0400, "group": GROUP_B, "risk_level": "critical", "aliases": ("lalukhet", "liaqatabad")},
    {"id": "gulberg", "name": "Gulberg", "lat": 24.9300, "lng": 67.0550, "group": GROUP_B, "risk_level": "elevated", "aliases": ()},
    {"id": "new-karachi", "name": "New Karachi", "lat": 24.9900, "lng": 67.0700, "group": GROUP_B, "risk_level": "elevated", "aliases": ()},
    {"id": "north-karachi", "name": "North Karachi", "lat": 24.9700, "lng": 67.0600, "group": GROUP_B, "risk_level": "elevated", "aliases": ()},
    {"id": "buffer-zone", "name": "Buffer Zone", "lat": 24.9600, "lng": 67.0650, "group": GROUP_B, "risk_level": "elevated", "aliases": ()},
    {"id": "surjani", "name": "Surjani Town", "lat": 25.0100, "lng": 67.0600, "group": GROUP_B, "risk_level": "critical", "aliases": ("surjani",)},
    {"id": "shadman", "name": "Shadman Town", "lat": 24.9650, "lng": 67.0600, "group": GROUP_B, "risk_level": "normal", "aliases": ("shadman",)},
    {"id": "sakhi-hassan", "name": "Sakhi Hassan", "lat": 24.9450, "lng": 67.0380, "group": GROUP_B, "risk_level": "normal", "aliases": ()},
    {"id": "paposh-nagar", "name": "Paposh Nagar", "lat": 24.9300, "lng": 67.0350, "group": GROUP_B, "risk_level": "normal", "aliases": ("paposh",)},
    {"id": "gujjar", "name": "Gujjar Nala", "lat": 24.9250, "lng": 67.0450, "group": GROUP_B, "risk_level": "critical", "aliases": ("gujjar", "gujar nala", "gujjar colony")},
    {"id": "orangi", "name": "Orangi Town", "lat": 24.9500, "lng": 66.9800, "group": GROUP_B, "risk_level": "critical", "aliases": ("orangi",)},
    {"id": "baldia", "name": "Baldia Town", "lat": 24.9200, "lng": 66.9600, "group": GROUP_B, "risk_level": "elevated", "aliases": ("baldia",)},
    {"id": "site", "name": "SITE Area", "lat": 24.9100, "lng": 67.0000, "group": GROUP_B, "risk_level": "elevated", "aliases": ("site town", "s.i.t.e")},
    {"id": "mominabad", "name": "Mominabad", "lat": 24.9400, "lng": 66.9700, "group": GROUP_B, "risk_level": "elevated", "aliases": ()},
    {"id": "manghopir", "name": "Manghopir", "lat": 25.0000, "lng": 66.9800, "group": GROUP_B, "risk_level": "elevated", "aliases": ("mangopir",)},
    {"id": "pak-colony", "name": "Pak Colony", "lat": 24.9000, "lng": 66.9900, "group": GROUP_B, "risk_level": "elevated", "aliases": ()},
    {"id": "banaras", "name": "Banaras", "lat": 24.9200, "lng": 66.9900, "group": GROUP_B, "risk_level": "elevated", "aliases": ("banaras chowk",)},
    {"id": "keamari", "name": "Keamari", "lat": 24.8400, "lng": 66.9800, "group": GROUP_B, "risk_level": "elevated", "aliases": ("kemari", "kiamari")},
    {"id": "maripur", "name": "Maripur", "lat": 24.8600, "lng": 66.9500, "group": GROUP_B, "risk_level": "elevated", "aliases": ("mauripur",)},
    {"id": "hawksbay", "name": "Hawksbay", "lat": 24.8500, "lng": 66.8500, "group": GROUP_B, "risk_level": "normal", "aliases": ("hawks bay",)},
    {"id": "steel-town", "name": "Steel Town", "lat": 24.8600, "lng": 67.3200, "group": GROUP_B, "risk_level": "normal", "aliases": ("bin qasim", "bin qasim town")},
    {"id": "gadap", "name": "Gadap Town", "lat": 25.0500, "lng": 67.2000, "group": GROUP_B, "risk_level": "elevated", "aliases": ("gadap",)},
    {"id": "murad-memon", "name": "Murad Memon", "lat": 25.0000, "lng": 67.2500, "group": GROUP_B, "risk_level": "normal", "aliases": ("murad memon goth",)},
)

AREA_IDS: Tuple[str, ...] = tuple(area["id"] for area in AREAS)
AREAS_BY_ID: Dict[str, Mapping[str, Any]] = {area["id"]: area for area in AREAS}


def by_group(group: str) -> List[str]:
    """Area ids belonging to one volunteer group."""
    return [area["id"] for area in AREAS if area["group"] == group]


def centroid(area_id: Optional[str]) -> Optional[Tuple[float, float]]:
    """Approximate ``(lat, lng)`` for an area, or ``None`` if unknown.

    Only ever used as a fallback for ranking and map display. A responder is
    shown an exact pin or nothing.
    """
    area = AREAS_BY_ID.get((area_id or "").strip().lower())
    if area is None:
        return None
    return float(area["lat"]), float(area["lng"])


def prompt_list() -> str:
    """The area list as the model sees it: ``id (Display Name)`` per line.

    Giving the model the real ids is what lets it map "Gulistan e Jauhar",
    "Jauhar" and a typo like "Guilstan" onto ``johar`` itself, rather than us
    trying to anticipate every spelling in a regex.
    """
    return "\n".join(f"{area['id']} ({area['name']})" for area in AREAS)


def search_index() -> List[Tuple[str, str]]:
    """``(searchable text, area id)`` pairs for the offline fallback matcher.

    Includes the id, the display name and every alias.
    """
    index: List[Tuple[str, str]] = []
    for area in AREAS:
        index.append((area["id"].replace("-", " "), area["id"]))
        index.append((area["name"].lower(), area["id"]))
        for alias in area.get("aliases", ()):
            index.append((alias.lower(), area["id"]))
    return index
