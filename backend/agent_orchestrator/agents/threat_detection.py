"""
Threat Detection Agent (SequentialAgent Step 2)
Computes a risk score 0–100 using the ML model output combined with
live density, gate pressure, and anomaly indicators.
"""

import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

import google.generativeai as genai
from google.adk.agents import LlmAgent

from tools.sensor_tools import get_zone_density_tool
from agents.gemini_client import call_gemini

logger = logging.getLogger(__name__)

THREAT_DETECTION_PROMPT = """
You are the Threat Detection Specialist for CrowdGuard Command.

Your job:
1. Ingest the routing agent's output and current density/gate data.
2. Compute an overall risk score from 0 (safe) to 100 (critical).
3. Identify specific anomaly types: crush risk, bottleneck cascade, heat emergency, surge wave.
4. Flag the top-3 risk factors with their individual scores.
5. Output a confidence-weighted overall risk score.

Risk scoring weights:
- Peak crowd density: 35%
- Gate pressure (bottleneck count): 25%
- Flow acceleration (rapid density change): 20%
- Weather heat stress: 10%
- Historical anomaly rate: 10%

Output JSON:
{
  "risk_score": int,
  "risk_level": "NORMAL|CAUTION|ELEVATED|CRITICAL",
  "anomalies": [{"type": str, "zone": str, "score": int, "description": str}],
  "top_risk_factors": [{"factor": str, "weight": float, "score": int}],
  "ml_model_score": float,
  "confidence": float,
  "threat_summary": str
}
"""

# Weight matrix for risk computation
RISK_WEIGHTS = {
    "peak_density": 0.35,
    "gate_pressure": 0.25,
    "flow_acceleration": 0.20,
    "weather_stress": 0.10,
    "anomaly_rate": 0.10,
}


class ThreatDetectionAgent:
    """Computes risk score using monitoring data and ML model inference."""

    def __init__(self, model: str = "gemini-1.5-pro"):
        self.model = model
        self.agent = LlmAgent(
            name="threat_detection_agent",
            model=model,
            description="Computes crowd risk score using ML model and live sensor data",
            instruction=THREAT_DETECTION_PROMPT,
            tools=[get_zone_density_tool],
        )
        self._ml_model = None
        # Initialise Gemini for threat assessment generation
        api_key = os.getenv("GOOGLE_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
            self._gemini = genai.GenerativeModel(model)
        else:
            self._gemini = None
            logger.warning("GOOGLE_API_KEY not set — agent will use template decisions")

    def _load_ml_model(self):
        """Lazy-load the PyTorch LSTM model."""
        if self._ml_model is not None:
            return self._ml_model

        model_path = os.path.join(
            os.path.dirname(__file__), "../../ml_model/model_checkpoint.pt"
        )
        try:
            # Dynamic import to avoid hard dependency at startup
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../ml_model"))
            from predict import CrowdRiskPredictor
            self._ml_model = CrowdRiskPredictor(model_path)
            logger.info("ML model loaded successfully")
        except Exception as e:
            logger.warning(f"ML model unavailable, using heuristic scoring: {e}")
            self._ml_model = None

        return self._ml_model

    async def assess(self, state: Dict[str, Any]) -> Dict[str, Any]:
        timestamp = datetime.utcnow().isoformat()

        monitoring = state.get("monitoring", [])
        routing = state.get("routing", {})

        density_meta = self._extract_meta(monitoring, "crowd_density")
        gate_meta = self._extract_meta(monitoring, "gate_sensor")
        weather_meta = self._extract_meta(monitoring, "weather_context")

        # Compute sub-scores
        density_score = self._score_density(density_meta)
        gate_score = self._score_gates(gate_meta)
        weather_score = self._score_weather(weather_meta)
        acceleration_score = self._score_acceleration(density_meta, state.get("phase"))

        # Try ML model inference
        ml_score = self._ml_inference(density_meta, gate_meta, state.get("phase", "mid_match"))

        # Weighted risk
        raw_score = (
            density_score * RISK_WEIGHTS["peak_density"]
            + gate_score * RISK_WEIGHTS["gate_pressure"]
            + acceleration_score * RISK_WEIGHTS["flow_acceleration"]
            + weather_score * RISK_WEIGHTS["weather_stress"]
            + 50 * RISK_WEIGHTS["anomaly_rate"]  # baseline anomaly rate
        )

        # Blend with ML score if available
        if ml_score is not None:
            risk_score = int(0.6 * raw_score + 0.4 * ml_score * 100)
        else:
            risk_score = int(raw_score)

        risk_score = max(0, min(100, risk_score))
        risk_level = self._risk_level(risk_score)
        anomalies = self._detect_anomalies(density_meta, gate_meta, weather_meta, risk_score)
        top_factors = self._top_risk_factors(
            density_score, gate_score, acceleration_score, weather_score
        )

        threat_summary = self._threat_summary(risk_score, anomalies)
        decision_text = f"Risk score {risk_score}/100 — level: {risk_level}"

        # Call Gemini for threat assessment
        if self._gemini:
            anomaly_desc = "; ".join(f"{a['type']} in {a['zone']}" for a in anomalies) or "none"
            top_factors_desc = ", ".join(f"{f['factor']}={f['score']}" for f in top_factors)
            result = await call_gemini(
                f"You are a crowd safety threat analyst. Risk score: {risk_score}/100, "
                f"level: {risk_level}. Anomalies: {anomaly_desc}. "
                f"Top factors: {top_factors_desc}. "
                f"Write a 2-3 sentence threat assessment for the operator.",
                model=self.model,
            )
            if result:
                threat_summary = result
                decision_text = result

        return {
            "agent": "threat_detection",
            "timestamp": timestamp,
            "decision": decision_text,
            "confidence": 0.87,
            "metadata": {
                "risk_score": risk_score,
                "risk_level": risk_level,
                "anomalies": anomalies,
                "top_risk_factors": top_factors,
                "ml_model_score": ml_score,
                "sub_scores": {
                    "density": round(density_score, 1),
                    "gate_pressure": round(gate_score, 1),
                    "acceleration": round(acceleration_score, 1),
                    "weather": round(weather_score, 1),
                },
                "threat_summary": threat_summary,
            },
        }

    def _extract_meta(self, monitoring: List[Dict], agent_name: str) -> Dict:
        for m in monitoring:
            if m.get("agent") == agent_name:
                return m.get("metadata", {})
        return {}

    def _score_density(self, density_meta: Dict) -> float:
        peak = density_meta.get("peak_density", 0.5)
        return peak * 100

    def _score_gates(self, gate_meta: Dict) -> float:
        gates = gate_meta.get("gates", [])
        if not gates:
            return 30.0
        bottleneck_count = len(gate_meta.get("bottleneck_gates", []))
        total_gates = len([g for g in gates if g.get("status") == "open"])
        if total_gates == 0:
            return 80.0
        return min(100, (bottleneck_count / total_gates) * 100 * 1.5)

    def _score_weather(self, weather_meta: Dict) -> float:
        impact = weather_meta.get("routing_impact", "none")
        mapping = {"none": 5, "minor": 20, "moderate": 50, "severe": 90}
        return float(mapping.get(impact, 10))

    def _score_acceleration(self, density_meta: Dict, phase: Optional[str]) -> float:
        """High acceleration zones: match_start and post_match get elevated score."""
        acceleration_by_phase = {
            "pre_match": 20,
            "match_start": 75,
            "mid_match": 15,
            "post_match": 80,
        }
        base = acceleration_by_phase.get(phase or "mid_match", 20)
        rising_zones = [
            z for z in density_meta.get("zones", []) if z.get("trend") == "rising"
        ]
        return min(100, base + len(rising_zones) * 5)

    def _ml_inference(
        self, density_meta: Dict, gate_meta: Dict, phase: str
    ) -> Optional[float]:
        """Run the LSTM model if available, return 0-1 risk score."""
        predictor = self._load_ml_model()
        if predictor is None:
            return None

        try:
            peak_density = density_meta.get("peak_density", 0.5)
            gates = gate_meta.get("gates", [])
            avg_flow = (
                sum(g.get("flow_rate_ppm", 0) for g in gates) / max(len(gates), 1) / 300
            )
            features = {
                "density": peak_density,
                "flow_magnitude": avg_flow,
                "acceleration": 0.5 if phase in ("match_start", "post_match") else 0.1,
                "gate_pressure": len(gate_meta.get("bottleneck_gates", [])) / 12,
            }
            return predictor.predict(features)
        except Exception as e:
            logger.warning(f"ML inference failed: {e}")
            return None

    @staticmethod
    def _risk_level(score: int) -> str:
        if score <= 25:
            return "NORMAL"
        if score <= 50:
            return "CAUTION"
        if score <= 75:
            return "ELEVATED"
        return "CRITICAL"

    def _detect_anomalies(
        self,
        density_meta: Dict,
        gate_meta: Dict,
        weather_meta: Dict,
        risk_score: int,
    ) -> List[Dict]:
        anomalies = []
        for zone in density_meta.get("hotspots", []):
            anomalies.append(
                {
                    "type": "crush_risk",
                    "zone": zone,
                    "score": min(100, risk_score + 10),
                    "description": f"Zone {zone} exceeds 80% capacity — crush risk elevated",
                }
            )
        if len(gate_meta.get("bottleneck_gates", [])) >= 3:
            anomalies.append(
                {
                    "type": "bottleneck_cascade",
                    "zone": "multiple_gates",
                    "score": 70,
                    "description": "Multiple gate bottlenecks — cascade failure possible",
                }
            )
        if weather_meta.get("heat_index", 30) > 42:
            anomalies.append(
                {
                    "type": "heat_emergency",
                    "zone": "open_stands",
                    "score": 60,
                    "description": f"Heat index {weather_meta['heat_index']}°C — mass heat stress risk",
                }
            )
        return anomalies

    @staticmethod
    def _top_risk_factors(
        density_score: float,
        gate_score: float,
        acceleration_score: float,
        weather_score: float,
    ) -> List[Dict]:
        factors = [
            {"factor": "peak_density", "weight": RISK_WEIGHTS["peak_density"], "score": int(density_score)},
            {"factor": "gate_pressure", "weight": RISK_WEIGHTS["gate_pressure"], "score": int(gate_score)},
            {"factor": "flow_acceleration", "weight": RISK_WEIGHTS["flow_acceleration"], "score": int(acceleration_score)},
            {"factor": "weather_stress", "weight": RISK_WEIGHTS["weather_stress"], "score": int(weather_score)},
        ]
        return sorted(factors, key=lambda x: x["score"], reverse=True)[:3]

    @staticmethod
    def _threat_summary(risk_score: int, anomalies: List[Dict]) -> str:
        if risk_score > 75:
            types = list({a["type"] for a in anomalies})
            return f"CRITICAL risk — active anomalies: {', '.join(types) or 'general overcrowding'}"
        if risk_score > 50:
            return f"ELEVATED risk — {len(anomalies)} anomaly/ies detected, response chain active"
        if risk_score > 25:
            return "CAUTION — crowd density elevated but within manageable range"
        return "Normal operating conditions — no active threats"
