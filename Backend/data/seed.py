"""Seed the dev database with zones, demo volunteers and sample incidents.

Run from ``Backend/``::

    python -m data.seed

Idempotent by construction: zones upsert on their text id, volunteers are
matched by name, and sample incidents are skipped when their seed report
already exists. Re-running must never duplicate queue entries.

Every phone number here is obviously fake (``923000000001`` style). Real demo
phones belong in ``DEMO_VOLUNTEERS`` in the environment, never in the repo.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Mapping

from core import config
from core.db import execute, get_db
from core.phone import mask, try_normalize
from data import areas
from services import risk

logger = logging.getLogger("safezone.seed")

# Areas and the volunteer split both live in data/areas.py -- one list, read
# by seeding, extraction and dispatch alike.
ZONES = areas.AREAS

# Fallback phones, used only when DEMO_VOLUNTEERS is unset. Obviously fake:
# the real team numbers live in DEMO_VOLUNTEERS in the environment, never in
# this repository, which is public (AGENTS.md 12).
PLACEHOLDER_PHONES = ("923000000001", "923000000002")

GROUP_ORDER = (areas.GROUP_A, areas.GROUP_B)


def volunteer_plan() -> list:
    """One volunteer row per configured phone, covering that phone's areas.

    Reads DEMO_VOLUNTEERS when it is set, so the real numbers reach the
    database without ever entering the repository. Each entry may name its
    group ("a" or "b"); otherwise groups are assigned in order. An entry may
    also list zones explicitly and those win.
    """
    configured = config.DEMO_VOLUNTEERS or []
    plan = []

    for index, group in enumerate(GROUP_ORDER):
        entry = configured[index] if index < len(configured) else {}
        if not isinstance(entry, dict):
            entry = {}

        phone = try_normalize(str(entry.get("phone") or "")) or PLACEHOLDER_PHONES[index]
        group_id = str(entry.get("group") or group).strip().lower()
        zone_ids = entry.get("zones") or areas.by_group(group_id)

        plan.append(
            {
                "name": entry.get("name") or f"Demo volunteer {group_id.upper()}",
                "phone": phone,
                "group": group_id,
                "zone_ids": list(zone_ids),
                "capabilities": list(entry.get("capabilities") or ["foot", "car", "first_aid"]),
                "is_placeholder": phone in PLACEHOLDER_PHONES,
            }
        )

    return plan


# A handful of cases so the queue is not empty on first open. The report's
# raw_text doubles as the idempotency marker.
SAMPLES = (
    {
        "marker": "[seed] Water rising in a ground-floor home in Gulshan",
        "zone_id": "gulshan",
        "category": "flood",
        "urgency": "high",
        "report_count": 3,
        "age_minutes": 20,
        "vulnerability": {"elderly": True, "alone": True, "floor": "ground"},
        "raw_text": "Water is rising in our ground-floor home. My elderly mother is "
        "alone with me. We cannot move her easily.",
    },
    {
        "marker": "[seed] Man collapsed near Korangi Crossing",
        "zone_id": "korangi",
        "category": "medical",
        "urgency": "critical",
        "report_count": 2,
        "age_minutes": 10,
        "vulnerability": {"chronic_illness": True},
        "raw_text": "A man has collapsed near Korangi Crossing. He is unconscious "
        "and not breathing. Someone is doing CPR.",
    },
    {
        "marker": "[seed] Family trapped on a roof in Johar",
        "zone_id": "johar",
        "category": "trapped",
        "urgency": "high",
        "report_count": 1,
        "age_minutes": 35,
        "vulnerability": {"children_present": True},
        "raw_text": "We are trapped on the roof with two children. The water below "
        "is still rising.",
    },
    {
        "marker": "[seed] Cracked wall after rain in DHA",
        "zone_id": "dha",
        "category": "structural",
        "urgency": "medium",
        "report_count": 1,
        "age_minutes": 50,
        "vulnerability": {},
        "raw_text": "A large crack appeared in our building wall after the rain. "
        "We are outside now.",
    },
)


def seed(client=None) -> Dict[str, int]:
    """Insert the demo data. Returns counts of new rows."""
    db = client or get_db()
    counts = {"zones": 0, "volunteers": 0, "incidents": 0, "cases": 0}

    for zone in ZONES:
        _upsert_zone(db, zone)
        counts["zones"] += 1

    for volunteer in volunteer_plan():
        if _upsert_volunteer(db, volunteer):
            counts["volunteers"] += 1

    for sample in SAMPLES:
        created = _seed_sample(db, sample)
        if created:
            counts["incidents"] += 1
            counts["cases"] += 1

    logger.info(
        "Seed complete: %s zones, %s volunteers, %s new incidents, %s new cases",
        counts["zones"],
        counts["volunteers"],
        counts["incidents"],
        counts["cases"],
    )
    return counts


def _upsert_zone(db, zone: Mapping[str, Any]) -> None:
    execute(
        db.table("zones").upsert(
            {
                "id": zone["id"],
                "name": zone["name"],
                "risk_level": zone["risk_level"],
                "lat": zone["lat"],
                "lng": zone["lng"],
                "volunteer_group": zone["group"],
            },
            on_conflict="id",
        )
    )


def _upsert_volunteer(db, volunteer: Mapping[str, Any]) -> bool:
    """Insert or refresh one demo volunteer. Returns whether the row is new.

    The volunteer sits at the centre of their first area, which is only ever
    used to rank rings. Re-seeding never resets status: a volunteer who sent
    ON DUTY stays on duty.
    """
    existing = execute(
        db.table("volunteers").select("id").eq("phone", volunteer["phone"]).limit(1)
    )
    rows = _rows(existing)

    first_area = volunteer["zone_ids"][0] if volunteer["zone_ids"] else None
    centre = areas.centroid(first_area) or (24.8607, 67.0104)

    payload = {
        "name": volunteer["name"],
        "phone": volunteer["phone"],
        "zone_ids": list(volunteer["zone_ids"]),
        "capabilities": list(volunteer["capabilities"]),
        "lat": centre[0],
        "lng": centre[1],
        "is_demo": True,
    }

    if rows:
        execute(db.table("volunteers").update(payload).eq("id", rows[0]["id"]))
        return False

    execute(db.table("volunteers").insert({**payload, "status": "off_duty"}))
    return True


def _seed_sample(db, sample: Mapping[str, Any]) -> bool:
    """Create one sample incident, report and case unless it already exists."""
    existing = execute(
        db.table("reports").select("id").eq("raw_text", sample["marker"]).limit(1)
    )
    if _rows(existing):
        return False

    now = datetime.now(timezone.utc)
    first_report = (now - timedelta(minutes=sample["age_minutes"])).isoformat()

    incident_row = {
        "category": sample["category"],
        "lat": _zone_centroid(sample["zone_id"])["lat"],
        "lng": _zone_centroid(sample["zone_id"])["lng"],
        "zone_id": sample["zone_id"],
        "location_known": True,
        "report_count": sample["report_count"],
        "confidence": risk.confidence(
            {"source_factor": 1.0, "report_count": sample["report_count"]}
        ),
        "urgency": risk.urgency_score(sample["urgency"]),
        "status": "open",
        "dispatch_status": "none",
        "first_report_at": first_report,
        "last_update_at": first_report,
    }
    priority_score, reason = risk.score(
        {
            **incident_row,
            "urgency": sample["urgency"],
            "report_count": sample["report_count"],
            "source_factor": 1.0,
            "first_report_at": first_report,
            "location_known": True,
        },
        sample["vulnerability"],
    )
    incident_row["priority_score"] = priority_score

    incident = _first(execute(db.table("incidents").insert(incident_row)), "incidents")
    incident_id = incident.get("id")

    execute(
        db.table("reports").insert(
            {
                "incident_id": incident_id,
                "raw_text": sample["marker"],
                "source": "whatsapp",
                "source_factor": 1.0,
                "category": sample["category"],
                "lat": incident_row["lat"],
                "lng": incident_row["lng"],
                "zone_id": sample["zone_id"],
                "location_known": True,
                "extraction": {
                    "seed": True,
                    "original_text": sample["raw_text"],
                    "vulnerability": sample["vulnerability"],
                },
            }
        )
    )

    execute(
        db.table("cases").insert(
            {
                "incident_id": incident_id,
                "priority_score": priority_score,
                "reason": reason,
                "vuln_summary": _summarise(sample["vulnerability"]),
                "protocol_path": [f"category:{sample['category']}", "safety_steps"],
                "status": "proposed",
                "dispatch_status": "none",
            }
        )
    )
    return True


def _first(result: Any, table: str) -> Mapping[str, Any]:
    rows = _rows(result)
    if rows:
        return rows[0]
    # Supabase returns the inserted representation. If that ever changes, fail
    # loudly rather than linking a report to an arbitrary row.
    logger.error("Insert into %s returned no row; cannot link the seed report", table)
    return {}


def _rows(result: Any) -> list:
    return list(getattr(result, "data", result) or [])


def _zone_centroid(zone_id: str) -> Mapping[str, Any]:
    for zone in ZONES:
        if zone["id"] == zone_id:
            return zone
    raise KeyError(zone_id)


def _summarise(vulnerability: Mapping[str, Any]) -> str:
    labels = [name for name, value in vulnerability.items() if value]
    return ", ".join(labels)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    counts = seed()
    print(
        "Seeded "
        f"{counts['zones']} zones, {counts['volunteers']} volunteers, "
        f"{counts['incidents']} incidents, {counts['cases']} cases."
    )
    for volunteer in volunteer_plan():
        marker = "  (PLACEHOLDER -- set DEMO_VOLUNTEERS)" if volunteer["is_placeholder"] else ""
        print(
            f"  group {volunteer['group']}: {mask(volunteer['phone'])} "
            f"covers {len(volunteer['zone_ids'])} areas{marker}"
        )


if __name__ == "__main__":
    main()
