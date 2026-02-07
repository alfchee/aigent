import asyncio
from collections import defaultdict
from typing import Any
from weakref import WeakSet


class ArtifactEventHub:
    def __init__(self):
        self._subscribers: dict[str, WeakSet[asyncio.Queue]] = defaultdict(WeakSet)

    def subscribe(self, session_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers[session_id].add(queue)
        return queue

    def unsubscribe(self, session_id: str, queue: asyncio.Queue) -> None:
        try:
            self._subscribers[session_id].discard(queue)
        except Exception:
            return

    def publish(self, session_id: str, event_type: str, data: dict[str, Any]) -> None:
        queues = list(self._subscribers.get(session_id, []))
        if not queues:
            return
        payload = {"event": event_type, "data": data}
        for q in queues:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                continue


hub = ArtifactEventHub()


def publish(session_id: str, event_type: str, data: dict[str, Any]) -> None:
    hub.publish(session_id, event_type, data)


def subscribe(session_id: str) -> asyncio.Queue:
    return hub.subscribe(session_id)


def unsubscribe(session_id: str, queue: asyncio.Queue) -> None:
    hub.unsubscribe(session_id, queue)
