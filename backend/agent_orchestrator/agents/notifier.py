"""
Notifier Agent (SequentialAgent Step 4)
Formats and sends alert messages to operators and field staff.
Uses Gemini to generate natural-language summaries of the situation.
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List

import google.generativeai as genai
from dotenv import load_dotenv
from google.adk.agents import LlmAgent

from tools.alert_tools import dispatch_alert_tool, get_active_alerts_tool
from agents.gemini_client import call_gemini

load_dotenv()
logger = logging.getLogger(__name__)

NOTIFIER_PROMPT = """
You are the Notifier Specialist for CrowdGuard Command.

Given the full response chain output (routing, threat, emergency decisions), your job is to:
1. Compose a concise operator alert summarising the situation and actions taken.
2. Compose a field staff message with specific, actionable instructions.
3. Compose a public PA announcement (if protocol level requires it).
4. Assign severity: INFO / WARNING / CRITICAL.
5. Return structured alert objects ready for dispatch.

Alert format:
{
  "alerts": [
    {
      "id": str,
      "severity": "INFO|WARNING|CRITICAL",
      "channel": "operator|field_staff|public_pa",
      "message": str,
      "timestamp": str,
      "actions_required": [str]
    }
  ]
}
"""


class NotifierAgent:
    """Composes and dispatches alerts using Gemini for natural-language generation."""

    def __init__(self, model: str = "gemini-1.5-pro"):
        self.model = model
        self.agent = LlmAgent(
            name="notifier_agent",
            model=model,
            description="Formats and dispatches crowd safety alerts to operators and staff",
            instruction=NOTIFIER_PROMPT,
            tools=[dispatch_alert_tool, get_active_alerts_tool],
        )
        # Initialise Gemini for message generation
        api_key = os.getenv("GOOGLE_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
            self._gemini = genai.GenerativeModel(model)
        else:
            self._gemini = None
            logger.warning("GOOGLE_API_KEY not set — Notifier will use template messages")

    async def notify(self, state: Dict[str, Any]) -> Dict[str, Any]:
        timestamp = datetime.utcnow().isoformat()

        emergency_meta = state.get("emergency", {}).get("metadata", {})
        threat_meta = state.get("threat", {}).get("metadata", {})
        routing_meta = state.get("routing", {}).get("metadata", {})

        protocol = emergency_meta.get("protocol", "NORMAL")
        risk_score = threat_meta.get("risk_score", 0)
        anomalies = threat_meta.get("anomalies", [])
        gate_actions = routing_meta.get("gate_actions", [])

        severity = self._protocol_to_severity(protocol)

        alerts = []

        # Operator alert
        operator_msg = await self._generate_operator_message(
            protocol, risk_score, anomalies, gate_actions
        )
        alerts.append(
            {
                "id": f"OPS-{timestamp[:19].replace(':', '').replace('-', '')}",
                "severity": severity,
                "channel": "operator",
                "message": operator_msg,
                "timestamp": timestamp,
                "actions_required": self._operator_actions(protocol, gate_actions),
            }
        )

        # Field staff alert (only for CAUTION or above)
        if protocol in ("CAUTION", "EVACUATE", "LOCKDOWN"):
            staff_msg = self._generate_staff_message(emergency_meta)
            alerts.append(
                {
                    "id": f"STAFF-{timestamp[:19].replace(':', '').replace('-', '')}",
                    "severity": severity,
                    "channel": "field_staff",
                    "message": staff_msg,
                    "timestamp": timestamp,
                    "actions_required": [emergency_meta.get("staff_instructions", "")],
                }
            )

        # Public PA (only for EVACUATE or LOCKDOWN)
        if protocol in ("EVACUATE", "LOCKDOWN"):
            alerts.append(
                {
                    "id": f"PA-{timestamp[:19].replace(':', '').replace('-', '')}",
                    "severity": "CRITICAL",
                    "channel": "public_pa",
                    "message": emergency_meta.get("public_announcement", ""),
                    "timestamp": timestamp,
                    "actions_required": ["Broadcast via stadium PA system immediately"],
                }
            )

        logger.info(f"NotifierAgent: Dispatching {len(alerts)} alert(s) — protocol={protocol}")

        # Collect zone density data from monitoring results
        crowd_meta = {}
        for m in state.get("monitoring", []):
            if isinstance(m, dict) and m.get("agent") == "crowd_density":
                crowd_meta = m.get("metadata", {})
                break

        # Build rich context to pass into each alert for richer emails
        rich_context = {
            "protocol": protocol,
            "risk_score": risk_score,
            "anomalies": anomalies,
            "gate_actions": gate_actions,
            "zones": crowd_meta.get("zones", []),
            "hotspots": crowd_meta.get("hotspots", []),
            "resources_deployed": emergency_meta.get("resources_deployed", {}),
            "staff_instructions": emergency_meta.get("staff_instructions", ""),
            "match_id": state.get("match_id", "IPL_2026_FINAL"),
            "phase": state.get("phase", "mid_match"),
        }

        # Actually send each alert (triggers SendGrid email for field_staff/public_pa/all)
        dispatch_results = []
        for alert in alerts:
            alert["context"] = rich_context
            try:
                result = dispatch_alert_tool(
                    severity=alert["severity"],
                    channel=alert["channel"],
                    message=alert["message"],
                    zone_id=alert.get("zone_id"),
                    actions_required=alert.get("actions_required"),
                    context=rich_context,
                )
                dispatch_results.append(result)
                logger.info(
                    f"Alert dispatched: {result['alert_id']} → {alert['channel']} "
                    f"({result.get('dispatch_status', 'unknown')})"
                )
            except Exception as e:
                logger.error(f"Failed to dispatch alert to {alert['channel']}: {e}")

        return {
            "agent": "notifier",
            "timestamp": timestamp,
            "decision": f"{len(alerts)} alert(s) dispatched — severity: {severity}",
            "confidence": 0.95,
            "metadata": {
                "alerts": alerts,
                "protocol": protocol,
                "risk_score": risk_score,
                "channels_notified": list({a["channel"] for a in alerts}),
                "dispatch_results": dispatch_results,
            },
        }

    async def _generate_operator_message(
        self,
        protocol: str,
        risk_score: int,
        anomalies: List[Dict],
        gate_actions: List[Dict],
    ) -> str:
        """Use Gemini to compose a natural-language operator summary."""
        if self._gemini:
            try:
                anomaly_text = (
                    "; ".join(f"{a['type']} in {a['zone']}" for a in anomalies)
                    or "none detected"
                )
                gate_text = (
                    "; ".join(
                        f"{a['gate_id']} → {a['action']}" for a in gate_actions[:5]
                    )
                    or "no changes"
                )
                prompt = (
                    f"Write a concise (2-3 sentences) operator alert for a cricket stadium crowd safety system.\n"
                    f"Protocol: {protocol}, Risk Score: {risk_score}/100\n"
                    f"Anomalies: {anomaly_text}\n"
                    f"Gate actions: {gate_text}\n"
                    f"Be factual, urgent if warranted, and actionable."
                )
                result = await call_gemini(prompt, model=self.model)
                if result:
                    return result

        # Fallback template
        return (
            f"[{protocol}] CrowdGuard Alert — Risk Score: {risk_score}/100. "
            f"{len(anomalies)} anomaly/ies detected. "
            f"{len(gate_actions)} gate reconfiguration(s) applied. "
            f"Monitor situation closely and follow playbook protocols."
        )

    @staticmethod
    def _generate_staff_message(emergency_meta: Dict) -> str:
        protocol = emergency_meta.get("protocol", "CAUTION")
        resources = emergency_meta.get("resources_deployed", {})
        return (
            f"[CROWDGUARD {protocol}] "
            f"Deploy {resources.get('marshals', 0)} marshals, "
            f"{resources.get('medical', 0)} medical, "
            f"{resources.get('police', 0)} police. "
            f"{emergency_meta.get('staff_instructions', 'Follow standard protocol.')}"
        )

    @staticmethod
    def _protocol_to_severity(protocol: str) -> str:
        mapping = {
            "NORMAL": "INFO",
            "CAUTION": "WARNING",
            "EVACUATE": "CRITICAL",
            "LOCKDOWN": "CRITICAL",
        }
        return mapping.get(protocol, "INFO")

    @staticmethod
    def _operator_actions(protocol: str, gate_actions: List[Dict]) -> List[str]:
        actions = []
        if gate_actions:
            for a in gate_actions[:3]:
                if a.get("gate_id") != "ALL":
                    actions.append(f"Confirm gate {a['gate_id']} is {a['action']}")
        if protocol == "EVACUATE":
            actions.append("Activate incident room and notify incident commander")
        if protocol == "LOCKDOWN":
            actions.append("Call emergency services (Police: 100, Ambulance: 108)")
            actions.append("Notify stadium director and local authorities")
        if not actions:
            actions.append("Continue monitoring — no immediate action required")
        return actions
