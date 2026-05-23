"""
Optical Flow Computation
Uses Lucas-Kanade or Farneback dense optical flow to compute crowd
movement direction vectors from consecutive stadium camera frames.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Grid size for dense flow sampling (n x n grid over the frame)
FLOW_GRID_COLS = 8
FLOW_GRID_ROWS = 6

# Farneback optical flow parameters
FARNEBACK_PARAMS = {
    "pyr_scale": 0.5,
    "levels": 3,
    "winsize": 15,
    "iterations": 3,
    "poly_n": 5,
    "poly_sigma": 1.2,
    "flags": 0,
}


def compute_optical_flow(
    prev_frame: np.ndarray,
    curr_frame: np.ndarray,
    method: str = "farneback",
) -> Dict[str, Any]:
    """
    Compute crowd movement vectors between two consecutive frames.

    Args:
        prev_frame: Previous video frame (BGR numpy array)
        curr_frame: Current video frame (BGR numpy array)
        method: 'farneback' (dense) or 'lk' (sparse Lucas-Kanade)

    Returns:
        Dict with flow vectors, magnitude, direction, and movement summary.
    """
    if prev_frame is None or curr_frame is None:
        return _empty_flow_result()

    # Convert to grayscale
    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    curr_gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)

    if method == "lk":
        return _lucas_kanade_flow(prev_gray, curr_gray, curr_frame.shape)
    else:
        return _farneback_flow(prev_gray, curr_gray)


def _farneback_flow(prev_gray: np.ndarray, curr_gray: np.ndarray) -> Dict[str, Any]:
    """Dense optical flow using Gunnar Farneback algorithm."""
    try:
        flow = cv2.calcOpticalFlowFarneback(
            prev_gray, curr_gray, None, **FARNEBACK_PARAMS
        )
        # flow shape: (H, W, 2) — flow[y, x] = (dx, dy)
        mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])

        h, w = prev_gray.shape
        grid_vectors = _sample_grid_vectors(flow, mag, ang, w, h)
        dominant_direction = _dominant_direction(ang, mag)
        avg_magnitude = float(np.mean(mag))
        max_magnitude = float(np.max(mag))

        # Detect crowd surge: high variance in flow = chaotic movement
        flow_variance = float(np.var(mag))
        is_surge = avg_magnitude > 3.0 and flow_variance > 5.0

        return {
            "method": "farneback",
            "grid_vectors": grid_vectors,
            "average_magnitude": round(avg_magnitude, 3),
            "max_magnitude": round(max_magnitude, 3),
            "dominant_direction_deg": round(dominant_direction, 1),
            "dominant_direction_label": _angle_to_label(dominant_direction),
            "flow_variance": round(flow_variance, 3),
            "is_surge_detected": is_surge,
            "frame_dimensions": {"width": w, "height": h},
        }

    except Exception as e:
        logger.error(f"Farneback flow computation failed: {e}")
        return _empty_flow_result()


def _lucas_kanade_flow(
    prev_gray: np.ndarray,
    curr_gray: np.ndarray,
    frame_shape: Tuple,
) -> Dict[str, Any]:
    """Sparse optical flow using Lucas-Kanade with Shi-Tomasi corner detection."""
    try:
        # Detect good feature points to track
        feature_params = dict(maxCorners=200, qualityLevel=0.3, minDistance=7, blockSize=7)
        lk_params = dict(
            winSize=(15, 15),
            maxLevel=2,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03),
        )

        p0 = cv2.goodFeaturesToTrack(prev_gray, mask=None, **feature_params)
        if p0 is None or len(p0) == 0:
            return _empty_flow_result()

        p1, st, err = cv2.calcOpticalFlowPyrLK(prev_gray, curr_gray, p0, None, **lk_params)

        good_new = p1[st == 1]
        good_old = p0[st == 1]

        vectors = []
        magnitudes = []
        angles = []

        for new, old in zip(good_new, good_old):
            x_new, y_new = new.ravel()
            x_old, y_old = old.ravel()
            dx = float(x_new - x_old)
            dy = float(y_new - y_old)
            mag = float(np.sqrt(dx**2 + dy**2))
            angle = float(np.degrees(np.arctan2(dy, dx)) % 360)
            magnitudes.append(mag)
            angles.append(angle)
            vectors.append({
                "x": round(float(x_old), 1),
                "y": round(float(y_old), 1),
                "dx": round(dx, 2),
                "dy": round(dy, 2),
                "magnitude": round(mag, 2),
                "angle_deg": round(angle, 1),
            })

        avg_magnitude = float(np.mean(magnitudes)) if magnitudes else 0.0
        dominant_direction = float(np.mean(angles)) if angles else 0.0

        return {
            "method": "lucas_kanade",
            "vectors": vectors[:50],  # Limit output size
            "tracked_points": len(vectors),
            "average_magnitude": round(avg_magnitude, 3),
            "dominant_direction_deg": round(dominant_direction, 1),
            "dominant_direction_label": _angle_to_label(dominant_direction),
            "is_surge_detected": avg_magnitude > 3.0,
        }

    except Exception as e:
        logger.error(f"LK flow computation failed: {e}")
        return _empty_flow_result()


def _sample_grid_vectors(
    flow: np.ndarray, mag: np.ndarray, ang: np.ndarray, w: int, h: int
) -> List[Dict]:
    """Sample flow vectors at grid points for visualisation."""
    cell_w = w // FLOW_GRID_COLS
    cell_h = h // FLOW_GRID_ROWS
    grid_vectors = []

    for row in range(FLOW_GRID_ROWS):
        for col in range(FLOW_GRID_COLS):
            y_start = row * cell_h
            y_end = y_start + cell_h
            x_start = col * cell_w
            x_end = x_start + cell_w

            cell_flow = flow[y_start:y_end, x_start:x_end]
            cell_mag = mag[y_start:y_end, x_start:x_end]

            avg_dx = float(np.mean(cell_flow[..., 0]))
            avg_dy = float(np.mean(cell_flow[..., 1]))
            avg_mag = float(np.mean(cell_mag))

            grid_vectors.append(
                {
                    "grid_col": col,
                    "grid_row": row,
                    "cx": x_start + cell_w // 2,
                    "cy": y_start + cell_h // 2,
                    "dx": round(avg_dx, 2),
                    "dy": round(avg_dy, 2),
                    "magnitude": round(avg_mag, 3),
                }
            )

    return grid_vectors


def _dominant_direction(ang: np.ndarray, mag: np.ndarray, threshold: float = 0.5) -> float:
    """Compute magnitude-weighted dominant direction in degrees."""
    mask = mag > threshold
    if not np.any(mask):
        return 0.0
    angles_deg = np.degrees(ang[mask])
    weights = mag[mask]
    # Circular mean
    sin_mean = float(np.average(np.sin(np.radians(angles_deg)), weights=weights))
    cos_mean = float(np.average(np.cos(np.radians(angles_deg)), weights=weights))
    return float(np.degrees(np.arctan2(sin_mean, cos_mean)) % 360)


def _angle_to_label(angle_deg: float) -> str:
    """Convert angle in degrees to compass-like directional label."""
    dirs = ["E", "NE", "N", "NW", "W", "SW", "S", "SE"]
    idx = int((angle_deg + 22.5) / 45) % 8
    return dirs[idx]


def _empty_flow_result() -> Dict[str, Any]:
    return {
        "method": "none",
        "grid_vectors": [],
        "average_magnitude": 0.0,
        "dominant_direction_deg": 0.0,
        "dominant_direction_label": "N",
        "is_surge_detected": False,
    }
