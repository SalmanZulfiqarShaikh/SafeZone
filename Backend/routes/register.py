"""Website registration endpoints.

Registration is the *optional* alerts path, not the front door. Anyone can
message SafeZone with no account at all and get the full help ladder; this
exists so someone can opt into proactive alerts for their area, and so the
24-hour WhatsApp window is open when we need to send one.

No phone number is accepted here. The number is whichever one sends the code
over WhatsApp -- the only one we can prove is reachable, and the only one Meta
lets us message.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from services import registration

logger = logging.getLogger("safezone.register")

router = APIRouter(tags=["registration"])


class RegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    first_name: str = Field(min_length=1, max_length=80)
    zone_id: Optional[str] = Field(default=None, max_length=60)
    wants_alerts: bool = True


@router.post("/api/register")
def register(body: RegistrationRequest) -> Dict[str, Any]:
    """Mint a single-use code and return the WhatsApp link that carries it."""
    try:
        return registration.create(
            body.first_name,
            body.zone_id,
            wants_alerts=body.wants_alerts,
        )
    except registration.RegistrationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/register/{code}")
def registration_status(code: str) -> Dict[str, Any]:
    """Poll whether the code has been sent over WhatsApp yet.

    Returns no phone number: the browser asking has not proved it owns one.
    """
    return registration.status(code)
