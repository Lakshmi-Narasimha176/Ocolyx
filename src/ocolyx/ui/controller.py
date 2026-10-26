"""Dashboard controller for Ocolyx."""

from threading import Lock, Thread
from typing import Any, Callable

from pystray import Icon, MenuItem, Menu

from .dashboard import DashboardView
from ..utils.asset_loader import load_tray_icon, resolve_icon_paths
from ..utils.runtime_paths import resource_root


class DashboardController:
    def __init__(
        self,
        config_manager: Any,
        background_service: Any,
        logger: Any,
        on_start_monitoring: Callable[[], None] | None = None,
        on_stop_monitoring: Callable[[], None] | None = None,
        get_status: Callable[[], dict[str, Any]] | None = None,
        get_session_log: Callable[[], list[dict[str, Any]]] | None = None,
        on_settings_change: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> None:
        self.config_manager = config_manager
        self.background_service = background_service
        self.logger = logger
        self.on_start_monitoring = on_start_monitoring
        self.on_stop_monitoring = on_stop_monitoring
        self.get_status = get_status
        self.get_session_log = get_session_log
        self.on_settings_change = on_settings_change
        self.root_dir = resource_root()
        self.window_icon_path, self.logo_path = resolve_icon_paths(self.root_dir)
        self.tray_icon_path = self.window_icon_path or self.logo_path
        self.lock = Lock()
        self.monitoring = False
        self.session_seconds = 0
        self.tray_icon: Icon | None = None
        self.icon_thread: Thread | None = None
        self._is_shutting_down = False
        self._status_after_id: str | None = None
        self._session_after_id: str | None = None

        self.view = DashboardView(
            config_manager.settings,
            self.logo_path,
            self.window_icon_path,
            on_start=self.start_monitoring,
            on_stop=self.stop_monitoring,
            on_minimize=self.minimize_to_tray,
            on_settings_change=self.update_settings,
            logger=logger,
        )

        self.view.safe_update(self.update_initial_status)
        self._session_after_id = self.view.schedule_after(1000, self._session_tick)
        self._status_after_id = self.view.schedule_after(500, self._status_tick)

    def update_initial_status(self) -> None:
        if not self._view_alive():
            return
        self.view.set_webcam_status("Ready")
        self.view.set_monitor_status("Idle")
        self.view.set_alert_status("No active alerts")
        self.view.set_blink_rate("0.0 bpm")

    def run(self) -> None:
        self.logger.info("Launching Ocolyx dashboard")
        self.show_window()
        self.view.mainloop()

    def show_window(self) -> None:
        if not self._view_alive():
            return
        try:
            if self.view.state() != "normal":
                self.view.deiconify()
            self.view.lift()
            self.view.focus_force()
            self.view.update_idletasks()
        except Exception as exc:
            self.logger.warning("Failed to restore dashboard window: %s", exc)

    def start_monitoring(self) -> None:
        if self._is_shutting_down:
            return
        with self.lock:
            if self.monitoring:
                return
            self.monitoring = True
            self.session_seconds = 0
            self.view.safe_update(self.view.set_monitor_status, "Active")
            self.view.safe_update(self.view.set_alert_status, "Monitoring enabled")
            self.logger.info("Monitoring started")
            self._run_monitoring_callback(self.on_start_monitoring or self.background_service.start, "start monitoring")

    def stop_monitoring(self) -> None:
        with self.lock:
            if not self.monitoring:
                return
            self.monitoring = False
            self.view.safe_update(self.view.set_monitor_status, "Stopped")
            self.view.safe_update(self.view.set_alert_status, "Monitoring paused")
            self.logger.info("Monitoring stopped")
            self._run_monitoring_callback(self.on_stop_monitoring or self.background_service.stop, "stop monitoring")

    def _run_monitoring_callback(self, callback: Callable[[], None], action_name: str) -> None:
        def worker() -> None:
            try:
                callback()
            except Exception as exc:
                self.logger.exception("Failed to %s from dashboard: %s", action_name, exc)
                if self._view_alive():
                    self.view.safe_update(self.view.set_alert_status, f"Failed to {action_name}")

        Thread(target=worker, daemon=True).start()

    def set_monitoring_active(self) -> None:
        with self.lock:
            self.monitoring = True
        if not self._view_alive():
            return
        self.view.safe_update(self.view.set_monitor_status, "Active")
        self.view.safe_update(self.view.set_alert_status, "Monitoring enabled")

    def set_monitoring_inactive(self) -> None:
        with self.lock:
            self.monitoring = False
        if not self._view_alive():
            return
        self.view.safe_update(self.view.set_monitor_status, "Stopped")
        self.view.safe_update(self.view.set_alert_status, "Monitoring paused")

    def update_live_status(self, status: dict[str, Any]) -> None:
        if not self._view_alive():
            return
        blink_rate = float(status.get("blink_rate", 0.0) or 0.0)
        blink_count = int(status.get("blink_count", 0) or 0)
        webcam_connected = bool(status.get("webcam_connected", False))
        self.view.safe_update(self.view.set_blink_rate, f"{blink_rate:.1f} bpm")
        self.view.safe_update(self.view.set_webcam_status, "Connected" if webcam_connected else "Disconnected")
        self.view.safe_update(self.view.set_alert_status, f"Session blinks: {blink_count}")

    def update_session_log(self, entries: list[dict[str, Any]]) -> None:
        if not self._view_alive():
            return
        self.view.safe_update(self.view.set_session_log_entries, entries)

    def update_settings(self, updates: dict[str, Any]) -> None:
        if self._is_shutting_down:
            return

        def worker() -> None:
            try:
                if self.on_settings_change:
                    settings = self.on_settings_change(updates)
                else:
                    self.config_manager.save(updates)
                    settings = self.config_manager.settings
                if self._view_alive():
                    self.view.safe_update(self.view.apply_settings_snapshot, settings)
                    self.view.safe_update(self.view.show_settings_success)
            except Exception as exc:
                self.logger.warning("Settings update failed: %s", exc)
                if self._view_alive():
                    self.view.safe_update(self.view.set_settings_error, str(exc))

        Thread(target=worker, daemon=True).start()

    def update_settings_snapshot(self, settings: dict[str, Any]) -> None:
        if not self._view_alive():
            return
        self.view.safe_update(self.view.apply_settings_snapshot, settings)

    def _status_tick(self) -> None:
        self._status_after_id = None
        if self._is_shutting_down or not self._view_alive():
            return

        if self.get_status:
            try:
                self.update_live_status(self.get_status())
            except Exception as exc:
                self.logger.warning("Failed to refresh dashboard status: %s", exc)

        if self.get_session_log:
            try:
                self.update_session_log(self.get_session_log())
            except Exception as exc:
                self.logger.warning("Failed to refresh session log: %s", exc)

        self._status_after_id = self.view.schedule_after(500, self._status_tick)

    def _session_tick(self) -> None:
        self._session_after_id = None
        if self._is_shutting_down or not self._view_alive():
            return

        with self.lock:
            if self.monitoring:
                self.session_seconds += 1
                self.view.safe_update(self.view.set_session_timer, self._format_duration(self.session_seconds))

        self._session_after_id = self.view.schedule_after(1000, self._session_tick)

    def minimize_to_tray(self) -> None:
        if self._is_shutting_down or not self._view_alive():
            return
        self.logger.info("Minimizing application to tray")
        self.view.withdraw()
        if self.tray_icon is None:
            self._create_tray_icon()

    def _create_tray_icon(self) -> None:
        image = load_tray_icon(self.tray_icon_path, logger=self.logger)
        if image is None:
            self.logger.warning("Unable to load tray icon; tray support will be disabled")
            return

        self.tray_icon = Icon(
            "Ocolyx",
            image,
            "Ocolyx",
            menu=Menu(
                MenuItem("Restore", self._on_restore),
                MenuItem("Quit", self._on_quit),
            ),
        )

        self.icon_thread = Thread(target=self.tray_icon.run, daemon=True)
        self.icon_thread.start()

    def _on_restore(self, icon: Icon, item: Any) -> None:
        self.logger.info("Restoring application from tray")
        icon.stop()
        self.tray_icon = None
        if self._view_alive():
            self.view.safe_update(self.show_window)

    def _on_quit(self, icon: Icon, item: Any) -> None:
        self.logger.info("Quit requested from tray")
        try:
            icon.stop()
        finally:
            self.tray_icon = None
        if self._view_alive():
            self.view.safe_update(self.shutdown)

    def shutdown(self) -> None:
        if self._is_shutting_down:
            return
        self._is_shutting_down = True
        with self.lock:
            self.monitoring = False

        if self._status_after_id is not None:
            self.view.cancel_after(self._status_after_id)
            self._status_after_id = None
        if self._session_after_id is not None:
            self.view.cancel_after(self._session_after_id)
            self._session_after_id = None

        if self.tray_icon is not None:
            try:
                self.tray_icon.stop()
            except Exception as exc:
                self.logger.warning("Failed to stop tray icon during dashboard shutdown: %s", exc)
            self.tray_icon = None

        if self._view_alive():
            self.view.destroy()

    def _view_alive(self) -> bool:
        return hasattr(self, "view") and self.view.is_alive()

    @staticmethod
    def _format_duration(seconds: int) -> str:
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02}:{minutes:02}:{seconds:02}"
