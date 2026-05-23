"""
Sensor Tools
Google ADK function tools for agents to read crowd density sensor data
from Google Cloud Storage or from the local simulated feed.
"""

import json
import logging
import os
import random
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ── Simulated density profiles per match phase ─────────────────────────────
# Values are fraction of zone capacity (0.0 - 1.0)
PHASE_DENSITY_PROFILES: Dict[str, Dict[str, float]] = {
    "pre_match": {
        "north_stand": 0.35,
        "south_stand": 0.30,
        "east_stand": 0.40,
        "west_stand": 0.25,
        "vip_pavilion": 0.50,
        "media_center": 0.60,
    },
    "match_start": {
        "north_stand": 0.85,
        "south_stand": 0.90,
        "east_stand": 0.75,
        "west_stand": 0.80,
        "vip_pavilion": 0.95,
        "media_center": 0.70,
    },
    "mid_match": {
        "north_stand": 0.92,
        "south_stand": 0.88,
        "east_stand": 0.78,
        "west_stand": 0.82,
        "vip_pavilion": 0.97,
        "media_center": 0.65,
    },
    "post_match": {
        "north_stand": 0.70,
        "south_stand": 0.75,
        "east_stand": 0.65,
        "west_stand": 0.60,
        "vip_pavilion": 0.40,
        "media_center": 0.30,
    },
}

# Zone capacities
ZONE_CAPACITIES = {
    "north_stand": 35000,
    "south_stand": 35000,
    "east_stand": 20000,
    "west_stand": 22000,
    "vip_pavilion": 10000,
    "media_center": 10000,
}


def get_zone_density_tool(zone_id: str, phase: str = "mid_match") -> Dict[str, Any]:
    """
    ADK Tool: Read current crowd density for a specific stadium zone.

    Args:
        zone_id: Zone identifier (e.g., 'north_stand', 'south_stand')
        phase: Match phase ('pre_match', 'match_start', 'mid_match', 'post_match')

    Returns:
        Density data including count, capacity percentage, and trend.
    """
    # Try GCS first, fall back to simulated
    gcs_data = _read_from_gcs(f"crowd_stats/{zone_id}/latest.json")
    if gcs_data:
        return gcs_data

    # Simulated data
    profiles = PHASE_DENSITY_PROFILES.get(phase, PHASE_DENSITY_PROFILES["mid_match"])
    base_density = profiles.get(zone_id, 0.5)
    density = max(0.0, min(1.0, base_density + random.uniform(-0.05, 0.05)))
    capacity = ZONE_CAPACITIES.get(zone_id, 20000)

    return {
        "zone_id": zone_id,
        "timestamp": datetime.utcnow().isoformat(),
        "current_count": int(capacity * density),
        "capacity": capacity,
        "density_pct": round(density, 3),
        "trend": "rising" if phase in ("pre_match", "match_start") else "stable",
        "source": "simulated",
        "phase": phase,
    }


def get_historical_density_tool(zone_id: str, lookback_minutes: int = 30) -> Dict[str, Any]:
    """
    ADK Tool: Get historical density readings for trend analysis.

    Args:
        zone_id: Zone identifier
        lookback_minutes: How many minutes of history to return

    Returns:
        Time-series density data for the specified zone.
    """
    gcs_prefix = f"crowd_stats/{zone_id}/history/"
    gcs_data = _read_from_gcs(f"{gcs_prefix}latest_30min.json")
    if gcs_data:
        return gcs_data

    # Generate realistic synthetic history
    now = datetime.utcnow()
    history = []
    base = 0.6
    for i in range(lookback_minutes, 0, -5):
        ts_offset = i
        density = max(0.1, min(1.0, base + random.gauss(0, 0.03)))
        base = density  # Walk the density forward
        history.append(
            {
                "timestamp": now.isoformat(),
                "density_pct": round(density, 3),
                "minutes_ago": ts_offset,
            }
        )

    return {
        "zone_id": zone_id,
        "history": history,
        "lookback_minutes": lookback_minutes,
        "average_density": round(sum(h["density_pct"] for h in history) / len(history), 3),
        "source": "simulated",
    }


def _read_from_gcs(blob_path: str) -> Optional[Dict]:
    """
    Attempt to read a JSON blob from Google Cloud Storage.
    Returns None if GCS is not configured or the blob doesn't exist.
    """
    bucket_name = os.getenv("GCS_BUCKET_NAME")
    if not bucket_name:
        return None

    try:
        from google.cloud import storage  # type: ignore

        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_path)

        if not blob.exists():
            return None

        data = json.loads(blob.download_as_text())
        logger.debug(f"GCS read: gs://{bucket_name}/{blob_path}")
        return data

    except Exception as e:
        logger.warning(f"GCS read failed for {blob_path}: {e}")
        return None


def write_to_gcs(blob_path: str, data: Dict) -> bool:
    """
    Write JSON data to Google Cloud Storage.
    Returns True on success, False on failure.
    """
    bucket_name = os.getenv("GCS_BUCKET_NAME")
    if not bucket_name:
        logger.debug("GCS_BUCKET_NAME not set — skipping GCS write")
        return False

    try:
        from google.cloud import storage  # type: ignore

        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        blob.upload_from_string(
            json.dumps(data, indent=2), content_type="application/json"
        )
        logger.info(f"GCS write: gs://{bucket_name}/{blob_path}")
        return True

    except Exception as e:
        logger.error(f"GCS write failed for {blob_path}: {e}")
        return False
