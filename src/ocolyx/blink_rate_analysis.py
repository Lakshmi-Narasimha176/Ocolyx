"""Blink rate analysis and health management for Ocolyx."""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable, Deque, Dict, Optional


@dataclass
class BlinkMetrics:
    blink_count: int
    blinks_per_minute: float
    last_blink_timestamp: float
    window_seconds: int


@dataclass
class HealthState:
    state: str
    message: str
    timestamp: float


UnhealthyCallback = Callable[[HealthState], None]
RecoveryCallback = Callable[[HealthState], None]


class BlinkRateAnalyzer:
    def __init__(
        self,
        window_seconds: int = 60,
        unhealthy_threshold_bpm: float = 10.0,
        warning_threshold_bpm: float = 12.0,
        cooldown_seconds: int = 20,
        on_unhealthy: Optional[UnhealthyCallback] = None,
        on_recovery: Optional[RecoveryCallback] = None,
    ) -> None:
        self.window_seconds = window_seconds
        self.unhealthy_threshold_bpm = unhealthy_threshold_bpm
        self.warning_threshold_bpm = warning_threshold_bpm
        self.cooldown_seconds = cooldown_seconds
        self.on_unhealthy = on_unhealthy
        self.on_recovery = on_recovery

        self._timestamps: Deque[float] = deque()
        self._lock = threading.Lock()
        self._last_state = HealthState("unknown", "Analyzer initialized", time.time())
        self._last_transition = 0.0

    def record_blink(self, timestamp: Optional[float] = None) -> BlinkMetrics:
        timestamp = timestamp or time.time()
        with self._lock:
            self._timestamps.append(timestamp)
            self._prune_old_timestamps(timestamp)
            metrics = self._current_metrics(timestamp)
            self._evaluate_health(metrics)
            return metrics

    def _prune_old_timestamps(self, now: float) -> None:
        cutoff = now - self.window_seconds
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()

    def _current_metrics(self, now: float) -> BlinkMetrics:
        blink_count = len(self._timestamps)
        bpm = (blink_count * 60.0) / max(self.window_seconds, 1)
        return BlinkMetrics(
            blink_count=blink_count,
            blinks_per_minute=bpm,
            last_blink_timestamp=self._timestamps[-1] if self._timestamps else 0.0,
            window_seconds=self.window_seconds,
        )

    def _evaluate_health(self, metrics: BlinkMetrics) -> None:
        state = self._determine_state(metrics.blinks_per_minute)
        now = metrics.last_blink_timestamp or time.time()

        if state == self._last_state.state:
            return

        if now - self._last_transition < self.cooldown_seconds:
            return

        self._last_transition = now
        self._last_state = HealthState(
            state=state,
            message=self._state_message(state, metrics.blinks_per_minute),
            timestamp=now,
        )

        if state == "unhealthy" and self.on_unhealthy:
            self.on_unhealthy(self._last_state)
        elif state == "healthy" and self.on_recovery:
            self.on_recovery(self._last_state)

    def _determine_state(self, bpm: float) -> str:
        if bpm <= self.unhealthy_threshold_bpm:
            return "unhealthy"
        if bpm <= self.warning_threshold_bpm:
            return "warning"
        return "healthy"

    def _state_message(self, state: str, bpm: float) -> str:
        if state == "unhealthy":
            return f"Blink rate is too low ({bpm:.1f} BPM); eye strain risk increased."
        if state == "warning":
            return f"Blink rate is borderline ({bpm:.1f} BPM); stay conscious of blinking."
        return f"Blink rate is healthy ({bpm:.1f} BPM)."

    def get_metrics(self) -> BlinkMetrics:
        with self._lock:
            now = time.time()
            self._prune_old_timestamps(now)
            return self._current_metrics(now)

    def get_state(self) -> HealthState:
        with self._lock:
            return self._last_state

    def reset(self) -> None:
        with self._lock:
            self._timestamps.clear()
            self._last_state = HealthState("unknown", "Analyzer reset", time.time())
            self._last_transition = 0.0

    def configure_thresholds(
        self,
        unhealthy_threshold_bpm: Optional[float] = None,
        warning_threshold_bpm: Optional[float] = None,
        cooldown_seconds: Optional[int] = None,
    ) -> None:
        with self._lock:
            if unhealthy_threshold_bpm is not None:
                self.unhealthy_threshold_bpm = unhealthy_threshold_bpm
            if warning_threshold_bpm is not None:
                self.warning_threshold_bpm = warning_threshold_bpm
            if cooldown_seconds is not None:
                self.cooldown_seconds = cooldown_seconds

    def snapshot(self) -> Dict[str, object]:
        metrics = self.get_metrics()
        state = self.get_state()
        return {
            "blink_count": metrics.blink_count,
            "blinks_per_minute": metrics.blinks_per_minute,
            "window_seconds": metrics.window_seconds,
            "health_state": state.state,
            "health_message": state.message,
            "health_timestamp": state.timestamp,
        }
