"""Blink monitoring service."""

from typing import Any

from ..blink_detector import BlinkDetector


class BlinkService:
    def __init__(self, config: dict[str, Any], logger: Any) -> None:
        self.config = config
        self.detector = BlinkDetector(logger=logger)
        self.logger = logger

    def check_blink_rate(self) -> float:
        rate = self.detector.get_blink_rate()
        self.logger.debug(f"Blink rate read: {rate}")
        return rate
