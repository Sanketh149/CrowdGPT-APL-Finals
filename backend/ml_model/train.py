"""
Train CrowdAnomalyDetector
Generates synthetic stadium data, trains the LSTM model, and saves
the checkpoint to model_checkpoint.pt.

Usage:
    python train.py
    python train.py --epochs 100 --hidden_size 128 --output model_checkpoint.pt
"""

import argparse
import os
import time

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from dataset import generate_simulation_df, train_val_split, SEQUENCE_LENGTH
from model import CrowdAnomalyDetector, CrowdAnomalyDetectorConfig, build_model


def run_training(
    epochs: int = 50,
    batch_size: int = 64,
    learning_rate: float = 1e-3,
    hidden_size: int = 64,
    num_layers: int = 2,
    dropout: float = 0.3,
    sequence_length: int = SEQUENCE_LENGTH,
    n_hours: int = 8,
    seed: int = 42,
    output_path: str = "model_checkpoint.pt",
    device: str = None,
) -> None:
    torch.manual_seed(seed)
    np.random.seed(seed)

    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Training on: {device}")

    # ── Data ──────────────────────────────────────────────────────────────
    print("Generating training data...")
    df = generate_simulation_df(n_hours=n_hours, zones=6, seed=seed)
    train_ds, val_ds = train_val_split(df, val_fraction=0.2, sequence_length=sequence_length)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=0)

    print(f"Train samples: {len(train_ds):,}  |  Val samples: {len(val_ds):,}")

    # ── Model ─────────────────────────────────────────────────────────────
    model = CrowdAnomalyDetector(
        input_size=4,
        hidden_size=hidden_size,
        num_layers=num_layers,
        dropout=dropout,
        attention=True,
    ).to(device)

    n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"Model parameters: {n_params:,}")

    # ── Training setup ────────────────────────────────────────────────────
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    best_val_loss = float("inf")
    patience = 10
    stagnation_counter = 0

    print(f"\n{'Epoch':>6}  {'Train Loss':>12}  {'Val Loss':>12}  {'Val MAE':>10}  {'Time':>8}")
    print("─" * 60)

    for epoch in range(1, epochs + 1):
        t0 = time.time()

        # --- Train ---
        model.train()
        train_losses = []
        for x_batch, y_batch in train_loader:
            x_batch = x_batch.to(device)
            y_batch = y_batch.to(device)

            optimizer.zero_grad()
            preds = model(x_batch)
            loss = criterion(preds, y_batch)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            train_losses.append(loss.item())

        # --- Validate ---
        model.eval()
        val_losses = []
        val_maes = []
        with torch.no_grad():
            for x_batch, y_batch in val_loader:
                x_batch = x_batch.to(device)
                y_batch = y_batch.to(device)
                preds = model(x_batch)
                val_losses.append(criterion(preds, y_batch).item())
                val_maes.append(torch.mean(torch.abs(preds - y_batch)).item())

        scheduler.step()

        train_loss = np.mean(train_losses)
        val_loss = np.mean(val_losses)
        val_mae = np.mean(val_maes)
        elapsed = time.time() - t0

        print(f"{epoch:>6}  {train_loss:>12.6f}  {val_loss:>12.6f}  {val_mae:>10.4f}  {elapsed:>7.1f}s")

        # Checkpoint on improvement
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            stagnation_counter = 0
            _save_checkpoint(model, optimizer, epoch, val_loss, output_path, train_ds)
            print(f"         Checkpoint saved (val_loss={val_loss:.6f})")
        else:
            stagnation_counter += 1
            if stagnation_counter >= patience:
                print(f"\nStopping at epoch {epoch} — no improvement for {patience} epochs")
                break

    print(f"\nTraining complete. Best val_loss: {best_val_loss:.6f}")
    print(f"Checkpoint saved to: {os.path.abspath(output_path)}")


def _save_checkpoint(
    model: nn.Module,
    optimizer: torch.optim.Optimizer,
    epoch: int,
    val_loss: float,
    path: str,
    train_ds,
) -> None:
    """Save model weights + training metadata."""
    checkpoint = {
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "epoch": epoch,
        "val_loss": val_loss,
        "model_config": {
            "input_size": model.lstm.input_size,
            "hidden_size": model.hidden_size,
            "num_layers": model.num_layers,
            "dropout": model.dropout.p,
            "attention": model.use_attention,
        },
        "feature_names": ["density", "flow_magnitude", "acceleration", "gate_pressure"],
        "normalisation": {
            "feature_min": train_ds.feature_min.tolist(),
            "feature_max": train_ds.feature_max.tolist(),
        },
    }
    torch.save(checkpoint, path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train CrowdAnomalyDetector LSTM model")
    parser.add_argument("--epochs",       type=int,   default=50)
    parser.add_argument("--batch_size",   type=int,   default=64)
    parser.add_argument("--lr",           type=float, default=1e-3)
    parser.add_argument("--hidden_size",  type=int,   default=64)
    parser.add_argument("--num_layers",   type=int,   default=2)
    parser.add_argument("--dropout",      type=float, default=0.3)
    parser.add_argument("--seq_len",      type=int,   default=SEQUENCE_LENGTH)
    parser.add_argument("--hours",        type=int,   default=8)
    parser.add_argument("--seed",         type=int,   default=42)
    parser.add_argument("--output",       type=str,   default="model_checkpoint.pt")
    parser.add_argument("--device",       type=str,   default=None)
    args = parser.parse_args()

    run_training(
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        hidden_size=args.hidden_size,
        num_layers=args.num_layers,
        dropout=args.dropout,
        sequence_length=args.seq_len,
        n_hours=args.hours,
        seed=args.seed,
        output_path=args.output,
        device=args.device,
    )
