"""Event bus for central application communication."""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from typing import Any, Callable, DefaultDict, Dict, List


EventCallback = Callable[..., None]


class EventBus:
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger("ocolyx.eventbus")
        self._subscribers: DefaultDict[str, List[EventCallback]] = defaultdict(list)
        self._lock = threading.RLock()

    def subscribe(self, event_name: str, callback: EventCallback) -> None:
        with self._lock:
            self._subscribers[event_name].append(callback)
            self.logger.debug("Subscribed to event '%s' with %s", event_name, callback)

    def unsubscribe(self, event_name: str, callback: EventCallback) -> None:
        with self._lock:
            if callback in self._subscribers.get(event_name, []):
                self._subscribers[event_name].remove(callback)
                self.logger.debug("Unsubscribed from event '%s' for %s", event_name, callback)

    def publish(self, event_name: str, *args: Any, **kwargs: Any) -> None:
        with self._lock:
            subscribers = list(self._subscribers.get(event_name, []))
        self.logger.debug("Publishing event '%s' to %d subscribers", event_name, len(subscribers))
        for callback in subscribers:
            try:
                callback(*args, **kwargs)
            except Exception as exc:
                self.logger.exception("Error while handling event '%s' in %s", event_name, callback)
