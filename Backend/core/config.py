"""Application configuration for Dastak.

Handles environment loading, defaults and the checks that catch a demo-killing
misconfiguration before it happens. Values follow AGENTS.md §12; the unsafe
defaults (real WhatsApp sends, unset emergency numbers) are opt-in only.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Dict, List, Optional

from dotenv import load_dotenv

# Load .env from the project root (find_dotenv walks up from this file).
load_dotenv()

logger = logging.getLogger("dastak.config")


def _get_bool(key: str, default: bool) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _get_int(key: str, default: int) -> int:
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return int(val.strip())
    except ValueError:
        return default


# ─── DATABASE / SUPABASE ───────────────────────────────────────
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "").strip()

# ─── CORE FLAGS ────────────────────────────────────────────────
# MOCK_MODE fakes WhatsApp sends and LLM extraction. It does NOT select a
# database: storage is always Supabase (see core/db.py).
MOCK_MODE: bool = _get_bool("MOCK_MODE", True)

# DEMO_MODE restricts volunteer rings to the demo phones and disables real
# responder contact.
DEMO_MODE: bool = _get_bool("DEMO_MODE", True)

# ALLOWLIST_ONLY means only numbers in DEMO_ALLOWLIST receive outbound WhatsApp.
ALLOWLIST_ONLY: bool = _get_bool("ALLOWLIST_ONLY", True)

# KILL_SWITCH: emergency stop for all outbound messaging.
KILL_SWITCH: bool = _get_bool("KILL_SWITCH", False)

# ─── DISPATCH SETTINGS ─────────────────────────────────────────
VOLUNTEER_OFFER_RING_SIZE: int = _get_int("VOLUNTEER_OFFER_RING_SIZE", 3)
VOLUNTEER_ACCEPT_TIMEOUT_S: int = _get_int("VOLUNTEER_ACCEPT_TIMEOUT_S", 300)
VOLUNTEER_ARRIVE_TIMEOUT_S: int = _get_int("VOLUNTEER_ARRIVE_TIMEOUT_S", 900)
GLOBAL_MESSAGE_CAP: int = _get_int("GLOBAL_MESSAGE_CAP", 500)

# Per-number rate limiting, enforced inside send_message().
PER_NUMBER_RATE_LIMIT: int = _get_int("PER_NUMBER_RATE_LIMIT", 10)
PER_NUMBER_RATE_WINDOW_S: int = _get_int("PER_NUMBER_RATE_WINDOW_S", 300)

# ─── PHONE ALLOWLIST & DEMO VOLUNTEERS ─────────────────────────
_raw_allowlist = os.getenv("DEMO_ALLOWLIST", "").strip()
DEMO_ALLOWLIST: List[str] = [
    num.strip() for num in _raw_allowlist.split(",") if num.strip()
]

_raw_demo_volunteers = os.getenv("DEMO_VOLUNTEERS", "").strip()
DEMO_VOLUNTEERS: List[Dict] = []
if _raw_demo_volunteers:
    try:
        DEMO_VOLUNTEERS = json.loads(_raw_demo_volunteers)
    except Exception:
        logger.error("DEMO_VOLUNTEERS is not valid JSON; ignoring it.")

# ─── EMERGENCY NUMBERS ─────────────────────────────────────────
# Never hardcoded from memory: a human must fill these from an official
# source. When missing, guidance degrades rather than crashing the first reply.
EMERGENCY_FIRE: str = os.getenv("EMERGENCY_FIRE", "").strip()
EMERGENCY_AMBULANCE: str = os.getenv("EMERGENCY_AMBULANCE", "").strip()
EMERGENCY_POLICE: str = os.getenv("EMERGENCY_POLICE", "").strip()


def get_emergency_number(category: str) -> Optional[str]:
    """Return the official emergency number for ``category``, or ``None``.

    This is called from the instant guidance reply, which fires before the LLM
    and before location is known. It must never raise: a missing setting is a
    degraded message, not a failed emergency response.

    Category mapping:
        fire, structural      -> fire service
        medical, trapped, flood -> ambulance
        other / unknown       -> police
    """
    cat = (category or "").strip().lower()

    if cat in ("fire", "structural"):
        number, setting = EMERGENCY_FIRE, "EMERGENCY_FIRE"
    elif cat in ("medical", "trapped", "flood"):
        number, setting = EMERGENCY_AMBULANCE, "EMERGENCY_AMBULANCE"
    else:
        number, setting = EMERGENCY_POLICE, "EMERGENCY_POLICE"

    if not number:
        logger.error(
            "%s is not configured; %s guidance will omit the official number.",
            setting,
            cat or "unknown",
        )
        return None

    return number


# ─── WHATSAPP (Meta Cloud API) ─────────────────────────────────
WHATSAPP_TOKEN: str = os.getenv("WHATSAPP_TOKEN", "").strip()
WHATSAPP_PHONE_ID: str = os.getenv("WHATSAPP_PHONE_ID", "").strip()
WHATSAPP_VERIFY_TOKEN: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "").strip()

# ─── LLM ───────────────────────────────────────────────────────
LLM_API_KEY: str = os.getenv("LLM_API_KEY", "").strip()
# Provider is configuration, not code: swapping it when a provider rate-limits
# during the event must not require a deploy.
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "groq").strip().lower()
LLM_MODEL: str = os.getenv("LLM_MODEL", "").strip()


def startup_report() -> List[str]:
    """Return human-readable problems with the current configuration.

    These are the settings that silently break a demo. main.py logs every line
    as a warning at startup; none of them should be discovered live.
    """
    problems: List[str] = []

    if not EMERGENCY_FIRE:
        problems.append("EMERGENCY_FIRE is not set — fire guidance will omit the official number.")
    if not EMERGENCY_AMBULANCE:
        problems.append(
            "EMERGENCY_AMBULANCE is not set — medical, trapped and flood guidance "
            "will omit the official number."
        )
    if not EMERGENCY_POLICE:
        problems.append("EMERGENCY_POLICE is not set — other guidance will omit the official number.")

    if KILL_SWITCH:
        problems.append("KILL_SWITCH is on — every outbound message will be suppressed.")

    if not MOCK_MODE and not WHATSAPP_TOKEN:
        problems.append("MOCK_MODE is off but WHATSAPP_TOKEN is empty — WhatsApp sends will fail.")

    if ALLOWLIST_ONLY and not DEMO_ALLOWLIST:
        problems.append(
            "ALLOWLIST_ONLY is on but DEMO_ALLOWLIST is empty — every outbound "
            "message will be suppressed."
        )

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        problems.append(
            "SUPABASE_URL or SUPABASE_SERVICE_KEY is missing — database access "
            "will raise DbError."
        )

    return problems
