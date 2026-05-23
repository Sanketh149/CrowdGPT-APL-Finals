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
    """Deliver alert via SendGrid email, Pub/Sub, webhook, or simulation."""

    # 1. SendGrid email — primary for field_staff and public_pa
    sendgrid_key = os.getenv("SENDGRID_API_KEY")
    if sendgrid_key and alert["channel"] in ("field_staff", "public_pa", "all"):
        status = _send_sendgrid_email(alert, sendgrid_key)
        if status == "delivered_email":
            return status

    # 2. Pub/Sub fallback
    pubsub_topic = os.getenv("ALERT_PUBSUB_TOPIC")
    if pubsub_topic:
        try:
            from google.cloud import pubsub_v1  # type: ignore
            publisher = pubsub_v1.PublisherClient()
            future = publisher.publish(pubsub_topic, data=json.dumps(alert).encode())
            future.result(timeout=5)
            return "delivered_pubsub"
        except Exception as e:
            logger.warning(f"Pub/Sub dispatch failed: {e}")

    # 3. Webhook fallback
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


def _send_sendgrid_email(alert: Dict, api_key: str) -> str:
    """Send HTML-formatted alert email via SendGrid."""
    try:
        import sendgrid as sg_module
        from sendgrid.helpers.mail import Mail

        from_email = os.getenv("ALERT_EMAIL_FROM", "alerts@crowdguard.demo")
        to_emails_raw = os.getenv("ALERT_EMAIL_TO", "")
        to_emails = [e.strip() for e in to_emails_raw.split(",") if e.strip()]
        if not to_emails:
            logger.warning("ALERT_EMAIL_TO not configured — skipping email")
            return "skipped_no_recipient"

        severity_emoji = {"INFO": "ℹ️", "WARNING": "⚠️", "CRITICAL": "🚨"}.get(
            alert["severity"], "📢"
        )
        channel_label = alert["channel"].replace("_", " ").title()
        subject = f"{severity_emoji} CrowdGuard [{alert['severity']}] — {channel_label}"

        actions_html = "".join(
            f"<li>{a}</li>" for a in (alert.get("actions_required") or [])
        )
        zone_line = (
            f"<p><strong>Zone:</strong> {alert['zone_id']}</p>"
            if alert.get("zone_id")
            else ""
        )
        accent = (
            "#dc2626"
            if alert["severity"] == "CRITICAL"
            else "#f59e0b"
            if alert["severity"] == "WARNING"
            else "#3b82f6"
        )

        html_body = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;
                    border:2px solid {accent};border-radius:8px;overflow:hidden">
          <div style="background:{accent};color:white;padding:16px 20px">
            <h2 style="margin:0">{severity_emoji} CrowdGuard Command Alert</h2>
            <p style="margin:4px 0 0;opacity:0.9">{alert['severity']} — {channel_label}</p>
          </div>
          <div style="padding:20px;background:#fff">
            <p style="font-size:16px;color:#111">{alert['message']}</p>
            {zone_line}
            <p><strong>Time:</strong> {alert['timestamp']}</p>
            <p><strong>Alert ID:</strong> {alert['alert_id']}</p>
            {'<p><strong>Required Actions:</strong></p><ul style="color:#dc2626">' + actions_html + '</ul>' if actions_html else ''}
          </div>
          <div style="background:#f3f4f6;padding:10px 20px;font-size:12px;color:#6b7280">
            CrowdGuard Command · Narendra Modi Stadium · IPL 2026 Final
          </div>
        </div>
        """

        sg = sg_module.SendGridAPIClient(api_key=api_key)
        message = Mail(
            from_email=from_email,
            to_emails=to_emails,
            subject=subject,
            html_content=html_body,
        )
        response = sg.send(message)
        if response.status_code in (200, 202):
            logger.info(f"SendGrid email delivered to {to_emails}: {alert['alert_id']}")
            return "delivered_email"
        else:
            logger.warning(f"SendGrid returned {response.status_code}")
            return "simulated"
    except Exception as e:
        logger.warning(f"SendGrid dispatch failed: {e}")
        return "simulated"
