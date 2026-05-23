"""Settings persistence service."""

from pathlib import Path
from typing import Any


class SettingsService:
    def __init__(self, settings_path: Path) -> None:
        self.settings_path = settings_path
        self.settings: dict[str, Any] = {}

    def load(self) -> dict[str, Any]:
        if self.settings_path.exists():
            with self.settings_path.open("r", encoding="utf-8") as handle:
                import json

                self.settings = json.load(handle)
        return self.settings

    def save(self, updates: dict[str, Any]) -> None:
        self.settings.update(updates)
        with self.settings_path.open("w", encoding="utf-8") as handle:
            import json

            json.dump(self.settings, handle, indent=2)
