# CrowdGuard — Crowd Anomaly Detection Model

## Overview

`CrowdAnomalyDetector` is a PyTorch LSTM model that takes a sliding window of per-minute crowd sensor readings and outputs a continuous **risk score between 0 (safe) and 1 (critical)**.

The model is designed to run as the core inference engine for the `ThreatDetectionAgent` in the CrowdGuard orchestrator, producing risk scores that drive emergency protocol selection.

---

## Model Architecture

```
Input: [batch, 20 timesteps, 4 features]
         └── density, flow_magnitude, acceleration, gate_pressure

  ┌─────────────────────────────────────────┐
  │  Stacked LSTM (2 layers, hidden=64)     │
  │  → All hidden states [batch, T, 64]     │
  └────────────────┬────────────────────────┘
                   │
  ┌────────────────▼────────────────────────┐
  │  Temporal Attention                     │
  │  → Weighted context vector [batch, 64]  │
  └────────────────┬────────────────────────┘
                   │
  ┌────────────────▼────────────────────────┐
  │  FC Head: 64 → 32 → 16 → 1             │
  │  Sigmoid activation → [0, 1]            │
  └─────────────────────────────────────────┘

Output: [batch, 1] — risk score in (0, 1)
```

### Why LSTM?

Crowd safety is inherently a **temporal** problem. A zone at 85% capacity is far more dangerous if density has been *rising for 20 minutes* than if it just briefly spiked. The LSTM captures this temporal context — it learns that a gradual density increase leading into match-start is normal, but a sudden density spike in mid-match is anomalous.

The **attention mechanism** lets the model focus on the most critical time steps in the window, rather than treating all minutes equally.

---

## Features

| Feature | Description | Range |
|---------|-------------|-------|
| `density` | Current zone occupancy as fraction of capacity | 0.0 – 1.0 |
| `flow_magnitude` | Average crowd movement speed (from optical flow) | 0.0 – 1.0 |
| `acceleration` | Rate of change of density per timestep | -1.0 – 1.0 |
| `gate_pressure` | Gate queue length as fraction of max throughput | 0.0 – 1.0 |

---

## Training Data

Training data is generated synthetically by `simulate_data.py` / `dataset.py`.

The simulation covers a full 8-hour match day with 6 stadium zones:

| Phase | Duration | Behaviour |
|-------|----------|-----------|
| `pre_match` | 0–90 min | Gradual inflow, density rising from ~30% |
| `match_start` | 90–150 min | Surge — density peaks at ~88% across all zones |
| `mid_match` | 150–330 min | Stable high density (~92%), minimal movement |
| `match_end` | 330–390 min | Outflow begins |
| `post_match` | 390+ min | Evacuation surge — high flow, falling density |

Anomaly events (labelled):
- **surge_wave**: Sudden density spike in a zone
- **bottleneck_queue**: Gate queue overflow
- **crowd_crush_risk**: Density exceeds 95% with high flow
- **post_match_surge**: Rapid outflow acceleration
- **evacuation_surge**: Full-stadium outflow event
- **heat_emergency**: Density + heat index threshold breach
- **micro_surge**: Random small crowd pulses (~0.8% frequency)

---

## Quick Start

### Install dependencies

```bash
pip install -r requirements.txt
```

### Generate training data

```bash
python simulate_data.py --hours 8 --output simulated_stadium_data.csv
```

### Train the model

```bash
python train.py
# With custom settings:
python train.py --epochs 100 --hidden_size 128 --lr 0.0005
```

This saves `model_checkpoint.pt` to the current directory.

### Run inference

```bash
python predict.py
```

Or programmatically:

```python
from predict import CrowdRiskPredictor

predictor = CrowdRiskPredictor("model_checkpoint.pt")
score = predictor.predict({
    "density": 0.88,
    "flow_magnitude": 0.75,
    "acceleration": 0.4,
    "gate_pressure": 0.82,
})
print(f"Risk score: {score:.3f}")  # e.g., 0.847 → CRITICAL
```

---

## Checkpoint Format

The saved `.pt` file contains:

```python
{
    "model_state_dict": ...,
    "model_config": {
        "input_size": 4,
        "hidden_size": 64,
        "num_layers": 2,
        "dropout": 0.3,
        "attention": True,
    },
    "feature_names": ["density", "flow_magnitude", "acceleration", "gate_pressure"],
    "normalisation": {
        "feature_min": [...],
        "feature_max": [...],
    },
    "epoch": 38,
    "val_loss": 0.004521,
}
```

---

## Integration with Orchestrator

The `ThreatDetectionAgent` loads this model via `predict.CrowdRiskPredictor`:

```python
from predict import CrowdRiskPredictor
predictor = CrowdRiskPredictor()
risk = predictor.predict(sensor_features)
```

The predictor maintains a 20-step rolling history internally, so each call with current readings automatically builds up context over time.
