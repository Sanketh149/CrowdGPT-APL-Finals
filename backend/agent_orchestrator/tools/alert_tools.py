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
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    ADK Tool: Dispatch a safety alert to the specified channel.

    Args:
        severity: Alert severity level ('INFO', 'WARNING', 'CRITICAL')
        channel: Delivery channel ('operator', 'field_staff', 'public_pa', 'all')
        message: Alert message text
        zone_id: Optional zone the alert pertains to
        actions_required: Optional list of required actions
        context: Optional rich context dict (protocol, risk_score, zones, etc.)

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
        "context": context or {},
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
        subject = f"{severity_emoji} CrowdGuard [{alert['severity']}] — {channel_label} · IPL 2026 Final"

        ctx = alert.get("context", {})
        protocol = ctx.get("protocol", "NORMAL")
        risk_score = ctx.get("risk_score", 0)
        anomalies = ctx.get("anomalies", [])
        gate_actions = ctx.get("gate_actions", [])
        zones = ctx.get("zones", [])
        hotspots = ctx.get("hotspots", [])
        resources = ctx.get("resources_deployed", {})
        phase = ctx.get("phase", "").replace("_", " ").title()
        match_id = ctx.get("match_id", "IPL_2026_FINAL")

        accent = (
            "#dc2626" if alert["severity"] == "CRITICAL"
            else "#f59e0b" if alert["severity"] == "WARNING"
            else "#3b82f6"
        )
        accent_light = (
            "#fef2f2" if alert["severity"] == "CRITICAL"
            else "#fffbeb" if alert["severity"] == "WARNING"
            else "#eff6ff"
        )
        protocol_color = {
            "EVACUATE": "#dc2626", "LOCKDOWN": "#7c3aed",
            "CAUTION": "#f59e0b", "NORMAL": "#16a34a",
        }.get(protocol, "#6b7280")

        # Zone density table rows
        zone_rows = ""
        for z in zones:
            pct = int(float(z.get("capacity_pct", 0)) * 100)
            bar_color = (
                "#dc2626" if pct > 90 else "#f97316" if pct > 75
                else "#eab308" if pct > 60 else "#22c55e"
            )
            is_hot = z.get("zone_id") in hotspots
            hot_badge = ' <span style="background:#f59e0b;color:#000;font-size:10px;padding:1px 5px;border-radius:3px;font-weight:bold">HOTSPOT</span>' if is_hot else ""
            zone_rows += f"""
            <tr style="border-bottom:1px solid #e5e7eb">
              <td style="padding:6px 10px;font-size:13px">{z.get("label", z.get("zone_id",""))}{hot_badge}</td>
              <td style="padding:6px 10px;font-size:13px;text-align:center">
                {z.get("current_count", "—"):,} / {z.get("capacity", "—"):,}
              </td>
              <td style="padding:6px 10px">
                <div style="background:#e5e7eb;border-radius:4px;height:10px;width:100px">
                  <div style="background:{bar_color};height:10px;border-radius:4px;width:{min(pct,100)}%"></div>
                </div>
              </td>
              <td style="padding:6px 10px;font-size:13px;font-weight:bold;color:{bar_color};text-align:right">{pct}%</td>
            </tr>"""

        zone_section = f"""
        <h3 style="font-size:14px;color:#374151;margin:20px 0 8px">Zone Density Breakdown</h3>
        <table style="width:100%;border-collapse:collapse;font-family:Arial,sans-serif;border:1px solid #e5e7eb;border-radius:6px;overflow:hidden">
          <thead>
            <tr style="background:#f9fafb">
              <th style="padding:6px 10px;text-align:left;font-size:12px;color:#6b7280">Zone</th>
              <th style="padding:6px 10px;text-align:center;font-size:12px;color:#6b7280">Occupancy</th>
              <th style="padding:6px 10px;text-align:left;font-size:12px;color:#6b7280">Density</th>
              <th style="padding:6px 10px;text-align:right;font-size:12px;color:#6b7280">%</th>
            </tr>
          </thead>
          <tbody>{zone_rows}</tbody>
        </table>""" if zone_rows else ""

        anomaly_rows = "".join(
            f'<li style="margin-bottom:4px"><strong>{a.get("type","Anomaly")}</strong> detected in <em>{a.get("zone","unknown zone")}</em>'
            + (f' — severity: {a.get("severity","")}' if a.get("severity") else "") + "</li>"
            for a in anomalies
        )
        anomaly_section = f"""
        <h3 style="font-size:14px;color:#374151;margin:20px 0 8px">⚠️ Detected Anomalies</h3>
        <ul style="margin:0;padding-left:20px;color:#b45309">{anomaly_rows}</ul>""" if anomaly_rows else ""

        gate_rows = "".join(
            f'<li style="margin-bottom:4px">Gate <strong>{g.get("gate_id","")}</strong> → <strong>{g.get("action","").upper()}</strong>'
            + (f' ({g.get("reason","")})' if g.get("reason") else "") + "</li>"
            for g in gate_actions[:8]
        )
        gate_section = f"""
        <h3 style="font-size:14px;color:#374151;margin:20px 0 8px">🚪 Gate Reconfigurations</h3>
        <ul style="margin:0;padding-left:20px;color:#1d4ed8">{gate_rows}</ul>""" if gate_rows else ""

        resources_html = ""
        if resources:
            res_items = "".join(
                f'<span style="display:inline-block;background:#e5e7eb;border-radius:4px;padding:3px 8px;margin:2px;font-size:12px">'
                f'<strong>{v}</strong> {k.replace("_"," ").title()}</span>'
                for k, v in resources.items() if v
            )
            resources_html = f"""
            <h3 style="font-size:14px;color:#374151;margin:20px 0 8px">🚑 Resources Deployed</h3>
            <div>{res_items}</div>"""

        actions_html = "".join(
            f'<li style="margin-bottom:6px;padding:6px 10px;background:{accent_light};border-left:3px solid {accent};border-radius:0 4px 4px 0">{a}</li>'
            for a in (alert.get("actions_required") or []) if a
        )
        actions_section = f"""
        <h3 style="font-size:14px;color:#374151;margin:20px 0 8px">✅ Required Actions</h3>
        <ul style="margin:0;padding:0;list-style:none">{actions_html}</ul>""" if actions_html else ""

        # IST timestamp
        from datetime import timezone, timedelta
        ist = datetime.now(timezone(timedelta(hours=5, minutes=30)))
        ist_str = ist.strftime("%d %b %Y, %I:%M:%S %p IST")

        html_body = f"""
        <div style="font-family:Arial,sans-serif;max-width:620px;margin:0 auto;background:#ffffff;border:1px solid #e5e7eb;border-radius:10px;overflow:hidden">

          <!-- Header -->
          <div style="background:linear-gradient(135deg,#0f172a 0%,#1e3a5f 100%);padding:24px 28px;color:white">
            <div style="display:flex;align-items:center;justify-content:space-between">
              <div>
                <p style="margin:0;font-size:11px;letter-spacing:2px;opacity:0.6;text-transform:uppercase">CrowdGuard Command</p>
                <h1 style="margin:4px 0 0;font-size:22px;font-weight:800">{severity_emoji} Safety Alert</h1>
              </div>
              <div style="text-align:right">
                <span style="background:{protocol_color};color:white;font-size:13px;font-weight:bold;padding:4px 12px;border-radius:20px">{protocol}</span>
                <p style="margin:6px 0 0;font-size:11px;opacity:0.6">{match_id}</p>
              </div>
            </div>
          </div>

          <!-- Alert banner -->
          <div style="background:{accent};padding:14px 28px;color:white">
            <p style="margin:0;font-size:15px;font-weight:600">{alert['message']}</p>
          </div>

          <!-- Key metrics -->
          <div style="display:flex;gap:0;border-bottom:1px solid #e5e7eb">
            <div style="flex:1;padding:16px 20px;text-align:center;border-right:1px solid #e5e7eb">
              <p style="margin:0;font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:1px">Severity</p>
              <p style="margin:4px 0 0;font-size:18px;font-weight:800;color:{accent}">{alert['severity']}</p>
            </div>
            <div style="flex:1;padding:16px 20px;text-align:center;border-right:1px solid #e5e7eb">
              <p style="margin:0;font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:1px">Risk Score</p>
              <p style="margin:4px 0 0;font-size:18px;font-weight:800;color:{accent}">{risk_score}<span style="font-size:12px;font-weight:400;color:#6b7280">/100</span></p>
            </div>
            <div style="flex:1;padding:16px 20px;text-align:center;border-right:1px solid #e5e7eb">
              <p style="margin:0;font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:1px">Channel</p>
              <p style="margin:4px 0 0;font-size:18px;font-weight:800;color:#111">{channel_label}</p>
            </div>
            <div style="flex:1;padding:16px 20px;text-align:center">
              <p style="margin:0;font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:1px">Match Phase</p>
              <p style="margin:4px 0 0;font-size:14px;font-weight:700;color:#111">{phase}</p>
            </div>
          </div>

          <!-- Body -->
          <div style="padding:24px 28px">
            {zone_section}
            {anomaly_section}
            {gate_section}
            {resources_html}
            {actions_section}

            <!-- Meta -->
            <div style="margin-top:24px;padding:12px 16px;background:#f9fafb;border-radius:6px;font-size:12px;color:#6b7280">
              <p style="margin:0"><strong>Alert ID:</strong> {alert['alert_id']}</p>
              <p style="margin:4px 0 0"><strong>Generated:</strong> {ist_str}</p>
              {'<p style="margin:4px 0 0"><strong>Zone:</strong> ' + alert['zone_id'] + '</p>' if alert.get('zone_id') else ''}
              {'<p style="margin:4px 0 0"><strong>Hotspots:</strong> ' + ", ".join(hotspots) + '</p>' if hotspots else ''}
            </div>
          </div>

          <!-- Footer -->
          <div style="background:#0f172a;padding:14px 28px;display:flex;align-items:center;justify-content:space-between">
            <p style="margin:0;font-size:11px;color:#6b7280">CrowdGPT · M. Chinnaswamy Stadium, Bangalore</p>
            <p style="margin:0;font-size:11px;color:#6b7280">IPL 2026 Final · Capacity 132,000</p>
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
