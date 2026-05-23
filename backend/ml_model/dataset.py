"""
Stadium Crowd Dataset
Generates synthetic training data for the CrowdAnomalyDetector.
Simulates per-minute sensor readings across multiple stadium zones
for all match phases, with realistic anomaly events labelled.
"""

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset
from typing import Tuple


# ── Simulation parameters ───────────────────────────────────────────────────

SEQUENCE_LENGTH = 20   # How many timesteps per training sample
FEATURE_NAMES = ["density", "flow_magnitude", "acceleration", "gate_pressure"]

# Risk threshold for binary anomaly label
ANOMALY_THRESHOLD = 0.65


class StadiumCrowdDataset(Dataset):
    """
    PyTorch Dataset wrapping the synthetic stadium sensor data.

    Each sample is a (sequence, label) pair:
        sequence: FloatTensor [seq_len, 4] — normalised sensor features
        label:    FloatTensor [1]          — risk score in [0, 1]
    """

    def __init__(
        self,
        df: pd.DataFrame,
        sequence_length: int = SEQUENCE_LENGTH,
        normalise: bool = True,
    ):
        self.seq_len = sequence_length
        self.features = FEATURE_NAMES
        self.data = df[self.features].values.astype(np.float32)
        self.labels = df["risk_score"].values.astype(np.float32)

        if normalise:
            # Min-max normalise each feature independently
            self.feature_min = self.data.min(axis=0)
            self.feature_max = self.data.max(axis=0)
            rng = self.feature_max - self.feature_min
            rng[rng == 0] = 1  # Avoid div by zero
            self.data = (self.data - self.feature_min) / rng

        # Build sliding window indices
        self.indices = list(range(len(self.data) - sequence_length))

    def __len__(self) -> int:
        return len(self.indices)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        start = self.indices[idx]
        end = start + self.seq_len
        x = torch.tensor(self.data[start:end], dtype=torch.float32)
        # Label is the risk score at the END of the window (predict current risk)
        y = torch.tensor([self.labels[end - 1]], dtype=torch.float32)
        return x, y


def generate_simulation_df(
    n_hours: int = 8,
    zones: int = 6,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generate a synthetic DataFrame of per-minute crowd sensor readings.
    Covers a full match day: pre_match → match_start → mid_match → post_match.
    Includes labelled anomaly events.

    Returns a pd.DataFrame with columns:
        timestamp, zone_id, phase, density, flow_magnitude, acceleration,
        gate_pressure, risk_score, is_anomaly, anomaly_type
    """
    rng = np.random.default_rng(seed)
    minutes_total = n_hours * 60
    records = []

    zone_ids = [
        "north_stand", "south_stand", "east_stand",
        "west_stand", "vip_pavilion", "media_center",
    ][:zones]

    for zone_idx, zone_id in enumerate(zone_ids):
        # Per-zone base density multiplier (VIP slightly higher base)
        base_mult = 1.0 + (zone_idx * 0.05)

        density = 0.1
        flow_mag = 0.1
        accel = 0.0
        gate_pressure = 0.1

        for t in range(minutes_total):
            phase, phase_density_target, phase_flow_target = _get_phase_targets(t, zone_id)

            # Smooth exponential move towards phase target
            density += 0.03 * (phase_density_target * base_mult - density) + rng.normal(0, 0.01)
            density = float(np.clip(density, 0.0, 1.0))

            flow_mag += 0.05 * (phase_flow_target - flow_mag) + rng.normal(0, 0.02)
            flow_mag = float(np.clip(flow_mag, 0.0, 1.0))

            # Acceleration = rate of change of density (delta)
            accel = float(np.clip(0.7 * accel + 0.3 * (density - (density - rng.normal(0, 0.02))), -1, 1))

            gate_pressure += 0.04 * (density - gate_pressure) + rng.normal(0, 0.01)
            gate_pressure = float(np.clip(gate_pressure, 0.0, 1.0))

            # Inject anomaly events
            is_anomaly, anomaly_type, anomaly_boost = _inject_anomaly(t, zone_id, rng)
            if is_anomaly:
                density = float(np.clip(density + anomaly_boost, 0.0, 1.0))
                flow_mag = float(np.clip(flow_mag + anomaly_boost * 0.8, 0.0, 1.0))

            # Risk score: weighted combination
            risk_score = float(
                0.45 * density
                + 0.25 * gate_pressure
                + 0.20 * flow_mag
                + 0.10 * abs(accel)
                + (0.3 if is_anomaly else 0.0)
            )
            risk_score = float(np.clip(risk_score, 0.0, 1.0))

            records.append({
                "minute": t,
                "zone_id": zone_id,
                "phase": phase,
                "density": round(density, 4),
                "flow_magnitude": round(flow_mag, 4),
                "acceleration": round(accel, 4),
                "gate_pressure": round(gate_pressure, 4),
                "risk_score": round(risk_score, 4),
                "is_anomaly": is_anomaly,
                "anomaly_type": anomaly_type or "none",
            })

    return pd.DataFrame(records)


def _get_phase_targets(minute: int, zone_id: str) -> Tuple[str, float, float]:
    """Return (phase_name, density_target, flow_magnitude_target) for a given minute."""
    # Match schedule (8-hour day): gates open → match → post
    if minute < 90:
        return "pre_match", 0.35, 0.45
    if minute < 150:
        return "match_start", 0.88, 0.80
    if minute < 330:
        return "mid_match", 0.92, 0.20
    if minute < 390:
        return "match_end", 0.75, 0.70
    return "post_match", 0.40, 0.90


def _inject_anomaly(
    minute: int, zone_id: str, rng: np.random.Generator
) -> Tuple[bool, str, float]:
    """
    Deterministically inject anomaly events at specific times.
    Returns (is_anomaly, anomaly_type, density_boost).
    """
    anomaly_schedule = [
        # (minute, zone_id_pattern, anomaly_type, density_boost)
        (100, "north_stand",  "surge_wave",         0.20),
        (145, "south_stand",  "bottleneck_queue",    0.18),
        (200, "east_stand",   "crowd_crush_risk",    0.25),
        (310, "west_stand",   "post_match_surge",    0.22),
        (350, "north_stand",  "evacuation_surge",    0.28),
        (370, "south_stand",  "heat_emergency",      0.15),
        (400, "vip_pavilion", "medical_emergency",   0.10),
    ]

    for (target_minute, zone_pattern, atype, boost) in anomaly_schedule:
        if abs(minute - target_minute) <= 3 and zone_pattern in zone_id:
            # Add stochastic jitter to the boost
            actual_boost = boost * (1.0 + rng.uniform(-0.1, 0.1))
            return True, atype, float(actual_boost)

    # Random low-probability micro-anomalies
    if rng.random() < 0.008:
        return True, "micro_surge", float(rng.uniform(0.05, 0.12))

    return False, None, 0.0


def train_val_split(
    df: pd.DataFrame,
    val_fraction: float = 0.2,
    sequence_length: int = SEQUENCE_LENGTH,
) -> Tuple[StadiumCrowdDataset, StadiumCrowdDataset]:
    """Split the dataframe into train and validation datasets (time-ordered split)."""
    split_idx = int(len(df) * (1 - val_fraction))
    train_df = df.iloc[:split_idx].reset_index(drop=True)
    val_df = df.iloc[split_idx:].reset_index(drop=True)

    # Compute normalisation stats on train, apply to val
    train_ds = StadiumCrowdDataset(train_df, sequence_length=sequence_length, normalise=True)
    val_ds = StadiumCrowdDataset(val_df, sequence_length=sequence_length, normalise=True)

    # Override val normalisation with train stats for consistency
    val_ds.feature_min = train_ds.feature_min
    val_ds.feature_max = train_ds.feature_max
    rng = train_ds.feature_max - train_ds.feature_min
    rng[rng == 0] = 1
    val_ds.data = (
        pd.DataFrame(val_df[FEATURE_NAMES].values.astype(np.float32)).values - train_ds.feature_min
    ) / rng

    return train_ds, val_ds


if __name__ == "__main__":
    df = generate_simulation_df(n_hours=8, zones=6)
    print(f"Generated {len(df):,} rows across {df['zone_id'].nunique()} zones")
    print(f"Anomaly rate: {df['is_anomaly'].mean():.1%}")
    print(f"Anomaly types: {df[df['is_anomaly']]['anomaly_type'].value_counts().to_dict()}")
    print(df.head(5).to_string())
