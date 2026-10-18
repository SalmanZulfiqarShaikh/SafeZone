"""The public WhatsApp number, served to the website.

One source of truth. The number already lives in ``WHATSAPP_PUBLIC_NUMBER``
in the backend environment, which is where the replies are sent from, so the
site reads it from here rather than keeping a second copy baked into the
frontend bundle at build time.

That removes a whole class of failure: no second env file to forget, no
rebuild when the number changes, and no way for the button and the QR to
disagree with the number people actually message.

Public on purpose -- this is the number on the poster.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter

from core import config

logger = logging.getLogger("safezone.routes.whatsapp")

router = APIRouter(tags=["whatsapp"])


def _pretty(number: str) -> str:
    """+92 349 2468494 — grouped the way people in Karachi read a number."""
    if len(number) == 12 and number.startswith("92"):
        return f"+{number[:2]} {number[2:5]} {number[5:]}"
    return f"+{number}"


@router.get("/api/whatsapp")
def whatsapp() -> Dict[str, Any]:
    """Where to message SafeZone.

    Always 200, never an error. The page has to render either way, and a
    number nobody has configured yet is a known state rather than a server
    fault -- the site shows its placeholder and says so.
    """
    number = "".join(ch for ch in config.WHATSAPP_PUBLIC_NUMBER if ch.isdigit())

    if not number:
        logger.warning(
            "WHATSAPP_PUBLIC_NUMBER is not set, so the public page cannot show a "
            "number or a working QR code."
        )
        return {"configured": False, "number": None, "display": None, "url": None}

    return {
        "configured": True,
        "number": number,
        "display": _pretty(number),
        "url": f"https://wa.me/{number}",
    }
