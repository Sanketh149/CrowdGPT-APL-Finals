"""
SimulationEngine — generates realistic stadium crowd data across match phases.

Phases:
  PRE_MATCH      : gates open, crowd builds steadily (0–60 min before match)
  ENTRY_SURGE    : peak entry, high density at entry gates (15–30 min before)
  MID_MATCH      : crowd stable inside, low gate activity
  INNINGS_BREAK  : movement between zones, food/toilet surge
  POST_MATCH     : exit surge, high density at exit gates — most dangerous phase
  EMERGENCY      : injected anomaly event (override any phase for demo)
"""

import asyncio
import random
import time
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Callable, Optional

import numpy as np


class MatchPhase(str, Enum):
    PRE_MATCH = "pre_match"
    ENTRY_SURGE = "entry_surge"
    MID_MATCH = "mid_match"
    INNINGS_BREAK = "innings_break"
    POST_MATCH = "post_match"
    EMERGENCY = "emergency"


# Stadium zones — maps to SVG zones in frontend StadiumMap
ZONES = [
    "gate_north", "gate_south", "gate_east", "gate_west",
    "stand_a", "stand_b", "stand_c", "stand_d",
    "concourse_north", "concourse_south",
]

# Base density profiles per zone per phase (0.0 = empty, 1.0 = max capacity)
PHASE_DENSITY_PROFILES: dict[MatchPhase, dict[str, tuple[float, float]]] = {
    MatchPhase.PRE_MATCH: {
        "gate_north": (0.3, 0.5), "gate_south": (0.3, 0.5),
        "gate_east": (0.2, 0.4), "gate_west": (0.2, 0.4),
        "stand_a": (0.1, 0.3), "stand_b": (0.1, 0.3),
        "stand_c": (0.1, 0.2), "stand_d": (0.1, 0.2),
        "concourse_north": (0.2, 0.4), "concourse_south": (0.2, 0.4),
    },
    MatchPhase.ENTRY_SURGE: {
        "gate_north": (0.7, 0.95), "gate_south": (0.7, 0.95),
        "gate_east": (0.6, 0.85), "gate_west": (0.5, 0.75),
        "stand_a": (0.4, 0.6), "stand_b": (0.4, 0.6),
        "stand_c": (0.3, 0.5), "stand_d": (0.3, 0.5),
        "concourse_north": (0.6, 0.8), "concourse_south": (0.5, 0.7),
    },
    MatchPhase.MID_MATCH: {
        "gate_north": (0.1, 0.2), "gate_south": (0.1, 0.2),
        "gate_east": (0.1, 0.15), "gate_west": (0.1, 0.15),
        "stand_a": (0.8, 0.95), "stand_b": (0.8, 0.95),
        "stand_c": (0.7, 0.9), "stand_d": (0.7, 0.9),
        "concourse_north": (0.2, 0.35), "concourse_south": (0.2, 0.35),
    },
    MatchPhase.INNINGS_BREAK: {
        "gate_north": (0.2, 0.35), "gate_south": (0.2, 0.35),
        "gate_east": (0.2, 0.3), "gate_west": (0.2, 0.3),
        "stand_a": (0.4, 0.6), "stand_b": (0.4, 0.6),
        "stand_c": (0.4, 0.6), "stand_d": (0.4, 0.6),
        "concourse_north": (0.6, 0.8), "concourse_south": (0.6, 0.8),
    },
    MatchPhase.POST_MATCH: {
        "gate_north": (0.75, 0.98), "gate_south": (0.75, 0.98),
        "gate_east": (0.7, 0.95), "gate_west": (0.65, 0.9),
        "stand_a": (0.3, 0.5), "stand_b": (0.3, 0.5),
        "stand_c": (0.3, 0.5), "stand_d": (0.3, 0.5),
        "concourse_north": (0.8, 0.98), "concourse_south": (0.8, 0.98),
    },
    MatchPhase.EMERGENCY: {
        # Simulates a sudden crowd surge at one gate — dangerous
        "gate_north": (0.95, 1.0), "gate_south": (0.5, 0.7),
        "gate_east": (0.9, 1.0), "gate_west": (0.3, 0.5),
        "stand_a": (0.6, 0.8), "stand_b": (0.6, 0.8),
        "stand_c": (0.5, 0.7), "stand_d": (0.5, 0.7),
        "concourse_north": (0.95, 1.0), "concourse_south": (0.4, 0.6),
    },
}


@dataclass
class ZoneReading:
    zone_id: str
    density: float          # 0.0–1.0 fraction of capacity
    person_count: int       # absolute count
    flow_magnitude: float   # avg movement speed (0–5 m/s)
    flow_direction: float   # degrees 0–360
    acceleration: float     # change in flow_magnitude vs last reading
    gate_pressure: float    # 0.0–1.0, only relevant for gate zones


@dataclass
class SensorFrame:
    timestamp: float
    phase: str
    zones: list[ZoneReading]
    overall_risk: float     # 0.0–1.0 computed from zone readings
    anomaly_detected: bool
    anomaly_zone: Optional[str]


def _compute_risk(zones: list[ZoneReading]) -> tuple[float, bool, Optional[str]]:
    """Compute overall risk score from zone readings."""
    max_risk = 0.0
    anomaly_zone = None

    for z in zones:
        # Risk factors: density + acceleration + gate_pressure
        zone_risk = (z.density * 0.5) + (z.acceleration * 2.0) + (z.gate_pressure * 0.3)
        zone_risk = min(zone_risk, 1.0)
        if zone_risk > max_risk:
            max_risk = zone_risk
            if zone_risk > 0.75:
                anomaly_zone = z.zone_id

    return round(max_risk, 3), max_risk > 0.75, anomaly_zone


class SimulationEngine:
    """
    Generates realistic stadium crowd data frames at configurable intervals.
    Supports phase-based simulation and emergency injection.
    """

    def __init__(self, interval_seconds: float = 2.0):
        self.interval = interval_seconds
        self.current_phase = MatchPhase.PRE_MATCH
        self._running = False
        self._prev_flow: dict[str, float] = {z: 0.0 for z in ZONES}
        self._callbacks: list[Callable[[SensorFrame], None]] = []

    def set_phase(self, phase: MatchPhase):
        self.current_phase = phase

    def inject_emergency(self):
        self.current_phase = MatchPhase.EMERGENCY

    def on_frame(self, callback: Callable[[SensorFrame], None]):
        self._callbacks.append(callback)

    def generate_frame(self) -> SensorFrame:
        profile = PHASE_DENSITY_PROFILES[self.current_phase]
        zone_readings = []

        for zone_id in ZONES:
            lo, hi = profile[zone_id]
            density = round(random.uniform(lo, hi) + random.gauss(0, 0.03), 3)
            density = max(0.0, min(1.0, density))

            capacity = 5000 if zone_id.startswith("stand") else 1200
            person_count = int(density * capacity)

            flow_mag = round(random.uniform(0.5, 4.5) * density, 2)
            flow_dir = round(random.uniform(0, 360), 1)
            acceleration = round(flow_mag - self._prev_flow.get(zone_id, flow_mag), 3)
            self._prev_flow[zone_id] = flow_mag

            gate_pressure = density if zone_id.startswith("gate") else 0.0

            zone_readings.append(ZoneReading(
                zone_id=zone_id,
                density=density,
                person_count=person_count,
                flow_magnitude=flow_mag,
                flow_direction=flow_dir,
                acceleration=acceleration,
                gate_pressure=gate_pressure,
            ))

        risk, anomaly, anomaly_zone = _compute_risk(zone_readings)

        return SensorFrame(
            timestamp=time.time(),
            phase=self.current_phase.value,
            zones=zone_readings,
            overall_risk=risk,
            anomaly_detected=anomaly,
            anomaly_zone=anomaly_zone,
        )

    def frame_as_dict(self) -> dict:
        return asdict(self.generate_frame())

    async def run(self):
        """Async loop — generates frames and calls registered callbacks."""
        self._running = True
        while self._running:
            frame = self.generate_frame()
            for cb in self._callbacks:
                try:
                    if asyncio.iscoroutinefunction(cb):
                        await cb(frame)
                    else:
                        cb(frame)
                except Exception as e:
                    print(f"[SimulationEngine] callback error: {e}")
            await asyncio.sleep(self.interval)

    def stop(self):
        self._running = False


# Phase auto-progression for demo (drives the timeline automatically)
DEMO_TIMELINE: list[tuple[int, MatchPhase]] = [
    (0,   MatchPhase.PRE_MATCH),
    (30,  MatchPhase.ENTRY_SURGE),
    (90,  MatchPhase.MID_MATCH),
    (150, MatchPhase.INNINGS_BREAK),
    (210, MatchPhase.MID_MATCH),
    (300, MatchPhase.POST_MATCH),
]


class DemoSimulation(SimulationEngine):
    """
    SimulationEngine with automatic phase progression following DEMO_TIMELINE.
    Starts at PRE_MATCH and advances phases on a compressed timeline for demo.
    """

    def __init__(self, interval_seconds: float = 2.0, speed_multiplier: float = 1.0):
        super().__init__(interval_seconds)
        self._start_time: Optional[float] = None
        self._speed = speed_multiplier  # >1 speeds up phase transitions

    async def run(self):
        self._running = True
        self._start_time = time.time()

        while self._running:
            elapsed = (time.time() - self._start_time) * self._speed

            # Advance phase based on timeline
            for threshold, phase in reversed(DEMO_TIMELINE):
                if elapsed >= threshold:
                    if self.current_phase != phase and self.current_phase != MatchPhase.EMERGENCY:
                        print(f"[DemoSimulation] Phase → {phase.value}")
                        self.current_phase = phase
                    break

            frame = self.generate_frame()
            for cb in self._callbacks:
                try:
                    if asyncio.iscoroutinefunction(cb):
                        await cb(frame)
                    else:
                        cb(frame)
                except Exception as e:
                    print(f"[DemoSimulation] callback error: {e}")

            await asyncio.sleep(self.interval)
