"""Settings data models."""

from dataclasses import dataclass, field


@dataclass
class WindowSettings:
    width: int = 960
    height: int = 620
    min_width: int = 800
    min_height: int = 540


@dataclass
class AppSettings:
    blink_threshold_seconds: int = 6
    blink_rate_threshold_bpm: float = 12.0
    monitor_interval_seconds: int = 1
    alert_delay_minutes: float = 1.0
    dim_delay_minutes: float = 5.0
    subsequent_dim_cooldown_minutes: float = 20.0
    alert_enabled: bool = True
    theme: str = "dark"
    overlay_enabled: bool = False
    overlay_opacity: float = 0.35
    window: WindowSettings = field(default_factory=WindowSettings)
