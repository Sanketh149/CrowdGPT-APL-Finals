"""
Broadcast Manager — pushes emergency announcements to all connected stadium screens.
Any screen (scoreboard, concourse display) subscribes to /broadcast/stream SSE.
When EVACUATE/LOCKDOWN is triggered, all screens flip to full-screen emergency message.
"""
import asyncio
import json
import logging
from typing import AsyncGenerator

logger = logging.getLogger(__name__)


class BroadcastManager:
    """Manages SSE connections for stadium display screens."""

    def __init__(self):
        self._queues: list[asyncio.Queue] = []
        self._latest: dict | None = None

    def _new_queue(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=10)
        self._queues.append(q)
        return q

    def _remove_queue(self, q: asyncio.Queue):
        try:
            self._queues.remove(q)
        except ValueError:
            pass

    async def broadcast(self, event: dict):
        """Push event to all connected screens."""
        self._latest = event
        dead = []
        for q in self._queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self._remove_queue(q)
        logger.info(f"Broadcast pushed to {len(self._queues)} screen(s): {event.get('type')}")

    async def stream(self) -> AsyncGenerator[str, None]:
        """SSE generator for a single screen connection."""
        q = self._new_queue()
        # Send latest state immediately on connect so a freshly loaded screen is in sync
        if self._latest:
            yield f"data: {json.dumps(self._latest)}\n\n"
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=25.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            self._remove_queue(q)

    @property
    def connected_screens(self) -> int:
        return len(self._queues)


# Singleton imported by main.py
broadcast_manager = BroadcastManager()
