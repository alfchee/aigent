import asyncio
from collections import defaultdict
from typing import Any
from weakref import WeakSet


class ChannelEventHub:
    def __init__(self):
        self._subscribers: dict[str, WeakSet[asyncio.Queue]] = defaultdict(WeakSet)

    def subscribe(self, topic: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers[topic].add(queue)
        return queue

    def unsubscribe(self, topic: str, queue: asyncio.Queue) -> None:
        try:
            self._subscribers[topic].discard(queue)
        except Exception:
            return

    def publish(self, topic: str, event_type: str, data: dict[str, Any]) -> None:
        queues = list(self._subscribers.get(topic, []))
        if not queues:
            return
        payload = {"event": event_type, "data": data}
        for q in queues:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                continue


hub = ChannelEventHub()


def publish(topic: str, event_type: str, data: dict[str, Any]) -> None:
    hub.publish(topic, event_type, data)


def subscribe(topic: str) -> asyncio.Queue:
    return hub.subscribe(topic)


def unsubscribe(topic: str, queue: asyncio.Queue) -> None:
    hub.unsubscribe(topic, queue)
