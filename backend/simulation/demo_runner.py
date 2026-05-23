"""
Quick demo runner — run this standalone to see the simulation in action.

  python -m backend.simulation.demo_runner
  python -m backend.simulation.demo_runner --video path/to/crowd.mp4
  python -m backend.simulation.demo_runner --emergency  # inject emergency after 10s
"""

import argparse
import asyncio
import json

from backend.simulation.engine import DemoSimulation, MatchPhase
from backend.simulation.video_looper import HybridFeedManager


async def print_frame(frame):
    if hasattr(frame, "phase"):
        # SensorFrame from simulation
        risk_bar = "█" * int(frame.overall_risk * 20)
        alert = " ⚠ ANOMALY" if frame.anomaly_detected else ""
        print(
            f"[{frame.phase:15s}] risk={frame.overall_risk:.2f} {risk_bar}{alert}"
            + (f" zone={frame.anomaly_zone}" if frame.anomaly_zone else "")
        )
    else:
        # Raw video frame dict
        print(f"[VIDEO] frame_id={frame.get('frame_id')} shape={frame.get('frame', {}).shape if hasattr(frame.get('frame'), 'shape') else 'N/A'}")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", help="Path to crowd video file", default=None)
    parser.add_argument("--emergency", action="store_true", help="Inject emergency after 10s")
    parser.add_argument("--speed", type=float, default=5.0, help="Phase progression speed multiplier")
    args = parser.parse_args()

    if args.video:
        manager = HybridFeedManager(video_path=args.video)
        manager.on_data(print_frame)
        print(f"[Demo] Starting in VIDEO mode: {args.video}")
    else:
        sim = DemoSimulation(interval_seconds=1.0, speed_multiplier=args.speed)
        sim.on_frame(print_frame)
        print(f"[Demo] Starting in SIMULATION mode (speed={args.speed}x)")

        if args.emergency:
            async def inject_later():
                await asyncio.sleep(10)
                print("\n🚨 INJECTING EMERGENCY EVENT\n")
                sim.inject_emergency()
            asyncio.create_task(inject_later())

        await sim.run()
        return

    await manager.run()


if __name__ == "__main__":
    asyncio.run(main())
