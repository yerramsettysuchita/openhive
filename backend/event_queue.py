"""In-memory event queue for graceful degradation.

When the Claude API is unavailable, webhook events are enqueued here and
drained once connectivity returns, satisfying the "degrade gracefully" NFR.
Phase 1 ships the structure and a working in-memory implementation; a later
phase swaps the backing store for a durable queue. Deliberately tiny and
dependency-free.
"""

from collections import deque
from threading import Lock
from typing import Any, Optional


class EventQueue:
    def __init__(self) -> None:
        self._q: "deque[dict[str, Any]]" = deque()
        self._lock = Lock()

    def enqueue(self, event: dict) -> None:
        with self._lock:
            self._q.append(event)

    def dequeue(self) -> Optional[dict]:
        with self._lock:
            return self._q.popleft() if self._q else None

    def __len__(self) -> int:
        with self._lock:
            return len(self._q)


# Module-level singleton used by the webhook layer.
event_queue = EventQueue()
