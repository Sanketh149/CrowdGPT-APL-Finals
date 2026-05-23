"""
CrowdGuard Command — Orchestrator Service Entry Point
FastAPI app that exposes /run to trigger the full agent pipeline.
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel

from auth import (
    create_jwt,
    exchange_code_for_user,
    get_current_user,
    get_google_auth_url,
    require_super_admin,
)
from broadcast import broadcast_manager
from orchestrator import CrowdGuardOrchestrator

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="CrowdGuard Command — Orchestrator",
    description="Multi-agent crowd safety platform for cricket stadiums",
    version="1.0.0",
)

ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = CrowdGuardOrchestrator()
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")


class RunRequest(BaseModel):
    match_id: str = "IPL_2026_FINAL"
    stadium_id: str = "chinnaswamy_stadium"
    phase: str = "mid_match"  # pre_match | match_start | mid_match | post_match
    trigger: str = "scheduled"  # scheduled | manual | alert
    override_data: Optional[Dict[str, Any]] = None


class AgentDecision(BaseModel):
    agent: str
    timestamp: str
    decision: str
    confidence: float
    metadata: Dict[str, Any]


@app.get("/auth/login")
async def auth_login():
    """Redirect to Google OAuth consent screen."""
    return RedirectResponse(get_google_auth_url(state="crowdguard"))


@app.get("/auth/callback")
async def auth_callback(code: str = "", error: str = "", state: str = ""):
    """Handle Google OAuth callback — issue JWT cookie and redirect to dashboard."""
    if error:
        return RedirectResponse(url=f"{FRONTEND_URL}/login?error=oauth_denied")
    try:
        user = await exchange_code_for_user(code)
    except Exception as e:
        detail = str(e)
        if "not an authorized admin" in detail:
            return RedirectResponse(url=f"{FRONTEND_URL}/login?error=unauthorized")
        return RedirectResponse(url=f"{FRONTEND_URL}/login?error=auth_failed")
    token = create_jwt(user)
    response = RedirectResponse(url=f"{FRONTEND_URL}/dashboard")
    response.set_cookie(
        key="cg_session",
        value=token,
        httponly=True,
        secure=os.getenv("COOKIE_SECURE", "false").lower() == "true",
        samesite="lax",
        max_age=8 * 3600,
    )
    logger.info(f"Login success: {user['email']} ({user['role']})")
    return response


@app.get("/auth/me")
async def auth_me(request: Request):
    """Return current user from JWT cookie — 401 if not authenticated."""
    user = get_current_user(request)
    return {
        "email": user["email"],
        "name": user["name"],
        "picture": user["picture"],
        "role": user["role"],
    }


@app.post("/auth/logout")
async def auth_logout():
    response = JSONResponse({"success": True})
    response.delete_cookie("cg_session")
    return response


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "crowdguard-orchestrator",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/run")
async def run_orchestrator(request: RunRequest):
    """
    Trigger the full multi-agent pipeline for a given match/stadium state.
    Returns structured decisions from all agents.
    """
    logger.info(f"Starting orchestrator run: match={request.match_id}, phase={request.phase}")
    try:
        result = await orchestrator.run(
            match_id=request.match_id,
            stadium_id=request.stadium_id,
            phase=request.phase,
            trigger=request.trigger,
            override_data=request.override_data,
        )
        # Push to all connected stadium screens
        if result.get("protocol") in ("EVACUATE", "LOCKDOWN"):
            pa_alerts = [a for a in result.get("alerts", []) if a.get("channel") == "public_pa"]
            await broadcast_manager.broadcast({
                "type": "emergency",
                "protocol": result["protocol"],
                "timestamp": datetime.utcnow().isoformat(),
                "message": pa_alerts[0]["message"] if pa_alerts else "Emergency protocol activated. Please follow staff instructions.",
                "open_gates": result.get("open_gates", []),
                "run_id": result["run_id"],
            })
        else:
            await broadcast_manager.broadcast({
                "type": "status",
                "protocol": result.get("protocol", "NORMAL"),
                "timestamp": datetime.utcnow().isoformat(),
                "message": None,
            })

        return {
            "status": "completed",
            "run_id": result["run_id"],
            "match_id": request.match_id,
            "timestamp": datetime.utcnow().isoformat(),
            "decisions": result["decisions"],
            "protocol": result["protocol"],
            "alerts": result["alerts"],
        }
    except Exception as e:
        logger.error(f"Orchestrator run failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/broadcast/stream")
async def broadcast_stream():
    """Unauthenticated SSE — stadium screens subscribe here for protocol changes."""
    return StreamingResponse(
        broadcast_manager.stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/broadcast/status")
async def broadcast_status():
    return {
        "connected_screens": broadcast_manager.connected_screens,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/stream")
async def stream_agent_decisions():
    """SSE endpoint — streams real-time agent decisions as they're produced."""
    async def event_generator():
        yield ": connected\n\n"
        while True:
            try:
                events = await orchestrator.get_latest_events()
                for event in events:
                    yield f"data: {json.dumps(event)}\n\n"
                # Heartbeat every 5s to keep connection alive
                yield ": heartbeat\n\n"
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception:
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Access-Control-Allow-Origin": "*"},
    )


@app.get("/status")
async def get_system_status():
    """Return current system-wide status summary."""
    return await orchestrator.get_status()


@app.get("/gates")
async def get_gates(gate_id: str = "ALL"):
    """Return status for all gates or a specific gate."""
    from tools.gate_control import get_gate_status_tool, DEFAULT_GATE_CONFIG
    import random
    data = get_gate_status_tool(gate_id)
    # Enrich with frontend-expected fields
    gates = data.get("gates", [data]) if gate_id == "ALL" else [data]
    enriched = []
    for g in gates:
        gid = g["gate_id"]
        state = g["status"]
        is_emergency = g.get("is_emergency", gid.startswith("E"))
        util = round(random.uniform(0.2, 0.85), 2)
        enriched.append({
            "gate_id": gid,
            "status": state,
            "is_emergency_gate": is_emergency,
            "flow_rate_ppm": random.randint(20, 120),
            "utilisation_pct": util,
            "queue_length": random.randint(0, 40) if util > 0.6 else 0,
            "bottleneck": util > 0.75,
            "timestamp": g.get("timestamp", datetime.utcnow().isoformat()),
        })
    return {"gates": enriched, "total": len(enriched)}


@app.get("/alerts")
async def get_alerts(severity: str = "", channel: str = ""):
    """Return active (unacknowledged) alerts."""
    from tools.alert_tools import get_active_alerts_tool
    return get_active_alerts_tool(
        severity_filter=severity or None,
        channel_filter=channel or None,
    )


@app.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, acknowledged_by: str = "operator"):
    """Acknowledge an alert — removes it from the active queue."""
    from tools.alert_tools import acknowledge_alert_tool
    result = acknowledge_alert_tool(alert_id=alert_id, acknowledged_by=acknowledged_by)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return result


@app.post("/gate/{gate_id}/override")
async def override_gate(gate_id: str, action: str):
    """Manual gate override — open access."""
    if action not in ("open", "close"):
        raise HTTPException(status_code=400, detail="action must be 'open' or 'close'")
    result = await orchestrator.override_gate(gate_id=gate_id, action=action)
    logger.info(f"Gate override: {gate_id} → {action}")
    return result


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
