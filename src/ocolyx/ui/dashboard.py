"""Modern dashboard view for Ocolyx."""

from pathlib import Path
import queue
import threading
from typing import Any, Callable
import tkinter as tk

import customtkinter as ctk

from .theme import ThemeManager
from ..utils.asset_loader import load_tk_icon


class DashboardView(ctk.CTk):
    def __init__(
        self,
        config: dict[str, Any],
        logo_path: Path | None,
        window_icon_path: Path | None,
        on_start: Callable[[], None],
        on_stop: Callable[[], None],
        on_minimize: Callable[[], None],
        on_settings_change: Callable[[dict[str, Any]], None],
        logger: Any,
    ) -> None:
        super().__init__()
        self.config = config
        self.logo_path = logo_path
        self.window_icon_path = window_icon_path
        self.on_start = on_start
        self.on_stop = on_stop
        self.on_minimize = on_minimize
        self.on_settings_change = on_settings_change
        self.logger = logger
        self._window_icon_photo = None
        self._logo_photo = None
        self._ui_queue: queue.Queue[tuple[Callable[..., None], tuple[Any, ...], dict[str, Any]]] = queue.Queue()
        self._main_thread_id = threading.get_ident()
        self._max_ui_callbacks_per_tick = 50
        self._current_view = "dashboard"
        self._session_log_entries: list[dict[str, Any]] = []
        self._setting_vars: dict[str, Any] = {}
        self._settings_error_var: ctk.StringVar | None = None
        self._settings_feedback_var: ctk.StringVar | None = None
        self._settings_feedback_frame: ctk.CTkFrame | None = None
        self._settings_feedback_label: ctk.CTkLabel | None = None
        self._settings_feedback_after_id: str | None = None

        self.theme = ThemeManager(config.get("theme", {}), logger=logger)
        self.theme.apply()

        self.title("Ocolyx • Cyber Blue")
        self.geometry(f"{config.get('window', {}).get('width', 960)}x{config.get('window', {}).get('height', 620)}")
        self.minsize(config.get('window', {}).get('min_width', 800), config.get('window', {}).get('min_height', 540))
        self.configure(fg_color=self.theme.bg_main)

        self.protocol("WM_DELETE_WINDOW", self._minimize_to_tray)
        self._apply_window_icon()
        self._create_variables()
        self._configure_grid()
        self._build_interface()
        self.after(0, self._dispatch_ui_queue)

    def _create_variables(self) -> None:
        self.blink_rate_value = ctk.StringVar(value="0.0 bpm")
        self.webcam_status_value = ctk.StringVar(value="Offline")
        self.monitor_status_value = ctk.StringVar(value="Stopped")
        self.alert_status_value = ctk.StringVar(value="No active alerts")
        self.session_timer_value = ctk.StringVar(value="00:00:00")

    def _configure_grid(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

    def _apply_window_icon(self) -> None:
        if self.window_icon_path is not None and self.window_icon_path.exists() and self.window_icon_path.suffix.lower() == ".ico":
            try:
                self.iconbitmap(str(self.window_icon_path))
                return
            except Exception as exc:
                self.logger.warning("Failed to set window icon from %s: %s", self.window_icon_path, exc)

        if self.logo_path is not None and self.logo_path.exists():
            photo = load_tk_icon(self.logo_path, size=(64, 64), logger=self.logger)
            if photo is not None:
                try:
                    self.iconphoto(True, photo)
                    self._window_icon_photo = photo
                    return
                except Exception as exc:
                    self.logger.warning("Failed to set window icon photo from %s: %s", self.logo_path, exc)

    def _build_interface(self) -> None:
        self.sidebar = ctk.CTkFrame(self, width=240, corner_radius=0, fg_color=self.theme.bg_sidebar)
        self.sidebar.grid(row=0, column=0, sticky="nswe")
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(8, weight=1)

        self.branding_label = ctk.CTkLabel(self.sidebar, text="OCOLYX", font=self.theme.display_font, text_color=self.theme.accent)
        self.branding_label.grid(row=0, column=0, padx=20, pady=(24, 4), sticky="w")

        subtitle_row = 1
        if self.logo_path is not None and self.logo_path.exists():
            photo = load_tk_icon(self.logo_path, size=(96, 96), logger=self.logger)
            if photo is not None:
                self._logo_photo = photo
                self.logo_label = tk.Label(self.sidebar, image=photo, bg=self.theme.bg_sidebar, bd=0)
                self.logo_label.image = photo
                self.logo_label.grid(row=1, column=0, padx=20, pady=(8, 8), sticky="w")
                subtitle_row = 2

        self.branding_subtitle = ctk.CTkLabel(self.sidebar, text="Cyber-eye defense", font=self.theme.caption_font, text_color=self.theme.text_secondary)
        self.branding_subtitle.grid(row=subtitle_row, column=0, padx=20, pady=(0, 18), sticky="w")

        nav_row = subtitle_row + 1
        self.nav_dashboard = ctk.CTkButton(self.sidebar, text="Dashboard", command=self.show_dashboard_view)
        self.theme.style_primary_button(self.nav_dashboard)
        self.nav_dashboard.grid(row=nav_row, column=0, padx=20, pady=8, sticky="ew")

        self.nav_settings = ctk.CTkButton(self.sidebar, text="Settings", command=self.show_settings_view)
        self.theme.style_secondary_button(self.nav_settings)
        self.nav_settings.grid(row=nav_row + 1, column=0, padx=20, pady=8, sticky="ew")

        self.nav_history = ctk.CTkButton(self.sidebar, text="Session Log", command=self.show_session_log_view)
        self.theme.style_secondary_button(self.nav_history)
        self.nav_history.grid(row=nav_row + 2, column=0, padx=20, pady=8, sticky="ew")

        self.sidebar_info = ctk.CTkFrame(self.sidebar, fg_color=self.theme.panel_bg, corner_radius=self.theme.border_radius)
        self.theme.style_panel(self.sidebar_info, corner_radius=self.theme.border_radius)
        self.sidebar_info.grid(row=nav_row + 3, column=0, padx=20, pady=(10, 0), sticky="ew")
        self.sidebar_info.grid_columnconfigure(0, weight=1)

        self.sidebar_info_title = ctk.CTkLabel(self.sidebar_info, text="Live status", font=self.theme.body_font, text_color=self.theme.accent)
        self.sidebar_info_title.grid(row=0, column=0, padx=16, pady=(16, 4), sticky="w")

        self.sidebar_info_text = ctk.CTkLabel(self.sidebar_info, text="Adaptive blur, thermal rhythm cues, and instant break prompts in one control plane.", font=self.theme.caption_font, text_color=self.theme.text_secondary, wraplength=180)
        self.sidebar_info_text.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="w")

        self.main_frame = ctk.CTkFrame(self, corner_radius=30, fg_color=self.theme.bg_main)
        self.theme.style_surface(self.main_frame, corner_radius=30)
        self.main_frame.grid(row=0, column=1, padx=(20, 20), pady=20, sticky="nswe")
        self.main_frame.grid_columnconfigure(0, weight=1)

        self.header_frame = ctk.CTkFrame(self.main_frame, fg_color=self.theme.header_bg, corner_radius=24)
        self.theme.style_panel(self.header_frame, corner_radius=24)
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 12))
        self.header_frame.grid_columnconfigure(0, weight=1)

        self.header_title = ctk.CTkLabel(self.header_frame, text="Eye-strain defense dashboard", font=self.theme.display_font, text_color=self.theme.text_primary)
        self.header_title.grid(row=0, column=0, padx=20, pady=(20, 4), sticky="w")

        self.header_subtitle = ctk.CTkLabel(self.header_frame, text="Neon-blue telemetry, smooth hover states, and a modern control cockpit for every session.", font=self.theme.body_font, text_color=self.theme.text_secondary, wraplength=620)
        self.header_subtitle.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="w")

        self.body_frame = ctk.CTkFrame(self.main_frame, fg_color=self.theme.bg_main)
        self.body_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nswe")
        self.body_frame.grid_columnconfigure((0, 1), weight=1)
        self.body_frame.grid_rowconfigure((0, 1, 2), weight=1)

        self.show_dashboard_view()

    def _clear_body(self) -> None:
        for child in self.body_frame.winfo_children():
            child.destroy()

    def show_dashboard_view(self) -> None:
        self._current_view = "dashboard"
        self._clear_body()
        self.header_title.configure(text="Eye-strain defense dashboard")
        self.header_subtitle.configure(text="Live blink telemetry, session controls, and alert status.")
        self._set_nav_state("dashboard")
        self._build_status_cards()
        self._build_controls_panel()
        self._build_settings_panel()

    def show_settings_view(self) -> None:
        self._current_view = "settings"
        self._clear_body()
        self.header_title.configure(text="Settings")
        self.header_subtitle.configure(text="Monitoring thresholds, alert timing, and screen dimming.")
        self._set_nav_state("settings")

        panel = ctk.CTkScrollableFrame(self.body_frame, fg_color=self.theme.panel_bg, corner_radius=self.theme.border_radius)
        self.theme.style_panel(panel, corner_radius=self.theme.border_radius)
        panel.grid(row=0, column=0, columnspan=2, padx=20, pady=20, sticky="nswe")
        panel.grid_columnconfigure(1, weight=1)
        self._setting_vars = {}
        self._settings_error_var = ctk.StringVar(value="")
        self._settings_feedback_var = ctk.StringVar(value="")
        self._settings_feedback_frame = None
        self._settings_feedback_label = None

        row = 0
        row = self._create_switch_setting(panel, row, "Screen dimming", "overlay_enabled")
        row = self._create_numeric_setting(panel, row, "Blink-rate threshold", "blink_rate_threshold_bpm", "bpm")
        row = self._create_numeric_setting(panel, row, "First notification delay", "alert_delay_minutes", "min")
        row = self._create_numeric_setting(panel, row, "First screen dim delay", "dim_delay_minutes", "min")
        row = self._create_numeric_setting(panel, row, "Screen dim cooldown", "subsequent_dim_cooldown_minutes", "min")

        apply_btn = ctk.CTkButton(panel, text="Apply", command=self._apply_numeric_settings)
        self.theme.style_primary_button(apply_btn)
        apply_btn.grid(row=row, column=1, padx=20, pady=(18, 8), sticky="e")

        error_label = ctk.CTkLabel(panel, textvariable=self._settings_error_var, font=self.theme.caption_font, text_color=self.theme.danger)
        error_label.grid(row=row + 1, column=0, columnspan=2, padx=20, pady=(0, 12), sticky="w")

        self._settings_feedback_frame = ctk.CTkFrame(
            panel,
            fg_color=self.theme.darken(self.theme.panel_bg, 0.12),
            corner_radius=self.theme.border_radius,
            border_width=1,
            border_color=self.theme.accent,
        )
        self._settings_feedback_frame.grid(row=row + 2, column=0, columnspan=2, padx=20, pady=(0, 16), sticky="ew")
        self._settings_feedback_frame.grid_columnconfigure(0, weight=1)
        self._settings_feedback_label = ctk.CTkLabel(
            self._settings_feedback_frame,
            textvariable=self._settings_feedback_var,
            font=self.theme.body_font,
            text_color=self.theme.success,
        )
        self._settings_feedback_label.grid(row=0, column=0, padx=14, pady=10, sticky="w")
        self._settings_feedback_frame.grid_remove()

    def show_session_log_view(self) -> None:
        self._current_view = "session_log"
        self._clear_body()
        self.header_title.configure(text="Session Log")
        self.header_subtitle.configure(text="Recent alert and blink-rate events from this session.")
        self._set_nav_state("session_log")

        panel = ctk.CTkScrollableFrame(self.body_frame, fg_color=self.theme.panel_bg, corner_radius=self.theme.border_radius)
        self.theme.style_panel(panel, corner_radius=self.theme.border_radius)
        panel.grid(row=0, column=0, columnspan=2, padx=20, pady=20, sticky="nswe")
        panel.grid_columnconfigure(0, weight=1)

        if not self._session_log_entries:
            empty_label = ctk.CTkLabel(panel, text="No session events yet", font=self.theme.body_font, text_color=self.theme.text_secondary)
            empty_label.grid(row=0, column=0, padx=20, pady=20, sticky="w")
            return

        for row, entry in enumerate(reversed(self._session_log_entries[-50:])):
            title = entry.get("title", "Session event")
            message = entry.get("message", "")
            severity = entry.get("severity", "info")
            blink_rate = entry.get("blink_rate")
            suffix = f" - {blink_rate:.1f} bpm" if isinstance(blink_rate, (int, float)) else ""
            item = ctk.CTkLabel(
                panel,
                text=f"{severity.upper()}  {title}{suffix}\n{message}",
                font=self.theme.body_font,
                text_color=self.theme.text_primary,
                justify="left",
                anchor="w",
            )
            item.grid(row=row, column=0, padx=20, pady=8, sticky="ew")

    def _set_nav_state(self, active: str) -> None:
        self.theme.style_primary_button(self.nav_dashboard if active == "dashboard" else self.nav_settings if active == "settings" else self.nav_history)
        for name, button in (("dashboard", self.nav_dashboard), ("settings", self.nav_settings), ("session_log", self.nav_history)):
            if name != active:
                self.theme.style_secondary_button(button)

    def _create_switch_setting(self, parent: Any, row: int, label: str, key: str) -> int:
        variable = tk.BooleanVar(value=bool(self.config.get(key, False)))
        self._setting_vars[key] = variable
        label_widget = ctk.CTkLabel(parent, text=label, font=self.theme.body_font, text_color=self.theme.text_secondary)
        label_widget.grid(row=row, column=0, padx=20, pady=10, sticky="w")
        switch = ctk.CTkSwitch(
            parent,
            text="",
            variable=variable,
            command=lambda setting_key=key, setting_var=variable: self._apply_boolean_setting(setting_key, setting_var),
        )
        switch.grid(row=row, column=1, padx=20, pady=10, sticky="e")
        return row + 1

    def _create_numeric_setting(self, parent: Any, row: int, label: str, key: str, suffix: str) -> int:
        variable = ctk.StringVar(value=self._format_setting_value(self.config.get(key, "")))
        self._setting_vars[key] = variable
        label_widget = ctk.CTkLabel(parent, text=label, font=self.theme.body_font, text_color=self.theme.text_secondary)
        label_widget.grid(row=row, column=0, padx=20, pady=10, sticky="w")
        entry = ctk.CTkEntry(parent, textvariable=variable, width=120)
        entry.grid(row=row, column=1, padx=(20, 72), pady=10, sticky="e")
        entry.bind("<Return>", lambda _: self._apply_numeric_settings())
        suffix_label = ctk.CTkLabel(parent, text=suffix, font=self.theme.caption_font, text_color=self.theme.text_muted)
        suffix_label.grid(row=row, column=1, padx=20, pady=10, sticky="e")
        return row + 1

    def _format_setting_value(self, value: Any) -> str:
        if isinstance(value, float):
            return f"{value:.2f}".rstrip("0").rstrip(".")
        return str(value)

    def _apply_boolean_setting(self, key: str, variable: tk.BooleanVar) -> None:
        self.set_settings_error("")
        self.clear_settings_feedback()
        self.on_settings_change({key: bool(variable.get())})

    def _apply_numeric_settings(self) -> None:
        updates: dict[str, Any] = {}
        numeric_fields = {
            "blink_rate_threshold_bpm": ("Blink-rate threshold", "bpm"),
            "alert_delay_minutes": ("First notification delay", "minutes"),
            "dim_delay_minutes": ("First screen dim delay", "minutes"),
            "subsequent_dim_cooldown_minutes": ("Screen dim cooldown", "minutes"),
        }
        try:
            for key, (label, unit) in numeric_fields.items():
                raw_value = self._setting_vars[key].get().strip()
                if not raw_value:
                    raise ValueError(f"{label} cannot be empty.")
                try:
                    value = float(raw_value)
                except ValueError as exc:
                    raise ValueError(f"{label} must be a number.") from exc
                if value <= 0:
                    raise ValueError(f"{label} must be greater than 0 {unit}.")
                if value.is_integer():
                    value = int(value)
                updates[key] = value

            threshold = float(updates["blink_rate_threshold_bpm"])
            updates["notice_blink_rate_bpm"] = threshold
            updates["warning_blink_rate_bpm"] = max(1.0, threshold - 2.0)
            updates["critical_blink_rate_bpm"] = max(1.0, threshold - 4.0)
        except ValueError as exc:
            self.set_settings_error(str(exc))
            return

        self.set_settings_error("")
        self.clear_settings_feedback()
        self.on_settings_change(updates)

    def _build_status_cards(self) -> None:
        self.card_frame = ctk.CTkFrame(self.body_frame, fg_color=self.theme.card_bg, corner_radius=self.theme.card_radius)
        self.theme.style_card(self.card_frame)
        self.card_frame.grid(row=0, column=0, columnspan=2, padx=20, pady=(20, 8), sticky="nswe")
        self.card_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.blink_card = self._create_status_card("Blink Rate", self.blink_rate_value)
        self.blink_card.grid(row=0, column=0, padx=10, pady=10, sticky="nswe")
        self.webcam_card = self._create_status_card("Webcam", self.webcam_status_value)
        self.webcam_card.grid(row=0, column=1, padx=10, pady=10, sticky="nswe")
        self.monitor_card = self._create_status_card("Monitoring", self.monitor_status_value)
        self.monitor_card.grid(row=0, column=2, padx=10, pady=10, sticky="nswe")
        self.alert_card = self._create_status_card("Alert Status", self.alert_status_value)
        self.alert_card.grid(row=1, column=0, padx=10, pady=10, sticky="nswe", columnspan=2)
        self.timer_card = self._create_status_card("Session Timer", self.session_timer_value)
        self.timer_card.grid(row=1, column=2, padx=10, pady=10, sticky="nswe")

    def _build_controls_panel(self) -> None:
        self.controls_frame = ctk.CTkFrame(self.body_frame, fg_color=self.theme.panel_bg, corner_radius=self.theme.border_radius)
        self.theme.style_panel(self.controls_frame, corner_radius=self.theme.border_radius)
        self.controls_frame.grid(row=1, column=0, padx=20, pady=(8, 8), sticky="nswe")
        self.controls_frame.grid_columnconfigure((0, 1), weight=1)

        self.controls_title = ctk.CTkLabel(self.controls_frame, text="Session controls", font=self.theme.heading_font, text_color=self.theme.text_primary)
        self.controls_title.grid(row=0, column=0, padx=20, pady=(18, 8), columnspan=2, sticky="w")

        self.start_button = ctk.CTkButton(self.controls_frame, text="Start Monitoring", command=self.on_start)
        self.theme.style_primary_button(self.start_button)
        self.start_button.grid(row=1, column=0, padx=20, pady=(8, 18), sticky="ew")

        self.stop_button = ctk.CTkButton(self.controls_frame, text="Stop Monitoring", command=self.on_stop)
        self.stop_button.configure(
            fg_color=self.theme.danger,
            hover_color=self.theme.lighten(self.theme.danger, 0.12),
            text_color=self.theme.text_primary,
            corner_radius=self.theme.border_radius,
            border_width=1,
            border_color=self.theme.lighten(self.theme.danger, 0.2),
            font=self.theme.body_font,
        )
        self.stop_button.grid(row=1, column=1, padx=20, pady=(8, 18), sticky="ew")

    def _build_settings_panel(self) -> None:
        self.settings_frame = ctk.CTkFrame(self.body_frame, fg_color=self.theme.panel_bg, corner_radius=self.theme.border_radius)
        self.theme.style_panel(self.settings_frame, corner_radius=self.theme.border_radius)
        self.settings_frame.grid(row=1, column=1, padx=20, pady=(8, 8), sticky="nswe")
        self.settings_frame.grid_columnconfigure(0, weight=1)
        self.settings_frame.grid_columnconfigure(1, weight=1)

        settings_title = ctk.CTkLabel(self.settings_frame, text="Current settings", font=self.theme.heading_font, text_color=self.theme.text_primary)
        settings_title.grid(row=0, column=0, padx=20, pady=(18, 8), sticky="w")

        self._create_setting_item("Blink Threshold", f"{self.config.get('blink_threshold_seconds', 6)} sec", row=1)
        self._create_setting_item("Overlay", "Enabled" if self.config.get('overlay_enabled', False) else "Disabled", row=2)
        self._create_setting_item("Theme", self.config.get('theme', 'dark'), row=3)
        self._create_setting_item("Interval", f"{self.config.get('monitor_interval_seconds', 1)} sec", row=4)

    def _create_status_card(self, title: str, variable: Any) -> ctk.CTkFrame:
        card = ctk.CTkFrame(self.card_frame, fg_color=self.theme.card_bg, corner_radius=self.theme.card_radius)
        self.theme.style_card(card)
        label = ctk.CTkLabel(card, text=title.upper(), font=self.theme.body_font, text_color=self.theme.accent)
        label.pack(anchor="w", padx=16, pady=(16, 4))
        value = ctk.CTkLabel(card, textvariable=variable, font=self.theme.heading_font, text_color=self.theme.text_primary)
        value.pack(anchor="w", padx=16, pady=(0, 16))
        return card

    def _create_setting_item(self, name: str, value: str, row: int) -> None:
        label = ctk.CTkLabel(self.settings_frame, text=name, font=self.theme.body_font, text_color=self.theme.text_secondary)
        label.grid(row=row, column=0, padx=(20, 10), pady=(10, 2), sticky="w")
        value_label = ctk.CTkLabel(self.settings_frame, text=value, font=self.theme.body_font, text_color=self.theme.text_primary)
        value_label.grid(row=row, column=1, padx=(10, 20), pady=(10, 2), sticky="e")

    def _minimize_to_tray(self) -> None:
        self.on_minimize()

    def set_blink_rate(self, value: str) -> None:
        self.blink_rate_value.set(value)

    def set_webcam_status(self, value: str) -> None:
        self.webcam_status_value.set(value)

    def set_monitor_status(self, value: str) -> None:
        self.monitor_status_value.set(value)

    def set_alert_status(self, value: str) -> None:
        self.alert_status_value.set(value)

    def set_session_timer(self, value: str) -> None:
        self.session_timer_value.set(value)

    def set_session_log_entries(self, entries: list[dict[str, Any]]) -> None:
        self._session_log_entries = entries
        if self._current_view == "session_log":
            self.show_session_log_view()

    def apply_settings_snapshot(self, settings: dict[str, Any]) -> None:
        self.config = settings
        if self._current_view == "settings":
            for key, variable in self._setting_vars.items():
                if key in settings:
                    if isinstance(variable, tk.BooleanVar):
                        variable.set(bool(settings[key]))
                    else:
                        variable.set(self._format_setting_value(settings[key]))
        self.set_settings_error("")

    def set_settings_error(self, message: str) -> None:
        if message:
            self.clear_settings_feedback()
        if self._settings_error_var is not None:
            self._settings_error_var.set(message)

    def show_settings_success(self, message: str = "Settings applied successfully") -> None:
        self._show_settings_feedback(message, self.theme.success, self.theme.accent, auto_hide_ms=2500)

    def clear_settings_feedback(self) -> None:
        if self._settings_feedback_after_id is not None:
            try:
                self.after_cancel(self._settings_feedback_after_id)
            except Exception:
                pass
            self._settings_feedback_after_id = None
        if self._settings_feedback_var is not None:
            self._settings_feedback_var.set("")
        if self._settings_feedback_frame is not None and self._settings_feedback_frame.winfo_exists():
            self._settings_feedback_frame.grid_remove()

    def _show_settings_feedback(self, message: str, text_color: str, border_color: str, auto_hide_ms: int) -> None:
        if self._settings_feedback_frame is None or self._settings_feedback_var is None:
            return
        if not self._settings_feedback_frame.winfo_exists():
            return
        if self._settings_feedback_after_id is not None:
            try:
                self.after_cancel(self._settings_feedback_after_id)
            except Exception:
                pass
            self._settings_feedback_after_id = None

        self._settings_feedback_var.set(message)
        if self._settings_feedback_label is not None and self._settings_feedback_label.winfo_exists():
            self._settings_feedback_label.configure(text_color=text_color)
        self._settings_feedback_frame.configure(border_color=border_color)
        self._settings_feedback_frame.grid()
        self._settings_feedback_after_id = self.after(auto_hide_ms, self.clear_settings_feedback)

    def _dispatch_ui_queue(self) -> None:
        if not self.winfo_exists():
            return

        processed = 0
        while processed < self._max_ui_callbacks_per_tick:
            try:
                callback, args, kwargs = self._ui_queue.get_nowait()
            except queue.Empty:
                break

            try:
                callback(*args, **kwargs)
            except Exception as exc:
                self.logger.exception("Queued UI callback failed: %s", exc)
            processed += 1

        self.after(10, self._dispatch_ui_queue)

    def safe_update(self, callback: Callable[..., None], *args: Any, **kwargs: Any) -> None:
        if threading.get_ident() == self._main_thread_id:
            callback(*args, **kwargs)
            return

        self._ui_queue.put((callback, args, kwargs))
