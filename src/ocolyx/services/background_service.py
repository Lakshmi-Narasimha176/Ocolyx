"""Background monitoring and service orchestration."""

from threading import Event, Lock, Thread
from time import sleep
from typing import Any


class BackgroundService:
    def __init__(self, config_manager: Any, logger: Any) -> None:
        self.config_manager = config_manager
        self.logger = logger
        self.shutdown_flag = Event()
        self.thread: Thread | None = None
        self._lock = Lock()

    def start(self) -> None:
        with self._lock:
            if self.thread is not None and self.thread.is_alive():
                self.logger.debug("Background service already running")
                return

            self.logger.info("Starting background service")
            self.shutdown_flag.clear()
            self.thread = Thread(target=self._run, daemon=True)
            self.thread.start()

    def _run(self) -> None:
        interval = self.config_manager.get("monitor_interval_seconds", 1)
        while not self.shutdown_flag.is_set():
            self.logger.debug("Background service heartbeat")
            sleep(interval)

    def stop(self) -> None:
        self.logger.info("Stopping background service")
        with self._lock:
            self.shutdown_flag.set()
            thread = self.thread

        if thread and thread.is_alive():
            thread.join(timeout=2)

        with self._lock:
            if thread is self.thread:
                self.thread = None
