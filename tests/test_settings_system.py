from __future__ import annotations

import logging
import json

import pytest

from src.ocolyx.alerts import AlertManager
from src.ocolyx.config_manager import ConfigManager, ConfigValidationError


def test_config_persists_new_settings(tmp_path) -> None:
    config_path = tmp_path / "settings.json"
    manager = ConfigManager(config_path, logger=logging.getLogger("test.settings"))

    manager.save(
        {
            "overlay_enabled": True,
            "blink_rate_threshold_bpm": 14,
            "alert_delay_minutes": 0.5,
            "dim_delay_minutes": 5,
            "subsequent_dim_cooldown_minutes": 20,
        }
    )

    reloaded = ConfigManager(config_path, logger=logging.getLogger("test.settings.reload"))

    assert reloaded.get("overlay_enabled") is True
    assert reloaded.get("blink_rate_threshold_bpm") == 14
    assert reloaded.get("alert_delay_minutes") == 0.5
    assert reloaded.get("dim_delay_minutes") == 5
    assert reloaded.get("subsequent_dim_cooldown_minutes") == 20


def test_config_migrates_legacy_second_timing_settings(tmp_path) -> None:
    config_path = tmp_path / "settings.json"
    config_path.write_text(
        json.dumps(
            {
                "alert_delay_seconds": 30,
                "dim_delay_seconds": 120,
                "subsequent_dim_cooldown_seconds": 600,
            }
        ),
        encoding="utf-8",
    )

    manager = ConfigManager(config_path, logger=logging.getLogger("test.settings.migration"))

    assert manager.get("alert_delay_minutes") == 0.5
    assert manager.get("dim_delay_minutes") == 2.0
    assert manager.get("subsequent_dim_cooldown_minutes") == 10.0


def test_config_rejects_invalid_settings(tmp_path) -> None:
    manager = ConfigManager(tmp_path / "settings.json", logger=logging.getLogger("test.settings"))

    with pytest.raises(ConfigValidationError):
        manager.save({"blink_rate_threshold_bpm": 0})

    with pytest.raises(ConfigValidationError):
        manager.save({"alert_delay_minutes": -1})

    with pytest.raises(ConfigValidationError):
        manager.save({"dim_delay_minutes": 0})


def test_alert_manager_shows_one_notification_per_session(monkeypatch) -> None:
    now = 1000.0
    monkeypatch.setattr("src.ocolyx.alerts.time.time", lambda: now)
    dialog_calls: list[tuple[str, str, str]] = []
    manager = AlertManager(
        {
            "alert_enabled": True,
            "alert_delay_minutes": 0.1,
            "blink_rate_threshold_bpm": 12,
        },
        logging.getLogger("test.alerts"),
        dialog_callback=lambda title, message, severity: dialog_calls.append((title, message, severity)),
    )

    manager.evaluate(7.0)
    assert dialog_calls == []

    now = 1006.0
    manager.evaluate(7.0)
    assert len(dialog_calls) == 1

    now = 1010.0
    manager.evaluate(7.0)
    now = 1020.0
    manager.evaluate(7.0)
    assert len(dialog_calls) == 1

    manager.reset_session()
    now = 1030.0
    manager.evaluate(7.0)
    now = 1037.0
    manager.evaluate(7.0)
    assert len(dialog_calls) == 2


def test_alert_manager_resets_notification_after_sustained_recovery(monkeypatch) -> None:
    now = 2000.0
    monkeypatch.setattr("src.ocolyx.alerts.time.time", lambda: now)
    dialog_calls: list[tuple[str, str, str]] = []
    manager = AlertManager(
        {
            "alert_enabled": True,
            "alert_delay_minutes": 0,
            "blink_rate_threshold_bpm": 12,
        },
        logging.getLogger("test.alerts.recovery"),
        dialog_callback=lambda title, message, severity: dialog_calls.append((title, message, severity)),
    )

    manager.evaluate(7.0)
    assert len(dialog_calls) == 1

    now = 2010.0
    manager.evaluate(13.0)
    now = 2071.0
    manager.evaluate(13.0)

    now = 2072.0
    manager.evaluate(7.0)
    assert len(dialog_calls) == 2


def test_alert_manager_honors_live_delay_update(monkeypatch) -> None:
    now = 3000.0
    monkeypatch.setattr("src.ocolyx.alerts.time.time", lambda: now)
    dialog_calls: list[tuple[str, str, str]] = []
    manager = AlertManager(
        {
            "alert_enabled": True,
            "alert_delay_minutes": 1,
            "blink_rate_threshold_bpm": 12,
        },
        logging.getLogger("test.alerts.delay_update"),
        dialog_callback=lambda title, message, severity: dialog_calls.append((title, message, severity)),
    )

    manager.evaluate(7.0)
    now = 3010.0
    manager.evaluate(7.0)
    assert dialog_calls == []

    manager.update_config(
        {
            "alert_enabled": True,
            "alert_delay_minutes": 0,
            "blink_rate_threshold_bpm": 12,
        }
    )
    now = 3011.0
    manager.evaluate(7.0)

    assert len(dialog_calls) == 1
