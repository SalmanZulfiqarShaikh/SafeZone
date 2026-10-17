"""Admin switches.

The kill switch is read at call time inside ``services.whatsapp``, so flipping
it here stops the next outbound message without a restart. Toggling is itself
an event: the timeline must show why messages stopped.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from core import config
from core.events import KILL_SWITCH_TOGGLED, emit

logger = logging.getLogger("safezone.routes.admin")

router = APIRouter(tags=["admin"])


class KillSwitchRequest(BaseModel):
    enabled: Optional[bool] = None


@router.post("/api/admin/killswitch")
def killswitch(body: KillSwitchRequest) -> Dict[str, Any]:
    """Set the switch explicitly, or toggle it when ``enabled`` is omitted."""
    enabled = (not config.KILL_SWITCH) if body.enabled is None else bool(body.enabled)
    config.KILL_SWITCH = enabled

    emit(KILL_SWITCH_TOGGLED, {"enabled": enabled})
    logger.warning("Kill switch set to %s", enabled)
    return {"kill_switch": enabled}


@router.get("/api/admin/status")
def status() -> Dict[str, Any]:
    """Current switches plus the same problems logged at startup."""
    return {
        "kill_switch": config.KILL_SWITCH,
        "mock_mode": config.MOCK_MODE,
        "demo_mode": config.DEMO_MODE,
        "allowlist_only": config.ALLOWLIST_ONLY,
        "problems": config.startup_report(),
    }
