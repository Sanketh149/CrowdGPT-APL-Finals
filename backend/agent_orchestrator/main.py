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
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from orchestrator import CrowdGuardOrchestrator

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="CrowdGuard Command — Orchestrator",
    description="Multi-agent crowd safety platform for cricket stadiums",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = CrowdGuardOrchestrator()


class RunRequest(BaseModel):
    match_id: str = "IPL_2026_FINAL"
    stadium_id: str = "narendra_modi_stadium"
    phase: str = "mid_match"  # pre_match | match_start | mid_match | post_match
    trigger: str = "scheduled"  # scheduled | manual | alert
    override_data: Optional[Dict[str, Any]] = None


class AgentDecision(BaseModel):
    agent: str
    timestamp: str
    decision: str
    confidence: float
    metadata: Dict[str, Any]


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


@app.get("/stream")
async def stream_agent_decisions():
    """
    SSE endpoint — streams real-time agent decisions as they're produced.
    """
    async def event_generator():
        while True:
            try:
                events = await orchestrator.get_latest_events()
                for event in events:
                    yield f"data: {json.dumps(event)}\n\n"
                await asyncio.sleep(2)
            except asyncio.CancelledError:
                break

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/status")
async def get_system_status():
    """Return current system-wide status summary."""
    return await orchestrator.get_status()


@app.post("/gate/{gate_id}/override")
async def override_gate(gate_id: str, action: str):
    """Manual gate override endpoint (open / close)."""
    if action not in ("open", "close"):
        raise HTTPException(status_code=400, detail="action must be 'open' or 'close'")
    result = await orchestrator.override_gate(gate_id=gate_id, action=action)
    return result


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
