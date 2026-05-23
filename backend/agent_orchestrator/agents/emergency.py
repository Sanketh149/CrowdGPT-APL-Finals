"""
Emergency Protocol Agent (SequentialAgent Step 3)
Maps risk scores to playbooks: NORMAL / CAUTION / EVACUATE / LOCKDOWN.
Activates predefined emergency protocols based on threat assessment.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

from google.adk.agents import LlmAgent

from tools.alert_tools import dispatch_alert_tool, get_active_alerts_tool
from tools.gate_control import open_gate_tool

logger = logging.getLogger(__name__)

EMERGENCY_PROMPT = """
You are the Emergency Protocol Specialist for CrowdGuard Command.

Given a risk score and anomaly list from the Threat Detection agent, your job is to:
1. Select the appropriate emergency protocol level.
2. Activate the predefined playbook for that level.
3. Identify which field resources to deploy (marshals, medical, police).
4. Determine which sections of the stadium to alert or clear first.
5. Output a structured activation record.

Protocol levels:
- NORMAL (0-25): Standard operations, maintain monitoring frequency
- CAUTION (26-50): Double monitoring frequency, alert section managers
- EVACUATE (51-75): Controlled evacuation of hotspot zones, open emergency gates
- LOCKDOWN (76-100): Full stadium lockdown, all emergency services activated

Output JSON:
{
  "protocol": "NORMAL|CAUTION|EVACUATE|LOCKDOWN",
  "protocol_code": str,
  "activated_at": str,
  "zones_affected": [str],
  "gates_to_open": [str],
  "resources_deployed": {"marshals": int, "medical": int, "police": int},
  "evacuation_sequence": [{"order": int, "zone": str, "gate": str, "estimated_time_min": int}],
  "public_announcement": str,
  "staff_instructions": str
}
"""

# Predefined playbooks per protocol level
PLAYBOOKS = {
    "NORMAL": {
        "resources": {"marshals": 50, "medical": 5, "police": 10},
        "monitoring_interval_sec": 30,
        "public_announcement": "Welcome to the match. Please proceed to your seats.",
        "staff_instructions": "Standard operations — maintain regular patrol routes",
    },
    "CAUTION": {
        "resources": {"marshals": 100, "medical": 10, "police": 20},
        "monitoring_interval_sec": 10,
        "public_announcement": (
            "Attention: Some areas are experiencing high crowd volumes. "
            "Please follow the guidance of stadium staff."
        ),
        "staff_instructions": "Elevated monitoring — double patrols on hotspot zones, report any crowd surges immediately",
    },
    "EVACUATE": {
        "resources": {"marshals": 250, "medical": 30, "police": 60},
        "monitoring_interval_sec": 5,
        "public_announcement": (
            "IMPORTANT: For your safety, please move calmly towards the nearest exit. "
            "Follow all staff instructions. Do not run."
        ),
        "staff_instructions": (
            "Begin controlled evacuation of hotspot zones. "
            "Open emergency gates E1-E4. Direct crowds to nearest safe exits. "
            "Medical teams to standby at G3, G6, G9."
        ),
        "emergency_gates": ["E1", "E2", "E3", "E4"],
    },
    "LOCKDOWN": {
        "resources": {"marshals": 500, "medical": 60, "police": 150},
        "monitoring_interval_sec": 2,
        "public_announcement": (
            "EMERGENCY: Please remain calm and stay in your seats. "
            "Emergency services are responding. Follow all instructions from security staff."
        ),
        "staff_instructions": (
            "LOCKDOWN ACTIVATED. All entry gates closed immediately. "
            "Emergency exits open. All medical teams deploy. "
            "Police cordon activated. Contact incident commander at +91-XXXX."
        ),
        "emergency_gates": ["E1", "E2", "E3", "E4"],
        "entry_gates_to_close": [f"G{i}" for i in range(1, 13)],
    },
}

# Evacuation sequences for key zones
EVACUATION_SEQUENCES = {
    "north_stand": [
        {"order": 1, "zone": "north_stand_row1", "gate": "G1", "estimated_time_min": 5},
        {"order": 2, "zone": "north_stand_row2", "gate": "G2", "estimated_time_min": 10},
        {"order": 3, "zone": "north_stand_row3", "gate": "E1", "estimated_time_min": 15},
    ],
    "south_stand": [
        {"order": 1, "zone": "south_stand_row1", "gate": "G7", "estimated_time_min": 5},
        {"order": 2, "zone": "south_stand_row2", "gate": "G8", "estimated_time_min": 10},
        {"order": 3, "zone": "south_stand_row3", "gate": "E3", "estimated_time_min": 15},
    ],
}


class EmergencyProtocolAgent:
    """Activates emergency playbooks based on risk score from threat detection."""

    def __init__(self, model: str = "gemini-1.5-pro"):
        self.model = model
        self.agent = LlmAgent(
            name="emergency_protocol_agent",
            model=model,
            description="Activates emergency playbooks based on crowd risk scores",
            instruction=EMERGENCY_PROMPT,
            tools=[dispatch_alert_tool, open_gate_tool, get_active_alerts_tool],
        )

    async def activate(self, state: Dict[str, Any]) -> Dict[str, Any]:
        timestamp = datetime.utcnow().isoformat()

        threat_meta = state.get("threat", {}).get("metadata", {})
        risk_score = threat_meta.get("risk_score", 0)
        anomalies = threat_meta.get("anomalies", [])
        routing_meta = state.get("routing", {}).get("metadata", {})

        protocol = self._select_protocol(risk_score)
        playbook = PLAYBOOKS[protocol]
        zones_affected = [a.get("zone", "unknown") for a in anomalies]
        evacuation_sequence = self._build_evacuation_sequence(zones_affected, protocol)

        gates_to_open = playbook.get("emergency_gates", [])
        if routing_meta.get("gate_actions"):
            for action in routing_meta["gate_actions"]:
                if action.get("action") == "open":
                    gates_to_open.append(action["gate_id"])

        activation_record = {
            "protocol": protocol,
            "protocol_code": f"CG-{protocol[:3]}-{timestamp[:10]}",
            "activated_at": timestamp,
            "risk_score": risk_score,
            "zones_affected": zones_affected,
            "gates_to_open": list(set(gates_to_open)),
            "resources_deployed": playbook["resources"],
            "evacuation_sequence": evacuation_sequence,
            "public_announcement": playbook["public_announcement"],
            "staff_instructions": playbook["staff_instructions"],
            "monitoring_interval_sec": playbook["monitoring_interval_sec"],
        }

        logger.info(
            f"Emergency protocol activated: {protocol} (risk={risk_score}, "
            f"zones={zones_affected})"
        )

        return {
            "agent": "emergency_protocol",
            "timestamp": timestamp,
            "decision": f"Protocol {protocol} activated — risk score {risk_score}/100",
            "confidence": 0.93,
            "metadata": activation_record,
        }

    @staticmethod
    def _select_protocol(risk_score: int) -> str:
        if risk_score <= 25:
            return "NORMAL"
        if risk_score <= 50:
            return "CAUTION"
        if risk_score <= 75:
            return "EVACUATE"
        return "LOCKDOWN"

    def _build_evacuation_sequence(
        self, zones_affected: List[str], protocol: str
    ) -> List[Dict]:
        if protocol not in ("EVACUATE", "LOCKDOWN"):
            return []

        sequence = []
        order = 1
        for zone in zones_affected:
            zone_key = zone.replace("_row1", "").replace("_row2", "").replace("_row3", "")
            if zone_key in EVACUATION_SEQUENCES:
                for step in EVACUATION_SEQUENCES[zone_key]:
                    seq_step = dict(step)
                    seq_step["order"] = order
                    sequence.append(seq_step)
                    order += 1

        # If no specific sequences, add generic stadium-wide evacuation
        if not sequence and protocol == "LOCKDOWN":
            sequence = [
                {"order": 1, "zone": "lower_tier", "gate": "G1-G6", "estimated_time_min": 15},
                {"order": 2, "zone": "upper_tier", "gate": "G7-G12", "estimated_time_min": 25},
                {"order": 3, "zone": "vip_pavilion", "gate": "E1-E2", "estimated_time_min": 10},
            ]

        return sequence
