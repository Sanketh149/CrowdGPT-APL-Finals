"""
Routing Agent (SequentialAgent Step 1)
Takes crowd density + gate sensor data and recommends gate open/close actions
to optimally redistribute crowd flow across the stadium.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

from google.adk.agents import LlmAgent

from tools.gate_control import open_gate_tool, close_gate_tool, get_gate_status_tool

logger = logging.getLogger(__name__)

ROUTING_PROMPT = """
You are the Routing Specialist for CrowdGuard Command.

Given crowd density data and gate sensor readings, your job is to:
1. Identify which gates should be opened to relieve pressure from high-density zones.
2. Identify which underutilised gates can absorb redirected crowd flow.
3. Generate a gate reconfiguration plan: list of (gate_id, action) tuples.
4. Estimate the impact of each change on crowd density.
5. Prioritise safety over spectator convenience.

Rules:
- Never close a gate if it is the only active gate for a zone.
- Always maintain at least 4 entry gates open during match phases.
- Emergency gates E1-E4 should only open when risk > 70.
- Prefer opening alternate gates over closing active ones.

Output JSON:
{
  "gate_actions": [{"gate_id": str, "action": "open|close", "reason": str, "priority": "high|medium|low"}],
  "estimated_density_reduction": {"zone_id": float},
  "estimated_completion_minutes": int,
  "confidence": float,
  "routing_rationale": str
}
"""


class RoutingAgent:
    """Generates gate reconfiguration plans based on density and sensor data."""

    def __init__(self, model: str = "gemini-1.5-pro"):
        self.model = model
        self.agent = LlmAgent(
            name="routing_agent",
            model=model,
            description="Recommends gate open/close actions based on crowd flow data",
            instruction=ROUTING_PROMPT,
            tools=[open_gate_tool, close_gate_tool, get_gate_status_tool],
        )

    async def decide(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute gate reconfiguration based on monitoring results in state.
        """
        timestamp = datetime.utcnow().isoformat()

        monitoring = state.get("monitoring", [])
        density_report = next(
            (m for m in monitoring if m.get("agent") == "crowd_density"), {}
        )
        gate_report = next(
            (m for m in monitoring if m.get("agent") == "gate_sensor"), {}
        )

        density_meta = density_report.get("metadata", {})
        gate_meta = gate_report.get("metadata", {})

        hotspots = density_meta.get("hotspots", [])
        bottleneck_gates = gate_meta.get("bottleneck_gates", [])
        underutilised_gates = gate_meta.get("underutilised_gates", [])
        peak_density = density_meta.get("peak_density", 0.5)

        gate_actions = self._generate_gate_actions(
            hotspots=hotspots,
            bottleneck_gates=bottleneck_gates,
            underutilised_gates=underutilised_gates,
            peak_density=peak_density,
            phase=state.get("phase", "mid_match"),
        )

        density_reduction = self._estimate_density_reduction(gate_actions, density_meta)

        rationale = self._build_rationale(gate_actions, hotspots, bottleneck_gates, peak_density)

        return {
            "agent": "routing",
            "timestamp": timestamp,
            "decision": f"{len(gate_actions)} gate action(s) recommended",
            "confidence": 0.88,
            "metadata": {
                "gate_actions": gate_actions,
                "estimated_density_reduction": density_reduction,
                "estimated_completion_minutes": len(gate_actions) * 2,
                "routing_rationale": rationale,
                "hotspots_addressed": hotspots,
                "bottlenecks_addressed": bottleneck_gates,
            },
        }

    def _generate_gate_actions(
        self,
        hotspots: List[str],
        bottleneck_gates: List[str],
        underutilised_gates: List[str],
        peak_density: float,
        phase: str,
    ) -> List[Dict]:
        actions = []

        # Open underutilised gates to absorb overflow
        for gate_id in underutilised_gates[:3]:
            actions.append(
                {
                    "gate_id": gate_id,
                    "action": "open",
                    "reason": f"Absorb overflow from hotspot zones — current utilisation < 30%",
                    "priority": "high" if peak_density > 0.80 else "medium",
                }
            )

        # Close severely underutilised entry gates during mid-match to focus flow
        if phase == "mid_match" and peak_density < 0.50:
            for gate_id in underutilised_gates[3:5]:
                actions.append(
                    {
                        "gate_id": gate_id,
                        "action": "close",
                        "reason": "Consolidate entry points during low-activity phase",
                        "priority": "low",
                    }
                )

        # Open emergency gates if density is critical
        if peak_density > 0.85:
            actions.append(
                {
                    "gate_id": "E1",
                    "action": "open",
                    "reason": f"Peak density {peak_density:.1%} — emergency overflow required",
                    "priority": "high",
                }
            )

        # If no actions generated, add a no-op recommendation
        if not actions:
            actions.append(
                {
                    "gate_id": "ALL",
                    "action": "maintain",
                    "reason": "Current gate configuration is optimal",
                    "priority": "low",
                }
            )

        return actions

    def _estimate_density_reduction(
        self, gate_actions: List[Dict], density_meta: Dict
    ) -> Dict[str, float]:
        """Rough estimate: each opened gate reduces peak density by ~3-5%."""
        opens = sum(1 for a in gate_actions if a["action"] == "open")
        zones = density_meta.get("zones", [])
        reduction = {}
        for zone in zones:
            if zone.get("capacity_pct", 0) > 0.7:
                reduction[zone["zone_id"]] = round(opens * 0.03, 3)
        return reduction

    def _build_rationale(
        self,
        actions: List[Dict],
        hotspots: List[str],
        bottleneck_gates: List[str],
        peak_density: float,
    ) -> str:
        if not hotspots and not bottleneck_gates:
            return "No hotspots or bottlenecks detected — maintaining current gate configuration"
        parts = []
        if hotspots:
            parts.append(f"Hotspot zones ({', '.join(hotspots)}) require outflow relief")
        if bottleneck_gates:
            parts.append(f"Gate bottlenecks ({', '.join(bottleneck_gates)}) redirected to alternates")
        parts.append(f"Peak density {peak_density:.1%} — {len(actions)} adjustment(s) applied")
        return ". ".join(parts)
