"""Application configuration manager."""

from __future__ import annotations

import json
import shutil
import time
from datetime import datetime
from json import JSONDecodeError
from pathlib import Path
from typing import Any


class ConfigValidationError(Exception):
    pass


DEFAULT_SETTINGS: dict[str, Any] = {
    "blink_threshold_seconds": 6,
    "blink_rate_threshold_bpm": 12,
    "monitor_interval_seconds": 1,
    "alert_delay_minutes": 1.0,
    "dim_delay_minutes": 5.0,
    "subsequent_dim_cooldown_minutes": 20.0,
    "ear_threshold": 0.23,
    "consecutive_frame_count": 3,
    "alert_enabled": True,
    "alert_popup_enabled": True,
    "escalation_delay_seconds": 30,
    "notice_blink_rate_bpm": 12,
    "warning_blink_rate_bpm": 10,
    "critical_blink_rate_bpm": 8,
    "alert_history_limit": 100,
    "alert_message": "Please take a short break and blink slowly.",
    "log_level": "INFO",
    "log_when": "midnight",
    "log_backup_days": 30,
    "overlay_enabled": False,
    "overlay_opacity": 0.35,
    "theme": {
        "mode": "dark",
        "accent_color": "blue",
    },
    "window": {
        "width": 960,
        "height": 620,
        "min_width": 800,
        "min_height": 540,
    },
}


_CONFIG_SCHEMA: dict[str, dict[str, Any]] = {
    "blink_threshold_seconds": {"type": (int, float), "min": 1, "max": 60},
    "blink_rate_threshold_bpm": {"type": (int, float), "min": 1, "max": 60},
    "monitor_interval_seconds": {"type": (int, float), "min": 0.1, "max": 10},
    "alert_delay_minutes": {"type": (int, float), "exclusive_min": 0, "max": 120},
    "dim_delay_minutes": {"type": (int, float), "exclusive_min": 0, "max": 120},
    "subsequent_dim_cooldown_minutes": {"type": (int, float), "exclusive_min": 0, "max": 240},
    "ear_threshold": {"type": (int, float), "min": 0.1, "max": 0.4},
    "consecutive_frame_count": {"type": int, "min": 1, "max": 10},
    "theme": {"type": dict},
    "alert_enabled": {"type": bool},
    "alert_popup_enabled": {"type": bool},
    "escalation_delay_seconds": {"type": (int, float), "min": 0, "max": 600},
    "notice_blink_rate_bpm": {"type": (int, float), "min": 1, "max": 60},
    "warning_blink_rate_bpm": {"type": (int, float), "min": 1, "max": 60},
    "critical_blink_rate_bpm": {"type": (int, float), "min": 1, "max": 60},
    "alert_history_limit": {"type": int, "min": 1, "max": 500},
    "alert_message": {"type": str},
    "overlay_enabled": {"type": bool},
    "overlay_opacity": {"type": (int, float), "min": 0.0, "max": 1.0},
    "alert_history_limit": {"type": int, "min": 1, "max": 500},
    "alert_message": {"type": str},
    "log_level": {"type": str},
    "log_when": {"type": str},
    "log_backup_days": {"type": int, "min": 1, "max": 90},
    "overlay_enabled": {"type": bool},
    "overlay_opacity": {"type": (int, float), "min": 0.0, "max": 1.0},
    "window": {"type": dict},
}


class ConfigManager:
    def __init__(self, config_path: Path, default_config_path: Path | None = None, logger=None) -> None:
        self.config_path = config_path
        self.default_config_path = default_config_path or self.config_path
        self.logger = logger
        self.settings: dict[str, Any] = {}
        self.corrupted: bool = False
        self._last_modified: float | None = None
        self.load()

    def load(self, force: bool = False) -> dict[str, Any]:
        if not self.config_path.exists():
            self._create_default_config()

        if not force and self._has_not_changed():
            return self.settings

        self._last_modified = self.config_path.stat().st_mtime
        try:
            with self.config_path.open("r", encoding="utf-8") as handle:
                raw_settings = json.load(handle)
        except (JSONDecodeError, OSError) as exc:
            self._backup_corrupted_config(exc)
            self._create_default_config()
            self.corrupted = True
            return self.settings

        self.settings = self._validate_settings(raw_settings)
        # Successfully loaded a valid config
        self.corrupted = False
        self.save(self.settings)
        return self.settings

    def reload_if_changed(self) -> bool:
        if self._has_not_changed():
            return False
        self.load(force=True)
        return True

    def save(self, updates: dict[str, Any]) -> None:
        merged = self.settings.copy()
        for key, value in updates.items():
            if key == "theme" and isinstance(value, dict):
                merged["theme"] = {**merged.get("theme", {}), **value}
            elif key == "window" and isinstance(value, dict):
                merged["window"] = {**merged.get("window", {}), **value}
            else:
                merged[key] = value

        validated = self._validate_settings(merged)
        self.settings = validated
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with self.config_path.open("w", encoding="utf-8") as handle:
            json.dump(validated, handle, indent=2)
        self._last_modified = self.config_path.stat().st_mtime

    def get(self, key: str, default: Any = None) -> Any:
        return self.settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.save({key: value})

    def backup_current_config(self) -> Path | None:
        if not self.config_path.exists():
            return None
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_path = self.config_path.with_name(f"{self.config_path.stem}_backup_{timestamp}{self.config_path.suffix}")
        shutil.copy2(self.config_path, backup_path)
        return backup_path

    def _create_default_config(self) -> None:
        default_settings = DEFAULT_SETTINGS.copy()
        if self.default_config_path.exists() and self.default_config_path != self.config_path:
            try:
                with self.default_config_path.open("r", encoding="utf-8") as handle:
                    loaded_defaults = json.load(handle)
                if isinstance(loaded_defaults, dict):
                    default_settings = loaded_defaults
            except (JSONDecodeError, OSError) as exc:
                if self.logger:
                    self.logger.warning("Unable to load bundled default config %s: %s", self.default_config_path, exc)

        default_settings = self._validate_settings(default_settings)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with self.config_path.open("w", encoding="utf-8") as handle:
            json.dump(default_settings, handle, indent=2)
        self.settings = default_settings
        self._last_modified = self.config_path.stat().st_mtime

    def _validate_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        settings = self._migrate_legacy_timing_settings(settings)
        validated: dict[str, Any] = {}
        for key, schema in _CONFIG_SCHEMA.items():
            if key in settings:
                value = settings[key]
                if not isinstance(value, schema["type"]):
                    raise ConfigValidationError(f"Config value for '{key}' must be {schema['type']}.")
                if "exclusive_min" in schema and value <= schema["exclusive_min"]:
                    raise ConfigValidationError(f"Config '{key}' must be greater than {schema['exclusive_min']}.")
                if "min" in schema and value < schema["min"]:
                    raise ConfigValidationError(f"Config '{key}' must be >= {schema['min']}.")
                if "max" in schema and value > schema["max"]:
                    raise ConfigValidationError(f"Config '{key}' must be <= {schema['max']}.")
                validated[key] = value
            else:
                validated[key] = DEFAULT_SETTINGS[key]

        validated["theme"] = self._validate_theme(validated.get("theme", DEFAULT_SETTINGS["theme"]))
        validated["window"] = self._validate_window(validated.get("window", DEFAULT_SETTINGS["window"]))
        self._validate_thresholds(validated)
        return validated

    def _migrate_legacy_timing_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        migrated = settings.copy()
        legacy_map = {
            "alert_delay_minutes": "alert_delay_seconds",
            "dim_delay_minutes": "dim_delay_seconds",
            "subsequent_dim_cooldown_minutes": "subsequent_dim_cooldown_seconds",
        }
        for minute_key, second_key in legacy_map.items():
            if minute_key not in migrated and second_key in migrated:
                migrated[minute_key] = float(migrated[second_key]) / 60.0
        return migrated

    def _validate_theme(self, theme: Any) -> dict[str, Any]:
        if isinstance(theme, str):
            return {"mode": theme, "accent_color": DEFAULT_SETTINGS["theme"]["accent_color"]}
        if not isinstance(theme, dict):
            raise ConfigValidationError("Theme configuration must be a dict or theme mode string.")
        return {
            "mode": theme.get("mode", DEFAULT_SETTINGS["theme"]["mode"]),
            "accent_color": theme.get("accent_color", DEFAULT_SETTINGS["theme"]["accent_color"]),
        }

    def _validate_window(self, window: Any) -> dict[str, int]:
        if not isinstance(window, dict):
            raise ConfigValidationError("Window settings must be a dict.")
        validated_window = {
            "width": int(window.get("width", DEFAULT_SETTINGS["window"]["width"])),
            "height": int(window.get("height", DEFAULT_SETTINGS["window"]["height"])),
            "min_width": int(window.get("min_width", DEFAULT_SETTINGS["window"]["min_width"])),
            "min_height": int(window.get("min_height", DEFAULT_SETTINGS["window"]["min_height"])),
        }
        if validated_window["min_width"] > validated_window["width"]:
            raise ConfigValidationError("Window min_width cannot be greater than width.")
        if validated_window["min_height"] > validated_window["height"]:
            raise ConfigValidationError("Window min_height cannot be greater than height.")
        return validated_window

    def _validate_thresholds(self, settings: dict[str, Any]) -> None:
        if settings["critical_blink_rate_bpm"] > settings["warning_blink_rate_bpm"]:
            raise ConfigValidationError("Critical blink rate must be lower than warning blink rate.")
        if settings["warning_blink_rate_bpm"] > settings["notice_blink_rate_bpm"]:
            raise ConfigValidationError("Warning blink rate must be lower than notice blink rate.")

    def _has_not_changed(self) -> bool:
        if not self.config_path.exists():
            return False
        current_mtime = self.config_path.stat().st_mtime
        return self._last_modified is not None and current_mtime <= self._last_modified

    def _backup_corrupted_config(self, exc: Exception) -> None:
        if self.logger:
            self.logger.warning("Backing up corrupted config file: %s", exc)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_path = self.config_path.with_name(f"{self.config_path.stem}_corrupt_{timestamp}{self.config_path.suffix}")
        self.config_path.rename(backup_path)
        if self.logger:
            self.logger.warning("Corrupted config backed up to %s", backup_path)
        self.corrupted = True
