"""
Simulate Stadium Sensor Data
Generates realistic CSV data covering the full match day lifecycle:
  - Pre-match (gates open, crowd arriving slowly)
  - Match start (crowd surge at all gates)
  - Mid-match (stable high density, minimal movement)
  - Post-match (evacuation surge)

Run:  python simulate_data.py
Output: simulated_stadium_data.csv
"""

import argparse
import os

import numpy as np
import pandas as pd

# Re-use the dataset simulation function
from dataset import generate_simulation_df, _get_phase_targets, _inject_anomaly

# ── Zone definitions (capacity in persons) ──────────────────────────────────
ZONE_CAPACITIES = {
    "north_stand":  35000,
    "south_stand":  35000,
    "east_stand":   20000,
    "west_stand":   22000,
    "vip_pavilion": 10000,
    "media_center": 10000,
}

# ── Gate throughput profiles (people per minute, per phase) ─────────────────
GATE_PROFILES = {
    "pre_match":    {"inflow": 800,  "outflow": 50},
    "match_start":  {"inflow": 2500, "outflow": 100},
    "mid_match":    {"inflow": 200,  "outflow": 150},
    "match_end":    {"inflow": 100,  "outflow": 1500},
    "post_match":   {"inflow": 50,   "outflow": 2800},
}

# ── Weather profile for a hot April day in Ahmedabad ────────────────────────
def _weather_at_minute(minute: int) -> dict:
    """Return simulated weather conditions at a given match minute."""
    base_temp = 32 + 6 * np.sin(np.pi * minute / 480)   # peaks midday
    humidity = 35 + 10 * np.sin(np.pi * minute / 300)
    wind = 8 + 4 * np.random.default_rng(minute).uniform(-1, 1)
    heat_index = base_temp + 0.33 * humidity - 0.70 * wind - 4.0
    return {
        "temperature_c": round(base_temp, 1),
        "humidity_pct":  round(humidity, 1),
        "wind_kmh":      round(wind, 1),
        "heat_index":    round(heat_index, 1),
    }


def generate_full_simulation(
    n_hours: int = 8,
    seed: int = 42,
    output_path: str = "simulated_stadium_data.csv",
) -> pd.DataFrame:
    """
    Generate a comprehensive CSV with:
      - Per-zone crowd density readings (1 row per minute per zone)
      - Gate throughput counters
      - Weather context
      - Labelled anomaly events
    """
    rng = np.random.default_rng(seed)
    minutes_total = n_hours * 60

    # ── Per-zone sensor data ──────────────────────────────────────────────
    base_df = generate_simulation_df(n_hours=n_hours, zones=6, seed=seed)

    # Attach capacity counts
    base_df["capacity"] = base_df["zone_id"].map(ZONE_CAPACITIES)
    base_df["person_count"] = (base_df["density"] * base_df["capacity"]).astype(int)

    # ── Gate throughput ───────────────────────────────────────────────────
    gate_rows = []
    for minute in range(minutes_total):
        phase, _, _ = _get_phase_targets(minute, "north_stand")
        profile = GATE_PROFILES.get(phase, GATE_PROFILES["mid_match"])
        inflow = int(profile["inflow"] * (1 + rng.uniform(-0.15, 0.15)))
        outflow = int(profile["outflow"] * (1 + rng.uniform(-0.15, 0.15)))

        gate_rows.append({
            "minute": minute,
            "record_type": "gate_throughput",
            "zone_id": "stadium_wide",
            "phase": phase,
            "inflow_ppm": inflow,
            "outflow_ppm": outflow,
            "net_flow": inflow - outflow,
            "cumulative_persons": None,  # filled below
        })

    gate_df = pd.DataFrame(gate_rows)
    # Compute running total
    gate_df["cumulative_persons"] = gate_df["net_flow"].cumsum().clip(0, 132000)

    # ── Weather data (one reading per minute, same for all zones) ─────────
    weather_rows = []
    for minute in range(minutes_total):
        w = _weather_at_minute(minute)
        weather_rows.append({
            "minute": minute,
            "record_type": "weather",
            "zone_id": "stadium",
            **w,
        })
    weather_df = pd.DataFrame(weather_rows)

    # ── Combine — zone sensor data + gate + weather ───────────────────────
    # Merge gate and weather into zone df (fan-out per zone per minute)
    combined = base_df.copy()
    combined["record_type"] = "zone_sensor"

    # Merge gate throughput
    combined = combined.merge(
        gate_df[["minute", "inflow_ppm", "outflow_ppm", "cumulative_persons"]],
        on="minute",
        how="left",
    )
    # Merge weather
    combined = combined.merge(
        weather_df[["minute", "temperature_c", "humidity_pct", "wind_kmh", "heat_index"]],
        on="minute",
        how="left",
    )

    # Sort and reorder columns
    cols_order = [
        "minute", "zone_id", "phase", "record_type",
        "density", "person_count", "capacity",
        "flow_magnitude", "acceleration", "gate_pressure",
        "risk_score", "is_anomaly", "anomaly_type",
        "inflow_ppm", "outflow_ppm", "cumulative_persons",
        "temperature_c", "humidity_pct", "wind_kmh", "heat_index",
    ]
    combined = combined[[c for c in cols_order if c in combined.columns]]
    combined = combined.sort_values(["minute", "zone_id"]).reset_index(drop=True)

    combined.to_csv(output_path, index=False)
    print(f"Saved {len(combined):,} rows → {output_path}")

    # Print summary
    _print_summary(combined)

    return combined


def _print_summary(df: pd.DataFrame) -> None:
    print("\n── Simulation Summary ──────────────────────────────────")
    print(f"Total rows:        {len(df):,}")
    print(f"Minutes covered:   {df['minute'].max() + 1}")
    print(f"Zones:             {df['zone_id'].nunique()}")
    print(f"Phases:            {df['phase'].unique().tolist()}")
    print(f"Anomaly events:    {df['is_anomaly'].sum():,} ({df['is_anomaly'].mean():.1%})")
    print(f"Anomaly types:     {df[df['is_anomaly']]['anomaly_type'].value_counts().to_dict()}")
    print(f"Peak density:      {df['density'].max():.3f}")
    print(f"Peak risk score:   {df['risk_score'].max():.3f}")
    print(f"Peak person count: {df['person_count'].max():,}")
    if "heat_index" in df.columns:
        print(f"Peak heat index:   {df['heat_index'].max():.1f}°C")
    print("────────────────────────────────────────────────────────")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate simulated stadium sensor data")
    parser.add_argument("--hours", type=int, default=8, help="Match day duration in hours")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--output", type=str, default="simulated_stadium_data.csv")
    args = parser.parse_args()

    generate_full_simulation(n_hours=args.hours, seed=args.seed, output_path=args.output)
