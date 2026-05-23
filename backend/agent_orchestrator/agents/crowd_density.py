"""
Crowd Density Agent
Reads per-zone density data from sensors/GCS, computes crowd flow vectors,
and returns a structured density report.
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List

import google.generativeai as genai
from google.adk.agents import LlmAgent

from tools.sensor_tools import get_zone_density_tool, get_historical_density_tool
from agents.gemini_client import call_gemini

logger = logging.getLogger(__name__)

CROWD_DENSITY_PROMPT = """
You are the Crowd Density Specialist for CrowdGuard Command.

Your job:
1. Read current crowd density data for all stadium zones.
2. Compare with historical baseline for the current match phase.
3. Compute density gradient (is it rising, stable, or falling?).
4. Identify the top-3 most congested zones.
5. Flag any zone exceeding 80% capacity as a hotspot.

Zones to monitor:
- north_stand (capacity: 35,000)
- south_stand (capacity: 35,000)
- east_stand (capacity: 20,000)
- west_stand (capacity: 22,000)
- vip_pavilion (capacity: 10,000)
- media_center (capacity: 10,000)

Output JSON:
{
  "zones": [{"zone_id": str, "density": float, "capacity_pct": float, "trend": "rising|stable|falling"}],
  "hotspots": [str],
  "peak_density": float,
  "flow_vectors": [{"zone_id": str, "direction": str, "magnitude": float}],
  "recommendation": str
}
"""

# Simulated zone data for demo (populated by sensor_tools in production)
STADIUM_ZONES = [
    {"zone_id": "north_stand", "capacity": 35000},
    {"zone_id": "south_stand", "capacity": 35000},
    {"zone_id": "east_stand", "capacity": 20000},
    {"zone_id": "west_stand", "capacity": 22000},
    {"zone_id": "vip_pavilion", "capacity": 10000},
    {"zone_id": "media_center", "capacity": 10000},
]


class CrowdDensityAgent:
    """Wraps the Google ADK LlmAgent for crowd density analysis."""

    def __init__(self, model: str = "gemini-1.5-pro"):
        self.model = model
        self.agent = LlmAgent(
            name="crowd_density_agent",
            model=model,
            description="Monitors per-zone crowd density and computes flow vectors",
            instruction=CROWD_DENSITY_PROMPT,
            tools=[get_zone_density_tool, get_historical_density_tool],
        )
        api_key = os.getenv("GOOGLE_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
            self._gemini = genai.GenerativeModel(model)
        else:
            self._gemini = None
            logger.warning("GOOGLE_API_KEY not set — CrowdDensityAgent using template decisions")
        # Initialise Gemini for decision generation
        api_key = os.getenv("GOOGLE_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
            self._gemini = genai.GenerativeModel(model)
        else:
            self._gemini = None
            logger.warning("GOOGLE_API_KEY not set — agent will use template decisions")

    async def analyze(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run density analysis for the current match phase.
        Falls back to simulated data when sensor feed is unavailable.
        """
        phase = context.get("phase", "mid_match")
        timestamp = datetime.utcnow().isoformat()

        try:
            zone_data = await self._fetch_zone_data(phase)
            flow_vectors = self._compute_flow_vectors(zone_data, phase)
            hotspots = [z["zone_id"] for z in zone_data if z["capacity_pct"] > 0.80]
            peak_density = max(z["capacity_pct"] for z in zone_data)

            recommendation = self._generate_recommendation(peak_density, hotspots, phase)

            # Call Gemini for operator decision text
            zone_data_summary = (
                f"Phase: {phase}. Peak density: {peak_density:.1%}. "
                f"Hotspots: {', '.join(hotspots) or 'none'}. "
                f"Zones: " + ", ".join(
                    f"{z['zone_id']}={z['capacity_pct']:.0%}" for z in zone_data
                )
            )
            decision_text = f"Peak density {peak_density:.1%} — {len(hotspots)} hotspot(s) detected"
            if self._gemini:
                result = await call_gemini(
                    f"Analyze this stadium crowd density data and give a 1-2 sentence operator decision:\n{zone_data_summary}",
                    model=self.model,
                )
                if result:
                    decision_text = result

            return {
                "agent": "crowd_density",
                "timestamp": timestamp,
                "decision": decision_text,
                "confidence": 0.92,
                "metadata": {
                    "zones": zone_data,
                    "hotspots": hotspots,
                    "peak_density": peak_density,
                    "flow_vectors": flow_vectors,
                    "recommendation": recommendation,
                    "phase": phase,
                },
            }

        except Exception as e:
            logger.error(f"CrowdDensityAgent error: {e}", exc_info=True)
            return self._fallback_response(timestamp, str(e))

    async def _fetch_zone_data(self, phase: str) -> List[Dict]:
        """Fetch zone densities from sensor tools or use simulated values."""
        from tools.sensor_tools import PHASE_DENSITY_PROFILES

        profiles = PHASE_DENSITY_PROFILES.get(phase, PHASE_DENSITY_PROFILES["mid_match"])
        zone_data = []

        for zone_cfg in STADIUM_ZONES:
            zid = zone_cfg["zone_id"]
            density_pct = profiles.get(zid, 0.5)
            # Add ±5% realistic jitter
            import random
            jitter = random.uniform(-0.05, 0.05)
            density_pct = max(0.0, min(1.0, density_pct + jitter))

            zone_data.append(
                {
                    "zone_id": zid,
                    "capacity": zone_cfg["capacity"],
                    "current_count": int(zone_cfg["capacity"] * density_pct),
                    "capacity_pct": round(density_pct, 3),
                    "trend": self._get_trend(zid, density_pct, phase),
                }
            )

        return zone_data

    def _compute_flow_vectors(
        self, zone_data: List[Dict], phase: str
    ) -> List[Dict]:
        """Derive movement direction from density imbalances between adjacent zones."""
        flow_map = {
            "pre_match": {"direction": "inward", "magnitude": 0.6},
            "match_start": {"direction": "inward", "magnitude": 0.9},
            "mid_match": {"direction": "lateral", "magnitude": 0.2},
            "post_match": {"direction": "outward", "magnitude": 0.95},
        }
        base = flow_map.get(phase, {"direction": "lateral", "magnitude": 0.3})

        vectors = []
        for zone in zone_data:
            mag = base["magnitude"] * zone["capacity_pct"]
            vectors.append(
                {
                    "zone_id": zone["zone_id"],
                    "direction": base["direction"],
                    "magnitude": round(mag, 3),
                    "speed_estimate_mps": round(mag * 1.4, 2),
                }
            )
        return vectors

    def _get_trend(self, zone_id: str, current_density: float, phase: str) -> str:
        """Determine density trend for a zone based on phase."""
        rising_phases = {"pre_match", "match_start"}
        falling_phases = {"post_match"}

        if phase in rising_phases:
            return "rising"
        if phase in falling_phases:
            return "falling"
        return "stable"

    def _generate_recommendation(
        self, peak_density: float, hotspots: List[str], phase: str
    ) -> str:
        if peak_density > 0.90:
            return f"CRITICAL: Open overflow gates immediately — {', '.join(hotspots)} at capacity"
        if peak_density > 0.75:
            return f"WARNING: Redirect inflow from {', '.join(hotspots)} — consider closing intake gates"
        if peak_density > 0.60:
            return "MONITOR: Density elevated, prepare gate reconfigurations"
        return "NOMINAL: Crowd density within safe operating parameters"

    def _fallback_response(self, timestamp: str, error: str) -> Dict:
        return {
            "agent": "crowd_density",
            "timestamp": timestamp,
            "decision": "Density data unavailable — using last known state",
            "confidence": 0.3,
            "metadata": {"error": error, "peak_density": 0.5, "hotspots": []},
        }
