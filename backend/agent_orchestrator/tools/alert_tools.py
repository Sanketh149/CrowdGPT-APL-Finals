"""
Alert Tools
Google ADK function tools for dispatching crowd safety alerts to operators,
field staff, and public PA systems.
"""

import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# In-memory alert store
_active_alerts: List[Dict] = []
_alert_history: List[Dict] = []


def dispatch_alert_tool(
    severity: str,
    channel: str,
    message: str,
    zone_id: Optional[str] = None,
    actions_required: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    ADK Tool: Dispatch a safety alert to the specified channel.

    Args:
        severity: Alert severity level ('INFO', 'WARNING', 'CRITICAL')
        channel: Delivery channel ('operator', 'field_staff', 'public_pa', 'all')
        message: Alert message text
        zone_id: Optional zone the alert pertains to
        actions_required: Optional list of required actions

    Returns:
        Dispatch confirmation with alert ID and delivery status.
    """
    if severity not in ("INFO", "WARNING", "CRITICAL"):
        severity = "INFO"

    alert_id = f"CG-{severity[:3]}-{uuid.uuid4().hex[:6].upper()}"
    timestamp = datetime.utcnow().isoformat()

    alert = {
        "alert_id": alert_id,
        "severity": severity,
        "channel": channel,
        "message": message,
        "zone_id": zone_id,
        "actions_required": actions_required or [],
        "timestamp": timestamp,
        "status": "dispatched",
        "acknowledged": False,
    }

    # Store in active alerts
    _active_alerts.append(alert)
    _alert_history.append(dict(alert))

    # Keep active alerts manageable
    if len(_active_alerts) > 50:
        _active_alerts.pop(0)

    # Attempt real dispatch (webhook, email, Pub/Sub)
    dispatch_status = _attempt_real_dispatch(alert)
    alert["dispatch_status"] = dispatch_status

    logger.info(
        f"Alert dispatched: [{severity}] {alert_id} → {channel}: "
        f"{message[:80]}..."
    )

    return {
        "alert_id": alert_id,
        "severity": severity,
        "channel": channel,
        "timestamp": timestamp,
        "success": True,
        "dispatch_status": dispatch_status,
    }


def get_active_alerts_tool(
    severity_filter: Optional[str] = None,
    channel_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """
    ADK Tool: Retrieve currently active (unacknowledged) alerts.

    Args:
        severity_filter: Filter by severity ('INFO', 'WARNING', 'CRITICAL')
        channel_filter: Filter by channel

    Returns:
        List of active alerts matching the filters.
    """
    filtered = [a for a in _active_alerts if not a.get("acknowledged")]

    if severity_filter:
        filtered = [a for a in filtered if a["severity"] == severity_filter]
    if channel_filter:
        filtered = [a for a in filtered if a["channel"] == channel_filter]

    return {
        "alerts": filtered,
        "count": len(filtered),
        "critical_count": sum(1 for a in filtered if a["severity"] == "CRITICAL"),
        "timestamp": datetime.utcnow().isoformat(),
    }


def acknowledge_alert_tool(alert_id: str, acknowledged_by: str = "operator") -> Dict[str, Any]:
    """
    ADK Tool: Acknowledge an alert to remove it from the active queue.

    Args:
        alert_id: Alert identifier to acknowledge
        acknowledged_by: Name/role of the person acknowledging

    Returns:
        Acknowledgement confirmation.
    """
    for alert in _active_alerts:
        if alert["alert_id"] == alert_id:
            alert["acknowledged"] = True
            alert["acknowledged_by"] = acknowledged_by
            alert["acknowledged_at"] = datetime.utcnow().isoformat()
            logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
            return {"alert_id": alert_id, "success": True, "acknowledged_by": acknowledged_by}

    return {"alert_id": alert_id, "success": False, "error": "Alert not found"}


def _attempt_real_dispatch(alert: Dict) -> str:
    """
    Try to deliver the alert via a configured webhook or Pub/Sub topic.
    Returns 'delivered', 'queued', or 'simulated'.
    """
    # Try Google Cloud Pub/Sub
    pubsub_topic = os.getenv("ALERT_PUBSUB_TOPIC")
    if pubsub_topic:
        try:
            from google.cloud import pubsub_v1  # type: ignore

            publisher = pubsub_v1.PublisherClient()
            message_data = json.dumps(alert).encode("utf-8")
            future = publisher.publish(pubsub_topic, data=message_data)
            future.result(timeout=5)
            return "delivered_pubsub"
        except Exception as e:
            logger.warning(f"Pub/Sub dispatch failed: {e}")

    # Try webhook
    webhook_url = os.getenv("ALERT_WEBHOOK_URL")
    if webhook_url:
        try:
            import httpx
            resp = httpx.post(webhook_url, json=alert, timeout=5.0)
            if resp.status_code == 200:
                return "delivered_webhook"
        except Exception as e:
            logger.warning(f"Webhook dispatch failed: {e}")

    return "simulated"
