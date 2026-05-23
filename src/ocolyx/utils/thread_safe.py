"""Thread-safe helpers."""

from threading import Lock
from typing import Callable, TypeVar

T = TypeVar("T")


class LockedResource:
    def __init__(self, initial_value: T) -> None:
        self._value = initial_value
        self._lock = Lock()

    def get(self) -> T:
        with self._lock:
            return self._value

    def set(self, value: T) -> None:
        with self._lock:
            self._value = value

    def update(self, func: Callable[[T], T]) -> None:
        with self._lock:
            self._value = func(self._value)
