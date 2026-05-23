"""Generate a trained model checkpoint with synthetic data."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from model import CrowdAnomalyDetector


def generate_synthetic_data(n_samples=2000, seq_len=20, n_features=4):
    X, y = [], []
    for _ in range(n_samples):
        density = np.random.uniform(0.1, 1.0)
        flow = np.random.uniform(0.0, 1.0)
        accel = np.random.uniform(0.0, 1.0)
        gate_p = np.random.uniform(0.0, 1.0)

        seq = []
        for t in range(seq_len):
            noise = np.random.normal(0, 0.03, n_features)
            step = np.clip([density, flow, accel, gate_p] + noise, 0, 1)
            # Add gradual trend
            density = np.clip(density + np.random.normal(0, 0.02), 0.05, 1.0)
            seq.append(step.tolist())

        # Risk label: weighted combination
        risk = 0.45 * density + 0.25 * gate_p + 0.20 * flow + 0.10 * accel
        risk = float(np.clip(risk, 0, 1))
        X.append(seq)
        y.append([risk])
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)


X, y = generate_synthetic_data()
feature_min = X.reshape(-1, 4).min(axis=0).tolist()
feature_max = X.reshape(-1, 4).max(axis=0).tolist()

split = int(0.8 * len(X))
X_train, y_train = torch.tensor(X[:split]), torch.tensor(y[:split])
X_val, y_val = torch.tensor(X[split:]), torch.tensor(y[split:])

model = CrowdAnomalyDetector(
    input_size=4, hidden_size=64, num_layers=2, dropout=0.3, attention=True
)
optimizer = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
criterion = nn.MSELoss()

loader = DataLoader(TensorDataset(X_train, y_train), batch_size=64, shuffle=True)

print("Training LSTM model...")
for epoch in range(30):
    model.train()
    total_loss = 0
    for xb, yb in loader:
        optimizer.zero_grad()
        pred = model(xb)
        loss = criterion(pred, yb)
        loss.backward()
        optimizer.step()
        total_loss += loss.item()
    if (epoch + 1) % 10 == 0:
        model.eval()
        with torch.no_grad():
            val_loss = criterion(model(X_val), y_val).item()
        print(
            f"  Epoch {epoch+1}/30 "
            f"train_loss={total_loss/len(loader):.4f}  val_loss={val_loss:.4f}"
        )

checkpoint_path = os.path.join(os.path.dirname(__file__), "model_checkpoint.pt")
torch.save(
    {
        "epoch": 30,
        "model_state_dict": model.state_dict(),
        "model_config": {
            "input_size": 4,
            "hidden_size": 64,
            "num_layers": 2,
            "dropout": 0.3,
            "attention": True,
        },
        "normalisation": {"feature_min": feature_min, "feature_max": feature_max},
    },
    checkpoint_path,
)
print(f"Checkpoint saved to {checkpoint_path}")
