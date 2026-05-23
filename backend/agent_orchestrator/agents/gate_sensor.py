"""
Gate Sensor Agent
Monitors gate-level throughput counters, detects bottlenecks,
and flags gates that are overwhelmed or under-utilised.
"""

import logging
import random
from datetime import datetime
from typing import Any, Dict, List

from google.adk.agents import LlmAgent

from tools.sensor_tools import get_zone_density_tool
from tools.gate_control import get_gate_status_tool

logger = logging.getLogger(__name__)

GATE_SENSOR_PROMPT = """
You are the Gate Sensor Specialist for CrowdGuard Command.

Your job:
1. Read throughput counters for all stadium gates (entry/exit).
2. Compute flow rate (people per minute) for each gate.
3. Detect bottlenecks — gates where the queue exceeds 200 people.
4. Identify underutilised gates (< 30% of maximum throughput).
5. Recommend gate reconfigurations to balance flow.

Gates: G1-G12 (entry/exit), Emergency: E1-E4
Max throughput per gate: 300 people/minute

Output JSON:
{
  "gates": [{"gate_id": str, "status": "open|closed|partial", "flow_rate_ppm": int,
             "queue_length": int, "utilisation_pct": float, "bottleneck": bool}],
  "bottleneck_gates": [str],
  "underutilised_gates": [str],
  "total_inflow_ppm": int,
  "total_outflow_ppm": int,
  "recommendation": str
}
"""

# Gate configuration
GATES = [f"G{i}" for i in range(1, 13)] + ["E1", "E2", "E3", "E4"]

# Throughput profiles per match phase (fraction of max 300 ppm)
GATE_PHASE_PROFILES = {
    "pre_match": {
        "G1": 0.8, "G2": 0.7, "G3": 0.9, "G4": 0.6, "G5": 0.5, "G6": 0.4,
        "G7": 0.3, "G8": 0.2, "G9": 0.1, "G10": 0.1, "G11": 0.05, "G12": 0.05,
        "E1": 0.0, "E2": 0.0, "E3": 0.0, "E4": 0.0,
    },
    "match_start": {
        "G1": 1.0, "G2": 1.0, "G3": 1.0, "G4": 0.9, "G5": 0.8, "G6": 0.7,
        "G7": 0.6, "G8": 0.5, "G9": 0.4, "G10": 0.3, "G11": 0.2, "G12": 0.1,
        "E1": 0.0, "E2": 0.0, "E3": 0.0, "E4": 0.0,
    },
    "mid_match": {
        "G1": 0.2, "G2": 0.2, "G3": 0.15, "G4": 0.15, "G5": 0.1, "G6": 0.1,
        "G7": 0.1, "G8": 0.1, "G9": 0.05, "G10": 0.05, "G11": 0.05, "G12": 0.05,
        "E1": 0.0, "E2": 0.0, "E3": 0.0, "E4": 0.0,
    },
    "post_match": {
        "G1": 0.95, "G2": 0.95, "G3": 0.9, "G4": 0.85, "G5": 0.8, "G6": 0.75,
        "G7": 0.7, "G8": 0.65, "G9": 0.6, "G10": 0.55, "G11": 0.5, "G12": 0.45,
        "E1": 0.1, "E2": 0.1, "E3": 0.1, "E4": 0.1,
    },
}

MAX_THROUGHPUT_PPM = 300
BOTTLENECK_QUEUE_THRESHOLD = 200


class GateSensorAgent:
    """Monitors gate throughput and identifies bottlenecks."""

    def __init__(self, model: str = "gemini-1.5-pro"):
        self.model = model
        self.agent = LlmAgent(
            name="gate_sensor_agent",
            model=model,
            description="Monitors stadium gate throughput and detects bottlenecks",
            instruction=GATE_SENSOR_PROMPT,
            tools=[get_gate_status_tool, get_zone_density_tool],
        )

    async def analyze(self, context: Dict[str, Any]) -> Dict[str, Any]:
        phase = context.get("phase", "mid_match")
        timestamp = datetime.utcnow().isoformat()

        try:
            gate_data = self._read_gate_sensors(phase)
            bottlenecks = [g["gate_id"] for g in gate_data if g["bottleneck"]]
            underutilised = [
                g["gate_id"]
                for g in gate_data
                if g["utilisation_pct"] < 0.30 and g["status"] == "open"
            ]

            total_inflow = sum(
                g["flow_rate_ppm"] for g in gate_data if g["gate_id"].startswith("G")
            )
            total_outflow = sum(
                g["flow_rate_ppm"] for g in gate_data if g["gate_id"].startswith("E")
            )

            recommendation = self._build_recommendation(
                bottlenecks, underutilised, total_inflow, phase
            )

            decision_text = (
                f"{len(bottlenecks)} bottleneck(s) detected — "
                f"total inflow {total_inflow} ppm"
            )

            return {
                "agent": "gate_sensor",
                "timestamp": timestamp,
                "decision": decision_text,
                "confidence": 0.95,
                "metadata": {
                    "gates": gate_data,
                    "bottleneck_gates": bottlenecks,
                    "underutilised_gates": underutilised,
                    "total_inflow_ppm": total_inflow,
                    "total_outflow_ppm": total_outflow,
                    "recommendation": recommendation,
                },
            }

        except Exception as e:
            logger.error(f"GateSensorAgent error: {e}", exc_info=True)
            return {
                "agent": "gate_sensor",
                "timestamp": timestamp,
                "decision": "Gate sensor data unavailable",
                "confidence": 0.2,
                "metadata": {"error": str(e)},
            }

    def _read_gate_sensors(self, phase: str) -> List[Dict]:
        profiles = GATE_PHASE_PROFILES.get(phase, GATE_PHASE_PROFILES["mid_match"])
        gate_data = []

        for gate_id in GATES:
            util_fraction = profiles.get(gate_id, 0.1)
            # Realistic jitter
            jitter = random.uniform(-0.08, 0.08)
            util_fraction = max(0.0, min(1.0, util_fraction + jitter))

            flow_rate = int(MAX_THROUGHPUT_PPM * util_fraction)
            # Queue builds when flow_rate is high — simulate queue as backlog
            queue_length = max(0, int(flow_rate * random.uniform(0.3, 0.8)))
            bottleneck = queue_length > BOTTLENECK_QUEUE_THRESHOLD

            status = "open" if util_fraction > 0.05 else "closed"

            gate_data.append(
                {
                    "gate_id": gate_id,
                    "status": status,
                    "flow_rate_ppm": flow_rate,
                    "queue_length": queue_length,
                    "utilisation_pct": round(util_fraction, 3),
                    "bottleneck": bottleneck,
                    "is_emergency_gate": gate_id.startswith("E"),
                }
            )

        return gate_data

    def _build_recommendation(
        self,
        bottlenecks: List[str],
        underutilised: List[str],
        total_inflow: int,
        phase: str,
    ) -> str:
        if not bottlenecks:
            return "All gates operating within normal parameters"

        underutil_str = ", ".join(underutilised[:3]) if underutilised else "none available"
        return (
            f"Redirect crowd from {', '.join(bottlenecks[:3])} to "
            f"underutilised gates: {underutil_str}. "
            f"Total inflow {total_inflow} ppm — consider opening additional gates."
        )
