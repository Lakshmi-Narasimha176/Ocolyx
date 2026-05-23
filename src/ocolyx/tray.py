"""System tray integration for Ocolyx."""

from __future__ import annotations

import logging
from pathlib import Path
from threading import Lock, Thread
from typing import Any, Callable, Optional

from pystray import Icon, Menu, MenuItem

from .utils.asset_loader import load_tray_icon


StatusCallback = Callable[[], dict[str, Any]]
ActionCallback = Callable[[], None]


class TrayManager:
    def __init__(
        self,
        icon_path: Optional[Path],
        logger: Optional[logging.Logger] = None,
        on_restore: Optional[ActionCallback] = None,
        on_start: Optional[ActionCallback] = None,
        on_stop: Optional[ActionCallback] = None,
        on_exit: Optional[ActionCallback] = None,
        get_status: Optional[StatusCallback] = None,
    ) -> None:
        self.icon_path = icon_path
        self.logger = logger or logging.getLogger("ocolyx.tray")
        self.on_restore = on_restore
        self.on_start = on_start
        self.on_stop = on_stop
        self.on_exit = on_exit
        self.get_status = get_status

        self._lock = Lock()
        self._icon: Optional[Icon] = None
        self._thread: Optional[Thread] = None

    def _load_icon_image(self):
        if self.icon_path is None:
            self.logger.warning("Tray icon path is unavailable; tray support disabled")
            return None

        image = load_tray_icon(self.icon_path, logger=self.logger)
        if image is None:
            self.logger.warning("Unable to load tray icon from %s", self.icon_path)
        return image

    def _build_menu(self) -> Menu:
        return Menu(
            MenuItem("Restore", self._restore),
            MenuItem("Start Monitoring", self._start_monitoring),
            MenuItem("Stop Monitoring", self._stop_monitoring),
            MenuItem("Exit", self._exit),
        )

    def start(self) -> None:
        with self._lock:
            if self._icon is not None:
                return

            image = self._load_icon_image()
            if image is None:
                return

            self._icon = Icon(
                "Ocolyx",
                image,
                "Ocolyx",
                menu=self._build_menu(),
            )
            self._thread = Thread(target=self._run_icon, daemon=True)
            self._thread.start()
            self.logger.info("Ocolyx tray icon started")

    def _run_icon(self) -> None:
        with self._lock:
            if self._icon is None:
                return
            icon = self._icon

        try:
            icon.run()
        except Exception as exc:
            self.logger.exception("Tray icon main loop failed: %s", exc)

    def stop(self) -> None:
        with self._lock:
            if self._icon is None:
                return
            self.logger.info("Stopping tray icon")
            try:
                self._icon.stop()
            except Exception as exc:
                self.logger.warning("Error stopping tray icon: %s", exc)
            self._icon = None

    def update_tooltip(self, blink_rate: Optional[float] = None) -> None:
        with self._lock:
            if self._icon is None:
                return
            tooltip = self._build_tooltip(blink_rate)
            try:
                self._icon.title = tooltip
            except Exception as exc:
                self.logger.warning("Failed to update tray tooltip: %s", exc)

    def _build_tooltip(self, blink_rate: Optional[float] = None) -> str:
        if blink_rate is None:
            blink_rate = self._current_blink_rate()
        return f"Ocolyx - Blink rate: {blink_rate:.1f} BPM" if blink_rate is not None else "Ocolyx"

    def _current_blink_rate(self) -> Optional[float]:
        if not self.get_status:
            return None
        try:
            status = self.get_status()
            return float(status.get("blink_rate", 0.0))
        except Exception as exc:
            self.logger.debug("Unable to read blink rate from status callback: %s", exc)
            return None

    def _restore(self, icon: Icon, item: Any) -> None:
        self.logger.info("Tray restore requested")
        if self.on_restore:
            self.on_restore()

    def _start_monitoring(self, icon: Icon, item: Any) -> None:
        self.logger.info("Tray start monitoring requested")
        if self.on_start:
            self.on_start()

    def _stop_monitoring(self, icon: Icon, item: Any) -> None:
        self.logger.info("Tray stop monitoring requested")
        if self.on_stop:
            self.on_stop()

    def _exit(self, icon: Icon, item: Any) -> None:
        self.logger.info("Tray exit requested")
        if self.on_exit:
            self.on_exit()
        try:
            icon.stop()
        except Exception as exc:
            self.logger.warning("Tray icon exit failed: %s", exc)


TrayIcon = TrayManager
