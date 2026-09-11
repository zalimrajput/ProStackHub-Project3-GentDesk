"""In-memory pub/sub event bus for Server-Sent Events.

The orchestrator publishes structured events per research session; the
SSE endpoint subscribes to the matching queue. Persistent copies of the
same events live in the agent_logs table so a reconnecting client can
replay history.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict


class EventBus:
    def __init__(self) -> None:
        self._queues: dict[str, list[asyncio.Queue]] = defaultdict(list)

    def ensure(self, research_id: str) -> None:
        """Prepare the bus for a research session (no-op if ready)."""
        self._queues.setdefault(research_id, [])

    async def publish(self, research_id: str, event: dict) -> None:
        for queue in list(self._queues.get(research_id, [])):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:  # pragma: no cover - queue is unbounded
                pass

    def subscribe(self, research_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._queues[research_id].append(queue)
        return queue

    def unsubscribe(self, research_id: str, queue: asyncio.Queue) -> None:
        queues = self._queues.get(research_id)
        if queues and queue in queues:
            queues.remove(queue)

    def disconnect_all(self, research_id: str) -> None:
        self._queues.pop(research_id, None)


bus = EventBus()