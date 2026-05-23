"""
CrowdAnomalyDetector — PyTorch LSTM Model
Time-series anomaly detection for stadium crowd density.

Input:  [batch_size, timesteps, 4_features]
         Features: density, flow_magnitude, acceleration, gate_pressure
Output: [batch_size, 1] — risk score in [0, 1]
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class CrowdAnomalyDetector(nn.Module):
    """
    LSTM-based sequence model that takes a window of crowd sensor readings
    and outputs a continuous risk score between 0 (safe) and 1 (critical).

    Architecture:
        1. Stacked LSTM (2 layers) to capture temporal crowd dynamics
        2. Attention over LSTM hidden states to focus on critical time steps
        3. Fully connected head for risk score regression
    """

    INPUT_FEATURES = 4   # density, flow_magnitude, acceleration, gate_pressure
    OUTPUT_DIM = 1        # risk score 0-1

    def __init__(
        self,
        input_size: int = 4,
        hidden_size: int = 64,
        num_layers: int = 2,
        dropout: float = 0.3,
        attention: bool = True,
    ):
        super().__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.use_attention = attention

        # LSTM layers
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
            bidirectional=False,
        )

        # Attention mechanism — learnable weight over all timesteps
        self.attention_weight = nn.Linear(hidden_size, 1)

        # Classifier head
        self.dropout = nn.Dropout(dropout)
        self.fc1 = nn.Linear(hidden_size, 32)
        self.fc2 = nn.Linear(32, 16)
        self.output = nn.Linear(16, self.OUTPUT_DIM)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: Tensor of shape [batch_size, timesteps, input_size]

        Returns:
            risk_score: Tensor of shape [batch_size, 1], values in (0, 1)
        """
        # LSTM forward pass — all hidden states
        lstm_out, (h_n, _) = self.lstm(x)
        # lstm_out: [batch, timesteps, hidden_size]

        if self.use_attention:
            # Compute attention weights over all timesteps
            attn_scores = self.attention_weight(lstm_out)          # [batch, T, 1]
            attn_weights = F.softmax(attn_scores, dim=1)           # [batch, T, 1]
            context = torch.sum(lstm_out * attn_weights, dim=1)    # [batch, hidden]
        else:
            # Use only the final hidden state
            context = lstm_out[:, -1, :]   # [batch, hidden]

        # Classification head
        out = self.dropout(context)
        out = F.relu(self.fc1(out))
        out = self.dropout(out)
        out = F.relu(self.fc2(out))
        risk_score = torch.sigmoid(self.output(out))   # [batch, 1] in (0,1)

        return risk_score

    def predict_risk(self, x: torch.Tensor) -> float:
        """
        Convenience method for single-batch inference.

        Args:
            x: Tensor [timesteps, input_size] or [1, timesteps, input_size]

        Returns:
            Float risk score in [0, 1]
        """
        self.eval()
        with torch.no_grad():
            if x.dim() == 2:
                x = x.unsqueeze(0)  # Add batch dim
            score = self.forward(x)
            return float(score.squeeze())


class CrowdAnomalyDetectorConfig:
    """Default hyperparameters for the CrowdAnomalyDetector."""

    input_size: int = 4
    hidden_size: int = 64
    num_layers: int = 2
    dropout: float = 0.3
    attention: bool = True
    sequence_length: int = 20    # 20 time steps (e.g., 20 minutes of readings)
    batch_size: int = 64
    learning_rate: float = 1e-3
    weight_decay: float = 1e-4
    epochs: int = 50
    feature_names = ["density", "flow_magnitude", "acceleration", "gate_pressure"]


def build_model(config: "CrowdAnomalyDetectorConfig" = None) -> CrowdAnomalyDetector:
    """Factory function to build model from config."""
    cfg = config or CrowdAnomalyDetectorConfig()
    return CrowdAnomalyDetector(
        input_size=cfg.input_size,
        hidden_size=cfg.hidden_size,
        num_layers=cfg.num_layers,
        dropout=cfg.dropout,
        attention=cfg.attention,
    )


if __name__ == "__main__":
    # Quick sanity check
    model = build_model()
    print(f"Model parameters: {sum(p.numel() for p in model.parameters()):,}")

    # Test forward pass
    batch = torch.randn(4, 20, 4)  # batch=4, T=20, features=4
    output = model(batch)
    print(f"Input shape:  {batch.shape}")
    print(f"Output shape: {output.shape}")
    print(f"Sample risk scores: {output.squeeze().tolist()}")
    assert output.shape == (4, 1), "Output shape mismatch"
    scores = output.squeeze().tolist()
    assert all(0 <= v <= 1 for v in scores), "Scores out of range"
    print("Model sanity check passed.")
