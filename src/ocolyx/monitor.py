"""Monitoring workflow for webcam and blink events."""

from .blink_detector import BlinkDetector
from .alerts import AlertManager


class Monitor:
    def __init__(self, config: dict, logger) -> None:
        self.detector = BlinkDetector(logger=logger)
        self.alert_manager = AlertManager(config, logger)
        self.config = config
        self.logger = logger

    def poll(self) -> None:
        blink_rate = self.detector.get_blink_rate()
        self.alert_manager.evaluate(blink_rate)
