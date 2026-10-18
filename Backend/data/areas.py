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

**The districts.** Every area carries the district it sits in, using the seven
official districts of Karachi Division (``DISTRICTS``): Karachi Central
(Nazimabad), Karachi East (Gulshan), Karachi South, Karachi West (Orangi),
Korangi, Malir and Keamari. Sub-divisions appear as areas in their own right
where people actually name them that way (Aram Bagh, Ferozabad, Mango Pir),
and the neighbourhoods under them are listed beside them, because a caller
says "Ancholi", not "Gulberg sub-division".

**The split.** Two volunteers cover 78 areas between them: group A covers 37
areas and group B covers 41.

Groups are assigned by WHOLE DISTRICT, never area by area. "Nearest
volunteer" is meaningless if one phone owns scattered areas across the city,
and a district boundary is the one line both volunteers and callers already
understand:

* **Group A** -- Karachi East, Korangi, Malir: the eastern and south-eastern
  corridor, from Gulshan and Johar out through Korangi and Landhi to Steel
  Town and Gadap.
* **Group B** -- Karachi South, Karachi Central, Karachi West, Keamari: the
  coast and old city, up through Nazimabad and Orangi to the harbour.

Each group is a contiguous block: A is East-Korangi-Malir, B chains
South-Keamari-West-Central. Adding a district means moving whole districts
between groups, not splitting one.

The phone numbers themselves are NOT here: they live in ``DEMO_VOLUNTEERS``
in the environment, because this repository is public (AGENTS.md 12).
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Tuple

GROUP_A = "a"
GROUP_B = "b"

# The seven districts of Karachi Division. Short stable ids: these are written
# into area rows and read by callers, so they outlive any renaming of the
# display names.
DISTRICT_CENTRAL = "central"
DISTRICT_EAST = "east"
DISTRICT_SOUTH = "south"
DISTRICT_WEST = "west"
DISTRICT_KORANGI = "korangi"
DISTRICT_MALIR = "malir"
DISTRICT_KEAMARI = "keamari"

DISTRICTS: Dict[str, str] = {
    DISTRICT_CENTRAL: "Karachi Central",
    DISTRICT_EAST: "Karachi East",
    DISTRICT_SOUTH: "Karachi South",
    DISTRICT_WEST: "Karachi West",
    DISTRICT_KORANGI: "Korangi",
    DISTRICT_MALIR: "Malir",
    DISTRICT_KEAMARI: "Keamari",
}

# Which volunteer group covers each district. Whole districts only -- see the
# module docstring. ``area["group"]`` is derived from this, so the two can
# never disagree.
DISTRICT_GROUPS: Dict[str, str] = {
    DISTRICT_EAST: GROUP_A,
    DISTRICT_KORANGI: GROUP_A,
    DISTRICT_MALIR: GROUP_A,
    DISTRICT_SOUTH: GROUP_B,
    DISTRICT_CENTRAL: GROUP_B,
    DISTRICT_WEST: GROUP_B,
    DISTRICT_KEAMARI: GROUP_B,
}

# id, display name, latitude, longitude, district, risk level.
# The volunteer group is NOT written here: it is derived from the district
# just below, so a per-area group can never drift out of step with the
# whole-district rule.
# Aliases carry the spellings people actually type, for the offline fallback
# matcher; the model handles the rest, including typos. Every alias is unique
# across the whole list: an alias that matched two areas would make the
# offline matcher pick one of them at random.
#
# Landmarks are different from aliases. An alias is another way of writing the
# area's OWN name ("jauhar" for Gulistan-e-Jauhar). A landmark is a place
# INSIDE the area that people name instead of the area -- nobody in an
# emergency writes "Gulshan-e-Iqbal", they write "Muskan" or "NIPA".
#
# They matter because the model only ever sees what prompt_list() shows it.
# Before landmarks existed that was the id and the display name, so "muskan
# chowrangi me aag lag gayi" resolved to nothing, the incident was created
# location_unknown, and AGENTS.md 9 bars an unlocated case from reaching a
# volunteer at all. A landmark is not decoration; it is the difference between
# a case being dispatchable and not.
#
# ⚠ EVERY LANDMARK BELOW NEEDS LOCAL VERIFICATION. A wrong mapping is worse
# than a missing one: a missing landmark leaves the case unlocated and visible
# to the coordinator, while a wrong one silently sends a volunteer to the
# wrong district and nobody finds out until they arrive. Check each line
# against what you actually know of the city, and delete any you are unsure
# of. Landmarks share the alias namespace, so they must be unique too.
AREAS: Tuple[Dict[str, Any], ...] = (
    # ═══ GROUP A ════════════════════════════════════════════════════════════

    # ─── Karachi East (Gulshan District) ────────────────────────────────────
    # Sub-divisions: Ferozabad, Gulshan-e-Iqbal, Gulzar-e-Hijri, Jamshed Qrs.
    {"id": "gulshan", "name": "Gulshan-e-Iqbal", "lat": 24.9200, "lng": 67.0970, "district": DISTRICT_EAST, "risk_level": "critical", "aliases": ("gulshan e iqbal", "gulshan iqbal"), "landmarks": ("nipa", "nipa chowrangi", "hasan square", "muskan", "muskan chowrangi", "expo centre", "expo center", "safari park", "urdu university", "disco bakery", "gulshan chowrangi",)},
    {"id": "johar", "name": "Gulistan-e-Jauhar", "lat": 24.9180, "lng": 67.1300, "district": DISTRICT_EAST, "risk_level": "elevated", "aliases": ("gulistan e jauhar", "gulistan e johar", "jauhar", "johar"), "landmarks": ("perfume chowk", "munawar chowrangi", "kamran chowrangi", "pehlwan goth", "rabia city", "jauhar chowrangi", "johar chowrangi",)},
    {"id": "gulzar-e-hijri", "name": "Gulzar-e-Hijri", "lat": 24.9400, "lng": 67.1300, "district": DISTRICT_EAST, "risk_level": "elevated", "aliases": ("gulzar hijri",)},
    {"id": "safoora", "name": "Safoora Goth", "lat": 24.9400, "lng": 67.1500, "district": DISTRICT_EAST, "risk_level": "elevated", "aliases": ("safora", "safoora chowrangi")},
    {"id": "scheme-33", "name": "Scheme 33", "lat": 24.9300, "lng": 67.1400, "district": DISTRICT_EAST, "risk_level": "elevated", "aliases": ("scheme33", "scheme thirty three")},
    {"id": "ferozabad", "name": "Ferozabad", "lat": 24.8870, "lng": 67.0730, "district": DISTRICT_EAST, "risk_level": "normal", "aliases": ("feroz abad", "firozabad")},
    {"id": "pechs", "name": "PECHS", "lat": 24.8700, "lng": 67.0600, "district": DISTRICT_EAST, "risk_level": "normal", "aliases": ("p.e.c.h.s", "pech society")},
    {"id": "bahadurabad", "name": "Bahadurabad", "lat": 24.8800, "lng": 67.0650, "district": DISTRICT_EAST, "risk_level": "normal", "aliases": ("bahadrabad",)},
    {"id": "tariq-road", "name": "Tariq Road", "lat": 24.8730, "lng": 67.0620, "district": DISTRICT_EAST, "risk_level": "normal", "aliases": ()},
    {"id": "jamshed", "name": "Jamshed Town", "lat": 24.8790, "lng": 67.0480, "district": DISTRICT_EAST, "risk_level": "normal", "aliases": ("jamshed quarters",)},
    {"id": "kda-scheme-1", "name": "KDA Scheme 1", "lat": 24.8900, "lng": 67.0700, "district": DISTRICT_EAST, "risk_level": "normal", "aliases": ("kda scheme one",)},
    {"id": "soldier-bazaar", "name": "Soldier Bazaar", "lat": 24.8720, "lng": 67.0320, "district": DISTRICT_EAST, "risk_level": "normal", "aliases": ("soldier bazar",)},
    {"id": "abyssinia-lines", "name": "Abyssinia Lines", "lat": 24.8740, "lng": 67.0410, "district": DISTRICT_EAST, "risk_level": "normal", "aliases": ("abysinia lines", "abyssinia")},
    {"id": "delhi-colony", "name": "Delhi Colony", "lat": 24.8290, "lng": 67.0320, "district": DISTRICT_EAST, "risk_level": "elevated", "aliases": ("dehli colony", "delhi mercantile colony")},
    {"id": "mehmoodabad", "name": "Mehmoodabad", "lat": 24.8630, "lng": 67.0760, "district": DISTRICT_EAST, "risk_level": "critical", "aliases": ("mahmoodabad", "mehmood abad", "mehmudabad")},

    # ─── Korangi District ───────────────────────────────────────────────────
    # Sub-divisions: Korangi, Landhi, Model Colony, Shah Faisal.
    {"id": "korangi", "name": "Korangi", "lat": 24.8400, "lng": 67.1300, "district": DISTRICT_KORANGI, "risk_level": "elevated", "aliases": ("korangi crossing", "korangi town"), "landmarks": ("mehran town", "korangi number 5", "singer chowrangi",)},
    {"id": "korangi-industrial", "name": "Korangi Industrial Area", "lat": 24.8330, "lng": 67.1480, "district": DISTRICT_KORANGI, "risk_level": "elevated", "aliases": ("korangi industrial", "korangi industrial estate")},
    {"id": "landhi", "name": "Landhi", "lat": 24.8500, "lng": 67.1900, "district": DISTRICT_KORANGI, "risk_level": "elevated", "aliases": ("landhi town",), "landmarks": ("future colony", "sharafi goth", "babar market",)},
    {"id": "landhi-colony", "name": "Landhi Colony", "lat": 24.8420, "lng": 67.2050, "district": DISTRICT_KORANGI, "risk_level": "elevated", "aliases": ("landhi coloney",)},
    {"id": "nasir-colony", "name": "Nasir Colony", "lat": 24.8370, "lng": 67.1680, "district": DISTRICT_KORANGI, "risk_level": "critical", "aliases": ("nasir coloney",)},
    {"id": "zaman-town", "name": "Zaman Town", "lat": 24.8460, "lng": 67.1430, "district": DISTRICT_KORANGI, "risk_level": "elevated", "aliases": ("zamaan town",)},
    {"id": "zia-colony", "name": "Zia Colony", "lat": 24.8390, "lng": 67.1250, "district": DISTRICT_KORANGI, "risk_level": "critical", "aliases": ("ziya colony",)},
    {"id": "akhtar-colony", "name": "Akhtar Colony", "lat": 24.8370, "lng": 67.0830, "district": DISTRICT_KORANGI, "risk_level": "critical", "aliases": ("akhter colony",)},
    {"id": "shah-faisal", "name": "Shah Faisal Colony", "lat": 24.8800, "lng": 67.1600, "district": DISTRICT_KORANGI, "risk_level": "elevated", "aliases": ("shah faisal", "shah faisal town")},
    {"id": "model-colony", "name": "Model Colony", "lat": 24.9000, "lng": 67.1700, "district": DISTRICT_KORANGI, "risk_level": "normal", "aliases": ("modal colony",)},

    # ─── Malir District ─────────────────────────────────────────────────────
    # Sub-divisions: Airport, Bin Qasim, Gadap, Ibrahim Hyderi, Murad Memon,
    # Shah Mureed.
    {"id": "malir-cantt", "name": "Malir Cantt", "lat": 24.8900, "lng": 67.1900, "district": DISTRICT_MALIR, "risk_level": "normal", "aliases": ("malir cantonment", "malir")},
    {"id": "malir-city", "name": "Malir City", "lat": 24.8930, "lng": 67.2050, "district": DISTRICT_MALIR, "risk_level": "elevated", "aliases": ("malir halt", "malir town", "malir no 1"), "landmarks": ("jafar e tayyar", "khokhrapar",)},
    {"id": "airport", "name": "Airport", "lat": 24.9050, "lng": 67.1600, "district": DISTRICT_MALIR, "risk_level": "normal", "aliases": ("karachi airport", "jinnah airport", "jinnah terminal", "airport area")},
    {"id": "quaidabad", "name": "Quaidabad", "lat": 24.8680, "lng": 67.2370, "district": DISTRICT_MALIR, "risk_level": "elevated", "aliases": ("quaid abad", "kaidabad", "qaidabad")},
    {"id": "ibrahim-hyderi", "name": "Ibrahim Hyderi", "lat": 24.7800, "lng": 67.1800, "district": DISTRICT_MALIR, "risk_level": "critical", "aliases": ("ibrahim haidari", "ibrahim hydri")},
    {"id": "abbas-town", "name": "Abbas Town", "lat": 24.9410, "lng": 67.1180, "district": DISTRICT_MALIR, "risk_level": "elevated", "aliases": ("abbas town block",)},
    {"id": "gulshan-e-maymar", "name": "Gulshan-e-Maymar", "lat": 25.0230, "lng": 67.1150, "district": DISTRICT_MALIR, "risk_level": "normal", "aliases": ("maymar", "gulshan maymar", "gulshan e memar")},
    {"id": "gulshan-e-hadeed", "name": "Gulshan-e-Hadeed", "lat": 24.8700, "lng": 67.3300, "district": DISTRICT_MALIR, "risk_level": "normal", "aliases": ("hadeed", "gulshan hadeed", "gulshan e hadid")},
    {"id": "steel-town", "name": "Steel Town", "lat": 24.8600, "lng": 67.3200, "district": DISTRICT_MALIR, "risk_level": "normal", "aliases": ("bin qasim", "bin qasim town", "pakistan steel mills township", "steel mills township")},
    {"id": "gadap", "name": "Gadap Town", "lat": 25.0500, "lng": 67.2000, "district": DISTRICT_MALIR, "risk_level": "elevated", "aliases": ("gadap",)},
    {"id": "murad-memon", "name": "Murad Memon", "lat": 25.0000, "lng": 67.2500, "district": DISTRICT_MALIR, "risk_level": "normal", "aliases": ("murad memon goth",)},
    {"id": "shah-mureed", "name": "Shah Mureed", "lat": 25.0100, "lng": 67.2800, "district": DISTRICT_MALIR, "risk_level": "elevated", "aliases": ("shah mureed goth", "shah murid")},

    # ═══ GROUP B ════════════════════════════════════════════════════════════

    # ─── Karachi South ──────────────────────────────────────────────────────
    # Sub-divisions: Aram Bagh, Civil Lines, Garden, Lyari, Saddar. Manora is
    # named under South and under Keamari; it is listed once, under Keamari,
    # whose harbour it sits off. Both are group B, so nothing changes for
    # dispatch either way.
    {"id": "saddar", "name": "Saddar", "lat": 24.8607, "lng": 67.0104, "district": DISTRICT_SOUTH, "risk_level": "normal", "aliases": ("sadar",), "landmarks": ("empress market", "zainab market", "regal chowk", "preedy street",)},
    {"id": "clifton", "name": "Clifton", "lat": 24.8138, "lng": 67.0300, "district": DISTRICT_SOUTH, "risk_level": "elevated", "aliases": (), "landmarks": ("boat basin", "teen talwar", "sea view", "seaview", "do talwar",)},
    {"id": "bath-island", "name": "Bath Island", "lat": 24.8280, "lng": 67.0270, "district": DISTRICT_SOUTH, "risk_level": "normal", "aliases": ("bathisland",)},
    {"id": "dha", "name": "DHA", "lat": 24.8008, "lng": 67.0518, "district": DISTRICT_SOUTH, "risk_level": "normal", "aliases": ("defence", "defence housing", "d.h.a"), "landmarks": ("zamzama", "khayaban e ittehad", "khayaban e shahbaz", "do darya",)},
    {"id": "lyari", "name": "Lyari", "lat": 24.8730, "lng": 66.9970, "district": DISTRICT_SOUTH, "risk_level": "critical", "aliases": ("liyari", "lyari town"), "landmarks": ("baghdadi", "chakiwara", "agra taj", "kalri",)},
    {"id": "kharadar", "name": "Kharadar", "lat": 24.8520, "lng": 66.9950, "district": DISTRICT_SOUTH, "risk_level": "elevated", "aliases": ("khara dar",)},
    {"id": "mithadar", "name": "Mithadar", "lat": 24.8545, "lng": 66.9930, "district": DISTRICT_SOUTH, "risk_level": "elevated", "aliases": ("mitha dar",)},
    {"id": "garden", "name": "Garden", "lat": 24.8740, "lng": 67.0220, "district": DISTRICT_SOUTH, "risk_level": "normal", "aliases": ("garden east", "garden west")},
    {"id": "aram-bagh", "name": "Aram Bagh", "lat": 24.8640, "lng": 67.0160, "district": DISTRICT_SOUTH, "risk_level": "elevated", "aliases": ("aram bagh quarters", "ram bagh", "arambagh")},
    {"id": "civil-lines", "name": "Civil Lines", "lat": 24.8480, "lng": 67.0240, "district": DISTRICT_SOUTH, "risk_level": "normal", "aliases": ()},

    # ─── Karachi Central (Nazimabad District) ───────────────────────────────
    # Sub-divisions: Gulberg, Liaquatabad, Nazimabad, North Nazimabad,
    # New Karachi, New Nazimabad.
    {"id": "nazimabad", "name": "Nazimabad", "lat": 24.9100, "lng": 67.0300, "district": DISTRICT_CENTRAL, "risk_level": "elevated", "aliases": (), "landmarks": ("golimar", "nazimabad number 1", "petrol pump chowrangi",)},
    {"id": "north-nazimabad", "name": "North Nazimabad", "lat": 24.9400, "lng": 67.0400, "district": DISTRICT_CENTRAL, "risk_level": "elevated", "aliases": ("nnazimabad",)},
    {"id": "new-nazimabad", "name": "New Nazimabad", "lat": 24.9480, "lng": 67.0250, "district": DISTRICT_CENTRAL, "risk_level": "normal", "aliases": ("new nazimabad scheme",)},
    {"id": "liaquatabad", "name": "Liaquatabad", "lat": 24.9000, "lng": 67.0400, "district": DISTRICT_CENTRAL, "risk_level": "critical", "aliases": ("lalukhet", "liaqatabad", "liyaquatabad"), "landmarks": ("liaquatabad number 10", "dak khana",)},
    {"id": "abbasi-shaheed", "name": "Abbasi Shaheed", "lat": 24.9150, "lng": 67.0460, "district": DISTRICT_CENTRAL, "risk_level": "elevated", "aliases": ("abbasi shaheed hospital", "abbasi shaheed colony")},
    {"id": "gulberg", "name": "Gulberg", "lat": 24.9300, "lng": 67.0550, "district": DISTRICT_CENTRAL, "risk_level": "elevated", "aliases": ()},
    {"id": "fb-area", "name": "Federal B. Area", "lat": 24.9230, "lng": 67.0620, "district": DISTRICT_CENTRAL, "risk_level": "elevated", "aliases": ("fb area", "f.b. area", "federal b area", "federal bee area", "f b area"), "landmarks": ("water pump", "water pump chowrangi", "ayesha manzil", "karimabad",)},
    {"id": "ancholi", "name": "Ancholi", "lat": 24.9290, "lng": 67.0470, "district": DISTRICT_CENTRAL, "risk_level": "elevated", "aliases": ("ancholi block 20", "anchuli")},
    {"id": "azizabad", "name": "Azizabad", "lat": 24.9230, "lng": 67.0530, "district": DISTRICT_CENTRAL, "risk_level": "elevated", "aliases": ("aziz abad",)},
    {"id": "hyderi", "name": "Hyderi", "lat": 24.9390, "lng": 67.0370, "district": DISTRICT_CENTRAL, "risk_level": "normal", "aliases": ("hyderi market", "haideri", "hydri")},
    {"id": "new-karachi", "name": "New Karachi", "lat": 24.9900, "lng": 67.0700, "district": DISTRICT_CENTRAL, "risk_level": "elevated", "aliases": (), "landmarks": ("godhra", "sir syed", "new karachi number 5",)},
    {"id": "north-karachi", "name": "North Karachi", "lat": 24.9700, "lng": 67.0600, "district": DISTRICT_CENTRAL, "risk_level": "elevated", "aliases": (), "landmarks": ("power house", "power house chowrangi", "five star chowrangi",)},
    {"id": "buffer-zone", "name": "Buffer Zone", "lat": 24.9600, "lng": 67.0650, "district": DISTRICT_CENTRAL, "risk_level": "elevated", "aliases": ()},
    {"id": "shadman", "name": "Shadman Town", "lat": 24.9650, "lng": 67.0600, "district": DISTRICT_CENTRAL, "risk_level": "normal", "aliases": ("shadman",)},
    {"id": "sakhi-hassan", "name": "Sakhi Hassan", "lat": 24.9450, "lng": 67.0380, "district": DISTRICT_CENTRAL, "risk_level": "normal", "aliases": ()},
    {"id": "paposh-nagar", "name": "Paposh Nagar", "lat": 24.9300, "lng": 67.0350, "district": DISTRICT_CENTRAL, "risk_level": "normal", "aliases": ("paposh",)},
    {"id": "gujjar", "name": "Gujjar Nala", "lat": 24.9250, "lng": 67.0450, "district": DISTRICT_CENTRAL, "risk_level": "critical", "aliases": ("gujjar", "gujar nala", "gujjar colony")},

    # ─── Karachi West (Orangi District) ─────────────────────────────────────
    # Sub-divisions: Mango Pir, Mominabad, Orangi Town. "Baldia Colony" in the
    # west is the same place people call Baldia Town, which sits under Keamari
    # below -- one pin, not two.
    {"id": "orangi", "name": "Orangi Town", "lat": 24.9500, "lng": 66.9800, "district": DISTRICT_WEST, "risk_level": "critical", "aliases": ("orangi",), "landmarks": ("qasba colony", "iqbal market", "orangi number 5",)},
    {"id": "mominabad", "name": "Mominabad", "lat": 24.9400, "lng": 66.9700, "district": DISTRICT_WEST, "risk_level": "elevated", "aliases": ("momin abad",)},
    {"id": "manghopir", "name": "Manghopir", "lat": 25.0000, "lng": 66.9800, "district": DISTRICT_WEST, "risk_level": "elevated", "aliases": ("mangopir", "mangho pir", "mango pir")},
    {"id": "banaras", "name": "Banaras", "lat": 24.9200, "lng": 66.9900, "district": DISTRICT_WEST, "risk_level": "elevated", "aliases": ("banaras chowk", "banaras colony")},
    {"id": "metroville", "name": "Metroville", "lat": 24.9300, "lng": 66.9930, "district": DISTRICT_WEST, "risk_level": "elevated", "aliases": ("metro ville", "metroville site")},
    {"id": "surjani", "name": "Surjani Town", "lat": 25.0100, "lng": 67.0600, "district": DISTRICT_WEST, "risk_level": "critical", "aliases": ("surjani",), "landmarks": ("khuda ki basti", "surjani number 5",)},

    # ─── Keamari District ───────────────────────────────────────────────────
    # Sub-divisions: Baldia, Harbor, Maripur, SITE.
    {"id": "keamari", "name": "Keamari", "lat": 24.8400, "lng": 66.9800, "district": DISTRICT_KEAMARI, "risk_level": "elevated", "aliases": ("kemari", "kiamari"), "landmarks": ("jackson market", "ice factory",)},
    {"id": "harbour", "name": "Keamari Harbour", "lat": 24.8450, "lng": 66.9680, "district": DISTRICT_KEAMARI, "risk_level": "elevated", "aliases": ("harbour", "harbor", "karachi port", "kemari harbour", "west wharf")},
    {"id": "manora", "name": "Manora", "lat": 24.7960, "lng": 66.9770, "district": DISTRICT_KEAMARI, "risk_level": "elevated", "aliases": ("manora island", "manoora", "manohra")},
    {"id": "maripur", "name": "Maripur", "lat": 24.8600, "lng": 66.9500, "district": DISTRICT_KEAMARI, "risk_level": "elevated", "aliases": ("mauripur",)},
    {"id": "hawksbay", "name": "Hawksbay", "lat": 24.8500, "lng": 66.8500, "district": DISTRICT_KEAMARI, "risk_level": "normal", "aliases": ("hawks bay",)},
    {"id": "baldia", "name": "Baldia Town", "lat": 24.9200, "lng": 66.9600, "district": DISTRICT_KEAMARI, "risk_level": "elevated", "aliases": ("baldia", "baldia colony")},
    {"id": "site", "name": "SITE Area", "lat": 24.9100, "lng": 67.0000, "district": DISTRICT_KEAMARI, "risk_level": "elevated", "aliases": ("site town", "s.i.t.e"), "landmarks": ("sher shah", "metroville chowrangi", "site industrial",)},
    {"id": "pak-colony", "name": "Pak Colony", "lat": 24.9000, "lng": 66.9900, "district": DISTRICT_KEAMARI, "risk_level": "elevated", "aliases": ("pak coloney",)},
)

for _area in AREAS:
    # One line instead of 78 hand-written group values, and the only place
    # an area's volunteer can come from.
    _area["group"] = DISTRICT_GROUPS[_area["district"]]

AREA_IDS: Tuple[str, ...] = tuple(area["id"] for area in AREAS)
AREAS_BY_ID: Dict[str, Mapping[str, Any]] = {area["id"]: area for area in AREAS}


def by_group(group: str) -> List[str]:
    """Area ids belonging to one volunteer group."""
    return [area["id"] for area in AREAS if area["group"] == group]


def by_district(district: str) -> List[str]:
    """Area ids inside one district, by its short id (``DISTRICTS`` key).

    Matching is case- and whitespace-insensitive, like ``centroid``, because
    the value may arrive from a query string or a seeded row.
    """
    key = (district or "").strip().lower()
    return [area["id"] for area in AREAS if area["district"] == key]


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
    lines = []
    for area in AREAS:
        line = f"{area['id']} ({area['name']}"
        marks = area.get("landmarks", ())
        if marks:
            # Only a handful per area: the list is already 78 lines and the
            # point is to anchor the common names, not to reproduce a gazetteer
            # inside the prompt.
            line += "; incl. " + ", ".join(marks[:6])
        lines.append(line + ")")
    return "\n".join(lines)


def search_index() -> List[Tuple[str, str]]:
    """``(searchable text, area id)`` pairs for the offline fallback matcher.

    Includes the id, the display name, every alias and every landmark, so the
    offline matcher resolves "muskan" with the model unreachable too.
    """
    index: List[Tuple[str, str]] = []
    for area in AREAS:
        index.append((area["id"].replace("-", " "), area["id"]))
        index.append((area["name"].lower(), area["id"]))
        for alias in area.get("aliases", ()):
            index.append((alias.lower(), area["id"]))
        for landmark in area.get("landmarks", ()):
            index.append((landmark.lower(), area["id"]))
    return index


# ─── Localities ────────────────────────────────────────────────────────────
#
# The 78 areas above are the unit SafeZone dispatches on. They are not what
# people type. Someone whose street is under water writes "Muskan",
# "Hussainabad", "Sindhi Muslim" -- the locality they live in, not the
# administrative area it sits inside.
#
# ``data/localities.json`` closes that gap. It is generated by
# ``scripts/build_localities.py`` from OpenStreetMap and committed, so nothing
# here calls a network service: a geocoding request during a flood is a
# dependency on the thing that is failing, on the path that decides whether
# someone is reachable at all.
#
# Every entry carries its own coordinates, which is the real prize. The area
# assignment is computed from those coordinates against the centroids above,
# so no human and no model guessed it. A caller that wants a point rather than
# an area id should take ``lat``/``lng`` from the match -- they are the real
# location of the locality, not the rough centre of a whole area.
#
# The file is optional. Without it everything above behaves exactly as before,
# which is what keeps a fresh clone working before anyone runs the build step.

_LOCALITY_INDEX: Optional[List[Tuple[str, Dict[str, Any]]]] = None


def _locality_index() -> List[Tuple[str, Dict[str, Any]]]:
    """``(searchable text, row)`` pairs, longest phrase first.

    Loaded once, lazily. Longest first so "north nazimabad" is tried before
    "nazimabad" -- the same rule the area index uses, for the same reason.
    """
    global _LOCALITY_INDEX
    if _LOCALITY_INDEX is not None:
        return _LOCALITY_INDEX

    import json
    from pathlib import Path

    path = Path(__file__).resolve().parent / "localities.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows: Mapping[str, Any] = payload.get("localities", {})
    except (OSError, ValueError):
        # Absent or unreadable is a normal state, not an error: the file is a
        # build artefact and a clone that has not built it still works.
        rows = {}

    _LOCALITY_INDEX = sorted(
        ((key, dict(row)) for key, row in rows.items() if isinstance(row, Mapping)),
        key=lambda pair: -len(pair[0]),
    )
    return _LOCALITY_INDEX


def locality_count() -> int:
    """How many localities are loaded. Zero when the file has not been built."""
    return len(_locality_index())


def find_locality(text: str) -> Optional[Dict[str, Any]]:
    """The locality named anywhere in free text, or ``None``.

    Returns the whole row -- ``name``, ``lat``, ``lng``, ``area`` -- because
    the coordinates are better evidence than the area id. An area centroid is
    the rough middle of a whole neighbourhood; a locality point is where the
    locality actually is.
    """
    flat = "".join(ch if ch.isalnum() else " " for ch in (text or "").lower())
    haystack = " " + " ".join(flat.split()) + " "
    for phrase, row in _locality_index():
        if " " + phrase + " " in haystack:
            return row
    return None
