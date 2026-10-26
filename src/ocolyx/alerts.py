"""Smart alert system for Ocolyx."""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Deque, Dict, List, Optional

import customtkinter as ctk


AlertDialogCallback = Callable[[str, str, str], None]


@dataclass
class AlertHistoryEntry:
    timestamp: float
    blink_rate: float
    severity: str
    title: str
    message: str
    suppressed: bool


class SmartAlertManager:
    def __init__(
        self,
        config: Dict[str, Any],
        logger: logging.Logger,
        dialog_callback: Optional[AlertDialogCallback] = None,
        ui_root: Optional[ctk.CTk] = None,
    ) -> None:
        self.config = config
        self.logger = logger
        self.dialog_callback = dialog_callback
        self.ui_root = ui_root

        self.alert_enabled = config.get("alert_enabled", True)
        self.popup_enabled = config.get("alert_popup_enabled", True)
        self.alert_delay_seconds = float(config.get("alert_delay_minutes", 1.0)) * 60.0
        self.escalation_delay_seconds = config.get("escalation_delay_seconds", 30)
        self.recovery_reset_seconds = max(60.0, self.alert_delay_seconds * 2.0)
        self.max_history_entries = config.get("alert_history_limit", 100)
        self.severity_levels = config.get("alert_severity_levels", ["notice", "warning", "critical"])

        self._last_alert_time = 0.0
        self._low_rate_since = 0.0
        self._healthy_since = 0.0
        self._notification_shown_this_session = False
        self._last_severity_index = -1
        self._alert_history: Deque[AlertHistoryEntry] = deque(maxlen=self.max_history_entries)
        self._lock = threading.Lock()

    def evaluate(self, blink_rate: float) -> None:
        now = time.time()
        with self._lock:
            if not self.alert_enabled:
                return

            severity_index = self._severity_index_from_rate(blink_rate)
            if severity_index is None:
                self._low_rate_since = 0.0
                if self._notification_shown_this_session:
                    if self._healthy_since <= 0:
                        self._healthy_since = now
                    elif now - self._healthy_since >= self.recovery_reset_seconds:
                        self._notification_shown_this_session = False
                        self._last_alert_time = 0.0
                        self._last_severity_index = -1
                        self.logger.info("Alert notification state reset after sustained healthy blink rate")
                self.logger.debug("Blink rate healthy; no alert triggered: %.2f", blink_rate)
                return

            self._healthy_since = 0.0
            if self._low_rate_since <= 0:
                self._low_rate_since = now

            if self._notification_shown_this_session:
                self.logger.debug("Alert notification already shown for this monitoring session")
                return

            if now - self._low_rate_since < self.alert_delay_seconds:
                self.logger.debug("Alert pending until delay elapses: sleepy blink rate %.2f", blink_rate)
                return

            if self._should_escalate(severity_index, now):
                severity_index = min(len(self.severity_levels) - 1, severity_index + 1)

            severity = self.severity_levels[severity_index]
            title, message = self._build_alert_message(severity, blink_rate)

            entry = AlertHistoryEntry(
                timestamp=now,
                blink_rate=blink_rate,
                severity=severity,
                title=title,
                message=message,
                suppressed=False,
            )

            self._alert_history.append(entry)
            self._last_alert_time = now
            self._notification_shown_this_session = True
            self._last_severity_index = severity_index

        self.logger.warning("Alert triggered (%s): %s", severity, message)
        self._show_alert(title, message, severity)

    def _severity_index_from_rate(self, blink_rate: float) -> Optional[int]:
        notice = self.config.get("blink_rate_threshold_bpm", self.config.get("notice_blink_rate_bpm", 12.0))
        warning = self.config.get("warning_blink_rate_bpm", max(1.0, notice - 2.0))
        critical = self.config.get("critical_blink_rate_bpm", max(1.0, notice - 4.0))

        if blink_rate < critical:
            return self.severity_levels.index("critical") if "critical" in self.severity_levels else 2
        if blink_rate < warning:
            return self.severity_levels.index("warning") if "warning" in self.severity_levels else 1
        if blink_rate < notice:
            return self.severity_levels.index("notice") if "notice" in self.severity_levels else 0
        return None

    def _should_escalate(self, severity_index: int, now: float) -> bool:
        if self._last_severity_index < 0:
            return False

        if severity_index <= self._last_severity_index:
            return False

        return now - self._last_alert_time >= self.escalation_delay_seconds

    def _build_alert_message(self, severity: str, blink_rate: float) -> tuple[str, str]:
        if severity == "critical":
            title = "Critical Blink Rate"
            message = f"Blink rate is dangerously low at {blink_rate:.1f} BPM. Please take an immediate break."
        elif severity == "warning":
            title = "Low Blink Rate"
            message = f"Blink rate is below healthy levels ({blink_rate:.1f} BPM). Remember to blink regularly."
        else:
            title = "Blink Rate Warning"
            message = f"Blink rate is below recommended range ({blink_rate:.1f} BPM). Keep your eyes refreshed."
        return title, message

    def _show_alert(self, title: str, message: str, severity: str) -> None:
        if self.dialog_callback:
            self.dialog_callback(title, message, severity)
            return

        if not self.popup_enabled:
            return

        if not self.ui_root:
            return
        try:
            if not self.ui_root.winfo_exists():
                return
        except Exception:
            return

        def _open_dialog() -> None:
            try:
                if not self.ui_root or not self.ui_root.winfo_exists():
                    return
            except Exception:
                return
            popup = ctk.CTkToplevel(self.ui_root)
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

        try:
            if hasattr(self.ui_root, "safe_update"):
                self.ui_root.safe_update(_open_dialog)
            elif hasattr(self.ui_root, "schedule_after"):
                self.ui_root.schedule_after(0, _open_dialog)
            else:
                self.ui_root.after(0, _open_dialog)
        except Exception as exc:
            self.logger.debug("Unable to schedule alert dialog: %s", exc)

    def get_history(self, limit: Optional[int] = None) -> List[AlertHistoryEntry]:
        with self._lock:
            entries = list(self._alert_history)
        if limit is not None:
            return entries[-limit:]
        return entries

    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "enabled": self.alert_enabled,
                "popup_enabled": self.popup_enabled,
                "escalation_delay_seconds": self.escalation_delay_seconds,
                "last_alert_time": self._last_alert_time,
                "last_severity": self.severity_levels[self._last_severity_index] if self._last_severity_index >= 0 else "none",
            }

    def update_config(self, config: Dict[str, Any]) -> None:
        with self._lock:
            self.config = config
            self.alert_enabled = config.get("alert_enabled", True)
            self.popup_enabled = config.get("alert_popup_enabled", True)
            self.alert_delay_seconds = float(config.get("alert_delay_minutes", 1.0)) * 60.0
            self.recovery_reset_seconds = max(60.0, self.alert_delay_seconds * 2.0)
            self.escalation_delay_seconds = config.get("escalation_delay_seconds", 30)
            self.max_history_entries = config.get("alert_history_limit", 100)

    def reset_session(self) -> None:
        with self._lock:
            self._low_rate_since = 0.0
            self._healthy_since = 0.0
            self._last_alert_time = 0.0
            self._last_severity_index = -1
            self._notification_shown_this_session = False

    def reset_history(self) -> None:
        with self._lock:
            self._alert_history.clear()
            self._last_alert_time = 0.0
            self._last_severity_index = -1
            self._notification_shown_this_session = False


AlertManager = SmartAlertManager
