"""
VideoLooper — feeds a pre-recorded crowd video as a simulated live stream.

Usage:
  looper = VideoLooper("crowd_footage.mp4", fps_override=15)
  looper.on_frame(my_callback)   # callback receives (frame_id, numpy_array)
  await looper.run()

The video loops indefinitely. Pair with YoloAnalyzer to extract crowd stats
from each frame exactly as you would from a live camera feed.
"""

import asyncio
import time
from pathlib import Path
from typing import Callable, Optional

import cv2
import numpy as np


FrameCallback = Callable[[int, np.ndarray], None]


class VideoLooper:
    """
    Reads a video file and emits frames at a controlled rate, looping forever.
    Simulates a live RTSP/camera feed from a pre-recorded crowd video.
    """

    def __init__(
        self,
        video_path: str,
        fps_override: Optional[float] = None,
        resize: Optional[tuple[int, int]] = None,
    ):
        self.video_path = Path(video_path)
        self.fps_override = fps_override
        self.resize = resize
        self._running = False
        self._callbacks: list[FrameCallback] = []
        self._frame_count = 0

        if not self.video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")

    def on_frame(self, callback: FrameCallback):
        self._callbacks.append(callback)

    def stop(self):
        self._running = False

    async def run(self):
        """Async loop — emits frames at video FPS (or fps_override) indefinitely."""
        self._running = True

        while self._running:
            cap = cv2.VideoCapture(str(self.video_path))
            if not cap.isOpened():
                raise RuntimeError(f"Could not open video: {self.video_path}")

            native_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            target_fps = self.fps_override or native_fps
            frame_interval = 1.0 / target_fps

            print(f"[VideoLooper] Starting loop: {self.video_path.name} @ {target_fps:.1f} fps")

            while self._running:
                t0 = time.monotonic()
                ret, frame = cap.read()

                if not ret:
                    # End of video — restart loop
                    print("[VideoLooper] End of video, restarting loop...")
                    break

                if self.resize:
                    frame = cv2.resize(frame, self.resize)

                self._frame_count += 1
                for cb in self._callbacks:
                    try:
                        if asyncio.iscoroutinefunction(cb):
                            await cb(self._frame_count, frame)
                        else:
                            cb(self._frame_count, frame)
                    except Exception as e:
                        print(f"[VideoLooper] callback error: {e}")

                elapsed = time.monotonic() - t0
                sleep_time = max(0.0, frame_interval - elapsed)
                await asyncio.sleep(sleep_time)

            cap.release()


class HybridFeedManager:
    """
    Manages switching between VideoLooper (Option 1) and SimulationEngine (Option 2).
    Exposes a single on_frame interface regardless of source.
    The dashboard can call switch_mode() to toggle live/simulation at runtime.
    """

    MODE_VIDEO = "video"
    MODE_SIMULATION = "simulation"

    def __init__(self, video_path: Optional[str] = None, sim_interval: float = 2.0):
        from backend.simulation.engine import DemoSimulation

        self._sim = DemoSimulation(interval_seconds=sim_interval)
        self._looper: Optional[VideoLooper] = None
        self._mode = self.MODE_SIMULATION
        self._callbacks: list[Callable] = []
        self._task: Optional[asyncio.Task] = None

        if video_path:
            self._looper = VideoLooper(video_path, fps_override=10, resize=(640, 480))
            self._looper.on_frame(self._on_video_frame)
            self._mode = self.MODE_VIDEO

        self._sim.on_frame(self._on_sim_frame)

    def on_data(self, callback: Callable):
        """Register callback that receives normalized crowd stats dict."""
        self._callbacks.append(callback)

    def switch_mode(self, mode: str):
        assert mode in (self.MODE_VIDEO, self.MODE_SIMULATION)
        print(f"[HybridFeedManager] Switching to {mode} mode")
        self._mode = mode

    def inject_emergency(self):
        self._sim.inject_emergency()

    async def _on_sim_frame(self, frame):
        if self._mode == self.MODE_SIMULATION:
            for cb in self._callbacks:
                await cb(frame) if asyncio.iscoroutinefunction(cb) else cb(frame)

    async def _on_video_frame(self, frame_id: int, frame_array):
        if self._mode == self.MODE_VIDEO:
            # In video mode, frames are processed by YoloAnalyzer externally
            # HybridFeedManager just forwards the raw frame
            for cb in self._callbacks:
                payload = {"source": "video", "frame_id": frame_id, "frame": frame_array}
                await cb(payload) if asyncio.iscoroutinefunction(cb) else cb(payload)

    async def run(self):
        tasks = [asyncio.create_task(self._sim.run())]
        if self._looper:
            tasks.append(asyncio.create_task(self._looper.run()))
        await asyncio.gather(*tasks)

    def stop(self):
        self._sim.stop()
        if self._looper:
            self._looper.stop()
