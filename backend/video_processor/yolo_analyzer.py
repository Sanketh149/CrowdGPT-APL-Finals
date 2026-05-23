"""
YOLO Analyzer
YOLOv8 person detection on stadium camera frames.
Returns person count and bounding boxes per zone.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# YOLOv8 COCO class index for 'person'
PERSON_CLASS_ID = 0

# Stadium zone bounding regions (normalised 0-1 fractions of frame dimensions)
# These map camera FOV regions to stadium zones
ZONE_REGIONS = {
    "north_stand": (0.0, 0.0, 1.0, 0.4),    # top 40% of frame
    "south_stand": (0.0, 0.6, 1.0, 1.0),    # bottom 40% of frame
    "east_stand":  (0.6, 0.0, 1.0, 1.0),    # right 40% of frame
    "west_stand":  (0.0, 0.0, 0.4, 1.0),    # left 40% of frame
    "vip_pavilion": (0.3, 0.3, 0.7, 0.7),   # centre region
    "media_center": (0.4, 0.0, 0.6, 0.2),   # top-centre
}


class YoloAnalyzer:
    """
    Wraps Ultralytics YOLOv8 for crowd detection.
    Supports yolov8n (nano), yolov8s (small), yolov8m (medium).
    """

    def __init__(self, model_size: str = "yolov8n"):
        self.model_size = model_size
        self._model = None
        self._model_loaded = False

    def _load_model(self):
        """Lazy-load YOLOv8 model on first use."""
        if self._model_loaded:
            return

        try:
            from ultralytics import YOLO  # type: ignore

            self._model = YOLO(f"{self.model_size}.pt")
            self._model_loaded = True
            logger.info(f"YOLOv8 model loaded: {self.model_size}")
        except Exception as e:
            logger.error(f"Failed to load YOLOv8: {e}")
            self._model = None
            self._model_loaded = True  # Mark as attempted

    def detect_persons(
        self,
        image_path: str,
        zone_id: str = "unknown",
        confidence_threshold: float = 0.35,
    ) -> Dict[str, Any]:
        """
        Run YOLOv8 detection on a single frame.

        Args:
            image_path: Path to the image file
            zone_id: Stadium zone this camera covers
            confidence_threshold: Minimum detection confidence

        Returns:
            Dict with person_count, bounding_boxes, density_estimate, zone_id
        """
        self._load_model()

        # Load image
        frame = cv2.imread(image_path)
        if frame is None:
            logger.error(f"Could not read image: {image_path}")
            return self._empty_result(zone_id)

        h, w = frame.shape[:2]

        if self._model is not None:
            return self._run_yolo_detection(frame, w, h, zone_id, confidence_threshold)
        else:
            # Fallback: simple motion-based heuristic
            return self._heuristic_detection(frame, w, h, zone_id)

    def _run_yolo_detection(
        self,
        frame: np.ndarray,
        width: int,
        height: int,
        zone_id: str,
        confidence_threshold: float,
    ) -> Dict[str, Any]:
        """Run actual YOLOv8 inference."""
        results = self._model(frame, classes=[PERSON_CLASS_ID], conf=confidence_threshold, verbose=False)

        bounding_boxes = []
        for result in results:
            for box in result.boxes:
                conf = float(box.conf[0])
                cls = int(box.cls[0])
                if cls == PERSON_CLASS_ID and conf >= confidence_threshold:
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                    bounding_boxes.append(
                        {
                            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                            "confidence": round(conf, 3),
                            "cx": (x1 + x2) // 2,
                            "cy": (y1 + y2) // 2,
                        }
                    )

        # Cluster density by sub-zone
        sub_zone_counts = self._count_by_region(bounding_boxes, width, height, zone_id)
        density = self._estimate_density(len(bounding_boxes), width, height)

        return {
            "zone_id": zone_id,
            "person_count": len(bounding_boxes),
            "bounding_boxes": bounding_boxes,
            "density_estimate": density,
            "sub_zone_counts": sub_zone_counts,
            "frame_dimensions": {"width": width, "height": height},
            "model": self.model_size,
        }

    def _heuristic_detection(
        self,
        frame: np.ndarray,
        width: int,
        height: int,
        zone_id: str,
    ) -> Dict[str, Any]:
        """
        Simple crowd density heuristic using pixel brightness variance.
        Used as fallback when YOLO is unavailable.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        variance = float(np.var(gray))
        # High variance typically means more people / movement
        estimated_count = int(variance * 0.05)
        density = min(1.0, estimated_count / 500)

        return {
            "zone_id": zone_id,
            "person_count": estimated_count,
            "bounding_boxes": [],
            "density_estimate": round(density, 3),
            "sub_zone_counts": {},
            "frame_dimensions": {"width": width, "height": height},
            "model": "heuristic",
        }

    @staticmethod
    def _count_by_region(
        boxes: List[Dict], width: int, height: int, zone_id: str
    ) -> Dict[str, int]:
        """Count persons per sub-region of the frame."""
        counts: Dict[str, int] = {}
        region = ZONE_REGIONS.get(zone_id, (0, 0, 1, 1))
        rx1, ry1, rx2, ry2 = (
            int(region[0] * width),
            int(region[1] * height),
            int(region[2] * width),
            int(region[3] * height),
        )
        in_zone = 0
        out_zone = 0
        for box in boxes:
            cx, cy = box["cx"], box["cy"]
            if rx1 <= cx <= rx2 and ry1 <= cy <= ry2:
                in_zone += 1
            else:
                out_zone += 1
        counts["in_zone"] = in_zone
        counts["out_of_zone"] = out_zone
        return counts

    @staticmethod
    def _estimate_density(person_count: int, width: int, height: int) -> float:
        """Estimate crowd density as persons per 100 sq pixels (normalised 0-1)."""
        area = width * height
        if area == 0:
            return 0.0
        # Assume avg person occupies ~4000 px at typical stadium camera distance
        avg_person_area = 4000
        max_persons = area / avg_person_area
        return min(1.0, round(person_count / max(max_persons, 1), 3))

    @staticmethod
    def _empty_result(zone_id: str) -> Dict[str, Any]:
        return {
            "zone_id": zone_id,
            "person_count": 0,
            "bounding_boxes": [],
            "density_estimate": 0.0,
            "sub_zone_counts": {},
            "frame_dimensions": {"width": 0, "height": 0},
            "model": "none",
            "error": "Image could not be read",
        }
