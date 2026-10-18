"""Telling the coordinator a case is waiting for them.

Approval is the one manual step in the whole loop (AGENTS.md 11), which makes
it the one place the system can stall silently. A case is created, ranked,
and then sits in ``proposed`` until a human acts -- and if nobody knows it is
there, the ranking was for nothing.

So every new case pushes a short message to the coordinators. Three rules:

* **Enough to triage without opening anything.** Category, area, urgency, the
  plain-language reason and the priority, so a coordinator woken at 3am knows
  whether this needs them now or in ten minutes.
* **No personal data.** The person's name and number are released exactly
  once, to the volunteer who accepts (``services/dispatch.accept``). A
  coordinator alert is a queue notification, not a case file.
* **Never fatal.** A failed notification must not cost us the case, so this
  swallows its own errors and returns how many actually went out.
"""

from __future__ import annotations

import logging
from typing import Any, List, Mapping, Optional

from core import config
from core.phone import mask, try_normalize
from services.whatsapp import send_message

logger = logging.getLogger("safezone.coordinator")


def numbers() -> List[str]:
    """Configured coordinator numbers, normalized and de-duplicated."""
    seen: List[str] = []
    for raw in config.COORDINATOR_NUMBERS:
        normalized = try_normalize(raw)
        if normalized and normalized not in seen:
            seen.append(normalized)
        elif not normalized:
            logger.warning("Ignoring unusable coordinator number %r", mask(str(raw)))
    return seen


def notify_new_case(
    *,
    case_id: Any,
    category: str,
    priority_score: Any,
    reason: Optional[str] = None,
    vuln_summary: Optional[str] = None,
    area: Optional[str] = None,
    location_known: bool = False,
    report_count: Any = 1,
) -> int:
    """Tell the coordinators a case is waiting. Returns how many were sent."""
    if not config.COORDINATOR_NOTIFY:
        return 0

    recipients = numbers()
    if not recipients:
        logger.warning(
            "Case %s is waiting for approval but COORDINATOR_NUMBERS is empty, "
            "so nobody was told.",
            case_id,
        )
        return 0

    text = compose(
        case_id=case_id,
        category=category,
        priority_score=priority_score,
        reason=reason,
        vuln_summary=vuln_summary,
        area=area,
        location_known=location_known,
        report_count=report_count,
    )

    sent = 0
    for number in recipients:
        try:
            if send_message(number, text):
                sent += 1
            else:
                logger.info("Coordinator alert to %s was suppressed", mask(number))
        except Exception:  # noqa: BLE001 - a notification must not lose a case
            logger.exception("Could not alert coordinator %s", mask(number))

    logger.info("Case %s: alerted %d of %d coordinators", case_id, sent, len(recipients))
    return sent


def compose(
    *,
    case_id: Any,
    category: str,
    priority_score: Any,
    reason: Optional[str] = None,
    vuln_summary: Optional[str] = None,
    area: Optional[str] = None,
    location_known: bool = False,
    report_count: Any = 1,
) -> str:
    """Build the alert. Carries no name and no phone number."""
    label = (category or "emergency").replace("_", " ").capitalize()
    where = f" near {area}" if area else ""

    lines = [f"SafeZone: case {case_id} needs a handoff decision", "", f"{label}{where}."]

    if vuln_summary:
        lines.append(f"Who: {vuln_summary}.")

    try:
        count = int(report_count or 1)
    except (TypeError, ValueError):
        count = 1
    if count > 1:
        lines.append(f"{count} separate reports.")

    if not location_known:
        # The coordinator's cue to call rather than dispatch blind.
        lines.append("No exact location shared yet — may need a phone call.")

    if reason:
        lines.append(f"Why it ranks here: {reason}")

    try:
        lines.append(f"Priority {float(priority_score):.2f}")
    except (TypeError, ValueError):
        pass

    lines.append("")
    # The distinction that matters at 3am: the neighbours already know, so
    # this is not "nobody has moved yet". What is waiting is the official
    # handoff, which is the expensive, irreversible half.
    lines.append("Nearby volunteers have already been offered this.")
    lines.append(f"Reply APPROVE {case_id} to send it to the official service, or REJECT {case_id}.")
    if config.PUBLIC_BASE_URL:
        lines.append(f"Control room: {config.PUBLIC_BASE_URL}/control")

    return "\n".join(lines)
