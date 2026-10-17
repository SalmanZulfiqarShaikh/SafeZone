"""Phone normalization contract for Dastak.

Strictly follows AGENTS.md §2.3 Rule 4 and §6.
Every phone number goes through normalize_phone() on the way in and on the way to storage.
Format: International format, no '+', no spaces, no leading zero.
Example: 923xxxxxxxxx (12 digits total for Pakistani mobile numbers).
"""

import re


def normalize_phone(raw: str) -> str:
    """Normalize a phone number to standard international format without '+' or spaces.

    Accepts formats such as:
      03xx xxxxxxx        -> 923xxxxxxxxx
      03xxxxxxxxx         -> 923xxxxxxxxx
      92 3xx xxxxxxx      -> 923xxxxxxxxx
      +923xxxxxxxxx       -> 923xxxxxxxxx
      923xxxxxxxxx        -> 923xxxxxxxxx

    Raises:
        ValueError: On anything it cannot confidently normalize.
    """
    if not raw or not isinstance(raw, str):
        raise ValueError("Phone number must be a non-empty string")

    # Strip whitespace, hyphens, parentheses, plus signs
    cleaned = re.sub(r"[\s\-\(\)\+]", "", raw.strip())

    # Only digits should remain
    if not cleaned.isdigit():
        raise ValueError(f"Phone number contains invalid non-numeric characters: '{raw}'")

    # Case 1: Local Pakistani format starting with 03 (e.g. 03001234567, 11 digits)
    if cleaned.startswith("03") and len(cleaned) == 11:
        return "92" + cleaned[1:]

    # Case 2: International format starting with 923 (e.g. 923001234567, 12 digits)
    if cleaned.startswith("923") and len(cleaned) == 12:
        return cleaned

    # Case 3: International format with 00923 (e.g. 00923001234567, 14 digits)
    if cleaned.startswith("00923") and len(cleaned) == 14:
        return cleaned[2:]

    # Case 4: 10-digit number starting with 3 (missing country code and leading 0, e.g. 3001234567)
    if cleaned.startswith("3") and len(cleaned) == 10:
        return "92" + cleaned

    raise ValueError(f"Cannot confidently normalize phone number: '{raw}' (cleaned: '{cleaned}')")
