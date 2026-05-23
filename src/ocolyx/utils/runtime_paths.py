"""Runtime path helpers for source and PyInstaller builds."""

from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "Ocolyx"


def is_packaged() -> bool:
    """Return True when running from a PyInstaller bundle."""
    return bool(getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"))


def resource_root() -> Path:
    """Return the root directory for bundled read-only resources."""
    if is_packaged():
        return Path(sys._MEIPASS).resolve()  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[3]


def resource_path(*parts: str) -> Path:
    """Build an absolute path to a bundled resource."""
    return resource_root().joinpath(*parts)


def user_data_root() -> Path:
    """Return the writable application data directory."""
    if is_packaged():
        base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / APP_NAME
        return Path.home() / f".{APP_NAME.lower()}"
    return resource_root()


def config_path(filename: str = "default_config.json") -> Path:
    """Return the writable config path for the current runtime."""
    return user_data_root() / "config" / filename


def bundled_config_path(filename: str = "default_config.json") -> Path:
    """Return the bundled default config path."""
    return resource_path("config", filename)


def log_path(filename: str = "ocolyx.log") -> Path:
    """Return the writable log path for the current runtime."""
    return user_data_root() / "logs" / filename


def dlib_shape_predictor_path() -> Path:
    """Return the bundled dlib 68-point landmark predictor path."""
    return resource_path("assets", "models", "shape_predictor_68_face_landmarks.dat")
