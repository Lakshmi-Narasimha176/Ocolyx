"""Main Ocolyx application controller."""

from __future__ import annotations

import logging
import signal
import time
from pathlib import Path
from typing import Any, Callable, Optional

import customtkinter as ctk

from .alerts import AlertManager
from .blink_detector import BlinkDetector
from .blink_detector import NoOpBlinkDetector
from .blink_rate_analysis import BlinkRateAnalyzer
from .config_manager import ConfigManager
from .event_bus import EventBus
from .logger import setup_logger
from .overlay import ScreenDimmer
from .services.background_service import BackgroundService
from .tray import TrayManager
from .ui import OcolyxDashboard
from .utils.asset_loader import resolve_icon_paths
from .utils.runtime_paths import bundled_config_path, config_path, log_path, resource_root


APP_EVENT_BLINK_DETECTED = "app.blink_detected"
APP_EVENT_ALERT_TRIGGERED = "app.alert_triggered"
APP_EVENT_SHUTDOWN = "app.shutdown"
APP_EVENT_EXCEPTION = "app.exception"
APP_EVENT_STATUS_UPDATE = "app.status_update"


class ApplicationController:
    def __init__(
        self,
        root_dir: Optional[Path] = None,
        config_manager: Optional[ConfigManager] = None,
        logger: Optional[logging.Logger] = None,
        event_bus: Optional[EventBus] = None,
        ui: Optional[OcolyxDashboard] = None,
        tray: Optional[TrayManager] = None,
        blink_detector: Optional[BlinkDetector] = None,
        alert_manager: Optional[AlertManager] = None,
        background_service: Optional[BackgroundService] = None,
        blink_analyzer: Optional[BlinkRateAnalyzer] = None,
    ) -> None:
        self.root_dir = root_dir or resource_root()
        self.config_manager = config_manager or ConfigManager(
            config_path(),
            default_config_path=bundled_config_path(),
            logger=logger,
        )
        log_level = self.config_manager.get("log_level", "INFO")
        log_when = self.config_manager.get("log_when", "midnight")
        log_backup_days = self.config_manager.get("log_backup_days", 30)
        self.logger = logger or setup_logger(
            log_path(),
            log_level=log_level,
            when=log_when,
            backup_count=log_backup_days,
        )
        self.event_bus = event_bus or EventBus(self.logger)
        self.background_service = background_service or BackgroundService(self.config_manager, self.logger)
        self.blink_analyzer = blink_analyzer or BlinkRateAnalyzer()
        self.screen_dimmer: Optional[ScreenDimmer] = None
        self._low_blink_since = 0.0
        self._last_dim_time = 0.0
        # Instantiate the blink detector and handle missing model or initialization errors.
        try:
            self.blink_detector = (
                blink_detector
                or BlinkDetector(
                    logger=self.logger,
                    on_blink=self._on_blink,
                    on_disconnect=self._on_disconnect,
                    on_reconnect=self._on_reconnect,
                    on_error=self._on_error,
                    process_fps=self.config_manager.get("process_fps", 6.0),
                )
            )
        except FileNotFoundError as exc:
            # Missing dlib model file: surface to user and continue with no-op detector
            self.logger.exception("Required model file missing: %s", exc)
            self.blink_detector = NoOpBlinkDetector(self.logger)
            try:
                self.show_error("Required model missing", str(exc))
            except Exception:
                self.logger.exception("Failed to show missing-model dialog to user")
        except Exception as exc:
            # Unexpected initialization error: log, notify user, and continue safely
            self.logger.exception("Blink detector initialization failed: %s", exc)
            self.blink_detector = NoOpBlinkDetector(self.logger)
            try:
                self.show_error("Blink detector error", "Blink detector failed to initialize. See logs for details.")
            except Exception:
                self.logger.exception("Failed to show blink-detector error dialog to user")
        self.ui = ui or OcolyxDashboard(
            self.config_manager,
            self.background_service,
            self.logger,
            on_start_monitoring=self.start_monitoring,
            on_stop_monitoring=self.stop_monitoring,
            get_status=self.get_status,
            get_session_log=self.get_session_log,
            on_settings_change=self.update_settings,
        )
        self.window_icon_path, self.logo_path = resolve_icon_paths(self.root_dir)
        self.tray_icon_path = self.window_icon_path or self.logo_path
        self.alert_manager = alert_manager or AlertManager(
            self.config_manager.settings,
            self.logger,
            dialog_callback=self._show_alert_dialog,
        )
        self.tray = tray or TrayManager(
            self.tray_icon_path,
            logger=self.logger,
            on_restore=self.restore,
            on_start=self.start_monitoring,
            on_stop=self.stop_monitoring,
            on_exit=self.shutdown,
            get_status=self.get_status,
        )
        self._is_shutting_down = False
        self._register_event_handlers()
        self._setup_signal_handlers()
        # Install a global thread exception hook where available to capture
        # uncaught exceptions from background threads and surface them
        try:
            import threading as _threading

            def _ex_hook(args: Any) -> None:
                # args has attribute exc_value on Python 3.8+
                exc = getattr(args, "exc_value", None)
                if exc is None:
                    exc = getattr(args, "exception", None)
                if exc is not None:
                    self.handle_exception(exc)

            _threading.excepthook = _ex_hook  # type: ignore[attr-defined]
        except Exception:
            # Not available on older Pythons; threads will be wrapped individually.
            self.logger.debug("threading.excepthook not available; falling back to per-thread handlers")

    def _register_event_handlers(self) -> None:
        self.event_bus.subscribe(APP_EVENT_BLINK_DETECTED, self._handle_blink_event)
        self.event_bus.subscribe(APP_EVENT_ALERT_TRIGGERED, self._handle_alert_event)
        self.event_bus.subscribe(APP_EVENT_EXCEPTION, self._handle_exception)
        self.event_bus.subscribe(APP_EVENT_SHUTDOWN, self._handle_shutdown)

    def _setup_signal_handlers(self) -> None:
        try:
            signal.signal(signal.SIGINT, lambda *_: self.shutdown())
            signal.signal(signal.SIGTERM, lambda *_: self.shutdown())
        except Exception:
            self.logger.debug("Unable to install OS signal handlers")

    def start_monitoring(self) -> None:
        self.safe_execute(self._start_monitoring)

    def stop_monitoring(self) -> None:
        self.safe_execute(self._stop_monitoring)

    def _start_monitoring(self) -> None:
        self.logger.info("Starting monitoring components")
        was_running = bool(getattr(self.blink_detector, "is_running", False))
        if not was_running:
            self.blink_analyzer.reset()
            if hasattr(self.alert_manager, "reset_session"):
                self.alert_manager.reset_session()
            self._low_blink_since = 0.0
            self._last_dim_time = 0.0
        self.background_service.start()
        self.blink_detector.start()
        self.tray.update_tooltip(self.get_status().get("blink_rate", 0.0))
        if hasattr(self.ui, "set_monitoring_active"):
            self.ui.set_monitoring_active()

    def _stop_monitoring(self) -> None:
        self.logger.info("Stopping monitoring components")
        self.blink_detector.stop()
        self.background_service.stop()
        if hasattr(self.ui, "set_monitoring_inactive"):
            self.ui.set_monitoring_inactive()

    def run(self) -> None:
        self.logger.info("Starting Ocolyx application controller")
        self._initialize_screen_dimmer()
        self.tray.start()
        self._start_monitoring()
        self._schedule_health_tick()

        try:
            self.ui.run()
        except Exception as exc:
            self.handle_exception(exc)
        finally:
            self.shutdown()

    def restore(self) -> None:
        self.logger.info("Restoring application from tray")
        if hasattr(self.ui, "view") and hasattr(self.ui.view, "safe_update"):
            self.ui.view.safe_update(self.ui.show_window)
            return
        if hasattr(self.ui, "view") and hasattr(self.ui.view, "deiconify"):
            self.ui.view.deiconify()

    def _show_alert_dialog(self, title: str, message: str, severity: str) -> None:
        if not hasattr(self.ui, "view") or not hasattr(self.ui.view, "safe_update"):
            self.logger.warning("Alert dialog requested but no UI view is available")
            return

        self.ui.view.safe_update(self._open_alert_dialog, title, message)

    def _open_alert_dialog(self, title: str, message: str) -> None:
        if not hasattr(self.ui, "view"):
            return

        popup = ctk.CTkToplevel(self.ui.view)
        popup.title(title)
        popup.geometry("420x170")
        popup.attributes("-topmost", True)
        popup.resizable(False, False)

        frame = ctk.CTkFrame(popup, fg_color="#101d33")
        frame.pack(fill="both", expand=True, padx=16, pady=16)

        header = ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(size=18, weight="bold"), text_color="#c7d2ff")
        header.pack(anchor="w", pady=(0, 12))

        body = ctk.CTkLabel(frame, text=message, wraplength=380, justify="left", font=ctk.CTkFont(size=13), text_color="#d1d8ff")
        body.pack(anchor="w", pady=(0, 16))

        close_btn = ctk.CTkButton(frame, text="Dismiss", fg_color="#2b6cb0", hover_color="#235185", command=popup.destroy)
        close_btn.pack(anchor="e")

    def _initialize_screen_dimmer(self) -> None:
        if self.screen_dimmer is not None:
            return
        if not hasattr(self.ui, "view"):
            return
        self.screen_dimmer = ScreenDimmer(
            self.ui.view,
            opacity=float(self.config_manager.get("overlay_opacity", 0.35)),
            logger=self.logger,
        )

    def update_settings(self, updates: dict[str, Any]) -> dict[str, Any]:
        self.config_manager.save(updates)
        settings = self.config_manager.settings
        if hasattr(self.alert_manager, "update_config"):
            self.alert_manager.update_config(settings)
        if self.screen_dimmer is not None:
            self.screen_dimmer.opacity = float(settings.get("overlay_opacity", 0.35))
        if hasattr(self.ui, "update_settings_snapshot"):
            self.ui.update_settings_snapshot(settings)
        self.logger.info("Settings updated: %s", sorted(updates.keys()))
        return settings

    def _evaluate_screen_dim(self, blink_rate: float, timestamp: Optional[float] = None) -> None:
        settings = self.config_manager.settings
        if not settings.get("overlay_enabled", False):
            self._low_blink_since = 0.0
            return

        threshold = float(settings.get("blink_rate_threshold_bpm", settings.get("notice_blink_rate_bpm", 12.0)))
        now = timestamp or time.time()
        if blink_rate >= threshold:
            self._low_blink_since = 0.0
            return

        if self._low_blink_since <= 0:
            self._low_blink_since = now

        dim_delay = float(settings.get("dim_delay_minutes", 5.0)) * 60.0
        cooldown = float(settings.get("subsequent_dim_cooldown_minutes", 20.0)) * 60.0
        if now - self._low_blink_since < dim_delay:
            return
        if self._last_dim_time and now - self._last_dim_time < cooldown:
            return

        self._last_dim_time = now
        self._show_screen_dim()

    def _show_screen_dim(self) -> None:
        self._initialize_screen_dimmer()
        if self.screen_dimmer is None:
            return

        settings = self.config_manager.settings
        opacity = float(settings.get("overlay_opacity", 0.35))

        def pulse() -> None:
            if self.screen_dimmer is None:
                return
            self.screen_dimmer.pulse(duration_ms=2500, opacity=opacity)

        if hasattr(self.ui, "view") and hasattr(self.ui.view, "safe_update"):
            self.ui.view.safe_update(pulse)

    def _schedule_health_tick(self) -> None:
        if hasattr(self.ui, "view") and hasattr(self.ui.view, "after"):
            self.ui.view.after(1000, self._health_tick)

    def _health_tick(self) -> None:
        if self._is_shutting_down:
            return
        try:
            is_running = bool(getattr(self.blink_detector, "is_running", False))
            if is_running:
                metrics = self.blink_analyzer.get_metrics()
                self.alert_manager.evaluate(metrics.blinks_per_minute)
                self._evaluate_screen_dim(metrics.blinks_per_minute)
        except Exception as exc:
            self.handle_exception(exc)
        finally:
            self._schedule_health_tick()

    def get_status(self) -> dict[str, Any]:
        metrics = self.blink_analyzer.get_metrics()
        webcam_connected = False
        latest_ear = 0.0
        camera_fps = 0.0
        try:
            webcam_manager = getattr(self.blink_detector, "webcam_manager", None)
            if webcam_manager is not None and hasattr(webcam_manager, "is_connected"):
                webcam_connected = bool(webcam_manager.is_connected())
            latest_ear = float(getattr(self.blink_detector, "latest_ear", 0.0))
            camera_fps = float(getattr(self.blink_detector, "camera_fps", 0.0))
        except Exception:
            self.logger.debug("Unable to read detector status", exc_info=True)

        return {
            "blink_rate": metrics.blinks_per_minute,
            "blink_count": metrics.blink_count,
            "last_blink_timestamp": metrics.last_blink_timestamp,
            "webcam_connected": webcam_connected,
            "latest_ear": latest_ear,
            "camera_fps": camera_fps,
        }

    def get_session_log(self) -> list[dict[str, Any]]:
        try:
            history = self.alert_manager.get_history()
        except Exception:
            self.logger.debug("Unable to read alert history", exc_info=True)
            return []

        entries: list[dict[str, Any]] = []
        for item in history:
            entries.append(
                {
                    "timestamp": getattr(item, "timestamp", 0.0),
                    "blink_rate": getattr(item, "blink_rate", None),
                    "severity": getattr(item, "severity", "info"),
                    "title": getattr(item, "title", "Alert"),
                    "message": getattr(item, "message", ""),
                }
            )
        return entries

    def shutdown(self) -> None:
        if self._is_shutting_down:
            return
        self._is_shutting_down = True
        self.logger.info("Shutting down Ocolyx application")
        self.event_bus.publish(APP_EVENT_SHUTDOWN)
        self.safe_execute(self.tray.stop)
        self.safe_execute(self.blink_detector.stop)
        self.safe_execute(self.background_service.stop)
        if hasattr(self.ui, "view") and hasattr(self.ui.view, "destroy"):
            self.ui.view.destroy()

    def handle_exception(self, exc: Exception) -> None:
        self.logger.exception("Unhandled exception in Ocolyx application: %s", exc)
        self.event_bus.publish(APP_EVENT_EXCEPTION, exc)

    def show_error(self, title: str, message: str) -> None:
        """Show a user-friendly error dialog on the UI thread when possible.

        Falls back to logging when a UI is not available.
        """
        try:
            if hasattr(self, "ui") and getattr(self.ui, "view", None) is not None:
                # Schedule the messagebox on the main UI thread
                from tkinter import messagebox

                def _show():
                    try:
                        messagebox.showerror(title, message)
                    except Exception:
                        # If messagebox fails, at least log it
                        self.logger.exception("Failed to display messagebox")

                try:
                    self.ui.view.safe_update(_show)
                except Exception:
                    # If the UI scheduling fails, run directly (best-effort)
                    _show()
            else:
                self.logger.error("%s: %s", title, message)
        except Exception:
            self.logger.exception("Unexpected error while attempting to show error dialog")

    def safe_execute(self, func: Callable[..., None], *args: Any, **kwargs: Any) -> None:
        try:
            func(*args, **kwargs)
        except Exception as exc:
            self.handle_exception(exc)

    def _on_blink(self, blink_event: Any) -> None:
        try:
            metrics = self.blink_analyzer.record_blink(getattr(blink_event, "timestamp", None))
            self.event_bus.publish(APP_EVENT_BLINK_DETECTED, blink_event, metrics)
            self.alert_manager.evaluate(metrics.blinks_per_minute)
            self._evaluate_screen_dim(metrics.blinks_per_minute, getattr(blink_event, "timestamp", None))
            self.tray.update_tooltip(metrics.blinks_per_minute)
        except Exception as exc:
            self.handle_exception(exc)

    def _on_disconnect(self, message: str) -> None:
        self.logger.warning("Blink detector disconnected: %s", message)

    def _on_reconnect(self, message: str) -> None:
        self.logger.info("Blink detector reconnected: %s", message)

    def _on_error(self, exc: Exception) -> None:
        self.handle_exception(exc)

    def _handle_blink_event(self, blink_event: Any, metrics: Any) -> None:
        self.logger.debug("Event bus received blink event. Current BPM: %.2f", metrics.blinks_per_minute)
        if hasattr(self.ui, "update_live_status"):
            self.ui.update_live_status(self.get_status())

    def _handle_alert_event(self, *args: Any, **kwargs: Any) -> None:
        self.logger.debug("Event bus received alert event: %s %s", args, kwargs)

    def _handle_exception(self, exc: Exception) -> None:
        # Log and present a friendly dialog to the user when exceptions bubble up
        self.logger.error("Application exception event: %s", exc)
        try:
            self.show_error("Application error", str(exc))
        except Exception:
            self.logger.exception("Failed to show application error dialog")

    def _handle_shutdown(self, *args: Any, **kwargs: Any) -> None:
        self.logger.info("Application shutdown event received")


OcolyxApp = ApplicationController
