"""
Crowd Stats Aggregator
Combines YOLO detection results and optical flow data into a standardised
crowd_stats.json schema for consumption by the orchestrator agents.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ZoneFlowData(BaseModel):
    average_magnitude: float = 0.0
    dominant_direction_deg: float = 0.0
    dominant_direction_label: str = "N"
    is_surge_detected: bool = False


class CrowdStatsSchema(BaseModel):
    """Canonical schema for crowd statistics emitted by the video processor."""

    zone_id: str
    camera_id: str
    timestamp: str
    phase: str

    # People count
    person_count: int = 0
    density_estimate: float = Field(0.0, ge=0.0, le=1.0)

    # Flow data
    flow: ZoneFlowData = Field(default_factory=ZoneFlowData)

    # Derived indicators
    is_hotspot: bool = False
    risk_contribution: float = Field(0.0, ge=0.0, le=1.0)
    congestion_level: str = "low"  # low | medium | high | critical

    # Raw data reference
    bounding_box_count: int = 0
    frame_dimensions: Dict[str, int] = Field(default_factory=dict)
    model_used: str = "unknown"
    source: str = "video_processor"


def aggregate_crowd_stats(
    detections: Dict[str, Any],
    zone_id: str,
    camera_id: str,
    phase: str,
    flow_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Combine detection + flow results into the canonical CrowdStatsSchema.

    Args:
        detections: Output from YoloAnalyzer.detect_persons()
        zone_id: Stadium zone identifier
        camera_id: Camera that produced the frame
        phase: Match phase
        flow_data: Optional output from compute_optical_flow()

    Returns:
        Serialised CrowdStatsSchema dict.
    """
    person_count = detections.get("person_count", 0)
    density = detections.get("density_estimate", 0.0)

    # Build flow object
    flow_obj = ZoneFlowData()
    if flow_data:
        flow_obj = ZoneFlowData(
            average_magnitude=flow_data.get("average_magnitude", 0.0),
            dominant_direction_deg=flow_data.get("dominant_direction_deg", 0.0),
            dominant_direction_label=flow_data.get("dominant_direction_label", "N"),
            is_surge_detected=flow_data.get("is_surge_detected", False),
        )

    # Derived indicators
    is_hotspot = density > 0.80
    congestion_level = _classify_congestion(density, flow_obj)
    risk_contribution = _compute_risk_contribution(density, flow_obj, phase)

    stats = CrowdStatsSchema(
        zone_id=zone_id,
        camera_id=camera_id,
        timestamp=datetime.utcnow().isoformat(),
        phase=phase,
        person_count=person_count,
        density_estimate=round(density, 4),
        flow=flow_obj,
        is_hotspot=is_hotspot,
        risk_contribution=round(risk_contribution, 4),
        congestion_level=congestion_level,
        bounding_box_count=len(detections.get("bounding_boxes", [])),
        frame_dimensions=detections.get("frame_dimensions", {}),
        model_used=detections.get("model", "unknown"),
    )

    return stats.model_dump()


def _classify_congestion(density: float, flow: ZoneFlowData) -> str:
    """Classify congestion level based on density and flow."""
    if density > 0.90 or (density > 0.75 and flow.is_surge_detected):
        return "critical"
    if density > 0.75 or flow.average_magnitude > 5.0:
        return "high"
    if density > 0.50:
        return "medium"
    return "low"


def _compute_risk_contribution(
    density: float, flow: ZoneFlowData, phase: str
) -> float:
    """
    Compute a 0-1 risk contribution score for this zone.
    Combines density, surge detection, and phase context.
    """
    base_risk = density

    # Surge during high-density phases amplifies risk
    if flow.is_surge_detected:
        base_risk = min(1.0, base_risk * 1.3)

    # Post-match outflow is inherently higher risk at high densities
    if phase == "post_match" and density > 0.6:
        base_risk = min(1.0, base_risk * 1.2)

    # High flow magnitude (rushing) increases risk
    flow_factor = min(0.3, flow.average_magnitude / 20.0)
    return min(1.0, base_risk + flow_factor)


def build_stadium_summary(zone_stats: List[Dict]) -> Dict[str, Any]:
    """
    Aggregate per-zone stats into a stadium-wide summary.
    Used by the orchestrator to get a quick overall view.
    """
    if not zone_stats:
        return {"total_persons": 0, "average_density": 0.0, "hotspot_zones": [], "overall_risk": 0.0}

    total_persons = sum(z.get("person_count", 0) for z in zone_stats)
    avg_density = sum(z.get("density_estimate", 0.0) for z in zone_stats) / len(zone_stats)
    hotspots = [z["zone_id"] for z in zone_stats if z.get("is_hotspot")]
    max_risk = max(z.get("risk_contribution", 0.0) for z in zone_stats)
    critical_zones = [z["zone_id"] for z in zone_stats if z.get("congestion_level") == "critical"]

    return {
        "total_persons": total_persons,
        "average_density": round(avg_density, 3),
        "hotspot_zones": hotspots,
        "critical_zones": critical_zones,
        "overall_risk": round(max_risk, 3),
        "timestamp": datetime.utcnow().isoformat(),
        "zones_monitored": len(zone_stats),
    }
