"""
Inference Wrapper for CrowdAnomalyDetector
Loads the saved model checkpoint and returns a risk score (0-1) for
a given set of crowd sensor features.
"""

import logging
import os
from typing import Dict, List, Optional

import numpy as np
import torch

from model import CrowdAnomalyDetector

logger = logging.getLogger(__name__)

DEFAULT_CHECKPOINT = os.path.join(os.path.dirname(__file__), "model_checkpoint.pt")
FEATURE_NAMES = ["density", "flow_magnitude", "acceleration", "gate_pressure"]
SEQUENCE_LENGTH = 20


class CrowdRiskPredictor:
    """
    Wraps a trained CrowdAnomalyDetector for production inference.

    Usage:
        predictor = CrowdRiskPredictor("model_checkpoint.pt")
        risk = predictor.predict({"density": 0.85, "flow_magnitude": 0.6,
                                  "acceleration": 0.3, "gate_pressure": 0.7})
        print(risk)  # 0.823
    """

    def __init__(self, checkpoint_path: str = DEFAULT_CHECKPOINT):
        self.checkpoint_path = checkpoint_path
        self.model: Optional[CrowdAnomalyDetector] = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.feature_min: Optional[np.ndarray] = None
        self.feature_max: Optional[np.ndarray] = None
        self._history: List[List[float]] = []
        self._loaded = False

    def _load(self) -> bool:
        """Load model from checkpoint. Returns True on success."""
        if self._loaded:
            return self.model is not None

        if not os.path.exists(self.checkpoint_path):
            logger.warning(f"Checkpoint not found: {self.checkpoint_path}")
            self._loaded = True
            return False

        try:
            checkpoint = torch.load(self.checkpoint_path, map_location=self.device)
            cfg = checkpoint.get("model_config", {})
            self.model = CrowdAnomalyDetector(
                input_size=cfg.get("input_size", 4),
                hidden_size=cfg.get("hidden_size", 64),
                num_layers=cfg.get("num_layers", 2),
                dropout=cfg.get("dropout", 0.3),
                attention=cfg.get("attention", True),
            )
            self.model.load_state_dict(checkpoint["model_state_dict"])
            self.model.to(self.device)
            self.model.train(False)

            norm = checkpoint.get("normalisation", {})
            if norm:
                self.feature_min = np.array(norm["feature_min"])
                self.feature_max = np.array(norm["feature_max"])

            epoch_loaded = checkpoint.get("epoch", "unknown")
            logger.info(f"Model loaded from {self.checkpoint_path} (epoch={epoch_loaded})")
            self._loaded = True
            return True

        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            self._loaded = True
            return False

    def predict(self, features: Dict[str, float]) -> float:
        """
        Compute risk score for current sensor readings.

        Args:
            features: Dict with keys: density, flow_magnitude, acceleration, gate_pressure
                      All values should be in 0-1 range.

        Returns:
            Float risk score in [0, 1]
        """
        if not self._load() or self.model is None:
            return self._heuristic_score(features)

        # Build feature vector
        feature_vec = [features.get(f, 0.5) for f in FEATURE_NAMES]

        # Apply normalisation if available
        if self.feature_min is not None and self.feature_max is not None:
            arr = np.array(feature_vec, dtype=np.float32)
            rng = self.feature_max - self.feature_min
            rng[rng == 0] = 1
            feature_vec = ((arr - self.feature_min) / rng).tolist()

        # Append to rolling history buffer
        self._history.append(feature_vec)
        if len(self._history) > SEQUENCE_LENGTH:
            self._history.pop(0)

        # Pad with zeros if history shorter than required window
        if len(self._history) < SEQUENCE_LENGTH:
            padding = [[0.0] * len(FEATURE_NAMES)] * (SEQUENCE_LENGTH - len(self._history))
            sequence = padding + self._history
        else:
            sequence = self._history[-SEQUENCE_LENGTH:]

        x = torch.tensor([sequence], dtype=torch.float32).to(self.device)

        with torch.no_grad():
            score = self.model(x)
            return float(score.squeeze().item())

    def predict_sequence(self, feature_sequence: List[Dict[str, float]]) -> float:
        """
        Compute risk score from a full historical sequence.

        Args:
            feature_sequence: List of feature dicts (most recent last).
                              If longer than SEQUENCE_LENGTH, uses most recent entries.

        Returns:
            Float risk score in [0, 1]
        """
        if not self._load() or self.model is None:
            return self._heuristic_score(feature_sequence[-1] if feature_sequence else {})

        rows = [
            [fs.get(f, 0.5) for f in FEATURE_NAMES]
            for fs in feature_sequence[-SEQUENCE_LENGTH:]
        ]

        # Pad if needed
        while len(rows) < SEQUENCE_LENGTH:
            rows.insert(0, [0.0] * len(FEATURE_NAMES))

        x = torch.tensor([rows], dtype=torch.float32).to(self.device)

        with torch.no_grad():
            score = self.model(x)
            return float(score.squeeze().item())

    def reset_history(self) -> None:
        """Clear the rolling history buffer (call between matches)."""
        self._history.clear()

    @staticmethod
    def _heuristic_score(features: Dict[str, float]) -> float:
        """Fallback heuristic when model checkpoint is unavailable."""
        density = features.get("density", 0.5)
        gate_pressure = features.get("gate_pressure", 0.3)
        flow = features.get("flow_magnitude", 0.2)
        accel = features.get("acceleration", 0.1)
        return min(1.0, 0.45 * density + 0.25 * gate_pressure + 0.20 * flow + 0.10 * accel)


def risk_level_label(score: float) -> str:
    """Map a 0-1 risk score to a human-readable level string."""
    if score > 0.75:
        return "CRITICAL"
    if score > 0.50:
        return "ELEVATED"
    if score > 0.25:
        return "CAUTION"
    return "NORMAL"


if __name__ == "__main__":
    predictor = CrowdRiskPredictor()

    test_cases = [
        ("pre_match (low density)",
         {"density": 0.3, "flow_magnitude": 0.4, "acceleration": 0.1, "gate_pressure": 0.2}),
        ("match_start (surge)",
         {"density": 0.85, "flow_magnitude": 0.9, "acceleration": 0.7, "gate_pressure": 0.8}),
        ("mid_match (stable high density)",
         {"density": 0.92, "flow_magnitude": 0.15, "acceleration": 0.05, "gate_pressure": 0.7}),
        ("post_match (evacuation surge)",
         {"density": 0.75, "flow_magnitude": 0.95, "acceleration": 0.85, "gate_pressure": 0.9}),
    ]

    print("CrowdRiskPredictor — Inference Test")
    print("─" * 55)
    for label, feats in test_cases:
        score = predictor.predict(feats)
        level = risk_level_label(score)
        print(f"{label:<42} risk={score:.3f}  [{level}]")
