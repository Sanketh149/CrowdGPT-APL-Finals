"""
CrowdGuard Command — Master Orchestrator
Uses Google ADK LlmAgent to coordinate a ParallelAgent (monitoring)
and a SequentialAgent (response chain).
"""

import asyncio
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

# Google ADK imports
from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent

from agents.crowd_density import CrowdDensityAgent
from agents.gate_sensor import GateSensorAgent
from agents.weather_context import WeatherContextAgent
from agents.routing import RoutingAgent
from agents.threat_detection import ThreatDetectionAgent
from agents.emergency import EmergencyProtocolAgent
from agents.notifier import NotifierAgent
from tools.sensor_tools import get_zone_density_tool, get_historical_density_tool
from tools.gate_control import open_gate_tool, close_gate_tool, get_gate_status_tool
from tools.alert_tools import dispatch_alert_tool, get_active_alerts_tool

load_dotenv()
logger = logging.getLogger(__name__)

ORCHESTRATOR_SYSTEM_PROMPT = """
You are CrowdGuard Command — the master orchestrator for crowd safety at a major cricket stadium.

Your responsibilities:
1. Continuously monitor crowd density, gate throughput, and weather conditions via specialist agents.
2. When monitoring agents detect anomalies or threshold breaches, activate the response chain.
3. Coordinate routing decisions, threat assessment, emergency protocols, and notifications.
4. Always prioritize crowd safety over match experience.
5. Provide clear, concise decisions with confidence scores.

Current Stadium: Narendra Modi Stadium, Ahmedabad (capacity: 132,000)
Zones: North Stand, South Stand, East Stand, West Stand, VIP Pavilion, Media Center
Gates: G1-G12 (entry/exit gates), Emergency E1-E4

When assessing risk levels:
- 0-25: NORMAL (green) — standard operations
- 26-50: CAUTION (yellow) — increase monitoring frequency
- 51-75: ELEVATED (orange) — activate routing adjustments
- 76-100: CRITICAL (red) — trigger emergency protocols

Always respond with structured JSON containing: decision, confidence, actions, and rationale.
"""


class CrowdGuardOrchestrator:
    """
    Master orchestrator that wraps Google ADK agents.
    Manages the ParallelAgent (monitoring) and SequentialAgent (response).
    """

    def __init__(self):
        self.model = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
        self._event_buffer: List[Dict] = []
        self._current_status: Dict = {
            "phase": "pre_match",
            "overall_risk": 0,
            "active_protocol": "NORMAL",
            "active_agents": [],
            "last_updated": datetime.utcnow().isoformat(),
        }
        self._setup_agents()

    def _setup_agents(self):
        """Initialise all specialist agents and compose the hierarchy."""

        # ── Specialist agents ──────────────────────────────────────────────
        self.crowd_density_agent = CrowdDensityAgent(model=self.model)
        self.gate_sensor_agent = GateSensorAgent(model=self.model)
        self.weather_context_agent = WeatherContextAgent(model=self.model)
        self.routing_agent = RoutingAgent(model=self.model)
        self.threat_detection_agent = ThreatDetectionAgent(model=self.model)
        self.emergency_agent = EmergencyProtocolAgent(model=self.model)
        self.notifier_agent = NotifierAgent(model=self.model)

        # ── ParallelAgent: runs monitoring agents concurrently ────────────
        self.monitoring_parallel = ParallelAgent(
            name="monitoring_parallel",
            description="Runs Crowd Density, Gate Sensor, and Weather agents simultaneously",
            sub_agents=[
                self.crowd_density_agent.agent,
                self.gate_sensor_agent.agent,
                self.weather_context_agent.agent,
            ],
        )

        # ── SequentialAgent: response chain ───────────────────────────────
        self.response_sequential = SequentialAgent(
            name="response_sequential",
            description="Executes routing → threat detection → emergency → notification in order",
            sub_agents=[
                self.routing_agent.agent,
                self.threat_detection_agent.agent,
                self.emergency_agent.agent,
                self.notifier_agent.agent,
            ],
        )

        # ── Master LlmAgent orchestrator ──────────────────────────────────
        self.master_agent = LlmAgent(
            name="crowdguard_orchestrator",
            model=self.model,
            description="Master crowd safety orchestrator for cricket stadiums",
            instruction=ORCHESTRATOR_SYSTEM_PROMPT,
            tools=[
                get_zone_density_tool,
                get_gate_status_tool,
                dispatch_alert_tool,
                get_active_alerts_tool,
            ],
            sub_agents=[self.monitoring_parallel, self.response_sequential],
        )

        logger.info("All agents initialised successfully")

    async def run(
        self,
        match_id: str,
        stadium_id: str,
        phase: str,
        trigger: str,
        override_data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Execute a full orchestrator cycle and return structured decisions."""
        run_id = str(uuid.uuid4())[:8]
        logger.info(f"[{run_id}] Starting orchestrator run — phase={phase}")

        context = {
            "run_id": run_id,
            "match_id": match_id,
            "stadium_id": stadium_id,
            "phase": phase,
            "trigger": trigger,
            "timestamp": datetime.utcnow().isoformat(),
            **(override_data or {}),
        }

        decisions: List[Dict] = []
        protocol = "NORMAL"
        alerts: List[Dict] = []

        try:
            # Step 1: Run monitoring agents in parallel
            monitoring_prompt = (
                f"Execute monitoring cycle for match {match_id} at phase '{phase}'. "
                f"Collect crowd density, gate throughput, and weather data. "
                f"Context: {context}"
            )
            monitoring_results = await self._run_parallel_monitoring(
                monitoring_prompt, context
            )
            decisions.extend(monitoring_results)

            # Step 2: Check if threshold is breached
            overall_density = self._extract_peak_density(monitoring_results)
            if overall_density > 0.65 or trigger == "manual":
                logger.info(
                    f"[{run_id}] Threshold breached (density={overall_density:.2f}), "
                    "activating response chain"
                )
                response_results = await self._run_sequential_response(
                    context, monitoring_results
                )
                decisions.extend(response_results)
                protocol = self._extract_protocol(response_results)
                alerts = self._extract_alerts(response_results)

            # Update internal status
            self._current_status.update(
                {
                    "phase": phase,
                    "overall_risk": int(overall_density * 100),
                    "active_protocol": protocol,
                    "last_updated": datetime.utcnow().isoformat(),
                }
            )
            self._event_buffer = (self._event_buffer + decisions)[-100:]

        except Exception as e:
            logger.error(f"[{run_id}] Agent run error: {e}", exc_info=True)
            decisions.append(
                {
                    "agent": "orchestrator",
                    "timestamp": datetime.utcnow().isoformat(),
                    "decision": f"Run failed: {e}",
                    "confidence": 0.0,
                    "metadata": {"error": str(e)},
                }
            )

        return {
            "run_id": run_id,
            "decisions": decisions,
            "protocol": protocol,
            "alerts": alerts,
        }

    async def _run_parallel_monitoring(
        self, prompt: str, context: Dict
    ) -> List[Dict]:
        """Delegate to each monitoring sub-agent asynchronously."""
        tasks = [
            self.crowd_density_agent.analyze(context),
            self.gate_sensor_agent.analyze(context),
            self.weather_context_agent.analyze(context),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        decisions = []
        for r in results:
            if isinstance(r, Exception):
                logger.warning(f"Monitoring agent error: {r}")
            else:
                decisions.append(r)
        return decisions

    async def _run_sequential_response(
        self, context: Dict, monitoring_results: List[Dict]
    ) -> List[Dict]:
        """Run the sequential response chain, passing state forward."""
        state = {**context, "monitoring": monitoring_results}
        decisions = []

        routing_result = await self.routing_agent.decide(state)
        decisions.append(routing_result)
        state["routing"] = routing_result

        threat_result = await self.threat_detection_agent.assess(state)
        decisions.append(threat_result)
        state["threat"] = threat_result

        emergency_result = await self.emergency_agent.activate(state)
        decisions.append(emergency_result)
        state["emergency"] = emergency_result

        notify_result = await self.notifier_agent.notify(state)
        decisions.append(notify_result)

        return decisions

    def _extract_peak_density(self, monitoring_results: List[Dict]) -> float:
        """Extract the highest zone density from monitoring results."""
        densities = []
        for r in monitoring_results:
            meta = r.get("metadata", {})
            if "peak_density" in meta:
                densities.append(float(meta["peak_density"]))
        return max(densities) if densities else 0.4

    def _extract_protocol(self, response_results: List[Dict]) -> str:
        """Find the emergency protocol from response decisions."""
        for r in response_results:
            if r.get("agent") == "emergency_protocol":
                return r.get("metadata", {}).get("protocol", "NORMAL")
        return "NORMAL"

    def _extract_alerts(self, response_results: List[Dict]) -> List[Dict]:
        """Collect dispatched alerts from the notifier."""
        for r in response_results:
            if r.get("agent") == "notifier":
                return r.get("metadata", {}).get("alerts", [])
        return []

    async def get_latest_events(self) -> List[Dict]:
        """Return buffered events for SSE streaming."""
        events = self._event_buffer.copy()
        self._event_buffer.clear()
        return events

    async def get_status(self) -> Dict:
        """Return current system status."""
        return self._current_status

    async def override_gate(self, gate_id: str, action: str) -> Dict:
        """Apply a manual gate override."""
        from tools.gate_control import _gate_state
        _gate_state[gate_id] = action
        result = {
            "gate_id": gate_id,
            "action": action,
            "timestamp": datetime.utcnow().isoformat(),
            "source": "manual_override",
        }
        self._event_buffer.append(
            {
                "agent": "orchestrator",
                "timestamp": datetime.utcnow().isoformat(),
                "decision": f"Manual override: Gate {gate_id} set to {action}",
                "confidence": 1.0,
                "metadata": result,
            }
        )
        return result
