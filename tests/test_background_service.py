from __future__ import annotations

import logging
import time

from src.ocolyx.services.background_service import BackgroundService


class Config:
    def get(self, key: str, default=None):
        if key == "monitor_interval_seconds":
            return 0.01
        return default


def test_background_service_start_is_idempotent() -> None:
    service = BackgroundService(Config(), logging.getLogger("test.background"))

    try:
        service.start()
        first_thread = service.thread
        service.start()

        assert service.thread is first_thread
        assert first_thread is not None
        assert first_thread.is_alive()
    finally:
        service.stop()


def test_background_service_can_restart_after_stop() -> None:
    service = BackgroundService(Config(), logging.getLogger("test.background"))

    service.start()
    first_thread = service.thread
    service.stop()
    time.sleep(0.02)

    service.start()
    try:
        assert service.thread is not None
        assert service.thread is not first_thread
        assert service.thread.is_alive()
    finally:
        service.stop()
