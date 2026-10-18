"""Official-service handoff: which service a case goes to, and how honestly.

SafeZone cannot command a boat, an ambulance or a fire truck, and it has no
integration with any emergency service or NGO. What it can do is make the
handoff effortless: a ranked, complete case on one read-only page, plus the
official number for that category.

Two AGENTS.md rules shape everything here:

* **2.2 honesty.** Never present a relationship with Edhi, Chhipa, Alkhidmat,
  1122 or anyone else. Listing a public number as a call target is fine;
  calling it an integration is not. So every record this module produces is
  stamped ``simulated: True`` and carries a label that says so, and the UI
  renders that label rather than inventing its own.
* **11. Fire and medical are never volunteer-only.** They always get the
  official handoff, whatever channel the coordinator picked. That is enforced
  by :func:`requires_official`, not left to whoever clicks Approve.

This module is deliberately pure: it decides *what* the handoff is and leaves
minting and persistence to the caller, so the policy can be tested without a
database.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Mapping, Optional

from core import config
from core.phone import mask
from services import protocol
from services.whatsapp import send_message

logger = logging.getLogger("safezone.officials")

SERVICE_LABELS = {
    "fire": "Fire service",
    "medical": "Ambulance",
    "ngo": "Relief organisation",
}

# The honesty stamp. It goes in the responder link's target label, so it shows
# up anywhere the handoff is displayed rather than only in the README.
SIMULATED_SUFFIX = "(simulated handoff — no live integration)"


def service_for(category: str) -> str:
    """The emergency service this category routes to.

    Reuses the protocol graph rather than keeping a second mapping, so adding
    a category in one place cannot silently misroute it here.
    """
    return protocol.node(category).get("emergency_kind", "ngo")


def requires_official(category: str) -> bool:
    """True when the case must go to an official service regardless of channel.

    Fire and medical are never volunteer-only (AGENTS.md 11). The protocol
    graph already marks these with ``official_first``.
    """
    return bool(protocol.node(category).get("official_first"))


def target_label(category: str, custom: Optional[str] = None) -> str:
    """The label stamped on the responder link for this handoff.

    A coordinator-supplied label is kept but still marked simulated: naming a
    real desk must not make the handoff look like an integration with it.
    """
    service = service_for(category)
    base = (custom or "").strip() or SERVICE_LABELS.get(service, "Emergency services")
    if not config.SHOW_SIMULATION_LABELS or SIMULATED_SUFFIX in base:
        return base[:120]
    return f"{base} {SIMULATED_SUFFIX}"[:120]


def handoff(category: str, custom_label: Optional[str] = None) -> Dict[str, Any]:
    """Describe the official handoff for a case of this category.

    The returned ``number`` is whatever a human put in config from an official
    source. It is ``None`` when unset, and that is a correct, loud state --
    AGENTS.md 2.1 #8 forbids filling these in from memory.
    """
    service = service_for(category)
    number = config.get_emergency_number(category)

    if number is None:
        logger.warning(
            "No emergency number configured for %r; handoff for a %s case will "
            "show no call target.",
            service,
            category,
        )

    return {
        "service": service,
        "label": SERVICE_LABELS.get(service, "Emergency services"),
        "number": number,
        "number_is_simulated": bool(number) and config.EMERGENCY_NUMBERS_SIMULATED,
        "target_label": target_label(category, custom_label),
        # Always true in this prototype. If this ever becomes a real
        # integration, it is a conversation with that organisation first.
        "simulated": True,
        "required": requires_official(category),
        "note": (
            "SafeZone does not dispatch emergency services. The coordinator "
            "sends this link and, where a number is configured, calls it."
        ),
    }


def notify(
    record: Mapping[str, Any],
    *,
    case_id: int,
    url: str,
    category: str,
    area: Optional[str] = None,
    reason: Optional[str] = None,
    vuln_summary: Optional[str] = None,
) -> bool:
    """Send the handoff link to the configured official number.

    This is still not a dispatch. It is the coordinator's "send this link"
    step, automated to the one number a human put in config -- which during a
    demo is a team phone, not a real service. Hence the opening and closing
    lines of the message: anyone reading it on a handset must understand what
    it is within the first sentence, not after scrolling.

    Returns whether a message actually went out. Never raises: a failed
    handoff must not fail the approval.
    """
    if not config.OFFICIAL_HANDOFF_AUTOSEND:
        return False

    number = record.get("number")
    if not number:
        logger.warning(
            "Case %s: no official number configured, so no handoff was sent.", case_id
        )
        return False

    heading = f"SafeZone {record['label']} handoff"
    if config.SHOW_SIMULATION_LABELS:
        heading = f"{heading} {SIMULATED_SUFFIX}"

    lines = [
        heading,
        "",
        f"Case {case_id}: {(category or 'emergency').replace('_', ' ').capitalize()}"
        + (f" near {area}." if area else "."),
    ]
    if vuln_summary:
        lines.append(f"Who: {vuln_summary}.")
    if reason:
        lines.append(f"Why this ranks here: {reason}")
    lines.append("")
    lines.append(f"Full case: {url}")
    if config.SHOW_SIMULATION_LABELS:
        lines.append("")
        lines.append(
            "This is a prototype demonstration. SafeZone has no integration "
            "with any emergency service and has not dispatched anyone."
        )

    sent = send_message(number, "\n".join(lines))
    if sent:
        logger.info(
            "Case %s: %s handoff sent to %s", case_id, record["service"], mask(number)
        )
    else:
        logger.warning(
            "Case %s: %s handoff to %s was suppressed",
            case_id,
            record["service"],
            mask(number),
        )
    return sent
