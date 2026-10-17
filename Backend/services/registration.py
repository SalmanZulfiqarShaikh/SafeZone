"""Website registration and the ``JOIN <code>`` handshake.

Registration is **optional**. Anyone can message SafeZone and get the whole
help ladder with no account (AGENTS.md 9). What registration buys is proactive
alerts for your area -- and the only reason it needs a WhatsApp handshake at
all is Meta's 24-hour rule: we may only message a number that messaged us
first. A web form alone cannot open that window.

So the flow is: form -> short code -> the person sends ``JOIN <code>`` to
SafeZone -> the code binds that phone to the registration, and the window is
open because they just messaged.

Codes are short because they are typed on a phone by someone who may be in a
hurry, and the alphabet excludes characters that look alike (0/O, 1/I/L).
They expire, and they are single use.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Mapping, Optional

from core import config
from core.db import execute, get_db
from core.phone import mask

logger = logging.getLogger("safezone.registration")

# No 0/O, 1/I/L -- misread characters become support messages we cannot answer.
CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
CODE_LENGTH = 6

MAX_NAME_LENGTH = 80


class RegistrationError(ValueError):
    """Raised when a registration request cannot be accepted."""


def create(
    first_name: str,
    zone_id: Optional[str] = None,
    *,
    wants_alerts: bool = True,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Mint a single-use code for a website registration.

    No phone number is taken here. The number is whichever one sends the code,
    which is the only number we can prove is reachable.
    """
    name = (first_name or "").strip()
    if not name:
        raise RegistrationError("A first name is required.")

    moment = now or datetime.now(timezone.utc)
    expires_at = moment + timedelta(minutes=config.REGISTRATION_CODE_TTL_MINUTES)

    code = _unique_code()
    row = {
        "code": code,
        "first_name": name[:MAX_NAME_LENGTH],
        "zone_id": _clean_zone(zone_id),
        "wants_alerts": bool(wants_alerts),
        "created_at": moment.isoformat(),
        "expires_at": expires_at.isoformat(),
        "redeemed_at": None,
        "phone": None,
    }
    _insert("registrations", row)

    logger.info("Issued registration code for zone %r", row["zone_id"])
    return {
        "code": code,
        "expires_at": row["expires_at"],
        "whatsapp_url": whatsapp_url(code),
        "instructions": f"Send JOIN {code} to SafeZone on WhatsApp to finish.",
    }


def redeem(code: str, phone: str, *, now: Optional[datetime] = None) -> Optional[Mapping[str, Any]]:
    """Bind a code to the phone that sent it, or return ``None``.

    ``None`` covers every failure the sender could cause -- unknown, expired
    or already used -- deliberately without distinguishing them in the reply.
    """
    moment = now or datetime.now(timezone.utc)
    cleaned = normalize_code(code)
    if not cleaned:
        return None

    registration = _select_one("registrations", code=cleaned)
    if registration is None:
        logger.info("Registration code not found")
        return None

    if registration.get("redeemed_at"):
        logger.info("Registration code already redeemed")
        return None

    expires_at = _parse_timestamp(registration.get("expires_at"))
    if expires_at is not None and moment > expires_at:
        logger.info("Registration code expired")
        return None

    _update(
        "registrations",
        {"phone": phone, "redeemed_at": moment.isoformat()},
        code=cleaned,
    )

    logger.info("Registration code redeemed by %s", mask(phone))
    return {**registration, "phone": phone, "redeemed_at": moment.isoformat()}


def status(code: str) -> Dict[str, Any]:
    """Whether a code has been redeemed yet, for the website to poll.

    The phone number is never returned: the browser polling this has not
    proved it owns that number.
    """
    registration = _select_one("registrations", code=normalize_code(code))
    if registration is None:
        return {"found": False, "verified": False}
    return {
        "found": True,
        "verified": bool(registration.get("redeemed_at")),
        "first_name": registration.get("first_name"),
        "zone_id": registration.get("zone_id"),
    }


def normalize_code(code: str) -> str:
    """Upper-case and strip the code. Tolerates spaces and dashes."""
    if not isinstance(code, str):
        return ""
    return "".join(ch for ch in code.strip().upper() if ch.isalnum())


def whatsapp_url(code: str) -> Optional[str]:
    """A wa.me deep link that pre-fills ``JOIN <code>``.

    ``None`` when the public number is unset, which is the correct state in a
    public repo -- the number lives only in the deployment environment.
    """
    number = config.WHATSAPP_PUBLIC_NUMBER
    if not number:
        logger.warning("WHATSAPP_PUBLIC_NUMBER is not set; cannot build a join link.")
        return None
    return f"https://wa.me/{number}?text=JOIN%20{code}"


# ─── Internals ─────────────────────────────────────────────────────────────


def _unique_code(attempts: int = 5) -> str:
    """A code not already in the table. Collisions are rare but not impossible."""
    for _ in range(attempts):
        candidate = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        if _select_one("registrations", code=candidate) is None:
            return candidate
    raise RegistrationError("Could not allocate a registration code; try again.")


def _clean_zone(zone_id: Optional[str]) -> Optional[str]:
    if not zone_id:
        return None
    return str(zone_id).strip().lower() or None


def _insert(table: str, row: Mapping[str, Any]) -> Any:
    return execute(get_db().table(table).insert(dict(row)))


def _select(table: str, **filters: Any) -> List[Mapping[str, Any]]:
    query = get_db().table(table).select("*")
    for column, value in filters.items():
        query = query.eq(column, value)
    rows = list(getattr(execute(query), "data", None) or [])
    return [row for row in rows if isinstance(row, Mapping)]


def _select_one(table: str, **filters: Any) -> Optional[Mapping[str, Any]]:
    rows = _select(table, **filters)
    return rows[0] if rows else None


def _update(table: str, values: Mapping[str, Any], **filters: Any) -> Any:
    query = get_db().table(table).update(dict(values))
    for column, value in filters.items():
        query = query.eq(column, value)
    return execute(query)


def _parse_timestamp(value: Any) -> Optional[datetime]:
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
