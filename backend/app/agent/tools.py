"""
tools.py
────────
Stage 3: Bound Investigation Tools.

Contains exactly 2 tools available to the LangGraph investigation agent:
  1. check_device_id_history(device_id) -> returns structured device history
  2. query_registry_velocity(kin_token) -> returns 6-hour registry velocity tier
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.identity import _load_synthetic_dataset
from app.utils.logging import get_logger

log = get_logger(__name__)


def check_device_id_history(device_id: str) -> Dict[str, Any]:
    """
    Check onboarding attempt history associated with a device fingerprint.

    Queries synthetic registry to determine if this device has been used for multiple
    onboarding attempts, associated with different KIN identities, or has prior rejections.

    Returns:
        dict containing:
            - device_id: str
            - total_attempts: int
            - associated_kins: list[str]
            - prior_failures: int
            - velocity_flagged: bool
            - risk_tier: "LOW" | "ELEVATED" | "HIGH_RISK"
    """
    db = _load_synthetic_dataset()
    records = db.get("by_device", {}).get(device_id, [])

    total_attempts = len(records)
    associated_kins = list({r.get("kin_token") for r in records if r.get("kin_token")})
    prior_failures = sum(1 for r in records if r.get("decision") == "fail")

    if total_attempts >= 6 or prior_failures >= 2:
        risk_tier = "HIGH_RISK"
        velocity_flagged = True
    elif total_attempts >= 3 or prior_failures >= 1:
        risk_tier = "ELEVATED"
        velocity_flagged = True
    else:
        risk_tier = "LOW"
        velocity_flagged = False

    result = {
        "device_id": device_id,
        "total_attempts": max(1, total_attempts),
        "associated_kins_count": max(1, len(associated_kins)),
        "associated_kins": associated_kins[:5],
        "prior_failures": prior_failures,
        "velocity_flagged": velocity_flagged,
        "risk_tier": risk_tier,
    }

    log.info("tool.check_device_id_history", device_id=device_id, risk_tier=risk_tier)
    return result


def query_registry_velocity(kin_token: str) -> Dict[str, Any]:
    """
    Query central identity registry for recent onboarding frequency for a KIN.

    Returns:
        dict containing:
            - kin_token: str
            - registry_velocity_6hr: int
            - velocity_tier: "NORMAL" | "MODERATE" | "BURST_ATTACK"
            - velocity_flagged: bool
            - risk_score: float (0.0 to 1.0)
    """
    db = _load_synthetic_dataset()
    rec = db.get("by_kin", {}).get(kin_token, {})

    vel = int(rec.get("registry_velocity_6hr", 1))

    if vel >= 6:
        velocity_tier = "BURST_ATTACK"
        velocity_flagged = True
        risk_score = 0.95
    elif vel >= 3:
        velocity_tier = "MODERATE"
        velocity_flagged = True
        risk_score = 0.50
    else:
        velocity_tier = "NORMAL"
        velocity_flagged = False
        risk_score = 0.05

    result = {
        "kin_token": kin_token,
        "registry_velocity_6hr": vel,
        "velocity_tier": velocity_tier,
        "velocity_flagged": velocity_flagged,
        "risk_score": risk_score,
    }

    log.info("tool.query_registry_velocity", kin_token=kin_token, vel=vel, tier=velocity_tier)
    return result


# List of tools bound to the LangGraph agent
BOUND_TOOLS = [
    check_device_id_history,
    query_registry_velocity,
]
