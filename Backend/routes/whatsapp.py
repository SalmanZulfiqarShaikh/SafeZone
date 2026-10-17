"""Public WhatsApp details and QR code endpoints for citizen entry.

Follows AGENTS.md §12: The public WhatsApp number comes strictly from
config.WHATSAPP_PUBLIC_NUMBER.

Endpoints:
- GET /api/whatsapp:
    Returns configuration state, normalized number, display string, wa.me URL,
    and QR code URL. When unconfigured, returns 200 with configured=false and
    all other fields null.
- GET /api/whatsapp/qr.svg:
    Returns pure SVG QR code image (SvgPathImage) with error correction H.
    Cached in module-level variable. Cache-Control: public, max-age=3600.
    Returns 404 when unconfigured.
"""

from __future__ import annotations

import io
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Response
import qrcode
import qrcode.constants
import qrcode.image.svg

from core import config
from core.phone import format_display, try_normalize

logger = logging.getLogger("safezone.routes.whatsapp")

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])

_CACHED_QR_SVG: Optional[bytes] = None
_CACHED_TARGET_URL: Optional[str] = None


def _get_whatsapp_details() -> Optional[Dict[str, str]]:
    raw = getattr(config, "WHATSAPP_PUBLIC_NUMBER", "").strip()
    if not raw:
        return None
    normalized = try_normalize(raw)
    if not normalized:
        return None

    url = f"https://wa.me/{normalized}"
    display = format_display(normalized)
    return {
        "number": normalized,
        "display": display,
        "url": url,
        "qr_url": "/api/whatsapp/qr.svg",
    }


def _generate_qr_svg(target_url: str) -> bytes:
    global _CACHED_QR_SVG, _CACHED_TARGET_URL

    if _CACHED_QR_SVG is not None and _CACHED_TARGET_URL == target_url:
        return _CACHED_QR_SVG

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2,
        image_factory=qrcode.image.svg.SvgPathImage,
    )
    qr.add_data(target_url)
    qr.make(fit=True)
    img = qr.make_image()

    buf = io.BytesIO()
    img.save(buf)
    svg_bytes = buf.getvalue()

    _CACHED_QR_SVG = svg_bytes
    _CACHED_TARGET_URL = target_url
    return svg_bytes


@router.get("")
@router.get("/")
def get_whatsapp_info() -> Dict[str, Any]:
    details = _get_whatsapp_details()
    if not details:
        return {
            "configured": False,
            "number": None,
            "display": None,
            "url": None,
            "qr_url": None,
        }

    return {
        "configured": True,
        "number": details["number"],
        "display": details["display"],
        "url": details["url"],
        "qr_url": details["qr_url"],
    }


@router.get("/qr.svg")
def get_whatsapp_qr() -> Response:
    details = _get_whatsapp_details()
    if not details:
        raise HTTPException(
            status_code=404, detail="WhatsApp public number is not configured"
        )

    svg_bytes = _generate_qr_svg(details["url"])
    return Response(
        content=svg_bytes,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )
