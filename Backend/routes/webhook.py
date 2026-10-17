"""WhatsApp webhook: Meta verification and inbound messages.

Two rules govern this file:

* **Always answer HTTP 200.** Meta retries any other status, and the retry is a
  duplicate report. Processing errors are logged, not surfaced.
* **Ignore what we cannot address.** An unsigned or malformed payload is
  acknowledged and dropped rather than retried forever.
"""

from __future__ import annotations

import hmac
import json
import logging
from dataclasses import dataclass
from typing import Any, Iterator, Mapping, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from core import config
from services import intake, whatsapp

logger = logging.getLogger("safezone.webhook")

router = APIRouter(tags=["webhook"])


@dataclass(frozen=True)
class InboundMessage:
    """One inbound WhatsApp message, flattened to what intake actually needs.

    A shared pin is the only exact location SafeZone ever gets -- a typed
    neighbourhood name is a zone guess, not coordinates -- and a case with no
    coordinates cannot be dispatched at all (``services/dispatch.py``). So the
    location type gets a first-class field rather than being stringified into
    ``text`` and re-parsed downstream.
    """

    sender: str
    text: str = ""
    lat: Optional[float] = None
    lng: Optional[float] = None
    location_name: Optional[str] = None


class WhatsAppText(BaseModel):
    model_config = ConfigDict(extra="ignore")

    body: str = ""


class WhatsAppLocation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    latitude: Optional[float] = None
    longitude: Optional[float] = None
    name: Optional[str] = None
    address: Optional[str] = None


class WhatsAppMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    sender: str = Field(alias="from")
    type: str
    text: Optional[WhatsAppText] = None
    location: Optional[WhatsAppLocation] = None


class WhatsAppValue(BaseModel):
    model_config = ConfigDict(extra="ignore")

    messages: list[Any] = Field(default_factory=list)


class WhatsAppChange(BaseModel):
    model_config = ConfigDict(extra="ignore")

    value: WhatsAppValue = Field(default_factory=WhatsAppValue)


class WhatsAppEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    changes: list[WhatsAppChange] = Field(default_factory=list)


class WhatsAppPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    entry: list[WhatsAppEntry] = Field(default_factory=list)


@router.get("/webhook/whatsapp")
def verify(request: Request):
    """Meta's subscription handshake: echo ``hub.challenge`` when the token matches."""
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token") or ""
    challenge = params.get("hub.challenge") or ""
    expected = config.WHATSAPP_VERIFY_TOKEN

    if mode == "subscribe" and expected and hmac.compare_digest(token, expected):
        return PlainTextResponse(challenge)

    logger.warning("Rejected webhook verification (mode=%r)", mode)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook/whatsapp")
async def receive(request: Request):
    """Accept an inbound event. This endpoint returns 200 on every path."""
    try:
        raw = await request.body()

        if not whatsapp.verify_signature(raw, request.headers.get("x-hub-signature-256")):
            logger.warning("Rejected webhook: invalid X-Hub-Signature-256")
            return {"status": "ignored"}

        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            logger.warning("Rejected webhook: body is not valid JSON")
            return {"status": "ignored"}

        if not isinstance(payload, Mapping):
            logger.warning("Rejected webhook: payload is not an object")
            return {"status": "ignored"}

        for message in parse_messages(payload):
            intake.handle_inbound(
                message.sender,
                message.text,
                lat=message.lat,
                lng=message.lng,
                location_name=message.location_name,
            )

    except Exception:  # noqa: BLE001 - retries cause duplicate reports
        logger.exception("Webhook processing failed; acknowledged anyway")

    return {"status": "received"}


def parse_messages(payload: Mapping[str, Any]) -> Iterator[InboundMessage]:
    """Yield one :class:`InboundMessage` per text or location message.

    Status callbacks (delivered, read) simply have no ``messages`` array.
    Other types are logged and ignored until their handlers land.
    """
    try:
        envelope = WhatsAppPayload.model_validate(payload)
    except ValidationError as exc:
        logger.warning("Ignoring malformed WhatsApp payload: %s", exc.errors()[:2])
        return

    for entry in envelope.entry:
        for change in entry.changes:
            for raw_message in change.value.messages:
                try:
                    message = WhatsAppMessage.model_validate(raw_message)
                except ValidationError:
                    logger.warning("Ignoring a malformed WhatsApp message")
                    continue

                parsed = _flatten(message)
                if parsed is None:
                    logger.info("Ignoring unsupported WhatsApp message type %r", message.type)
                    continue

                yield parsed


def _flatten(message: WhatsAppMessage) -> Optional[InboundMessage]:
    """Reduce a Meta message object to the fields intake uses, or ``None``."""
    if message.type == "text" and message.text is not None:
        return InboundMessage(sender=message.sender, text=message.text.body)

    if message.type == "location" and message.location is not None:
        lat, lng = message.location.latitude, message.location.longitude
        if not _plausible_coordinates(lat, lng):
            logger.warning("Ignoring a location message with unusable coordinates")
            return None
        # The label is carried as text so the existing keyword path can still
        # read a landmark out of it; the pin itself travels in lat/lng.
        label = (message.location.name or message.location.address or "").strip()
        return InboundMessage(
            sender=message.sender,
            text=label,
            lat=lat,
            lng=lng,
            location_name=label or None,
        )

    return None


def _plausible_coordinates(lat: Optional[float], lng: Optional[float]) -> bool:
    """Reject nulls and out-of-range values before they reach the database."""
    if lat is None or lng is None:
        return False
    return -90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0
