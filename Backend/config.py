"""Application configuration for Dastak.

Strictly follows AGENTS.md §2.1, §2.3, and §3.
Handles environment variable loading, validation, and emergency number checks.
"""

import json
import os
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Load .env file from project root
load_dotenv()


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
# MOCK_MODE: Zero network mode. Fakes WhatsApp, fakes LLM, uses in-memory or seeded data.
MOCK_MODE: bool = _get_bool("MOCK_MODE", True)

# DEMO_MODE: Disables real responder contact, limits volunteer ring to demo phones.
DEMO_MODE: bool = _get_bool("DEMO_MODE", True)

# ALLOWLIST_ONLY: Only phone numbers in DEMO_ALLOWLIST receive outbound WhatsApp.
ALLOWLIST_ONLY: bool = _get_bool("ALLOWLIST_ONLY", True)

# KILL_SWITCH: Emergency stop for all outbound messaging. Non-negotiable §2.1 Rule 7.
KILL_SWITCH: bool = _get_bool("KILL_SWITCH", False)

# ─── DISPATCH SETTINGS ─────────────────────────────────────────
VOLUNTEER_OFFER_RING_SIZE: int = _get_int("VOLUNTEER_OFFER_RING_SIZE", 3)
VOLUNTEER_ACCEPT_TIMEOUT_S: int = _get_int("VOLUNTEER_ACCEPT_TIMEOUT_S", 300)
VOLUNTEER_ARRIVE_TIMEOUT_S: int = _get_int("VOLUNTEER_ARRIVE_TIMEOUT_S", 900)
GLOBAL_MESSAGE_CAP: int = _get_int("GLOBAL_MESSAGE_CAP", 500)

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
        DEMO_VOLUNTEERS = []

# ─── EMERGENCY NUMBERS ─────────────────────────────────────────
# Non-negotiable §2.1 Rule 8: NEVER hardcoded from memory.
# Must be filled from official sources by a human. Left empty and loudly broken otherwise.
EMERGENCY_FIRE: str = os.getenv("EMERGENCY_FIRE", "").strip()
EMERGENCY_AMBULANCE: str = os.getenv("EMERGENCY_AMBULANCE", "").strip()
EMERGENCY_POLICE: str = os.getenv("EMERGENCY_POLICE", "").strip()


def get_emergency_number(category: str) -> Optional[str]:
    """Return the official emergency number for the specified category.
    
    Raises RuntimeError if the requested emergency number is not configured,
    strictly enforcing AGENTS.md §2.1 Rule 8.
    """
    cat = (category or "").lower().strip()
    if cat == "fire":
        if not EMERGENCY_FIRE:
            raise RuntimeError("EMERGENCY_FIRE is not configured in .env! Sourcing from memory is forbidden.")
        return EMERGENCY_FIRE
    if cat in ("medical", "ambulance"):
        if not EMERGENCY_AMBULANCE:
            raise RuntimeError("EMERGENCY_AMBULANCE is not configured in .env! Sourcing from memory is forbidden.")
        return EMERGENCY_AMBULANCE
    if cat == "police":
        if not EMERGENCY_POLICE:
            raise RuntimeError("EMERGENCY_POLICE is not configured in .env! Sourcing from memory is forbidden.")
        return EMERGENCY_POLICE
    
    # Generic emergency fallback if ambulance exists
    return EMERGENCY_AMBULANCE or None


# ─── WHATSAPP (Meta Cloud API) ─────────────────────────────────
WHATSAPP_TOKEN: str = os.getenv("WHATSAPP_TOKEN", "").strip()
WHATSAPP_PHONE_ID: str = os.getenv("WHATSAPP_PHONE_ID", "").strip()
WHATSAPP_VERIFY_TOKEN: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "").strip()

# ─── LLM ───────────────────────────────────────────────────────
LLM_API_KEY: str = os.getenv("LLM_API_KEY", "").strip()
