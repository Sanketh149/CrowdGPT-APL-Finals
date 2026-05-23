"""
Gate Control Tools
Google ADK function tools for opening, closing, and querying stadium gates.
In production these would call a physical gate management API.
For the demo, gate state is stored in memory and optionally persisted to GCS.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# In-memory gate state store (keyed by gate_id)
_gate_state: Dict[str, str] = {}

# Default gate configuration
DEFAULT_GATE_CONFIG = {
    **{f"G{i}": "open" for i in range(1, 7)},    # G1-G6 open by default
    **{f"G{i}": "closed" for i in range(7, 13)},  # G7-G12 closed
    **{f"E{i}": "closed" for i in range(1, 5)},   # Emergency gates closed
}


def _get_current_gate_state(gate_id: str) -> str:
    """Return current state for a gate, defaulting to config defaults."""
    if gate_id not in _gate_state:
        _gate_state[gate_id] = DEFAULT_GATE_CONFIG.get(gate_id, "closed")
    return _gate_state[gate_id]


def open_gate_tool(gate_id: str, reason: str = "") -> Dict[str, Any]:
    """
    ADK Tool: Open a stadium gate.

    Args:
        gate_id: Gate identifier (e.g., 'G3', 'E1')
        reason: Reason for opening the gate (for audit log)

    Returns:
        Confirmation with gate status and timestamp.
    """
    previous_state = _get_current_gate_state(gate_id)
    _gate_state[gate_id] = "open"

    result = {
        "gate_id": gate_id,
        "action": "open",
        "previous_state": previous_state,
        "current_state": "open",
        "timestamp": datetime.utcnow().isoformat(),
        "reason": reason or "agent_decision",
        "success": True,
    }

    logger.info(f"Gate {gate_id} opened: {reason}")
    _audit_log(result)
    return result


def close_gate_tool(gate_id: str, reason: str = "") -> Dict[str, Any]:
    """
    ADK Tool: Close a stadium gate.

    Args:
        gate_id: Gate identifier (e.g., 'G3', 'E1')
        reason: Reason for closing (for audit log)

    Returns:
        Confirmation with gate status and timestamp.
    """
    # Safety check: don't close emergency gates if a LOCKDOWN/EVACUATE is active
    if gate_id.startswith("E"):
        logger.warning(f"Attempt to close emergency gate {gate_id} — blocked by safety rule")
        return {
            "gate_id": gate_id,
            "action": "close",
            "current_state": _get_current_gate_state(gate_id),
            "timestamp": datetime.utcnow().isoformat(),
            "success": False,
            "error": "Emergency gates cannot be closed via automated control",
        }

    previous_state = _get_current_gate_state(gate_id)
    _gate_state[gate_id] = "closed"

    result = {
        "gate_id": gate_id,
        "action": "close",
        "previous_state": previous_state,
        "current_state": "closed",
        "timestamp": datetime.utcnow().isoformat(),
        "reason": reason or "agent_decision",
        "success": True,
    }

    logger.info(f"Gate {gate_id} closed: {reason}")
    _audit_log(result)
    return result


def get_gate_status_tool(gate_id: str = "ALL") -> Dict[str, Any]:
    """
    ADK Tool: Get current status of one or all gates.

    Args:
        gate_id: Gate identifier, or 'ALL' to return all gate statuses

    Returns:
        Gate status data including state and last change time.
    """
    timestamp = datetime.utcnow().isoformat()

    if gate_id == "ALL":
        all_gates: List[Dict] = []
        all_gate_ids = (
            [f"G{i}" for i in range(1, 13)] + [f"E{i}" for i in range(1, 5)]
        )
        for gid in all_gate_ids:
            state = _get_current_gate_state(gid)
            all_gates.append(
                {
                    "gate_id": gid,
                    "status": state,
                    "is_emergency": gid.startswith("E"),
                    "timestamp": timestamp,
                }
            )
        open_count = sum(1 for g in all_gates if g["status"] == "open")
        return {
            "gates": all_gates,
            "total": len(all_gates),
            "open_count": open_count,
            "closed_count": len(all_gates) - open_count,
            "timestamp": timestamp,
        }

    state = _get_current_gate_state(gate_id)
    return {
        "gate_id": gate_id,
        "status": state,
        "is_emergency": gate_id.startswith("E"),
        "timestamp": timestamp,
    }


# ── Audit log ───────────────────────────────────────────────────────────────
_audit_trail: List[Dict] = []


def _audit_log(record: Dict) -> None:
    """Append a gate action to the in-memory audit trail."""
    _audit_trail.append(record)
    # Keep last 1000 entries
    if len(_audit_trail) > 1000:
        _audit_trail.pop(0)


def get_gate_audit_trail(limit: int = 50) -> List[Dict]:
    """Return the most recent gate control actions."""
    return _audit_trail[-limit:]
