"""Application configuration for SafeZone.

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

logger = logging.getLogger("safezone.config")


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
# Bare greetings ("hi", "salam", "test") never open a case. This flag only
# decides whether the one orientation line is sent back; the filter itself is
# deterministic and always on -- see ``services/intake.is_greeting``.
GREETING_REPLY: bool = _get_bool("GREETING_REPLY", True)

# How much SafeZone logs. INFO shows each case being created and which LLM
# provider answered; DEBUG adds the rest. Never log a full phone number --
# every log line goes through core.phone.mask.
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").strip().upper()

# ─── AREA ALERTS ───────────────────────────────────────────────────────────
# Proactive warnings to registered people. Gated hard on purpose: a system
# that messages about every report trains people to ignore it, and alert
# fatigue during a disaster is a safety failure, not a UX one.
ZONE_ALERTS_ENABLED: bool = _get_bool("ZONE_ALERTS_ENABLED", True)
# 0.75 is "high" on the risk scale; see services/risk.URGENCY_SCORES.
ZONE_ALERT_MIN_URGENCY: float = float(os.getenv("ZONE_ALERT_MIN_URGENCY", "0.75"))
# Corroboration is its own kind of severity.
ZONE_ALERT_MIN_REPORTS: int = _get_int("ZONE_ALERT_MIN_REPORTS", 3)
# One incident must not be able to exhaust GLOBAL_MESSAGE_CAP.
ZONE_ALERT_MAX_RECIPIENTS: int = _get_int("ZONE_ALERT_MAX_RECIPIENTS", 50)

# Website registration: how long a JOIN code stays valid. Short enough that
# a leaked code is useless, long enough to switch apps and type it.
REGISTRATION_CODE_TTL_MINUTES: int = _get_int("REGISTRATION_CODE_TTL_MINUTES", 30)

# SafeZone's own public WhatsApp number, used to build wa.me join links.
# The repo is public: this stays empty here and is set per deployment.
WHATSAPP_PUBLIC_NUMBER: str = os.getenv("WHATSAPP_PUBLIC_NUMBER", "").strip().lstrip("+")

VOLUNTEER_OFFER_RING_SIZE: int = _get_int("VOLUNTEER_OFFER_RING_SIZE", 3)
VOLUNTEER_ACCEPT_TIMEOUT_S: int = _get_int("VOLUNTEER_ACCEPT_TIMEOUT_S", 300)
VOLUNTEER_ARRIVE_TIMEOUT_S: int = _get_int("VOLUNTEER_ARRIVE_TIMEOUT_S", 900)
# How long to wait for "1 yes / 2 no" after a case is marked done. Silence is
# treated as a failure to confirm, and reopens the case.
PERSON_SILENCE_TIMEOUT_S: int = _get_int("PERSON_SILENCE_TIMEOUT_S", 900)
GLOBAL_MESSAGE_CAP: int = _get_int("GLOBAL_MESSAGE_CAP", 500)
# Absolute base for responder links handed to official desks. Relative links
# work locally; set this to the deployed origin before the demo.
PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
RESPONDER_LINK_TTL_HOURS: int = _get_int("RESPONDER_LINK_TTL_HOURS", 24)

# ─── Control-room login ────────────────────────────────────────────────────
# The coordinator surfaces show reporter names, numbers and exact locations,
# so they are not public. These three are empty here on purpose: the
# repository is public (AGENTS.md 12), and a password or a signing secret in
# a committed file is the same mistake as a real phone number.
#
# ADMIN_PASSWORD_HASH is a PBKDF2 hash, never the password itself. Generate
# it with:  python -m scripts.hash_password
#
# With any of the three empty the server refuses every login rather than
# falling open, and says so plainly at startup.
ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "").strip()
ADMIN_PASSWORD_HASH: str = os.getenv("ADMIN_PASSWORD_HASH", "").strip()
SESSION_SECRET: str = os.getenv("SESSION_SECRET", "").strip()
SESSION_TTL_HOURS: int = _get_int("SESSION_TTL_HOURS", 12)

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
# Food, water and anything we could not classify go to a relief
# organisation, not to the police. Someone who cannot classify their own
# emergency is usually not reporting a crime, and sending them to a police
# line wastes the one message they had the composure to send.
EMERGENCY_NGO: str = os.getenv("EMERGENCY_NGO", "").strip()

# Whether outbound messages carry an in-message "this is a demo" caveat.
#
# Off by default. In a controlled demo every recipient is on DEMO_ALLOWLIST
# and already knows what they are looking at, so the caveat is only clutter.
#
# Turn it ON for the one combination that can mislead someone: ALLOWLIST_ONLY
# switched off, so strangers can reach the system, while the emergency numbers
# still point at a team phone. startup_report() warns when that happens.
SHOW_SIMULATION_LABELS: bool = _get_bool("SHOW_SIMULATION_LABELS", False)

# Alias kept so an existing .env setting still works.
EMERGENCY_NUMBERS_SIMULATED: bool = _get_bool(
    "EMERGENCY_NUMBERS_SIMULATED", SHOW_SIMULATION_LABELS
)

# On approval, message the responder link to the configured official number.
# This is the coordinator's "send this link" step, automated.
OFFICIAL_HANDOFF_AUTOSEND: bool = _get_bool("OFFICIAL_HANDOFF_AUTOSEND", True)

# ─── COORDINATORS ──────────────────────────────────────────────────────────
# Approval is the one manual step in the loop, so it is the one place the
# system can stall silently. Every new case pushes an alert to these
# numbers. They must also be in DEMO_ALLOWLIST to actually receive it.
_raw_coordinators = os.getenv("COORDINATOR_NUMBERS", "").strip()
COORDINATOR_NUMBERS: List[str] = [
    number.strip() for number in _raw_coordinators.split(",") if number.strip()
]
COORDINATOR_NOTIFY: bool = _get_bool("COORDINATOR_NOTIFY", True)

# Channel used when a coordinator approves by text ("APPROVE 14").
#
# "responder" -- the official handoff -- because nearby volunteers were
# already offered the case the moment it arrived (services/intake). Approval
# is now about the expensive, irreversible half: putting an ambulance, a fire
# crew or the police on the road. Set "both" to also re-offer volunteers,
# which is useful when the first ring all declined.
COORDINATOR_DEFAULT_CHANNEL: str = os.getenv(
    "COORDINATOR_DEFAULT_CHANNEL", "responder"
).strip().lower()

SIMULATED_NUMBER_NOTE = "(demo number, not the real emergency service)"


def emergency_number_note() -> str:
    """The caveat to append to a demo number, or an empty string."""
    return f" {SIMULATED_NUMBER_NOTE}" if EMERGENCY_NUMBERS_SIMULATED else ""


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
        number, setting = EMERGENCY_NGO, "EMERGENCY_NGO"

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
# App secret used to verify X-Hub-Signature-256 on inbound webhooks. When
# empty, verification is skipped (fine for local dev, never for prod).
WHATSAPP_APP_SECRET: str = os.getenv("WHATSAPP_APP_SECRET", "").strip()

# ─── LLM ───────────────────────────────────────────────────────
# Provider is configuration, not code: swapping it when a provider rate-limits
# during the event must not require a deploy.
#
# Two ways to configure this, and they compose:
#   * LLM_PROVIDERS -- ordered fallback chain, tried left to right
#   * LLM_PROVIDER  -- single provider, kept so existing .env files work
#
# A provider with no key is skipped rather than treated as a failure, so a
# half-filled .env degrades to whatever is actually set.
LLM_API_KEY: str = os.getenv("LLM_API_KEY", "").strip()
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "deepseek").strip().lower()
LLM_MODEL: str = os.getenv("LLM_MODEL", "").strip()

DEFAULT_LLM_PROVIDERS = ("deepseek", "groq", "gemini")

_raw_providers = os.getenv("LLM_PROVIDERS", "").strip()
LLM_PROVIDERS: List[str] = [
    name.strip().lower() for name in _raw_providers.split(",") if name.strip()
] or list(DEFAULT_LLM_PROVIDERS)

# Per-provider credentials. Model defaults live in services/llm.py.
DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "").strip()

GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "").strip()

GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "").strip()

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "").strip()

OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "").strip()


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
    if not EMERGENCY_NGO:
        problems.append(
            "EMERGENCY_NGO is not set — food, water and unclassified guidance "
            "will omit the relief contact."
        )

    if not ALLOWLIST_ONLY and not SHOW_SIMULATION_LABELS and (
        EMERGENCY_FIRE or EMERGENCY_AMBULANCE or EMERGENCY_NGO
    ):
        problems.append(
            "ALLOWLIST_ONLY is off and SHOW_SIMULATION_LABELS is off — anyone "
            "who messages this number will be told to call the configured "
            "emergency numbers with no caveat. Make sure those are the real "
            "official numbers."
        )

    if KILL_SWITCH:
        problems.append("KILL_SWITCH is on — every outbound message will be suppressed.")

    if not MOCK_MODE and not WHATSAPP_TOKEN:
        problems.append("MOCK_MODE is off but WHATSAPP_TOKEN is empty — WhatsApp sends will fail.")

    if not MOCK_MODE and not WHATSAPP_APP_SECRET:
        problems.append(
            "MOCK_MODE is off but WHATSAPP_APP_SECRET is empty — webhook signatures "
            "will not be verified."
        )

    if COORDINATOR_NOTIFY and not COORDINATOR_NUMBERS:
        problems.append(
            "COORDINATOR_NUMBERS is empty — nobody will be told when a case "
            "needs approval, so cases will sit in the queue unseen."
        )

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
