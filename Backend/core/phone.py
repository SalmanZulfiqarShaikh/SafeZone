"""Phone normalization contract for Dastak.

Strictly follows AGENTS.md §2.3 Rule 4 and §6.
Every phone number goes through normalize_phone() on the way in and on the way
to storage. Format: international, no '+', no spaces, no leading zero.

Pakistani mobile numbers only. Rejecting foreign numbers is deliberate: it is
one less silent failure on a demo that handles real numbers badly.
"""

import re
from typing import Optional


class PhoneError(ValueError):
    """Raised when a phone number cannot be confidently normalized."""


def normalize_phone(raw: str) -> str:
    """Normalize a phone number to standard international format.

    Accepts formats such as:
      03xx xxxxxxx        -> 923xxxxxxxxx
      03xxxxxxxxx         -> 923xxxxxxxxx
      92 3xx xxxxxxx      -> 923xxxxxxxxx
      +923xxxxxxxxx       -> 923xxxxxxxxx
      923xxxxxxxxx        -> 923xxxxxxxxx
      (0300) 123 4567     -> 923001234567

    Raises:
        PhoneError: On anything it cannot confidently normalize.
    """
    if not raw or not isinstance(raw, str):
        raise PhoneError("Phone number must be a non-empty string")

    # Strip whitespace, hyphens, parentheses and plus signs.
    cleaned = re.sub(r"[\s\-\(\)\+]", "", raw.strip())

    # Only digits should remain.
    if not cleaned.isdigit():
        raise PhoneError(f"Phone number contains invalid non-numeric characters: '{raw}'")

    # Case 1: Local Pakistani format starting with 03 (e.g. 03001234567, 11 digits)
    if cleaned.startswith("03") and len(cleaned) == 11:
        return "92" + cleaned[1:]

    # Case 2: International format starting with 923 (e.g. 923001234567, 12 digits)
    if cleaned.startswith("923") and len(cleaned) == 12:
        return cleaned

    # Case 3: International format with 00923 (e.g. 00923001234567, 14 digits)
    if cleaned.startswith("00923") and len(cleaned) == 14:
        return cleaned[2:]

    # Case 4: 10-digit number starting with 3 (missing country code and leading 0)
    if cleaned.startswith("3") and len(cleaned) == 10:
        return "92" + cleaned

    raise PhoneError(f"Cannot confidently normalize phone number: '{raw}' (cleaned: '{cleaned}')")


def try_normalize(raw: str) -> Optional[str]:
    """Non-raising variant of :func:`normalize_phone`.

    The webhook must not return a 500 for a malformed number; it answers with a
    clarification question instead. Returns ``None`` on any failure.
    """
    try:
        return normalize_phone(raw)
    except PhoneError:
        return None


def mask(phone: str) -> str:
    """Mask every digit except the last four, for logs and terminal output.

    ``923001234567`` becomes ``********4567``. Full numbers must never reach
    logs or terminal scrollback.
    """
    digits = "".join(ch for ch in phone if ch.isdigit()) if isinstance(phone, str) else ""
    if not digits:
        return "****"
    visible = digits[-4:]
    return "*" * (len(digits) - len(visible)) + visible
